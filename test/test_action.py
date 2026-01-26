import time
import unittest
from unittest.mock import Mock, patch

from src.action import Action

# 测试类移到模块顶层（全局作用域），让unittest能够发现
class TestAction(unittest.TestCase):

    def test_driver_switch(self):
        """测试驱动切换"""
        with patch('pyautogui.position', return_value=(0, 0)):
            action_pyautogui = Action(driver_type="pyautogui")
            self.assertEqual(action_pyautogui.driver_type, "pyautogui")

        with patch('pydirectinput.position', return_value=(0, 0)):
            action_pydirect = Action(driver_type="pydirectinput")
            self.assertEqual(action_pydirect.driver_type, "pydirectinput")

    def test_smooth_move(self):
        """测试平滑移动"""
        with patch('pyautogui.position', return_value=(0, 0)), \
                patch('pyautogui.moveTo') as mock_move:
            action = Action(
                driver_type="pyautogui",
                humanization={"smooth_move": True, "jitter": 5}
            )

            action.move_to(100, 100, duration=0.1)

            # 验证moveTo被调用多次(平滑移动)
            self.assertGreater(mock_move.call_count, 5)

    def test_safety_delay(self):
        """测试安全延迟"""
        with patch('pyautogui.position', return_value=(0, 0)), \
                patch('pyautogui.keyDown'), \
                patch('pyautogui.keyUp'), \
                patch('time.sleep') as mock_sleep:
            action = Action(driver_type="pyautogui", safety_delay=0.05)

            action.press_key("a", press_duration=0)

            # 验证sleep至少被调用一次且时间>=safety_delay
            mock_sleep.assert_called()
            self.assertGreaterEqual(mock_sleep.call_args[0][0], 0.05)

    def test_move_duration(self):
        """测试移动耗时"""
        with patch('pyautogui.position', return_value=(0, 0)), \
                patch('pyautogui.moveTo'), \
                patch('time.sleep') as mock_sleep:
            action = Action(
                driver_type="pyautogui",
                humanization={"smooth_move": True}
            )

            start_time = time.time()
            action.move_to(100, 100, duration=1.0)

            # 计算总sleep时间
            total_sleep = sum(call[0][0] for call in mock_sleep.call_args_list)

            # 验证总耗时接近1秒(允许10%误差)
            self.assertAlmostEqual(total_sleep, 1.0, delta=0.1)

    def test_interval_execution(self):
        """测试循环任务执行"""
        with patch('pyautogui.position', return_value=(0, 0)):
            action = Action(driver_type="pyautogui")

            # 创建mock函数
            mock_fn = Mock()

            # 启动任务
            task_id = action.start_interval(
                name="test",
                fn=mock_fn,
                interval=0.1,
                args=(1, 2),
                kwargs={"key": "value"}
            )

            # 等待执行几次
            time.sleep(0.35)

            # 停止任务
            action.stop_interval(task_id)

            # 验证函数被调用多次(至少2次)
            self.assertGreaterEqual(mock_fn.call_count, 2)
            mock_fn.assert_called_with(1, 2, key="value")

    def test_interval_jitter(self):
        """测试间隔抖动"""
        with patch('pyautogui.position', return_value=(0, 0)):
            action = Action(driver_type="pyautogui")

            call_times = []

            def record_time():
                call_times.append(time.time())

            # 启动带抖动的任务
            task_id = action.start_interval(
                name="jitter_test",
                fn=record_time,
                interval=0.1,
                jitter=0.05
            )

            time.sleep(0.5)
            action.stop_interval(task_id)

            # 计算间隔
            if len(call_times) >= 3:
                intervals = [call_times[i + 1] - call_times[i]
                             for i in range(len(call_times) - 1)]

                # 验证间隔有波动
                self.assertGreater(max(intervals) - min(intervals), 0.01)

def run_tests():
    """运行单元测试"""
    # 直接调用unittest.main()，此时能正常发现顶层的TestAction类
    unittest.main(argv=[''], exit=False, verbosity=2)

if __name__ == "__main__":
    print("=" * 60)
    print("动作执行模块 - 单元测试")
    print("=" * 60)
    run_tests()