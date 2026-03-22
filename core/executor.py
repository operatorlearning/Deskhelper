# -*- coding: utf-8 -*-
"""
文件名称：core/executor.py
文件用途：任务执行执行器模块，它接收 Planner 拆解后的 TaskPlan，负责调用注册的工具逐步执行每个子步骤，
          处理重试逻辑、状态通知、结果摘要生成以及执行过程中的截图/记忆保存等放大操作。
"""

import time  # 引入时间库，用于执行中断和重试的睡眠控制
from typing import Dict, Any, Callable, Optional  # 提供类型提示，提升可读性

from loguru import logger  # 用于记录任务执行的日志（info/warning/success）

from core.planner import TaskPlan, TaskStep, StepStatus  # 导入 Planner 的数据结构


class ToolRegistry:
    """工具注册表：维护所有可用工具（如模拟点击、文件操作等）的映射关系。"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}  # 字典结构，key 是工具名，value 是可调用的函数对象

    def register(self, name: str, fn: Callable):
        """注册一个工具供执行器调用。"""
        self._tools[name] = fn
        logger.debug(f"注册工具: {name}")  # 记录每一个工具注册的操作

    def get(self, name: str) -> Optional[Callable]:
        """根据名字获取注册的工具函数。"""
        return self._tools.get(name)

    def list_tools(self):
        """返回当前注册的工具名称清单。"""
        return list(self._tools.keys())


class TaskExecutor:
    """任务执行器：负责将 Planner 生成的 TaskStep 按顺序执行，并处理失败与重试逻辑。"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        screen_capture=None,
        vision_model=None,
        memory_system=None,
        max_retries: int = 2,
    ):
        self.registry = tool_registry  # 注册好的工具清单
        self.screen = screen_capture  # 屏幕抓取模块
        self.vision = vision_model  # 视觉模型（可选）
        self.memory = memory_system  # 记忆系统（可选）
        self.max_retries = max_retries  # 每一步最多重试次数
        self._step_callbacks = []  # 记录订阅步骤状态变化的回调函数

    def on_step_update(self, callback: Callable):
        """允许外部订阅步骤状态变化（用于 UI 展示当前执行进度）。"""
        self._step_callbacks.append(callback)

    def _notify(self, step: TaskStep):
        """遍历回调列表，通知每一个观察者当前步骤的最新状态。"""
        for cb in self._step_callbacks:
            try:
                cb(step)
            except Exception:
                pass  # 回调异常不影响主流程

    def execute_plan(self, plan: TaskPlan) -> Dict[str, Any]:
        """执行完整任务计划并返回各步骤结果。"""
        logger.info(f"开始执行任务: {plan.task}")
        results = []  # 用于保存每一步的执行结果

        for step in plan.steps:
            result = self.execute_step(step)
            results.append(result)

            if step.status == StepStatus.FAILED:
                logger.warning(f"步骤 {step.step_id} 失败，停止执行")
                break  # 一旦某步失败，终止后续执行

        success = plan.is_complete and not plan.has_failed
        summary = self._build_summary(plan, results)

        if self.memory:
            self.memory.remember_task_result(plan.task, summary)  # 将任务执行结果写入记忆库，便于未来追溯

        logger.info(f"任务执行{'成功' if success else '失败'}")
        return {"success": success, "results": results, "summary": summary}

    def execute_step(self, step: TaskStep) -> Dict[str, Any]:
        """执行单步任务，包含重试循环、状态更新与异常捕获。"""
        step.status = StepStatus.RUNNING  # 标记步骤为正在执行
        self._notify(step)  # 通知观察者状态变化
        logger.info(f"执行步骤 {step.step_id}: [{step.tool}] {step.description}")

        for attempt in range(1, self.max_retries + 2):
            try:
                result = self._call_tool(step.tool, step.parameters)
                step.status = StepStatus.DONE
                step.result = str(result)
                self._notify(step)
                logger.success(f"步骤 {step.step_id} 完成: {str(result)[:80]}")
                return {
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "result": str(result),
                    "success": True,
                }
            except Exception as e:
                logger.warning(f"步骤 {step.step_id} 第{attempt}次失败: {e}")
                if attempt > self.max_retries:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    self._notify(step)
                    return {
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "result": None,
                        "success": False,
                        "error": str(e),
                    }
                time.sleep(1.0)  # 重试前休眠，避免过度快速打击目标

    def _call_tool(self, tool_name: str, parameters: Dict) -> Any:
        """执行具体工具调用，包含内置工具和注册表中工具。"""
        if tool_name == "wait":
            seconds = parameters.get("seconds", 1.0)
            time.sleep(float(seconds))
            return f"等待 {seconds} 秒完成"

        if tool_name == "take_screenshot":
            if self.screen:
                img, path = self.screen.capture_full(save=True)
                return f"截图已保存: {path}"
            return "屏幕捕获模块未初始化"

        if tool_name == "analyze_screen":
            if self.screen and self.vision:
                img, path = self.screen.capture_full(save=False)
                task = parameters.get("task", "描述当前屏幕")
                return self.vision.understand_task_context(img, task)
            return "视觉模型未初始化"

        if tool_name == "recall_memory":
            if self.memory:
                query = parameters.get("query", "")
                return self.memory.recall_as_context(query)
            return "记忆系统未初始化"

        if tool_name == "save_memory":
            if self.memory:
                content = parameters.get("content", "")
                mem_type = parameters.get("type", "general")
                self.memory.remember(content, mem_type)
                return f"已保存记忆: {content[:50]}"
            return "记忆系统未初始化"

        fn = self.registry.get(tool_name)
        if fn is None:
            raise ValueError(f"未知工具: {tool_name}")
        return fn(**parameters)

    def _build_summary(self, plan: TaskPlan, results: list) -> str:
        """构建任务执行的摘要，用于日志和记忆记录。"""
        done = sum(1 for r in results if r.get("success"))
        failed = sum(1 for r in results if not r.get("success"))
        lines = [
            f"任务: {plan.task}",
            f"执行结果: {done}步成功 / {failed}步失败",
            "",
        ]
        for r in results:
            status = "✅" if r.get("success") else "❌"
            lines.append(f"  {status} 步骤{r['step_id']} [{r['tool']}]: {str(r.get('result', r.get('error', '')))[:100]}")
        return "\n".join(lines)
