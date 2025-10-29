"""
测试配置管理器
"""

import unittest
import os
import tempfile
import shutil
import yaml

from src.config.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """配置管理器测试类"""
    
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
                },
                "jimeng": {
                    "base_url": "https://jimeng.jianying.com/api/v1",
                    "api_key": "test_key",
                    "model": "jimeng-v1"
                }
            },
            "prompts": {
                "topic_generation": "生成关于{category}的选题",
                "content_generation": "为{topic}写文案"
            },
            "output": {
                "image_dir": "output/images",
                "content_dir": "output/content"
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
        config_manager = ConfigManager(self.config_file)
        
        # 测试获取API配置
        deepseek_config = config_manager.get_api_config("deepseek")
        self.assertEqual(deepseek_config["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(deepseek_config["api_key"], "test_key")
        self.assertEqual(deepseek_config["model"], "deepseek-chat")
        
        # 测试获取提示词配置
        topic_prompt = config_manager.get_prompt_config("topic_generation")
        self.assertEqual(topic_prompt, "生成关于{category}的选题")
        
        # 测试获取输出配置
        image_dir = config_manager.get_output_config("image_dir")
        self.assertEqual(image_dir, "output/images")
    
    def test_update_config(self):
        """测试更新配置"""
        config_manager = ConfigManager(self.config_file)
        
        # 更新API配置
        config_manager.update_api_config("deepseek", {"api_key": "new_key"})
        deepseek_config = config_manager.get_api_config("deepseek")
        self.assertEqual(deepseek_config["api_key"], "new_key")
        
        # 更新提示词配置
        config_manager.update_prompt_config("content_generation", "新提示词")
        content_prompt = config_manager.get_prompt_config("content_generation")
        self.assertEqual(content_prompt, "新提示词")
    
    def test_save_config(self):
        """测试保存配置"""
        config_manager = ConfigManager(self.config_file)
        
        # 更新配置
        config_manager.update_api_config("deepseek", {"api_key": "saved_key"})
        
        # 保存配置
        config_manager.save_config()
        
        # 重新加载配置
        new_config_manager = ConfigManager(self.config_file)
        deepseek_config = new_config_manager.get_api_config("deepseek")
        self.assertEqual(deepseek_config["api_key"], "saved_key")


if __name__ == "__main__":
    unittest.main()