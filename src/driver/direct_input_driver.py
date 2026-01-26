import importlib

from .base import BaseDriver


class DirectInputDriver(BaseDriver):
    def __init__(self) -> None:
        self._lib = importlib.import_module("pydirectinput")
        self._lib.PAUSE = 0

    def move_to(self, x: int, y: int) -> bool:
        try:
            self._lib.moveTo(x, y)
        except Exception:
            return False
        return True

    def mouse_down(self, button: str = "left") -> bool:
        try:
            self._lib.mouseDown(button=button.lower())
        except Exception:
            return False
        return True

    def mouse_up(self, button: str = "left") -> bool:
        try:
            self._lib.mouseUp(button=button.lower())
        except Exception:
            return False
        return True

    def key_down(self, key: str) -> bool:
        try:
            self._lib.keyDown(key.lower())
        except Exception:
            return False
        return True

    def key_up(self, key: str) -> bool:
        try:
            self._lib.keyUp(key.lower())
        except Exception:
            return False
        return True
