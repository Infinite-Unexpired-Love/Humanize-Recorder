"""
动作执行模块 - 支持多驱动、拟人化、循环任务管理
"""

import random
import time
import math
import threading
import uuid
from typing import Callable, Any, Optional, Dict, List, Tuple


class Action:
    """
    动作执行类 - 负责底层硬件输入模拟和任务调度

    支持特性:
    - 多驱动适配 (pyautogui/pydirectinput)
    - 拟人化移动 (贝塞尔曲线)
    - 循环任务管理 (基于线程)
    - 安全延迟保护
    """

    def __init__(
            self,
            driver_type: str = "pyautogui",
            humanization: Optional[Dict[str, Any]] = None,
            safety_delay: float = 0.05
    ):
        """
        初始化动作执行器

        Args:
            driver_type: 驱动类型 ("pyautogui" 或 "pydirectinput")
            humanization: 拟人化配置字典
            safety_delay: 最小安全延迟时间(秒)
        """
        self.driver_type = driver_type.lower()
        self.safety_delay = safety_delay

        # 初始化驱动
        self._init_driver()

        # 拟人化配置
        self.humanization = humanization or {}
        self.smooth_move = self.humanization.get("smooth_move", True)
        self.random_delay_mean = self.humanization.get("random_delay_mean", 0.01)
        self.jitter = self.humanization.get("jitter", 5)

        # 任务管理器
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    def _init_driver(self) -> None:
        """初始化底层驱动"""
        if self.driver_type == "pyautogui":
            import pyautogui
            self.driver = pyautogui
            # 关闭pyautogui的安全检查以提高性能
            pyautogui.FAILSAFE = False
        elif self.driver_type == "pydirectinput":
            import pydirectinput
            self.driver = pydirectinput
        else:
            raise ValueError(f"不支持的驱动类型: {self.driver_type}")

    def _smooth_path(
            self,
            start_x: int,
            start_y: int,
            end_x: int,
            end_y: int,
            duration: float
    ) -> List[Tuple[int, int, float]]:
        """
        生成贝塞尔曲线路径

        Args:
            start_x, start_y: 起始坐标
            end_x, end_y: 目标坐标
            duration: 移动总时长

        Returns:
            路径点列表 [(x, y, timestamp), ...]
        """
        # 计算控制点(添加随机偏移实现曲线效果)
        distance = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
        steps = max(10, int(distance / 10))  # 根据距离动态调整步数

        # 随机生成1-2个控制点
        num_controls = random.randint(1, 2)
        control_points = []

        for _ in range(num_controls):
            offset_x = random.randint(-self.jitter, self.jitter)
            offset_y = random.randint(-self.jitter, self.jitter)
            t = random.uniform(0.3, 0.7)
            cx = int(start_x + (end_x - start_x) * t + offset_x)
            cy = int(start_y + (end_y - start_y) * t + offset_y)
            control_points.append((cx, cy))

        # 生成路径点
        path = []
        time_per_step = duration / steps

        for i in range(steps + 1):
            t = i / steps

            if num_controls == 1:
                # 二次贝塞尔曲线
                x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * control_points[0][0] + t ** 2 * end_x
                y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * control_points[0][1] + t ** 2 * end_y
            else:
                # 三次贝塞尔曲线
                x = ((1 - t) ** 3 * start_x +
                     3 * (1 - t) ** 2 * t * control_points[0][0] +
                     3 * (1 - t) * t ** 2 * control_points[1][0] +
                     t ** 3 * end_x)
                y = ((1 - t) ** 3 * start_y +
                     3 * (1 - t) ** 2 * t * control_points[0][1] +
                     3 * (1 - t) * t ** 2 * control_points[1][1] +
                     t ** 3 * end_y)

            path.append((int(x), int(y), time_per_step))

        return path

    def _humanize_delay(self, base_delay: float = None) -> float:
        """
        生成拟人化的随机延迟

        Args:
            base_delay: 基础延迟时间,默认使用配置值

        Returns:
            随机延迟时间(秒)
        """
        if base_delay is None:
            base_delay = self.random_delay_mean

        # 使用正态分布生成延迟
        delay = random.gauss(base_delay, base_delay * 0.3)
        return max(0, delay)

    def move_to(self, x: int, y: int, duration: float = 0.5) -> None:
        """
        移动鼠标到指定位置

        Args:
            x, y: 目标坐标
            duration: 移动耗时(秒),默认0.5秒
        """
        if duration == 0:
            # 瞬移模式(仅用于测试)
            self.driver.moveTo(x, y)
            return

        if self.smooth_move:
            # 获取当前位置
            current_pos = self.driver.position()
            start_x, start_y = current_pos[0], current_pos[1]

            # 如果已在目标位置,直接返回
            if start_x == x and start_y == y:
                return

            # 生成平滑路径
            path = self._smooth_path(start_x, start_y, x, y, duration)

            # 按路径移动
            for px, py, delay in path:
                self.driver.moveTo(px, py)
                if delay > 0:
                    time.sleep(delay)
        else:
            # 直线移动
            self.driver.moveTo(x, y, duration=duration)

    def click(
            self,
            button: str = "left",
            x: Optional[int] = None,
            y: Optional[int] = None,
            duration: float = 0.5
    ) -> None:
        """
        执行鼠标点击

        Args:
            button: 按键类型 ("left", "right", "middle")
            x, y: 点击位置,None则在当前位置点击
            duration: 移动到目标位置的耗时
        """
        # 先移动到目标位置
        if x is not None and y is not None:
            self.move_to(x, y, duration)

        # 执行点击: 按下 -> 延迟 -> 松开
        self.mouse_down(button)
        time.sleep(self._humanize_delay(0.01))  # 随机延迟10ms左右
        self.mouse_up(button)

    def press_key(self, key: str, press_duration: Optional[float] = None) -> None:
        """
        模拟按键

        Args:
            key: 按键名称
            press_duration: 按键保持时间,None则使用safety_delay
        """
        if press_duration is None:
            press_duration = self.safety_delay
        else:
            press_duration = max(press_duration, self.safety_delay)

        self.key_down(key)
        time.sleep(press_duration)
        self.key_up(key)

    def key_down(self, key: str) -> None:
        """按下按键"""
        self.driver.keyDown(key)

    def key_up(self, key: str) -> None:
        """松开按键"""
        self.driver.keyUp(key)

    def mouse_down(self, button: str = "left") -> None:
        """按下鼠标按键"""
        self.driver.mouseDown(button=button)

    def mouse_up(self, button: str = "left") -> None:
        """松开鼠标按键"""
        self.driver.mouseUp(button=button)

    def wait(self, ms: int) -> None:
        """显式等待"""
        time.sleep(ms / 1000.0)

    # ========== 循环任务管理 ==========

    def start_interval(
            self,
            name: str,
            fn: Callable[..., Any],
            interval: float,
            *,
            args: tuple = (),
            kwargs: Optional[dict] = None,
            mode: str = "serial",
            jitter: float = 0.0
    ) -> str:
        """
        启动循环任务

        Args:
            name: 任务名称
            fn: 执行函数
            interval: 执行间隔(秒)
            args: 函数位置参数
            kwargs: 函数关键字参数
            mode: 执行模式 ("serial": 串行)
            jitter: 间隔抖动范围(秒)

        Returns:
            任务ID
        """
        if kwargs is None:
            kwargs = {}

        task_id = str(uuid.uuid4())
        stop_event = threading.Event()

        def task_loop():
            """任务循环"""
            while not stop_event.is_set():
                try:
                    # 执行函数
                    fn(*args, **kwargs)

                    # 计算下次执行的等待时间
                    wait_time = interval
                    if jitter > 0:
                        wait_time += random.uniform(-jitter, jitter)
                    wait_time = max(0.001, wait_time)  # 至少等待1ms

                    # 可中断的等待
                    stop_event.wait(wait_time)

                except Exception as e:
                    print(f"任务 {name} 执行出错: {e}")
                    # 出错后等待一小段时间再继续
                    stop_event.wait(0.1)

        # 创建并启动线程
        thread = threading.Thread(target=task_loop, daemon=True, name=f"Task-{name}")
        thread.start()

        # 保存任务信息
        with self._tasks_lock:
            self._tasks[task_id] = {
                "id": task_id,
                "name": name,
                "interval": interval,
                "jitter": jitter,
                "thread": thread,
                "stop_event": stop_event,
                "fn": fn
            }

        return task_id

    def stop_interval(self, task_id: str) -> bool:
        """
        停止指定任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功停止
        """
        with self._tasks_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            # 设置停止标志
            task["stop_event"].set()

            # 等待线程结束(最多1秒)
            task["thread"].join(timeout=1.0)

            # 移除任务
            del self._tasks[task_id]
            return True

    def stop_all_intervals(self) -> int:
        """
        停止所有任务

        Returns:
            停止的任务数量
        """
        with self._tasks_lock:
            task_ids = list(self._tasks.keys())

        count = 0
        for task_id in task_ids:
            if self.stop_interval(task_id):
                count += 1

        return count

    def list_intervals(self) -> List[Dict[str, Any]]:
        """
        列出所有活动任务

        Returns:
            任务信息列表
        """
        with self._tasks_lock:
            return [
                {
                    "id": task["id"],
                    "name": task["name"],
                    "interval": task["interval"],
                    "jitter": task["jitter"]
                }
                for task in self._tasks.values()
            ]

    # ========== 便捷包装方法 ==========

    def click_interval(
            self,
            interval: float,
            button: str = "left",
            x: Optional[int] = None,
            y: Optional[int] = None,
            duration: float = 0.2,
            jitter: float = 0.0
    ) -> str:
        """
        启动循环点击任务

        Args:
            interval: 点击间隔(秒)
            button: 鼠标按键
            x, y: 点击位置
            duration: 移动耗时
            jitter: 间隔抖动

        Returns:
            任务ID
        """
        return self.start_interval(
            name=f"click_{button}",
            fn=self.click,
            interval=interval,
            kwargs={"button": button, "x": x, "y": y, "duration": duration},
            jitter=jitter
        )

    def press_interval(
            self,
            interval: float,
            key: str,
            press_duration: Optional[float] = None,
            jitter: float = 0.0
    ) -> str:
        """
        启动循环按键任务

        Args:
            interval: 按键间隔(秒)
            key: 按键名称
            press_duration: 按键保持时间
            jitter: 间隔抖动

        Returns:
            任务ID
        """
        return self.start_interval(
            name=f"press_{key}",
            fn=self.press_key,
            interval=interval,
            kwargs={"key": key, "press_duration": press_duration},
            jitter=jitter
        )
