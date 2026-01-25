from __future__ import annotations

from typing import Any

from src.driver import BaseDriver


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

    def move_to(self, x: int, y: int, duration: float) -> None:
        # TODO: implement move action
        pass

    def click(self, button: str = "left", x: int | None = None, y: int | None = None, duration: float = 0.2) -> None:
        # TODO: implement click action
        pass

    def mouse_down(self, button: str = "left", duration: float = 0.05) -> None:
        # TODO: implement mouse down action
        pass

    def mouse_up(self, button: str = "left", duration: float = 0.02) -> None:
        # TODO: implement mouse up action
        pass

    def key_down(self, key: str) -> None:
        # TODO: implement key down action
        pass

    def key_up(self, key: str) -> None:
        # TODO: implement key up action
        pass

    def press_key(self, key: str, press_duration: float | None = None) -> None:
        # TODO: implement press key action
        pass

    def wait(self, ms: int) -> None:
        # TODO: implement wait action
        pass
