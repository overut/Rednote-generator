"""
配置管理器实现
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """配置管理器，负责读取和管理系统配置"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self._config = {}
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._config = yaml.safe_load(file) or {}
        except FileNotFoundError:
            print(f"配置文件 {self.config_path} 不存在，将使用默认配置")
            self._config = self._get_default_config()
            self.save_config()
        except yaml.YAMLError as e:
            print(f"配置文件格式错误: {e}")
            self._config = self._get_default_config()
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取完整配置
        
        Returns:
            配置字典
        """
        return self._config
    
    def get_api_config(self, api_name: str) -> Dict[str, Any]:
        """
        获取特定API配置
        
        Args:
            api_name: API名称
            
        Returns:
            API配置字典
        """
        return self._config.get('api', {}).get(api_name, {})
    
    def get_prompt_config(self, prompt_name: str) -> str:
        """
        获取特定提示词配置
        
        Args:
            prompt_name: 提示词名称
            
        Returns:
            提示词字符串
        """
        return self._config.get('prompts', {}).get(prompt_name, "")
    
    def get_output_config(self, key: str = None) -> Dict[str, Any]:
        """
        获取输出配置
        
        Args:
            key: 可选，获取特定配置项
            
        Returns:
            输出配置字典或特定配置项
        """
        output_config = self._config.get('output', {})
        if key:
            return output_config.get(key)
        return output_config
    
    def get_ui_config(self) -> Dict[str, Any]:
        """
        获取UI配置
        
        Returns:
            UI配置字典
        """
        return self._config.get('ui', {})
    
    def get_generation_config(self) -> Dict[str, Any]:
        """
        获取生成配置
        
        Returns:
            生成配置字典
        """
        return self._config.get('generation', {})
    
    def update_config(self, section: str, key: str, value: Any) -> None:
        """
        更新配置
        
        Args:
            section: 配置节名
            key: 配置键
            value: 配置值
        """
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
    
    def save_config(self) -> None:
        """保存配置到文件"""
        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as file:
            yaml.dump(self._config, file, default_flow_style=False, allow_unicode=True)
    
    def ensure_output_dirs(self) -> None:
        """确保输出目录存在"""
        output_config = self.get_output_config()
        for dir_key in ['image_dir', 'content_dir', 'log_dir']:
            dir_path = output_config.get(dir_key)
            if dir_path:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'apis': {
                'deepseek': {
                    'api_key': '',
                    'base_url': 'https://api.deepseek.com',
                    'model': 'deepseek-chat'
                },
                'doubao': {
                    'api_key': '',
                    'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
                    'model': 'doubao-pro-4k'
                },
                'jimeng': {
                    'api_key': '',
                    'base_url': 'https://jimeng.jianying.com'
                },
                'tongyi': {
                    'api_key': '',
                    'base_url': 'https://dashscope.aliyuncs.com/api/v1',
                    'model': 'wanx-v1'
                }
            },
            'prompts': {
                'topic_generation': '请为小红书平台生成5个关于{category}的热门选题...',
                'content_generation': '根据以下选题：{topic}，生成小红书笔记内容...',
                'image_generation': '根据以下标题：{title}和内容：{content}，生成小红书风格图片...'
            },
            'output': {
                'image_dir': './output/images',
                'content_dir': './output/content',
                'log_dir': './logs'
            },
            'ui': {
                'theme': 'light',
                'language': 'zh-CN',
                'page_title': '小红书笔记生成器',
                'page_icon': '✍️'
            },
            'generation': {
                'default_topic_count': 5,
                'default_image_count': 3,
                'max_retries': 3,
                'timeout': 30
            }
        }