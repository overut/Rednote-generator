"""
图片生成器实现
"""

import logging
import os
import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from ..config import ConfigManager
from ..api import JimengAPIClient, TongyiAPIClient


logger = logging.getLogger(__name__)


@dataclass
class ImageResult:
    """图片生成结果数据类"""
    image_path: str
    image_url: Optional[str] = None
    prompt: Optional[str] = None
    provider: Optional[str] = None


class ImageGenerator:
    """图片生成器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化图片生成器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.api_client = None
    
    async def _get_api_client(self, provider: str):
        """
        获取API客户端
        
        Args:
            provider: API提供商，支持"jimeng"和"tongyi"
            
        Returns:
            API客户端实例
        """
        if provider == "jimeng":
            config = self.config_manager.get_api_config("jimeng")
            return JimengAPIClient(config)
        elif provider == "tongyi":
            config = self.config_manager.get_api_config("tongyi")
            return TongyiAPIClient(config)
        else:
            raise ValueError(f"不支持的API提供商: {provider}")
    
    async def generate_image(self, title: str, prompt: str, provider: str = "jimeng", **kwargs) -> ImageResult:
        """
        根据提示词生成图片
        
        Args:
            title: 图片标题
            prompt: 图片描述提示词
            provider: API提供商
            **kwargs: 其他参数，如width, height等
            
        Returns:
            图片生成结果
        """
        api_client = None
        try:
            # 获取API客户端
            api_client = await self._get_api_client(provider)
            
            # 构建图片提示词
            image_prompt = self._build_image_prompt(title, prompt)
            
            # 设置默认参数，如果kwargs中已有则使用kwargs中的值
            if "width" not in kwargs:
                kwargs["width"] = 1080
            if "height" not in kwargs:
                kwargs["height"] = 1920  # 竖屏比例 9:16，兼容即梦4.0版本API
            
            # 调用API生成图片
            image_data = await api_client.generate_image(
                prompt=image_prompt,
                **kwargs
            )
            
            # 保存图片到本地
            image_path = await self._save_image(image_data, provider)
            
            # 返回结果
            result = ImageResult(
                image_path=image_path,
                prompt=image_prompt,
                provider=provider
            )
            
            return result
            
        except Exception as e:
            logger.error(f"生成图片失败: {e}")
            raise Exception(f"生成图片失败: {e}")
        finally:
            if api_client:
                await api_client.close()
    
    def _build_image_prompt(self, title: str, base_prompt: str) -> str:
        """
        构建图片提示词
        
        Args:
            base_prompt: 基础提示词
            
        Returns:
            完整的图片提示词
        """
        # 获取基础提示词模板
        prompt_template = self.config_manager.get_prompt_config("image_generation")
        
        # 如果没有配置提示词，使用默认提示词
        if not prompt_template:
            prompt_template = "{prompt}, 小红书风格, 高质量, 精美细节, 9:16竖屏比例"
        
        # 替换占位符，支持{topic}和{prompt}两种格式
        try:
            # 尝试使用{topic}占位符
            image_prompt = prompt_template.format(title=title, topic=base_prompt)
        except KeyError:
            try:
                # 尝试使用{prompt}占位符
                image_prompt = prompt_template.format(prompt=base_prompt)
            except KeyError:
                # 如果都没有，直接使用基础提示词
                image_prompt = f"{base_prompt}, 小红书风格, 高质量, 精美细节, 9:16竖屏比例"
        
        return image_prompt
    
    async def _save_image(self, image_data: bytes, provider: str) -> str:
        """
        保存图片到本地
        
        Args:
            image_data: 图片二进制数据
            provider: API提供商
            
        Returns:
            图片保存路径
        """
        # 确保输出目录存在
        output_dir = self.config_manager.get_output_config("image_dir")
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成唯一文件名
        filename = f"{provider}_{uuid.uuid4().hex[:8]}.jpg"
        image_path = os.path.join(output_dir, filename)
        
        # 保存图片
        with open(image_path, "wb") as f:
            f.write(image_data)
        
        logger.info(f"图片已保存到: {image_path}")
        
        return image_path
    
    async def generate_multiple_images(self, prompts: List[str], provider: str = "jimeng", **kwargs) -> List[ImageResult]:
        """
        根据多个提示词生成多张图片
        
        Args:
            prompts: 图片描述提示词列表
            provider: API提供商
            **kwargs: 其他参数
            
        Returns:
            图片生成结果列表
        """
        results = []
        
        for prompt in prompts:
            try:
                result = await self.generate_image(prompt, provider, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"生成图片失败: {prompt}, 错误: {e}")
                # 继续处理其他提示词
                continue
        
        return results