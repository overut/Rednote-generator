"""小红书发布器单元测试"""
import unittest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# 从src.publish模块导入XiaohongshuPublisher和PublishResult
from src.publish.publisher import XiaohongshuPublisher, PublishResult, PublishConfig
from src.config.config_manager import ConfigManager

class TestXiaohongshuPublisher(unittest.TestCase):
    
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
    
    def test_initialization(self):
        """测试初始化功能"""
        # 验证初始化参数是否正确设置
        self.assertEqual(self.publisher.config_manager, self.mock_config_manager)
        self.assertEqual(self.publisher.browser_manager, self.mock_browser_manager)
        self.assertIsInstance(self.publisher.publish_config, PublishConfig)
        self.assertEqual(self.publisher.publish_config.account_name, 'test_user')
    
    @patch('src.publish.publisher.publish_utils.generate_note_id')
    @patch('src.publish.publisher.XiaohongshuPublisher._login_if_needed')
    @patch('src.publish.publisher.XiaohongshuPublisher._fill_content')
    @patch('src.publish.publisher.XiaohongshuPublisher._upload_images')
    @patch('src.publish.publisher.XiaohongshuPublisher._add_tags')
    @patch('src.publish.publisher.XiaohongshuPublisher._set_publish_params')
    @patch('src.publish.publisher.XiaohongshuPublisher._execute_publish')
    @patch('asyncio.sleep')
    async def test_publish_note_success(self, mock_sleep, mock_execute_publish, 
                                       mock_set_publish_params, mock_add_tags,
                                       mock_upload_images, mock_fill_content,
                                       mock_login_if_needed, mock_generate_note_id):
        """测试发布笔记成功的情况"""
        # 设置mock返回值
        mock_generate_note_id.return_value = "note123"
        mock_login_if_needed.return_value = True
        mock_fill_content.return_value = True
        mock_upload_images.return_value = True
        mock_add_tags.return_value = True
        mock_set_publish_params.return_value = True
        mock_execute_publish.return_value = {
            "status": "success",
            "note_id": "note123",
            "url": "https://www.xiaohongshu.com/explore/note123"
        }
        
        # 模拟page对象
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.close = AsyncMock()
        self.mock_browser_manager.get_page.return_value = mock_page
        
        # 调用异步发布方法
        result = await self.publisher.publish_note(
            title="测试标题",
            content="测试内容",
            image_paths=[],
            hashtags=["测试", "标签"]
        )
        
        # 验证结果
        self.assertEqual(result.status, "success")
        self.assertEqual(result.note_id, "note123")
        self.assertEqual(result.publish_url, "https://www.xiaohongshu.com/explore/note123")
    
    @patch('src.publish.publisher.publish_utils.generate_note_id')
    @patch('src.publish.publisher.XiaohongshuPublisher._login_if_needed')
    @patch('src.publish.publisher.XiaohongshuPublisher._fill_content')
    async def test_publish_note_failure(self, mock_fill_content, 
                                       mock_login_if_needed, mock_generate_note_id):
        """测试发布笔记失败的情况"""
        # 设置mock返回值
        mock_generate_note_id.return_value = "note456"
        mock_login_if_needed.return_value = True
        mock_fill_content.return_value = False
        
        # 模拟page对象
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.close = AsyncMock()
        self.mock_browser_manager.get_page.return_value = mock_page
        
        # 调用异步发布方法
        result = await self.publisher.publish_note(
            title="测试标题",
            content="测试内容",
            image_paths=[],
            hashtags=["测试", "标签"]
        )
        
        # 验证结果
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.note_id, "note456")
        self.assertIsNotNone(result.error_message)
    
    @patch('src.publish.publisher.XiaohongshuPublisher._load_publish_config')
    @patch('src.publish.publisher.get_browser_manager')
    async def test_initialize_async(self, mock_get_browser_manager, mock_load_publish_config):
        """测试异步初始化功能"""
        # 设置mock返回值
        mock_load_publish_config.return_value = self.publisher.publish_config
        mock_get_browser_manager.return_value = self.mock_browser_manager
        self.mock_browser_manager.init_browser.return_value = True
        
        # 重置初始化状态
        self.publisher.is_initialized = False
        
        # 调用异步初始化方法
        result = await self.publisher._initialize()
        
        # 验证结果
        self.assertTrue(result)
        self.assertTrue(self.publisher.is_initialized)
        mock_load_publish_config.assert_called_once()
        mock_get_browser_manager.assert_called_once()
        self.mock_browser_manager.init_browser.assert_called_once()
    
    async def test_close(self):
        """测试资源清理功能"""
        # 调用关闭方法
        await self.publisher.close()
        
        # 验证browser_manager被关闭
        self.mock_browser_manager.close.assert_called_once()
        self.assertFalse(self.publisher.is_initialized)
    
    def test_load_publish_config(self):
        """测试加载发布配置功能"""
        # 获取配置
        config = self.publisher._load_publish_config()
        
        # 验证配置
        self.assertIsInstance(config, PublishConfig)
        self.assertEqual(config.account_name, 'test_user')
        self.assertEqual(config.headless_mode, False)
        self.assertEqual(config.retry_count, 3)
    
    @patch('src.publish.publisher.publish_utils.generate_note_id')
    @patch('src.publish.publisher.XiaohongshuPublisher._login_if_needed')
    @patch('src.publish.publisher.XiaohongshuPublisher._fill_content')
    @patch('asyncio.sleep')
    async def test_publish_retry_mechanism(self, mock_sleep, mock_fill_content,
                                          mock_login_if_needed, mock_generate_note_id):
        """测试发布重试机制"""
        # 设置重试次数为2
        self.publisher.publish_config.retry_count = 2
        
        # 设置mock返回值
        mock_generate_note_id.return_value = "note789"
        mock_login_if_needed.return_value = True
        
        # 模拟第一次失败，第二次成功
        mock_fill_content.side_effect = [False, True]
        
        # 模拟page对象
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.close = AsyncMock()
        self.mock_browser_manager.get_page.return_value = mock_page
        
        # 调用异步发布方法
        result = await self.publisher.publish_note(
            title="测试标题",
            content="测试内容",
            image_paths=[],
            hashtags=["测试", "标签"]
        )
        
        # 验证结果
        self.assertEqual(mock_fill_content.call_count, 2)  # 验证重试了一次
        mock_sleep.assert_called_once()  # 验证等待了重试间隔

class TestPublishResult(unittest.TestCase):
    """测试PublishResult类"""
    
    def test_publish_result_initialization(self):
        """测试PublishResult初始化"""
        # 测试成功情况
        result_success = PublishResult(
            note_id='test123',
            status='success',
            publish_url='https://example.com/note/test123',
            publish_time=datetime.now()
        )
        
        self.assertEqual(result_success.note_id, 'test123')
        self.assertEqual(result_success.status, 'success')
        
        # 测试失败情况
        result_failed = PublishResult(
            note_id='test456',
            status='failed',
            publish_url='',
            publish_time=None,
            error_message='发布失败'
        )
        
        self.assertEqual(result_failed.note_id, 'test456')
        self.assertEqual(result_failed.status, 'failed')
        self.assertEqual(result_failed.error_message, '发布失败')
        
    def test_publish_result_str(self):
        """测试PublishResult的字符串表示"""
        result = PublishResult(
            note_id='test123',
            status='success',
            publish_url='https://example.com/note/test123',
            publish_time=datetime.now()
        )
        
        # 验证字符串表示包含关键信息
        result_str = str(result)
        self.assertIn('test123', result_str)
        self.assertIn('success', result_str)
        self.assertIn('https://example.com/note/test123', result_str)

if __name__ == '__main__':
    unittest.main()