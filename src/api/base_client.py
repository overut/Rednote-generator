"""
API客户端基类
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """API客户端基类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化API客户端
        
        Args:
            config: API配置
        """
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', '')
        self.model = config.get('model', '')
        self.max_retries = config.get('max_retries', 3)
        self.timeout = config.get('timeout', 30)
        
        # 创建会话
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = await self._get_headers()
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
        return self.session
    
    async def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    async def close(self) -> None:
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """
        生成响应，子类需要实现
        
        Args:
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            生成的响应文本
        """
        pass
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _make_request(self, url: str, method: str = "POST", 
                           data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        发起HTTP请求
        
        Args:
            url: 请求URL
            method: 请求方法
            data: 请求数据
            params: 查询参数
            
        Returns:
            响应数据
        """
        session = await self._get_session()
        
        try:
            async with session.request(method, url, json=data, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API请求失败: {response.status}, {error_text}")
                    raise Exception(f"API请求失败: {response.status}, {error_text}")
        except aiohttp.ClientError as e:
            logger.error(f"网络请求错误: {e}")
            raise Exception(f"网络请求错误: {e}")
    
    def __del__(self):
        """析构函数，确保会话被关闭"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            # 不能在析构函数中使用await，所以创建一个任务
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.create_task(self.close())


class ImageGenerationClient(BaseAPIClient):
    """图片生成API客户端基类"""
    
    @abstractmethod
    async def generate_image(self, prompt: str, **kwargs) -> bytes:
        """
        生成图片，子类需要实现
        
        Args:
            prompt: 图片描述提示词
            **kwargs: 其他参数
            
        Returns:
            图片二进制数据
        """
        pass
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _download_image(self, url: str) -> bytes:
        """
        下载图片
        
        Args:
            url: 图片URL
            
        Returns:
            图片二进制数据
        """
        session = await self._get_session()
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    logger.error(f"图片下载失败: {response.status}, {error_text}")
                    raise Exception(f"图片下载失败: {response.status}, {error_text}")
        except aiohttp.ClientError as e:
            logger.error(f"图片下载网络错误: {e}")
            raise Exception(f"图片下载网络错误: {e}")