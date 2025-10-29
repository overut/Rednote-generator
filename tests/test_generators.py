"""
测试生成器
"""

import unittest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from src.generators.topic_generator import TopicGenerator, Topic
from src.generators.content_generator import ContentGenerator, Content
from src.generators.image_generator import ImageGenerator, ImageResult
from src.generators.note_generator import NoteGenerator, NoteResult


class TestTopicGenerator(unittest.TestCase):
    """选题生成器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.config = {
            "api": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "test_key",
                    "model": "deepseek-chat"
                }
            },
            "prompts": {
                "topic_generation": "生成关于{category}的选题，数量：{count}"
            }
        }
        
        self.generator = TopicGenerator(self.config)
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.generator.config, self.config)
        self.assertIsNone(self.generator.api_client)
    
    @patch('src.generators.topic_generator.DeepseekAPIClient')
    def test_get_api_client(self, mock_client_class):
        """测试获取API客户端"""
        # 模拟API客户端
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 调用方法
        client = self.generator.get_api_client()
        
        # 验证结果
        self.assertEqual(client, mock_client)
        mock_client_class.assert_called_once_with(self.config["api"]["deepseek"])
    
    @patch('src.generators.topic_generator.DeepseekAPIClient')
    def test_generate_topics(self, mock_client_class):
        """测试生成选题"""
        # 模拟API客户端
        mock_client = Mock()
        mock_client.generate_topics.return_value = [
            Topic(title="选题一", description="描述一", tags=["#标签1"]),
            Topic(title="选题二", description="描述二", tags=["#标签2"])
        ]
        mock_client_class.return_value = mock_client
        
        # 调用方法
        topics = self.generator.generate_topics("美妆", count=2)
        
        # 验证结果
        self.assertEqual(len(topics), 2)
        self.assertEqual(topics[0].title, "选题一")
        self.assertEqual(topics[1].title, "选题二")
        
        # 验证API调用
        mock_client.generate_topics.assert_called_once()
        call_args = mock_client.generate_topics.call_args
        self.assertEqual(call_args[0][0], "美妆")
        self.assertEqual(call_args[1]["count"], 2)


class TestContentGenerator(unittest.TestCase):
    """文案生成器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.config = {
            "api": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "test_key",
                    "model": "deepseek-chat"
                }
            },
            "prompts": {
                "content_generation": "为{topic}写文案"
            }
        }
        
        self.generator = ContentGenerator(self.config)
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.generator.config, self.config)
        self.assertIsNone(self.generator.api_client)
    
    @patch('src.generators.content_generator.DeepseekAPIClient')
    def test_generate_content(self, mock_client_class):
        """测试生成文案"""
        # 模拟API客户端
        mock_client = Mock()
        mock_client.generate_content.return_value = Content(
            title="测试标题",
            body="这是测试正文",
            tags=["#测试", "#标签"]
        )
        mock_client_class.return_value = mock_client
        
        # 调用方法
        content = self.generator.generate_content("测试选题")
        
        # 验证结果
        self.assertEqual(content.title, "测试标题")
        self.assertEqual(content.body, "这是测试正文")
        self.assertEqual(len(content.tags), 2)
        
        # 验证API调用
        mock_client.generate_content.assert_called_once_with("测试选题")


class TestImageGenerator(unittest.TestCase):
    """图片生成器测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        self.config = {
            "api": {
                "jimeng": {
                    "base_url": "https://jimeng.jianying.com/api/v1",
                    "api_key": "test_key",
                    "model": "jimeng-v1"
                }
            },
            "output": {
                "image_dir": self.temp_dir
            }
        }
        
        self.generator = ImageGenerator(self.config)
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.generator.config, self.config)
        self.assertIsNone(self.generator.api_client)
    
    @patch('src.generators.image_generator.JimengAPIClient')
    @patch('src.generators.image_generator.download_image')
    def test_generate_image(self, mock_download, mock_client_class):
        """测试生成图片"""
        # 模拟API客户端
        mock_client = Mock()
        mock_client.generate_image.return_value = ImageResult(
            image_url="https://example.com/image.jpg",
            prompt="测试提示词",
            status="success"
        )
        mock_client_class.return_value = mock_client
        
        # 模拟图片下载
        mock_download.return_value = os.path.join(self.temp_dir, "test_image.jpg")
        
        # 调用方法
        result = self.generator.generate_image("测试提示词", save_path=self.temp_dir)
        
        # 验证结果
        self.assertEqual(result.image_url, "https://example.com/image.jpg")
        self.assertEqual(result.prompt, "测试提示词")
        self.assertEqual(result.status, "success")
        
        # 验证API调用
        mock_client.generate_image.assert_called_once_with("测试提示词")


class TestNoteGenerator(unittest.TestCase):
    """笔记生成器测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        self.config = {
            "api": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "test_key",
                    "model": "deepseek-chat"
                },
                "jimeng": {
                    "base_url": "https://jimeng.jianying.com/api/v1",
                    "api_key": "test_key",
                    "model": "jimeng-v1"
                }
            },
            "output": {
                "image_dir": os.path.join(self.temp_dir, "images"),
                "content_dir": os.path.join(self.temp_dir, "content")
            }
        }
        
        self.generator = NoteGenerator(self.config)
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.generator.config, self.config)
        self.assertIsNone(self.generator.topic_generator)
        self.assertIsNone(self.generator.content_generator)
        self.assertIsNone(self.generator.image_generator)
    
    @patch('src.generators.note_generator.ImageGenerator')
    @patch('src.generators.note_generator.ContentGenerator')
    @patch('src.generators.note_generator.TopicGenerator')
    def test_generate_note(self, mock_topic_class, mock_content_class, mock_image_class):
        """测试生成笔记"""
        # 模拟生成器
        mock_topic_generator = Mock()
        mock_topic_generator.generate_topics.return_value = [
            Topic(title="测试选题", description="测试描述", tags=["#测试"])
        ]
        mock_topic_class.return_value = mock_topic_generator
        
        mock_content_generator = Mock()
        mock_content_generator.generate_content.return_value = Content(
            title="测试标题",
            body="测试正文",
            tags=["#测试", "#标签"]
        )
        mock_content_class.return_value = mock_content_generator
        
        mock_image_generator = Mock()
        mock_image_generator.generate_image.return_value = ImageResult(
            image_url="https://example.com/image.jpg",
            prompt="测试提示词",
            status="success",
            local_path=os.path.join(self.temp_dir, "test_image.jpg")
        )
        mock_image_class.return_value = mock_image_generator
        
        # 调用方法
        result = self.generator.generate_note("美妆", generate_image=True)
        
        # 验证结果
        self.assertIsInstance(result, NoteResult)
        self.assertEqual(result.topic.title, "测试选题")
        self.assertEqual(result.content.title, "测试标题")
        self.assertEqual(result.image.image_url, "https://example.com/image.jpg")
        
        # 验证生成器调用
        mock_topic_generator.generate_topics.assert_called_once()
        mock_content_generator.generate_content.assert_called_once()
        mock_image_generator.generate_image.assert_called_once()


if __name__ == "__main__":
    unittest.main()