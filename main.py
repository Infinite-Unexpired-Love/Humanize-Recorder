import json
import logging
from pathlib import Path

from src.action import Action
from src.driver import PyAutoGUIDriver


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    manifest = load_manifest(Path("manifest.json"))

    driver = PyAutoGUIDriver()
    action_config = manifest.get("action", {})
    Action(
        driver=driver,
        humanization_config=action_config.get("humanization", {}),
        safety_delay_ms=action_config.get("safety_delay", 0),
        min_mouse_duration=action_config.get("min_mouse_duration", 0.0),
    )

    logging.info("Init done")


if __name__ == "__main__":
    main()
