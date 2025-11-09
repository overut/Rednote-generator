"""发布工具类单元测试"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import json

# 导入被测试的类和函数
from src.publish.publish_utils import PublishUtils, publish_utils

class TestPublishUtils(unittest.TestCase):
    
    def setUp(self):
        """测试前的设置"""
        self.publish_utils = PublishUtils()
        
    def test_extract_tags(self):
        """测试从内容中提取标签"""
        # 测试有#标签的情况
        content = "这是一个测试内容 #标签1 #标签2 这里还有一些内容"
        tags = publish_utils.extract_tags(content)
        self.assertIn("标签1", tags)
        self.assertIn("标签2", tags)
        
        # 测试没有#标签的情况
        content_no_tags = "这是一个没有标签的测试内容，只有一些普通文字"
        tags = publish_utils.extract_tags(content_no_tags)
        self.assertTrue(len(tags) > 0)
        
        # 测试标签数量限制
        content_many_tags = "#标签1 #标签2 #标签3 #标签4 #标签5 #标签6 #标签7"
        tags = publish_utils.extract_tags(content_many_tags, max_tags=3)
        self.assertEqual(len(tags), 3)
    
    def test_preprocess_content(self):
        """测试内容预处理"""
        # 测试基本预处理功能
        content = "这是一个包含**和**的测试"
        processed = publish_utils.preprocess_content(content)
        
        # 验证内容没有被错误修改
        self.assertEqual(processed, "这是一个包含**和**的测试")
        
        # 测试空内容处理
        self.assertEqual(publish_utils.preprocess_content(""), "")
        
        # 测试None处理
        self.assertEqual(publish_utils.preprocess_content(None), "")
    
    def test_validate_images(self):
        """测试图片验证功能"""
        # 测试有效图片
        valid_images = [
            {"path": "test_image1.jpg"},
            {"path": "test_image2.jpg"}
        ]
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024 * 1024):  # 1MB
            result = self.publish_utils.validate_images(valid_images)
            self.assertEqual(len(result), 2)
        
        # 测试无效图片
        invalid_images = [
            {"path": "non_existent_image.jpg"}
        ]
        
        with patch('os.path.exists', return_value=False):
            result = self.publish_utils.validate_images(invalid_images)
            self.assertEqual(len(result), 0)
        
        # 测试图片数量限制
        many_images = [{"path": f"image{i}.jpg"} for i in range(15)]
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024 * 1024):
            result = self.publish_utils.validate_images(many_images)
            self.assertEqual(len(result), 9)  # 小红书限制最多9张图
    
    def test_generate_note_id(self):
        """测试生成笔记ID功能"""
        note_id = self.publish_utils.generate_note_id()
        
        # 检查格式
        self.assertTrue(note_id.startswith("note_"))
        
        # 检查组成部分
        parts = note_id.split("_")
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[1].isdigit())
    
    def test_create_cookies_dir(self):
        """测试创建cookies目录"""
        with patch('os.makedirs') as mock_makedirs, \
             patch('os.path.exists', return_value=False), \
             patch('builtins.open', mock_open()):
            
            cookies_dir = self.publish_utils.create_cookies_dir("test_dir")
            
            # 验证目录创建
            expected_dir = os.path.join("test_dir", ".cookies")
            mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)
            
            # 验证返回值
            self.assertEqual(cookies_dir, expected_dir)
    


if __name__ == '__main__':
    unittest.main()