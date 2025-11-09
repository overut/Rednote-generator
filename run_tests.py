"""运行所有测试的脚本"""
import unittest
import sys
import os

# 添加项目根目录到Python路径，确保能正确导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    # 查找所有测试
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    # 运行测试
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # 根据测试结果设置退出码
    sys.exit(not result.wasSuccessful())