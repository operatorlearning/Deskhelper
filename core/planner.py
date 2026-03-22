# -*- coding: utf-8 -*-
"""
任务规划器
将用户的自然语言任务分解为可执行的步骤序列
"""

import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    """单个执行步骤"""
    step_id: int
    description: str                    # 步骤描述
    tool: str                           # 使用的工具名称
    parameters: Dict = field(default_factory=dict)  # 工具参数
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool": self.tool,
            "parameters": self.parameters,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class TaskPlan:
    """完整任务计划"""
    task: str                           # 原始任务描述
    steps: List[TaskStep] = field(default_factory=list)
    summary: str = ""
    total_steps: int = 0

    @property
    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.DONE, StepStatus.SKIPPED)
            for s in self.steps
        )

    @property
    def has_failed(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)

    @property
    def current_step(self) -> Optional[TaskStep]:
        for s in self.steps:
            if s.status == StepStatus.PENDING:
                return s
        return None

    def to_summary(self) -> str:
        lines = [f"任务: {self.task}", f"共 {len(self.steps)} 步："]
        for s in self.steps:
            icon = {"pending": "⬜", "running": "🔄", "done": "✅", "failed": "❌", "skipped": "⏭️"}
            lines.append(f"  {icon.get(s.status.value, '?')} 步骤{s.step_id}: {s.description}")
        return "\n".join(lines)


class TaskPlanner:
    """
    任务规划器：将自然语言任务分解为步骤
    使用规则模板 + LLM 混合规划
    """

    # 可用工具清单（供LLM参考）
    AVAILABLE_TOOLS = [
        "take_screenshot",       # 截图
        "analyze_screen",        # 分析屏幕内容
        "click",                  # 点击坐标
        "double_click",           # 双击
        "right_click",            # 右键
        "type_text",              # 输入文字
        "hotkey",                 # 快捷键
        "scroll",                 # 滚动
        "focus_window",           # 激活窗口
        "launch_app",             # 启动应用
        "kill_app",               # 关闭应用
        "open_url",               # 打开网页
        "read_file",              # 读取文件
        "write_file",             # 写入文件
        "copy_file",              # 复制文件
        "move_file",              # 移动文件
        "delete_file",            # 删除文件
        "list_dir",               # 列出目录
        "search_files",           # 搜索文件
        "send_wechat_message",    # 发送微信消息
        "run_command",            # 执行系统命令
        "ocr_screen",             # OCR识别屏幕文字
        "find_text_on_screen",    # 在屏幕上查找文字位置
        "wait",                   # 等待指定时间
        "recall_memory",          # 检索记忆
        "save_memory",            # 保存记忆
    ]

    PLAN_PROMPT_TEMPLATE = """你是一个桌面AI助手的任务规划模块。
请将用户任务分解为具体的可执行步骤。

可用工具列表：
{tools}

相关历史记忆：
{memory_context}

用户任务：{task}

请以JSON格式输出执行计划，格式如下：
{{
  "summary": "任务简述",
  "steps": [
    {{
      "step_id": 1,
      "description": "步骤描述",
      "tool": "工具名称",
      "parameters": {{"param1": "value1"}}
    }}
  ]
}}

注意：
- 步骤要尽量原子化，每步只做一件事
- 参数要具体，避免模糊描述
- 如果需要先截图了解当前状态，第一步通常是 take_screenshot + analyze_screen
- 最多{max_steps}步

只输出JSON，不要其他内容："""

    def __init__(self, llm_invoke_fn, memory_system=None, max_steps: int = 15):
        """
        Args:
            llm_invoke_fn: 调用LLM的函数 fn(prompt: str) -> str
            memory_system: MemorySystem 实例
            max_steps: 最大步骤数
        """
        self.llm = llm_invoke_fn
        self.memory = memory_system
        self.max_steps = max_steps

    def plan(self, task: str) -> TaskPlan:
        """
        为任务生成执行计划
        Args:
            task: 用户任务描述
        Returns:
            TaskPlan
        """
        logger.info(f"开始规划任务: {task}")

        # 检索相关记忆
        memory_context = ""
        if self.memory:
            memory_context = self.memory.recall_as_context(task)

        prompt = self.PLAN_PROMPT_TEMPLATE.format(
            tools="\n".join(f"- {t}" for t in self.AVAILABLE_TOOLS),
            memory_context=memory_context or "（暂无相关记忆）",
            task=task,
            max_steps=self.max_steps,
        )

        try:
            response = self.llm(prompt)
            plan_data = self._parse_plan(response)
            steps = [
                TaskStep(
                    step_id=s["step_id"],
                    description=s["description"],
                    tool=s["tool"],
                    parameters=s.get("parameters", {}),
                )
                for s in plan_data["steps"]
            ]
            plan = TaskPlan(
                task=task,
                steps=steps,
                summary=plan_data.get("summary", ""),
                total_steps=len(steps),
            )
            logger.info(f"任务规划完成，共 {len(steps)} 步")
            logger.debug(plan.to_summary())
            return plan

        except Exception as e:
            logger.error(f"任务规划失败: {e}")
            # 降级：返回单步计划
            return TaskPlan(
                task=task,
                steps=[TaskStep(
                    step_id=1,
                    description=f"直接处理: {task}",
                    tool="analyze_screen",
                    parameters={"task": task},
                )],
                summary=task,
                total_steps=1,
            )

    def _parse_plan(self, response: str) -> Dict:
        """解析LLM输出的JSON计划"""
        # 提取JSON块
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        return json.loads(response)

    def replan(self, plan: TaskPlan, failed_step: TaskStep, error_msg: str) -> TaskPlan:
        """
        重新规划（某步骤失败后）
        Args:
            plan: 原计划
            failed_step: 失败的步骤
            error_msg: 错误信息
        Returns:
            新的计划
        """
        task = (
            f"{plan.task}\n\n"
            f"注意：步骤{failed_step.step_id}（{failed_step.description}）执行失败，"
            f"错误: {error_msg}。请调整计划，跳过或替换该步骤。"
        )
        return self.plan(task)

