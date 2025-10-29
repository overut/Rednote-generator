"""
通义万象API客户端实现
"""

import json
import logging
import base64
from typing import Dict, Any, Optional
from .base_client import ImageGenerationClient


logger = logging.getLogger(__name__)


class TongyiAPIClient(ImageGenerationClient):
    """通义万象API客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化通义万象API客户端
        
        Args:
            config: API配置
        """
        super().__init__(config)
        self.image_url = f"{self.base_url}/services/aigc/text2image/image-synthesis"
    
    async def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-DashScope-Async": "enable"  # 启用异步模式
        }
    
    async def generate_image(self, prompt: str, **kwargs) -> bytes:
        """
        调用通义万象API生成图片
        
        Args:
            prompt: 图片描述提示词
            **kwargs: 其他参数，如width, height等
            
        Returns:
            图片二进制数据
        """
        # 构建请求数据
        data = {
            "model": self.model,
            "input": {
                "prompt": prompt,
                "style": kwargs.get("style", "<auto>"),
                "size": kwargs.get("size", "\"720*1280\""),  # 竖屏比例 9:16
                "n": kwargs.get("n", 1),
                "seed": kwargs.get("seed", -1)
            },
            "parameters": {
                "seed": kwargs.get("seed", -1)
            }
        }
        
        # 发送请求
        response = await self._make_request(self.image_url, "POST", data)
        
        # 解析响应
        if "output" in response and "task_id" in response["output"]:
            # 获取任务ID
            task_id = response["output"]["task_id"]
            
            # 查询任务结果
            result_url = await self._get_task_result(task_id)
            
            # 下载图片
            return await self._download_image(result_url)
        else:
            logger.error(f"通义万象API响应格式错误: {response}")
            raise Exception("通义万象API响应格式错误")
    
    async def _get_task_result(self, task_id: str) -> str:
        """
        获取异步任务结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            图片URL
        """
        import asyncio
        
        # 构建查询请求
        result_url = f"{self.base_url}/tasks/{task_id}"
        
        # 轮询任务状态
        max_attempts = 30  # 最多轮询30次
        for _ in range(max_attempts):
            response = await self._make_request(result_url, "GET")
            
            if "output" in response and "task_status" in response["output"]:
                task_status = response["output"]["task_status"]
                
                if task_status == "SUCCEEDED":
                    # 任务成功，返回图片URL
                    if "results" in response["output"] and len(response["output"]["results"]) > 0:
                        return response["output"]["results"][0]["url"]
                    else:
                        logger.error(f"通义万象API任务成功但缺少图片URL: {response}")
                        raise Exception("通义万象API任务成功但缺少图片URL")
                elif task_status == "FAILED":
                    # 任务失败
                    logger.error(f"通义万象API图片生成任务失败: {response}")
                    raise Exception("通义万象API图片生成任务失败")
                elif task_status in ["PENDING", "RUNNING"]:
                    # 任务仍在进行中，等待后重试
                    await asyncio.sleep(2)
                else:
                    # 未知状态
                    logger.error(f"通义万象API任务状态未知: {task_status}")
                    raise Exception(f"通义万象API任务状态未知: {task_status}")
            else:
                logger.error(f"通义万象API任务状态查询响应格式错误: {response}")
                raise Exception("通义万象API任务状态查询响应格式错误")
        
        # 超时
        logger.error("通义万象API图片生成任务超时")
        raise Exception("通义万象API图片生成任务超时")