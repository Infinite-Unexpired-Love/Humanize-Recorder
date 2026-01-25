from abc import ABC, abstractmethod


class BaseDriver(ABC):
    @abstractmethod
    def move_to(self, x: int, y: int, duration: float) -> bool:
        raise NotImplementedError

    @abstractmethod
    def click(self, button: str = "left", x: int | None = None, y: int | None = None, duration: float = 0.2) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mouse_down(self, button: str = "left", duration: float = 0.05) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mouse_up(self, button: str = "left", duration: float = 0.02) -> bool:
        raise NotImplementedError

    @abstractmethod
    def key_down(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def key_up(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def press_key(self, key: str, press_duration: float | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def wait(self, ms: int) -> bool:
        raise NotImplementedError
