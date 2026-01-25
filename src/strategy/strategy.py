class Strategy:
    def __init__(self, config: dict) -> None:
        self.config = config

    def next_state(self, current_state: str) -> str | None:
        return None
