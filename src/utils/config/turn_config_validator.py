import yaml

from typing import Dict, List, Any, Optional, Union
from pathlib import Path

class TurnConfigValidator:
    """Turn 配置文件校验工具类"""

    VALID_DEVICES = {"mouse", "keyboard", "task", None}
    VALID_MOUSE_EVENTS = {"move", "click", "mouse_down", "mouse_up"}
    VALID_KEYBOARD_EVENTS = {"press", "key_down", "key_up"}
    VALID_TASK_EVENTS = {"start_loop", "stop_loop"}

    @classmethod
    def validate_step(cls, step: Dict[str, Any], step_index: int) -> List[str]:
        """
        校验单个步骤配置

        Args:
            step: 步骤配置字典
            step_index: 步骤索引

        Returns:
            错误信息列表，空列表表示无错误
        """
        errors = []

        # 检查设备类型
        device = step.get("device")
        if device not in cls.VALID_DEVICES:
            errors.append(f"步骤 {step_index}: 无效的 device '{device}'")

        # 检查事件类型
        event = step.get("event")
        if not event and device:  # device 存在时 event 必须存在
            errors.append(f"步骤 {step_index}: 缺少 event 字段")

        # 根据设备类型检查事件合法性
        if device == "mouse" and event not in cls.VALID_MOUSE_EVENTS:
            errors.append(f"步骤 {step_index}: 鼠标事件 '{event}' 无效")
        elif device == "keyboard" and event not in cls.VALID_KEYBOARD_EVENTS:
            errors.append(f"步骤 {step_index}: 键盘事件 '{event}' 无效")
        elif device == "task" and event not in cls.VALID_TASK_EVENTS:
            errors.append(f"步骤 {step_index}: 任务事件 '{event}' 无效")

        # 检查鼠标相关字段
        if device == "mouse":
            if event in ("move", "click"):
                position = step.get("position")
                if not position or not isinstance(position, list) or len(position) != 2:
                    errors.append(f"步骤 {step_index}: 鼠标操作需要有效的 position [x, y]")

            if event == "click" and "button" not in step:
                errors.append(f"步骤 {step_index}: click 事件缺少 button 字段")

        # 检查键盘相关字段
        if device == "keyboard" and "key" not in step:
            errors.append(f"步骤 {step_index}: 键盘操作缺少 key 字段")

        # 检查任务相关字段
        if device == "task":
            if event == "start_loop":
                task_params = step.get("task_params", {})
                if "interval" not in task_params:
                    errors.append(f"步骤 {step_index}: start_loop 需要 task_params.interval")
                if "fn_name" not in task_params:
                    errors.append(f"步骤 {step_index}: start_loop 需要 task_params.fn_name")
            elif event == "stop_loop":
                if "task_id" not in step and "task_name" not in step:
                    errors.append(f"步骤 {step_index}: stop_loop 需要 task_id 或 task_name")

        # 检查 duration 类型
        if "duration" in step:
            duration = step["duration"]
            if not isinstance(duration, (int, float)) or duration < 0:
                errors.append(f"步骤 {step_index}: duration 必须是非负数")

        # 检查 delay 格式
        if "delay" in step:
            delay = step["delay"]
            if isinstance(delay, list):
                if len(delay) not in (1, 3, 4):
                    errors.append(f"步骤 {step_index}: delay 列表长度应为 1/3/4")
            elif not isinstance(delay, (int, float)):
                errors.append(f"步骤 {step_index}: delay 应为数字或列表")

        return errors

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> List[str]:
        """
        校验整个配置

        Args:
            config: 完整配置字典

        Returns:
            所有错误信息列表
        """
        errors = []

        # 检查必需字段
        if "actions" not in config:
            errors.append("配置缺少 'actions' 字段")
            return errors

        actions = config["actions"]
        if not isinstance(actions, list):
            errors.append("'actions' 必须是列表")
            return errors

        if len(actions) == 0:
            errors.append("'actions' 列表不能为空")

        # 校验每个步骤
        for i, step in enumerate(actions):
            step_errors = cls.validate_step(step, i)
            errors.extend(step_errors)

        return errors

    @classmethod
    def load_and_validate(cls, yaml_path: Union[str, Path]) -> Dict[str, Any]:
        """
        加载并校验 YAML 配置文件

        Args:
            yaml_path: YAML 文件路径

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 文件不存在
            yaml.YAMLError: YAML 格式错误
            ValueError: 配置校验失败
        """
        yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {yaml_path}")

        # 加载 YAML
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 校验配置
        errors = cls.validate_config(config)
        if errors:
            error_msg = "配置校验失败:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

        return config
