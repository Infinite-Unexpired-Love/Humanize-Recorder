from __future__ import annotations

import logging
import math
import random
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from src.driver import BaseDriver

logger = logging.getLogger(__name__)


@dataclass
class TaskRecord:
    thread: threading.Thread
    stop_event: threading.Event
    name: str
    interval: float
    mode: str
    jitter: float
    last_run_ts: float | None = None
    error_count: int = 0


class Action:
    def __init__(
        self,
        driver: BaseDriver,
        humanization_config: dict[str, Any],
        safety_delay_ms: int,
        min_mouse_duration: float,
    ) -> None:
        self.driver = driver
        self.humanization_config = humanization_config
        self.safety_delay_ms = safety_delay_ms
        self.min_mouse_duration = min_mouse_duration
        self._last_position: tuple[int, int] | None = None
        self._tasks: dict[str, TaskRecord] = {}
        self._tasks_lock = threading.Lock()

    def move_to(self, x: int, y: int, duration: float) -> bool:
        duration = self._normalize_mouse_duration(duration)
        points = self._generate_bezier_points(x, y)
        if len(points) < 2:
            points = [(x, y)]

        step_sleep = duration / max(len(points) - 1, 1)
        start_time = time.monotonic()
        success = True
        for idx, (px, py) in enumerate(points):
            success = self.driver.move_to(px, py) and success
            if idx < len(points) - 1:
                self._sleep_with_stop(step_sleep)
        elapsed = time.monotonic() - start_time
        remaining = duration - elapsed
        if remaining > 0:
            self._sleep_with_stop(remaining)
        self._last_position = (x, y)
        return success

    def click(
        self,
        button: str = "left",
        x: int | None = None,
        y: int | None = None,
        duration: float = 0.2,
    ) -> bool:
        duration = self._normalize_mouse_duration(duration)
        click_duration = duration
        if x is not None and y is not None:
            move_duration = duration * 0.7
            click_duration = duration - move_duration
            self.move_to(x, y, move_duration)
        down_duration = max(click_duration * 0.6, 0)
        up_duration = max(click_duration - down_duration, 0)
        success = self.mouse_down(button=button, duration=down_duration)
        success = self.mouse_up(button=button, duration=up_duration) and success
        return success

    def mouse_down(self, button: str = "left", duration: float = 0.05) -> bool:
        duration = self._normalize_mouse_duration(duration)
        success = self.driver.mouse_down(button=button.lower())
        self._sleep_with_stop(duration)
        return success

    def mouse_up(self, button: str = "left", duration: float = 0.02) -> bool:
        duration = self._normalize_mouse_duration(duration)
        success = self.driver.mouse_up(button=button.lower())
        self._sleep_with_stop(duration)
        return success

    def key_down(self, key: str) -> bool:
        return self.driver.key_down(key.lower())

    def key_up(self, key: str) -> bool:
        return self.driver.key_up(key.lower())

    def press_key(self, key: str, press_duration_ms: int | None = None) -> bool:
        key = key.lower()
        success = self.key_down(key)
        if press_duration_ms is not None:
            self.wait(press_duration_ms)
        else:
            self._sleep_with_stop(self.safety_delay_ms / 1000.0)
        success = self.key_up(key) and success
        return success

    def wait(self, ms: int) -> None:
        self._sleep_with_stop(ms / 1000.0)

    def start_interval(
        self,
        name: str,
        fn: Callable[..., Any],
        interval: float,
        *,
        args: tuple = (),
        kwargs: dict | None = None,
        mode: str = "serial",
        jitter: float = 0.0,
    ) -> str:
        if interval <= 0:
            raise ValueError("interval must be > 0")
        if jitter < 0:
            raise ValueError("jitter must be >= 0")
        if mode not in {"serial", "skip"}:
            raise ValueError("mode must be 'serial' or 'skip'")

        task_id = uuid.uuid4().hex
        stop_event = threading.Event()
        task_kwargs = kwargs or {}

        def runner() -> None:
            next_run = time.monotonic() + interval
            while not stop_event.is_set():
                scheduled = next_run + random.uniform(-jitter, jitter) if jitter else next_run
                self._sleep_until(scheduled, stop_event)

                if stop_event.is_set():
                    break

                self._update_task_timestamp(task_id, time.time())
                try:
                    fn(*args, **task_kwargs)
                except Exception:
                    logger.error("Interval task '%s' failed", name, exc_info=True)
                    self._increment_task_error(task_id)

                run_finished = time.monotonic()
                if mode == "serial":
                    next_run = run_finished + interval
                else:
                    while next_run <= run_finished:
                        next_run += interval

        thread = threading.Thread(target=runner, name=f"interval-{name}", daemon=True)
        record = TaskRecord(
            thread=thread,
            stop_event=stop_event,
            name=name,
            interval=interval,
            mode=mode,
            jitter=jitter,
        )

        with self._tasks_lock:
            self._tasks[task_id] = record
        logger.info("Started interval task '%s' (%s)", name, task_id)
        thread.start()
        return task_id

    def stop_interval(self, task_id: str) -> bool:
        with self._tasks_lock:
            record = self._tasks.get(task_id)
        if not record:
            return False
        record.stop_event.set()
        logger.info("Stopped interval task '%s' (%s)", record.name, task_id)
        return True

    def stop_all_intervals(self) -> int:
        with self._tasks_lock:
            items = list(self._tasks.items())
        for _, record in items:
            record.stop_event.set()
            logger.info("Stopped interval task '%s'", record.name)
        return len(items)

    def list_intervals(self) -> list[dict]:
        with self._tasks_lock:
            records = list(self._tasks.items())
        result: list[dict] = []
        for task_id, record in records:
            result.append(
                {
                    "task_id": task_id,
                    "name": record.name,
                    "interval": record.interval,
                    "mode": record.mode,
                    "running": record.thread.is_alive() and not record.stop_event.is_set(),
                    "last_run_ts": record.last_run_ts,
                    "error_count": record.error_count,
                }
            )
        return result

    def click_interval(
        self,
        button: str = "left",
        x: int | None = None,
        y: int | None = None,
        duration: float = 0.2,
        interval: float = 1.0,
        *,
        mode: str = "serial",
        jitter: float = 0.0,
    ) -> str:
        name = f"click_interval:{button.lower()}"
        return self.start_interval(
            name,
            self.click,
            interval,
            args=(),
            kwargs={"button": button, "x": x, "y": y, "duration": duration},
            mode=mode,
            jitter=jitter,
        )

    def press_key_interval(
        self,
        key: str,
        press_duration_ms: int | None = None,
        interval: float = 1.0,
        *,
        mode: str = "serial",
        jitter: float = 0.0,
    ) -> str:
        name = f"press_key_interval:{key.lower()}"
        return self.start_interval(
            name,
            self.press_key,
            interval,
            args=(),
            kwargs={"key": key, "press_duration_ms": press_duration_ms},
            mode=mode,
            jitter=jitter,
        )

    def _generate_bezier_points(self, x: int, y: int) -> list[tuple[int, int]]:
        end = (x, y)
        if self._last_position is None:
            start = end
        else:
            start = self._last_position

        distance = math.hypot(end[0] - start[0], end[1] - start[1])
        if distance <= 0:
            return [end]

        points_count = max(20, min(120, int(distance / 5) + 20))
        control_offset = max(5.0, distance * 0.3)
        jitter_scale = max(3.0, distance * 0.15)

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        ctrl1 = (
            start[0] + dx * 0.3 + random.uniform(-control_offset, control_offset),
            start[1] + dy * 0.3 + random.uniform(-control_offset, control_offset),
        )
        ctrl2 = (
            start[0] + dx * 0.7 + random.uniform(-control_offset, control_offset),
            start[1] + dy * 0.7 + random.uniform(-control_offset, control_offset),
        )

        points: list[tuple[int, int]] = []
        for idx in range(points_count):
            t = idx / (points_count - 1)
            x_val = (
                (1 - t) ** 3 * start[0]
                + 3 * (1 - t) ** 2 * t * ctrl1[0]
                + 3 * (1 - t) * t**2 * ctrl2[0]
                + t**3 * end[0]
            )
            y_val = (
                (1 - t) ** 3 * start[1]
                + 3 * (1 - t) ** 2 * t * ctrl1[1]
                + 3 * (1 - t) * t**2 * ctrl2[1]
                + t**3 * end[1]
            )
            if idx not in {0, points_count - 1}:
                x_val += random.uniform(-jitter_scale, jitter_scale)
                y_val += random.uniform(-jitter_scale, jitter_scale)
            points.append((int(round(x_val)), int(round(y_val))))
        return points

    def _normalize_mouse_duration(self, duration: float) -> float:
        if duration <= 0:
            logger.warning("Mouse duration %.4f <= 0; using min_mouse_duration", duration)
            return self.min_mouse_duration
        return duration

    def _sleep_with_stop(self, seconds: float) -> None:
        if seconds <= 0:
            return
        time.sleep(seconds)

    def _sleep_until(self, target_time: float, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            remaining = target_time - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.1))

    def _update_task_timestamp(self, task_id: str, ts: float) -> None:
        with self._tasks_lock:
            record = self._tasks.get(task_id)
            if record:
                record.last_run_ts = ts

    def _increment_task_error(self, task_id: str) -> None:
        with self._tasks_lock:
            record = self._tasks.get(task_id)
            if record:
                record.error_count += 1
