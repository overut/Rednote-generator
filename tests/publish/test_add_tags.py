"""标签添加功能单元测试"""
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import sys
import os
import time

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.publish.publisher import XiaohongshuPublisher, PublishResult, PublishConfig
from src.config.config_manager import ConfigManager


class TestAddTagsFunction(unittest.TestCase):
    """测试标签添加功能"""
    
    def setUp(self):
        """测试前的设置"""
        # 创建ConfigManager的mock
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_config_manager.get_config.return_value = {
            'publish': {
                'account_name': 'test_user',
                'headless_mode': False,
                'retry_count': 3,
                'retry_interval': 5,
                'enable_comments': True,
                'sync_to_other_platforms': False
            }
        }
        
        # 模拟BrowserManager
        self.mock_browser_manager = MagicMock()
        self.mock_browser_manager.init_browser = AsyncMock()
        self.mock_browser_manager.load_cookies = AsyncMock()
        self.mock_browser_manager.get_page = AsyncMock()
        self.mock_browser_manager.save_cookies = AsyncMock()
        self.mock_browser_manager.close = AsyncMock()
        
        # 模拟get_browser_manager函数
        with patch('src.publish.publisher.get_browser_manager', return_value=self.mock_browser_manager):
            # 初始化发布器
            self.publisher = XiaohongshuPublisher(self.mock_config_manager)
            self.publisher.is_initialized = True  # 跳过初始化过程
        
        # 模拟日志记录器
        self.publisher.logger = MagicMock()
    
    @patch('time.time')
    def test_add_tags_success_with_textarea(self, mock_time):
        """测试成功向textarea添加标签"""
        # 设置时间模拟
        mock_time.side_effect = [0, 1.5]  # 开始时间和结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_keyboard = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.evaluate = AsyncMock(side_effect=[
            'textarea',  # 元素类型
            '这是测试内容',  # 当前内容
            True,  # 元素可见
            '这是测试内容 #测试 #标签',  # 更新后的内容
        ])
        
        # 模拟fill方法
        mock_page.fill = AsyncMock()
        
        # 模拟keyboard对象
        mock_page.keyboard = mock_keyboard
        mock_keyboard.press = AsyncMock()
        mock_keyboard.type = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertTrue(result)
            mock_page.query_selector.assert_called()
            mock_page.fill.assert_called()
            self.publisher.logger.info.assert_called()
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_success_with_contenteditable(self, mock_time):
        """测试成功向contenteditable元素添加标签"""
        # 设置时间模拟
        mock_time.side_effect = [0, 1.2]  # 开始时间和结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_keyboard = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.evaluate = AsyncMock(side_effect=[
            'div',  # 元素类型
            '这是测试内容',  # 当前内容
            True,  # 元素可见
            None,  # click操作
            None,  # evaluate操作（JavaScript代码）
            '这是测试内容 #测试 #标签',  # 更新后的内容
        ])
        
        # 模拟click方法
        mock_page.click = AsyncMock()
        
        # 模拟keyboard对象
        mock_page.keyboard = mock_keyboard
        mock_keyboard.press = AsyncMock()
        mock_keyboard.type = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertTrue(result)
            mock_page.query_selector.assert_called()
            mock_page.click.assert_called()
            self.publisher.logger.info.assert_called()
        
        asyncio.run(run_test())
    
    def test_add_tags_already_exists(self):
        """测试标签已存在的情况"""
        # 模拟页面对象
        mock_page = MagicMock()
        mock_element = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.evaluate = AsyncMock(side_effect=[
            'textarea',  # 元素类型
            '这是测试内容 #测试 #标签',  # 当前内容（已包含标签）
            True,  # 元素可见
        ])
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertTrue(result)
            self.publisher.logger.info.assert_called_with(
                "[标签添加] 所有标签已存在于内容中，无需重复添加，选择器: .publish-content textarea"
            )
        
        asyncio.run(run_test())
    
    def test_add_tags_no_content_element(self):
        """测试找不到内容元素的情况"""
        # 模拟页面对象
        mock_page = MagicMock()
        
        # 设置模拟返回值 - 将query_selector设置为AsyncMock，找不到元素
        mock_page.query_selector = AsyncMock(return_value=None)
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertFalse(result)
            self.publisher.logger.warning.assert_called()
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_with_javascript_fallback(self, mock_time):
        """测试JavaScript备用方案"""
        # 设置时间模拟
        mock_time.side_effect = [0, 1.0, 1.5]  # 开始时间、JS开始时间、结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        mock_keyboard = MagicMock()
        
        # 设置模拟返回值 - 将query_selector设置为AsyncMock，所有选择器都失败
        mock_page.query_selector = AsyncMock(return_value=None)
        
        # 设置JavaScript评估成功 - 将evaluate设置为AsyncMock
        mock_page.evaluate = AsyncMock(return_value=True)
        
        # 模拟keyboard对象
        mock_page.keyboard = mock_keyboard
        mock_keyboard.press = AsyncMock()
        mock_keyboard.type = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertTrue(result)
            self.publisher.logger.info.assert_called_with("使用JavaScript方式成功添加标签到正文内容")
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_with_manual_input_fallback(self, mock_time):
        """测试手动输入备用方案"""
        # 设置时间模拟
        mock_time.side_effect = [0, 1.0, 1.5]  # 开始时间、JS开始时间、结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        mock_element = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock，所有选择器都失败
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.evaluate = AsyncMock(side_effect=[
            None,  # 元素类型
            None,  # 当前内容
            True,  # 元素可见
            False,  # JavaScript方式失败
        ])
        
        # 模拟wait_for_selector和fill方法
        mock_page.wait_for_selector = AsyncMock(return_value=mock_element)
        mock_page.fill = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertTrue(result)
            mock_page.wait_for_selector.assert_called()
            mock_page.fill.assert_called()
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_with_keyboard_fallback(self, mock_time):
        """测试键盘快捷键备用方案"""
        # 设置时间模拟
        mock_time.side_effect = [0, 1.0, 1.5, 2.0]  # 开始时间、JS开始时间、手动输入开始时间、结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        mock_element = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock，所有选择器、JavaScript和手动输入都失败
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.evaluate = AsyncMock(side_effect=[
            None,  # 元素类型
            None,  # 当前内容
            True,  # 元素可见
            False,  # JavaScript方式失败
            None,  # 手动输入元素类型
            None,  # 手动输入当前内容
            True,  # 手动输入元素可见
            None,  # 手动输入失败
        ])
        
        # 模拟wait_for_selector、click和type方法
        mock_page.wait_for_selector = AsyncMock(return_value=mock_element)
        mock_page.click = AsyncMock()
        mock_page.type = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertTrue(result)
            mock_page.wait_for_selector.assert_called()
            mock_page.click.assert_called()
            mock_page.type.assert_called()
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_all_methods_fail(self, mock_time):
        """测试所有方法都失败的情况"""
        # 设置时间模拟
        mock_time.side_effect = [0, 1.0, 1.5, 2.0, 2.5]  # 开始时间、JS开始时间、手动输入开始时间、键盘开始时间、结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock，所有方法都失败
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.evaluate = AsyncMock(side_effect=[
            None,  # 元素类型
            None,  # 当前内容
            True,  # 元素可见
            False,  # JavaScript方式失败
            None,  # 手动输入元素类型
            None,  # 手动输入当前内容
            True,  # 手动输入元素可见
            None,  # 手动输入失败
            None,  # 键盘输入元素类型
            None,  # 键盘输入当前内容
            True,  # 键盘输入元素可见
            None,  # 键盘输入失败
        ])
        
        # 模拟wait_for_selector、click和type方法
        mock_page.wait_for_selector = AsyncMock(return_value=None)
        
        # 模拟截图方法
        mock_page.screenshot = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertFalse(result)
            mock_page.wait_for_selector.assert_called()
            mock_page.screenshot.assert_called()
            self.publisher.logger.error.assert_called()
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_with_empty_tags(self, mock_time):
        """测试空标签列表的情况"""
        # 设置时间模拟
        mock_time.return_value = 0
        
        # 模拟页面对象
        mock_page = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock
        mock_page.query_selector = AsyncMock(return_value=MagicMock())
        mock_page.evaluate = AsyncMock(side_effect=[
            None,  # 元素类型
            None,  # 当前内容
            True,  # 元素可见
        ])
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, [])
            
            # 验证结果
            self.assertTrue(result)  # 空标签列表应该被视为成功
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_with_long_content(self, mock_time):
        """测试内容很长的情况"""
        # 设置时间模拟
        mock_time.side_effect = [0, 2.0]  # 开始时间和结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        mock_element = MagicMock()
        
        # 创建长内容
        long_content = "这是一个很长的测试内容。" * 100
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.evaluate = AsyncMock(side_effect=[
            'textarea',  # 元素类型
            long_content,  # 当前内容
            True,  # 元素可见
            long_content + " #测试 #标签",  # 更新后的内容
        ])
        
        # 模拟fill方法
        mock_page.fill = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试", "#标签"])
            
            # 验证结果
            self.assertTrue(result)
            mock_page.fill.assert_called()
            self.publisher.logger.info.assert_called()
        
        asyncio.run(run_test())
    
    @patch('time.time')
    def test_add_tags_with_special_characters(self, mock_time):
        """测试包含特殊字符的标签"""
        # 设置时间模拟
        mock_time.side_effect = [0, 1.5]  # 开始时间和结束时间
        
        # 模拟页面对象
        mock_page = MagicMock()
        mock_element = MagicMock()
        
        # 设置模拟返回值 - 将query_selector和evaluate设置为AsyncMock
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        mock_page.evaluate = AsyncMock(side_effect=[
            'textarea',  # 元素类型
            '这是测试内容',  # 当前内容
            True,  # 元素可见
            '这是测试内容 #测试@#$%^&*()_+-=[]{}|;:,.<>?',  # 更新后的内容
        ])
        
        # 模拟fill方法
        mock_page.fill = AsyncMock()
        
        # 运行异步测试
        async def run_test():
            # 调用标签添加方法
            result = await self.publisher._add_tags(mock_page, ["#测试@#$%^&*()_+-=[]{}|;:,.<>?"])
            
            # 验证结果
            self.assertTrue(result)
            mock_page.fill.assert_called()
            self.publisher.logger.info.assert_called()
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()