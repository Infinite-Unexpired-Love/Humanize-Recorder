"""
回合控制模块 - 自动化流程的最小战术单元
"""

import time
import random
import threading
from typing import Dict, List, Any, Optional, Union


class Turn:
    """
    回合控制类 - 自动化流程的最小战术单元

    负责按照预定义的步骤列表驱动 Action 模块执行动作，
    并管理动作的生命周期（暂停、恢复、中止、任务清理）。
    """

    def __init__(self, config: Dict[str, Any], action_instance):
        """
        初始化回合控制器

        Args:
            config: 回合配置字典，包含 'actions' 列表
            action_instance: Action 实例，用于执行底层操作
        """
        self.config = config
        self.action = action_instance
        self.steps = config.get("actions", [])

        # 状态管理
        self._paused = False
        self._stopped = False
        self._current_step_index = 0

        # 任务追踪器 - 记录本回合启动的所有后台任务ID
        self.active_task_ids: List[str] = []
        self.task_name_mapping: Dict[str, str] = {}  # name -> task_id

        # 执行锁
        self._lock = threading.Lock()

    def _ms_to_sec(self, ms: Optional[Union[int, float]]) -> float:
        """
        毫秒转秒

        Args:
            ms: 毫秒数

        Returns:
            秒数
        """
        if ms is None:
            return 0.0
        return ms / 1000.0

    def _calculate_delay(self, delay_config: Union[int, float, List]) -> float:
        """
        计算延迟时间

        Args:
            delay_config: 延迟配置
                - 数字: 固定延迟
                - [fixed]: 固定延迟
                - [fixed, random_min, random_max]: 固定 + 随机范围
                - [fixed, random_min, random_max, mean]: 固定 + 正态分布

        Returns:
            延迟时间(秒)
        """
        if isinstance(delay_config, (int, float)):
            return self._ms_to_sec(delay_config)

        if isinstance(delay_config, list):
            if len(delay_config) == 1:
                return self._ms_to_sec(delay_config[0])

            elif len(delay_config) == 3:
                # [fixed, min, max] - 固定 + 均匀分布
                fixed, min_rand, max_rand = delay_config
                random_part = random.uniform(min_rand, max_rand)
                return self._ms_to_sec(fixed + random_part)

            elif len(delay_config) == 4:
                # [fixed, min, max, mean] - 固定 + 正态分布
                fixed, min_rand, max_rand, mean = delay_config
                std_dev = (max_rand - min_rand) / 6  # 3-sigma 规则
                random_part = random.gauss(mean, std_dev)
                random_part = max(min_rand, min(max_rand, random_part))  # 限制范围
                return self._ms_to_sec(fixed + random_part)

        return 0.0

    def _execute_step(self, step: Dict[str, Any], step_index: int) -> None:
        """
        执行单个步骤

        Args:
            step: 步骤配置
            step_index: 步骤索引
        """
        device = step.get("device")
        event = step.get("event")

        # Case 1: Mouse
        if device == "mouse":
            position = step.get("position")
            duration = self._ms_to_sec(step.get("duration", 500))  # 默认500ms

            if event == "move":
                x, y = position
                self.action.move_to(x, y, duration=duration)

            elif event == "click":
                button = step.get("button", "left")
                x, y = position if position else (None, None)
                self.action.click(button=button, x=x, y=y, duration=duration)

            elif event == "mouse_down":
                button = step.get("button", "left")
                self.action.mouse_down(button=button)

            elif event == "mouse_up":
                button = step.get("button", "left")
                self.action.mouse_up(button=button)

        # Case 2: Keyboard
        elif device == "keyboard":
            key = step.get("key")
            duration = self._ms_to_sec(step.get("duration", 50))  # 默认50ms

            if event == "press":
                self.action.press_key(key, press_duration=duration)

            elif event == "key_down":
                self.action.key_down(key)

            elif event == "key_up":
                self.action.key_up(key)

        # Case 3: Task (后台任务管理)
        elif device == "task":
            task_params = step.get("task_params", {})

            if event == "start_loop":
                interval = self._ms_to_sec(task_params.get("interval", 1000))
                jitter = self._ms_to_sec(task_params.get("jitter", 0))
                fn_name = task_params.get("fn_name")  # "click" 或 "press"
                task_name = step.get("task_name", f"task_{step_index}")

                # 根据函数名调用对应的循环方法
                if fn_name == "click":
                    x = task_params.get("x")
                    y = task_params.get("y")
                    button = task_params.get("button", "left")
                    duration = self._ms_to_sec(task_params.get("duration", 200))

                    task_id = self.action.click_interval(
                        interval=interval,
                        button=button,
                        x=x,
                        y=y,
                        duration=duration,
                        jitter=jitter
                    )

                elif fn_name == "press":
                    key = task_params.get("key")
                    press_duration = self._ms_to_sec(task_params.get("press_duration"))

                    task_id = self.action.press_interval(
                        interval=interval,
                        key=key,
                        press_duration=press_duration,
                        jitter=jitter
                    )

                else:
                    raise ValueError(f"不支持的任务函数: {fn_name}")

                # 记录任务ID
                self.active_task_ids.append(task_id)
                self.task_name_mapping[task_name] = task_id

            elif event == "stop_loop":
                # 支持通过 task_id 或 task_name 停止
                task_id = step.get("task_id")
                if not task_id:
                    task_name = step.get("task_name")
                    task_id = self.task_name_mapping.get(task_name)

                if task_id:
                    self.action.stop_interval(task_id)
                    # 从活动列表中移除
                    if task_id in self.active_task_ids:
                        self.active_task_ids.remove(task_id)

        # Case 4: Delay/Wait (纯等待，无设备操作)
        elif device is None:
            pass  # 仅执行后续的 delay

        # 步骤后延迟
        if "delay" in step:
            delay_time = self._calculate_delay(step["delay"])
            if delay_time > 0:
                time.sleep(delay_time)

    def _check_control_flags(self) -> bool:
        """
        检查控制标志（暂停/停止）

        Returns:
            True 表示应继续执行，False 表示应停止
        """
        # 处理暂停
        while self._paused and not self._stopped:
            time.sleep(0.1)  # 暂停时轮询检查

        # 检查停止标志
        return not self._stopped

    def execute(self) -> str:
        """
        执行回合流程

        Returns:
            执行结果: "success", "stopped", "failed"
        """
        try:
            with self._lock:
                # 重置状态
                self._stopped = False
                self._paused = False
                self._current_step_index = 0

            for i, step in enumerate(self.steps):
                # 更新当前步骤索引
                self._current_step_index = i

                # 检查控制标志
                if not self._check_control_flags():
                    return "stopped"

                # 执行步骤
                self._execute_step(step, i)

            return "success"

        except Exception as e:
            print(f"执行失败: {e}")
            return "failed"

        finally:
            # 执行完成后清理（成功或失败都清理）
            if not self._stopped:
                self._cleanup_tasks()

    def pause(self) -> None:
        """暂停执行"""
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        """恢复执行"""
        with self._lock:
            self._paused = False

    def stop(self) -> None:
        """
        停止执行并清理所有后台任务
        """
        with self._lock:
            self._stopped = True
            self._paused = False  # 解除暂停以便退出

        # 清理所有后台任务
        self._cleanup_tasks()

    def _cleanup_tasks(self) -> None:
        """清理所有活动的后台任务"""
        for task_id in self.active_task_ids[:]:  # 复制列表以避免迭代时修改
            try:
                self.action.stop_interval(task_id)
            except Exception as e:
                print(f"停止任务 {task_id} 失败: {e}")

        # 清空任务列表
        self.active_task_ids.clear()
        self.task_name_mapping.clear()

    def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态

        Returns:
            状态字典
        """
        return {
            "paused": self._paused,
            "stopped": self._stopped,
            "current_step": self._current_step_index,
            "total_steps": len(self.steps),
            "active_tasks": len(self.active_task_ids)
        }