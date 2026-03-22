# -*- coding: utf-8 -*-
"""
任务执行器
将 TaskPlan 中的步骤逐一调用对应工具执行
"""

import time
from typing import Dict, Any, Callable, Optional

from loguru import logger

from core.planner import TaskPlan, TaskStep, StepStatus


class ToolRegistry:
    """工具注册表：管理所有可调用工具"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable):
        self._tools[name] = fn
        logger.debug(f"注册工具: {name}")

    def get(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def list_tools(self):
        return list(self._tools.keys())


class TaskExecutor:
    """
    任务执行器：逐步执行 TaskPlan 中的步骤
    每步执行前可截图分析，失败时可重试
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        screen_capture=None,
        vision_model=None,
        memory_system=None,
        max_retries: int = 2,
    ):
        self.registry = tool_registry
        self.screen = screen_capture
        self.vision = vision_model
        self.memory = memory_system
        self.max_retries = max_retries
        self._step_callbacks = []  # 步骤状态变化回调

    def on_step_update(self, callback: Callable):
        """注册步骤更新回调（用于UI实时显示）"""
        self._step_callbacks.append(callback)

    def _notify(self, step: TaskStep):
        for cb in self._step_callbacks:
            try:
                cb(step)
            except Exception:
                pass

    def execute_plan(self, plan: TaskPlan) -> Dict[str, Any]:
        """
        执行完整任务计划
        Args:
            plan: TaskPlan 实例
        Returns:
            {"success": bool, "results": [...], "summary": str}
        """
        logger.info(f"开始执行任务: {plan.task}")
        results = []

        for step in plan.steps:
            result = self.execute_step(step)
            results.append(result)

            if step.status == StepStatus.FAILED:
                logger.warning(f"步骤 {step.step_id} 失败，停止执行")
                break

        success = plan.is_complete and not plan.has_failed
        summary = self._build_summary(plan, results)

        # 保存任务结果到记忆
        if self.memory:
            self.memory.remember_task_result(plan.task, summary)

        logger.info(f"任务执行{'成功' if success else '失败'}")
        return {"success": success, "results": results, "summary": summary}

    def execute_step(self, step: TaskStep) -> Dict[str, Any]:
        """
        执行单个步骤（含重试）
        Args:
            step: TaskStep 实例
        Returns:
            {"step_id": int, "tool": str, "result": str, "success": bool}
        """
        step.status = StepStatus.RUNNING
        self._notify(step)
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
                time.sleep(1.0)

    def _call_tool(self, tool_name: str, parameters: Dict) -> Any:
        """
        调用注册的工具
        Args:
            tool_name: 工具名称
            parameters: 工具参数
        Returns:
            工具返回值
        """
        # 内置工具处理
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

        # 从注册表查找工具
        fn = self.registry.get(tool_name)
        if fn is None:
            raise ValueError(f"未知工具: {tool_name}")
        return fn(**parameters)

    def _build_summary(self, plan: TaskPlan, results: list) -> str:
        """生成执行摘要"""
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

