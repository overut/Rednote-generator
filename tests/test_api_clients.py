"""
测试API客户端
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from src.api.deepseek_client import DeepseekAPIClient
from src.api.jimeng_client import JimengAPIClient


class TestDeepseekAPIClient(unittest.TestCase):
    """Deepseek API客户端测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.api_config = {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "test_key",
            "model": "deepseek-chat",
            "timeout": 30,
            "max_retries": 3
        }
        
        self.client = DeepseekAPIClient(self.api_config)
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.client.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(self.client.api_key, "test_key")
        self.assertEqual(self.client.model, "deepseek-chat")
        self.assertEqual(self.client.timeout, 30)
        self.assertEqual(self.client.max_retries, 3)
    
    @patch('src.api.base_client.requests.Session.post')
    def test_generate_response(self, mock_post):
        """测试生成响应"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "这是测试响应"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # 调用方法
        response = self.client.generate_response("测试提示词")
        
        # 验证结果
        self.assertEqual(response, "这是测试响应")
        
        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["model"], "deepseek-chat")
        self.assertEqual(call_args[1]["json"]["messages"][0]["content"], "测试提示词")
    
    @patch('src.api.base_client.requests.Session.post')
    def test_generate_topics(self, mock_post):
        """测试生成选题"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "1. 选题一\n2. 选题二\n3. 选题三"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # 调用方法
        topics = self.client.generate_topics("美妆")
        
        # 验证结果
        self.assertEqual(len(topics), 3)
        self.assertEqual(topics[0].title, "选题一")
        self.assertEqual(topics[1].title, "选题二")
        self.assertEqual(topics[2].title, "选题三")
    
    @patch('src.api.base_client.requests.Session.post')
    def test_generate_content(self, mock_post):
        """测试生成文案"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "标题：测试标题\n正文：这是测试正文\n标签：#测试 #标签"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # 调用方法
        content = self.client.generate_content("测试选题")
        
        # 验证结果
        self.assertEqual(content.title, "测试标题")
        self.assertEqual(content.body, "这是测试正文")
        self.assertEqual(len(content.tags), 2)
        self.assertEqual(content.tags[0], "#测试")
        self.assertEqual(content.tags[1], "#标签")


class TestJimengAPIClient(unittest.TestCase):
    """即梦API客户端测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.api_config = {
            "base_url": "https://jimeng.jianying.com/api/v1",
            "api_key": "test_key",
            "model": "jimeng-v1",
            "timeout": 30,
            "max_retries": 3
        }
        
        self.client = JimengAPIClient(self.api_config)
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.client.base_url, "https://jimeng.jianying.com/api/v1")
        self.assertEqual(self.client.api_key, "test_key")
        self.assertEqual(self.client.model, "jimeng-v1")
        self.assertEqual(self.client.timeout, 30)
        self.assertEqual(self.client.max_retries, 3)
    
    @patch('src.api.base_client.requests.Session.post')
    def test_generate_image(self, mock_post):
        """测试生成图片"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "url": "https://example.com/image.jpg"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # 调用方法
        result = self.client.generate_image("测试提示词")
        
        # 验证结果
        self.assertEqual(result.image_url, "https://example.com/image.jpg")
        self.assertEqual(result.prompt, "测试提示词")
        self.assertEqual(result.status, "success")
        
        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["model"], "jimeng-v1")
        self.assertEqual(call_args[1]["json"]["prompt"], "测试提示词")


if __name__ == "__main__":
    unittest.main()