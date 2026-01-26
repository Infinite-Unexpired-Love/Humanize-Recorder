from abc import ABC, abstractmethod


class BaseDriver(ABC):
    @abstractmethod
    def move_to(self, x: int, y: int) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mouse_down(self, button: str = "left") -> bool:
        raise NotImplementedError

    @abstractmethod
    def mouse_up(self, button: str = "left") -> bool:
        raise NotImplementedError

    @abstractmethod
    def key_down(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def key_up(self, key: str) -> bool:
        raise NotImplementedError
