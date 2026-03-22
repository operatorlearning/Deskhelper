# -*- coding: utf-8 -*-
"""
文件名称：core/executor.py
文件用途：任务执行执行器模块。负责将规划好的步骤（TaskPlan）转化为具体的工具调用，处理重试、状态通知、结果汇总。
"""

import time  # 导入时间库，用于处理执行间隔和重试等待
from typing import Dict, Any, Callable, Optional  # 导入类型提示，增强代码可读性和健壮性

from loguru import logger  # 导入日志库，用于记录任务执行过程中的关键信息

from core.planner import TaskPlan, TaskStep, StepStatus  # 导入任务规划相关的核心数据模型


class ToolRegistry:
    """
    工具注册表类：管理系统中所有可供 Agent 调用的底层功能函数。
    """

    def __init__(self):
        """初始化空的工具映射字典。"""
        self._tools: Dict[str, Callable] = {}  # 存储工具名到函数对象的映射

    def register(self, name: str, fn: Callable):
        """将一个具体的 Python 函数注册为 Agent 可识别的‘工具’。"""
        self._tools[name] = fn  # 将函数保存到字典中
        logger.debug(f"注册工具: {name}")  # 打印调试日志

    def get(self, name: str) -> Optional[Callable]:
        """根据工具名称检索对应的函数对象，若不存在则返回 None。"""
        return self._tools.get(name)  # 从字典中获取函数

    def list_tools(self):
        """返回当前注册表中所有可用工具的名称列表。"""
        return list(self._tools.keys())  # 转换字典键为列表并返回


class TaskExecutor:
    """
    任务执行器类：核心逻辑层，负责串联工具并按照计划步骤执行任务。
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        screen_capture=None,
        vision_model=None,
        memory_system=None,
        max_retries: int = 2,
    ):
        """
        初始化执行器并注入依赖。
        """
        self.registry = tool_registry  # 注入工具注册表实例
        self.screen = screen_capture  # 注入屏幕捕获模块
        self.vision = vision_model  # 注入视觉大模型（用于分析屏幕）
        self.memory = memory_system  # 注入记忆系统（用于保存/检索任务结果）
        self.max_retries = max_retries  # 设置单个步骤失败后的最大重试次数
        self._step_callbacks = []  # 初始化空的回调列表，用于同步 UI 状态

    def on_step_update(self, callback: Callable):
        """允许外部（如 UI 界面）注册回调函数，以便实时获取任务进度。"""
        self._step_callbacks.append(callback)  # 将回调函数加入列表

    def _notify(self, step: TaskStep):
        """执行状态变更时，遍历并触发所有已注册的回调函数。"""
        for cb in self._step_callbacks:  # 循环每个回调
            try:
                cb(step)  # 执行回调并传入当前步骤对象
            except Exception:
                pass  # 忽略回调执行中的异常，防止主流程崩溃

    def execute_plan(self, plan: TaskPlan) -> Dict[str, Any]:
        """
        执行一整个完整的任务计划（包含多个步骤）。
        """
        logger.info(f"开始执行任务: {plan.task}")  # 记录任务开始
        results = []  # 初始化空列表，保存每一步的执行明细

        for step in plan.steps:  # 顺序遍历计划中的每一个子步骤
            result = self.execute_step(step)  # 调用单步执行方法
            results.append(result)  # 将单步执行结果记录下来

            if step.status == StepStatus.FAILED:  # 如果其中一个核心步骤彻底失败
                logger.warning(f"步骤 {step.step_id} 失败，停止执行后续计划")  # 记录警告
                break  # 终止后续所有步骤的执行

        success = plan.is_complete and not plan.has_failed  # 计算任务最终是否整体成功
        summary = self._build_summary(plan, results)  # 根据各步结果生成自然语言摘要

        if self.memory:  # 如果记忆系统可用
            self.memory.remember_task_result(plan.task, summary)  # 将此项任务的成败存入长期记忆

        logger.info(f"任务执行{'成功' if success else '失败'}")  # 打印最终结果日志
        return {"success": success, "results": results, "summary": summary}  # 返回详细的结果字典

    def execute_step(self, step: TaskStep) -> Dict[str, Any]:
        """
        执行计划中的单个具体步骤，包含重试逻辑。
        """
        step.status = StepStatus.RUNNING  # 将步骤状态更新为“运行中”
        self._notify(step)  # 通知前端 UI
        logger.info(f"执行步骤 {step.step_id}: [{step.tool}] {step.description}")  # 记录步骤描述

        for attempt in range(1, self.max_retries + 2):  # 开始重试循环（包含初次尝试）
            try:
                result = self._call_tool(step.tool, step.parameters)  # 尝试调用具体工具
                step.status = StepStatus.DONE  # 调用成功，更新状态为“完成”
                step.result = str(result)  # 将结果转为字符串保存
                self._notify(step)  # 再次通知 UI
                logger.success(f"步骤 {step.step_id} 完成: {str(result)[:80]}")  # 记录成功日志
                return {  # 返回成功的详细信息
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "result": str(result),
                    "success": True,
                }
            except Exception as e:  # 捕获执行过程中的任何错误
                logger.warning(f"步骤 {step.step_id} 第 {attempt} 次尝试失败: {e}")  # 记录尝试失败日志
                if attempt > self.max_retries:  # 如果超过最大重试次数
                    step.status = StepStatus.FAILED  # 更新状态为“失败”
                    step.error = str(e)  # 记录错误信息
                    self._notify(step)  # 通知 UI 报错
                    return {  # 返回失败的详细信息
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "result": None,
                        "success": False,
                        "error": str(e),
                    }
                time.sleep(1.0)  # 如果还有重试机会，则休眠 1 秒后再试

    def _call_tool(self, tool_name: str, parameters: Dict) -> Any:
        """
        内部工具调用路由：根据工具名决定是调用内置逻辑还是调用注册表中的工具。
        """
        if tool_name == "wait":  # 内置工具：等待/延迟
            seconds = parameters.get("seconds", 1.0)  # 获取等待时长参数
            time.sleep(float(seconds))  # 执行休眠
            return f"等待 {seconds} 秒完成"  # 返回执行反馈

        if tool_name == "take_screenshot":  # 内置工具：全屏截图
            if self.screen:  # 检查屏幕模块是否已就绪
                img, path = self.screen.capture_full(save=True)  # 调用截图并存盘
                return f"截图已保存至: {path}"  # 返回文件路径
            return "错误：屏幕捕获模块未初始化"  # 报错提示

        if tool_name == "analyze_screen":  # 内置工具：屏幕视觉分析
            if self.screen and self.vision:  # 检查屏幕和视觉大模型是否都就绪
                img, path = self.screen.capture_full(save=False)  # 仅截取内存图像
                task = parameters.get("task", "描述当前屏幕")  # 获取具体的分析任务
                return self.vision.understand_task_context(img, task)  # 调用大模型理解当前屏幕
            return "错误：视觉模型或屏幕模块未就绪"  # 报错提示

        if tool_name == "recall_memory":  # 内置工具：检索记忆
            if self.memory:  # 检查记忆系统是否就绪
                query = parameters.get("query", "")  # 获取搜索关键词
                return self.memory.recall_as_context(query)  # 从向量数据库检索相关背景
            return "错误：记忆系统未初始化"  # 报错提示

        if tool_name == "save_memory":  # 内置工具：保存新记忆
            if self.memory:  # 检查记忆系统是否就绪
                content = parameters.get("content", "")  # 获取要保存的内容
                mem_type = parameters.get("type", "general")  # 获取记忆类型
                self.memory.remember(content, mem_type)  # 存入数据库
                return f"已成功保存记忆，长度为 {len(content)}"  # 返回成功提示
            return "错误：记忆系统未初始化"  # 报错提示

        fn = self.registry.get(tool_name)  # 尝试从外部注册表中查找该工具函数
        if fn is None:  # 如果注册表中也找不到
            raise ValueError(f"系统无法识别工具名称: {tool_name}")  # 抛出未知工具异常
        return fn(**parameters)  # 解包参数并调用工具函数，返回其执行结果

    def _build_summary(self, plan: TaskPlan, results: list) -> str:
        """
        私有方法：将所有步骤的执行结果汇总成一段易读的文字报告。
        """
        done = sum(1 for r in results if r.get("success"))  # 统计成功的步数
        failed = sum(1 for r in results if not r.get("success"))  # 统计失败的步数
        lines = [  # 构建报告行列表
            f"任务指令: {plan.task}",
            f"汇总统计: 共执行 {len(results)} 步，其中 {done} 步成功，{failed} 步失败。",
            "--- 执行明细 ---",
        ]
        for r in results:  # 遍历每个结果行
            status = "✅" if r.get("success") else "❌"  # 根据成败选择图标
            detail = str(r.get("result", r.get("error", "无反馈信息")))[:100]  # 获取截断后的结果或错误描述
            lines.append(f"  {status} 步骤 {r['step_id']} [{r['tool']}]: {detail}")  # 格式化输出
        return "\n".join(lines)  # 将所有行连接成一个大的字符串并返回
