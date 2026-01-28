import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time

from src.turn import Turn
from src.utils.config.turn_config_validator import TurnConfigValidator

# ========== 测试类移到模块顶层（全局作用域） ==========
class TestTurnConfigValidator(unittest.TestCase):
    """配置校验器测试"""

    def test_valid_config(self):
        """测试有效配置"""
        config = {
            "actions": [
                {
                    "device": "mouse",
                    "event": "move",
                    "position": [100, 200],
                    "duration": 500
                }
            ]
        }
        errors = TurnConfigValidator.validate_config(config)
        self.assertEqual(len(errors), 0)

    def test_missing_position(self):
        """测试缺少位置信息"""
        config = {
            "actions": [
                {
                    "device": "mouse",
                    "event": "click",
                    "button": "left"
                }
            ]
        }
        errors = TurnConfigValidator.validate_config(config)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("position" in e for e in errors))

    def test_invalid_device(self):
        """测试无效设备"""
        config = {
            "actions": [
                {
                    "device": "invalid_device",
                    "event": "something"
                }
            ]
        }
        errors = TurnConfigValidator.validate_config(config)
        self.assertGreater(len(errors), 0)

class TestTurn(unittest.TestCase):
    """Turn 类测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_action = Mock()
        self.mock_action.move_to = Mock()
        self.mock_action.click = Mock()
        self.mock_action.press_key = Mock()
        self.mock_action.click_interval = Mock(return_value="task_123")
        self.mock_action.stop_interval = Mock(return_value=True)

        # 定义move_to的副作用：模拟耗时（读取duration参数并休眠）
        def mock_move_to(x,y, duration):
            # 模拟duration对应的耗时（可以简化，比如除以1000，避免测试过久）
            # 因为原始duration是100（毫秒级），这里休眠0.01秒（10毫秒）即可，既不慢又能留时间给stop
            print(x,y,duration)
            time.sleep(duration)
            print(x)

        # 给mock的move_to方法绑定side_effect
        self.mock_action.move_to.side_effect = mock_move_to

    def test_duration_conversion(self):
        """测试时长参数转换(ms -> s)"""
        config = {
            "actions": [
                {
                    "device": "mouse",
                    "event": "move",
                    "position": [100, 200],
                    "duration": 500  # 500ms
                }
            ]
        }

        turn = Turn(config, self.mock_action)
        turn.execute()

        # 验证 duration 被转换为秒并传递
        self.mock_action.move_to.assert_called_once_with(100, 200, duration=0.5)

    def test_pause_resume(self):
        """测试暂停和恢复"""
        config = {
            "actions": [
                {"device": "mouse", "event": "move", "position": [100, 100], "duration": 100},
                {"device": "mouse", "event": "move", "position": [200, 200], "duration": 100},
                {"device": "mouse", "event": "move", "position": [300, 300], "duration": 100}
            ]
        }

        turn = Turn(config, self.mock_action)

        def execute_with_pause():
            time.sleep(0.05)
            turn.pause()
            time.sleep(0.1)
            turn.resume()

        # 在后台线程执行暂停操作
        pause_thread = threading.Thread(target=execute_with_pause)
        pause_thread.start()

        result = turn.execute()
        pause_thread.join()

        self.assertEqual(result, "success")
        self.assertEqual(self.mock_action.move_to.call_count, 3)

    def test_stop_execution(self):
        """测试停止执行"""
        config = {
            "actions": [
                {"device": "mouse", "event": "move", "position": [i * 100, i * 100], "duration": 1000}
                for i in range(10)
            ]
        }

        turn = Turn(config, self.mock_action)

        def stop_after_delay():
            time.sleep(5)
            turn.stop()

        stop_thread = threading.Thread(target=stop_after_delay)
        stop_thread.start()

        result = turn.execute()
        stop_thread.join()

        self.assertEqual(result, "stopped")
        # 应该只执行了部分步骤
        self.assertLess(self.mock_action.move_to.call_count, 10)

    def test_task_cleanup(self):
        """测试任务清理"""
        config = {
            "actions": [
                {
                    "device": "task",
                    "event": "start_loop",
                    "task_name": "auto_click",
                    "task_params": {
                        "fn_name": "click",
                        "interval": 1000,
                        "x": 100,
                        "y": 200,
                        "button": "left"
                    }
                }
            ]
        }

        turn = Turn(config, self.mock_action)
        turn.execute()

        # 验证任务被启动
        self.mock_action.click_interval.assert_called_once()
        self.assertEqual(len(turn.active_task_ids), 1)
        self.assertEqual(turn.active_task_ids[0], "task_123")

        # 调用 stop，验证任务被清理
        turn.stop()
        self.mock_action.stop_interval.assert_called_with("task_123")
        self.assertEqual(len(turn.active_task_ids), 0)

    def test_delay_calculation(self):
        """测试延迟计算"""
        config = {
            "actions": [
                {
                    "device": None,
                    "delay": 1000  # 固定1秒
                }
            ]
        }

        turn = Turn(config, self.mock_action)

        start_time = time.time()
        turn.execute()
        elapsed = time.time() - start_time

        # 验证延迟接近1秒
        self.assertAlmostEqual(elapsed, 1.0, delta=0.1)

    def test_random_delay(self):
        """测试随机延迟"""
        config = {
            "actions": [
                {
                    "device": None,
                    "delay": [100, 0, 100]  # 100 + [0~100]
                }
            ]
        }

        turn = Turn(config, self.mock_action)
        delays = []

        for _ in range(5):
            start = time.time()
            turn.execute()
            delays.append(time.time() - start)

        # 验证延迟在合理范围内
        for d in delays:
            self.assertGreaterEqual(d, 0.1)
            self.assertLessEqual(d, 0.25)

# ========== 运行测试的函数 ==========
def run_tests():
    """运行单元测试"""
    # 直接调用unittest.main()，此时能正常发现顶层的两个测试类
    unittest.main(argv=[''], exit=False, verbosity=2)

if __name__ == "__main__":
    print("=" * 60)
    print("回合控制模块 - 单元测试")
    print("=" * 60)
    run_tests()