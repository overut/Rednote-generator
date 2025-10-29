"""
测试工具函数
"""

import unittest
import os
import tempfile
import shutil
import json
import yaml

from src.utils.utils import (
    load_config, save_config, validate_config,
    format_prompt, extract_tags, extract_keywords,
    generate_uuid, ensure_dir_exists,
    resize_image, crop_image, download_image
)


class TestUtils(unittest.TestCase):
    """工具函数测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试配置文件
        self.config_file = os.path.join(self.temp_dir, "test_config.yaml")
        test_config = {
            "api": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "test_key",
                    "model": "deepseek-chat"
                }
            },
            "prompts": {
                "topic_generation": "生成关于{category}的选题"
            },
            "output": {
                "image_dir": "output/images"
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f, default_flow_style=False, allow_unicode=True)
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir)
    
    def test_load_config(self):
        """测试加载配置"""
        # 测试加载YAML配置
        config = load_config(self.config_file)
        self.assertEqual(config["api"]["deepseek"]["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(config["prompts"]["topic_generation"], "生成关于{category}的选题")
        
        # 测试加载JSON配置
        json_config_file = os.path.join(self.temp_dir, "test_config.json")
        with open(json_config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        json_config = load_config(json_config_file)
        self.assertEqual(json_config["api"]["deepseek"]["base_url"], "https://api.deepseek.com/v1")
    
    def test_save_config(self):
        """测试保存配置"""
        config = {
            "api": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "new_key",
                    "model": "deepseek-chat"
                }
            }
        }
        
        # 保存为YAML
        yaml_file = os.path.join(self.temp_dir, "saved_config.yaml")
        save_config(config, yaml_file)
        
        # 验证保存结果
        loaded_config = load_config(yaml_file)
        self.assertEqual(loaded_config["api"]["deepseek"]["api_key"], "new_key")
        
        # 保存为JSON
        json_file = os.path.join(self.temp_dir, "saved_config.json")
        save_config(config, json_file)
        
        # 验证保存结果
        loaded_config = load_config(json_file)
        self.assertEqual(loaded_config["api"]["deepseek"]["api_key"], "new_key")
    
    def test_validate_config(self):
        """测试验证配置"""
        # 测试有效配置
        valid_config = {
            "api": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    "api_key": "test_key",
                    "model": "deepseek-chat"
                }
            },
            "prompts": {
                "topic_generation": "生成关于{category}的选题"
            },
            "output": {
                "image_dir": "output/images"
            }
        }
        
        self.assertTrue(validate_config(valid_config))
        
        # 测试无效配置（缺少必需字段）
        invalid_config = {
            "api": {
                "deepseek": {
                    "base_url": "https://api.deepseek.com/v1",
                    # 缺少api_key
                    "model": "deepseek-chat"
                }
            }
        }
        
        self.assertFalse(validate_config(invalid_config))
    
    def test_format_prompt(self):
        """测试格式化提示词"""
        template = "生成关于{category}的选题，数量：{count}"
        
        # 测试正常替换
        result = format_prompt(template, category="美妆", count=5)
        self.assertEqual(result, "生成关于美妆的选题，数量：5")
        
        # 测试部分替换
        result = format_prompt(template, category="美食")
        self.assertEqual(result, "生成关于美食的选题，数量：{count}")
        
        # 测试无替换
        result = format_prompt(template)
        self.assertEqual(result, "生成关于{category}的选题，数量：{count}")
    
    def test_extract_tags(self):
        """测试提取标签"""
        text = "这是一篇关于#美妆和#护肤的笔记，还有#推荐产品"
        
        tags = extract_tags(text)
        self.assertEqual(len(tags), 3)
        self.assertIn("#美妆", tags)
        self.assertIn("#护肤", tags)
        self.assertIn("#推荐产品", tags)
    
    def test_extract_keywords(self):
        """测试提取关键词"""
        text = "这是一篇关于美妆和护肤的笔记，推荐使用保湿面霜"
        
        keywords = extract_keywords(text, count=3)
        self.assertEqual(len(keywords), 3)
        self.assertIn("美妆", keywords)
        self.assertIn("护肤", keywords)
        self.assertIn("保湿面霜", keywords)
    
    def test_generate_uuid(self):
        """测试生成UUID"""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        
        # 验证UUID格式
        self.assertEqual(len(uuid1), 36)
        self.assertEqual(len(uuid2), 36)
        
        # 验证唯一性
        self.assertNotEqual(uuid1, uuid2)
    
    def test_ensure_dir_exists(self):
        """测试确保目录存在"""
        # 测试创建新目录
        new_dir = os.path.join(self.temp_dir, "new_dir", "sub_dir")
        ensure_dir_exists(new_dir)
        self.assertTrue(os.path.exists(new_dir))
        
        # 测试已存在的目录
        ensure_dir_exists(self.temp_dir)
        self.assertTrue(os.path.exists(self.temp_dir))
    
    @patch('src.utils.utils.Image')
    def test_resize_image(self, mock_image_class):
        """测试调整图片大小"""
        # 模拟PIL Image
        mock_image = Mock()
        mock_image_class.open.return_value = mock_image
        
        # 调用方法
        input_path = os.path.join(self.temp_dir, "input.jpg")
        output_path = os.path.join(self.temp_dir, "output.jpg")
        resize_image(input_path, output_path, (300, 300))
        
        # 验证调用
        mock_image_class.open.assert_called_once_with(input_path)
        mock_image.resize.assert_called_once_with((300, 300))
        mock_image.save.assert_called_once_with(output_path)
    
    @patch('src.utils.utils.Image')
    def test_crop_image(self, mock_image_class):
        """测试裁剪图片"""
        # 模拟PIL Image
        mock_image = Mock()
        mock_image_class.open.return_value = mock_image
        
        # 调用方法
        input_path = os.path.join(self.temp_dir, "input.jpg")
        output_path = os.path.join(self.temp_dir, "output.jpg")
        crop_image(input_path, output_path, (100, 100, 400, 400))
        
        # 验证调用
        mock_image_class.open.assert_called_once_with(input_path)
        mock_image.crop.assert_called_once_with((100, 100, 400, 400))
        mock_image.save.assert_called_once_with(output_path)
    
    @patch('src.utils.utils.requests.get')
    def test_download_image(self, mock_get):
        """测试下载图片"""
        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake_image_data"
        mock_get.return_value = mock_response
        
        # 调用方法
        url = "https://example.com/image.jpg"
        output_path = os.path.join(self.temp_dir, "downloaded.jpg")
        result = download_image(url, output_path)
        
        # 验证结果
        self.assertEqual(result, output_path)
        self.assertTrue(os.path.exists(output_path))
        
        # 验证文件内容
        with open(output_path, 'rb') as f:
            content = f.read()
        self.assertEqual(content, b"fake_image_data")
        
        # 验证HTTP调用
        mock_get.assert_called_once_with(url, stream=True)


if __name__ == "__main__":
    unittest.main()