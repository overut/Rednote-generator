"""
豆包API客户端实现
"""

import json
import logging
from typing import Dict, Any, List, Optional
from .base_client import BaseAPIClient


logger = logging.getLogger(__name__)


class DoubaoAPIClient(BaseAPIClient):
    """豆包API客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化豆包API客户端
        
        Args:
            config: API配置
        """
        super().__init__(config)
        self.chat_url = f"{self.base_url}/chat/completions"
    
    async def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """
        调用豆包API生成响应
        
        Args:
            prompt: 提示词
            **kwargs: 其他参数，如temperature, max_tokens等
            
        Returns:
            生成的响应文本
        """
        # 构建请求数据
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个专业的小红书内容创作助手，擅长创作吸引人的小红书笔记内容。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
            "top_p": kwargs.get("top_p", 0.95),
            "stream": False
        }
        
        # 发送请求
        response = await self._make_request(self.chat_url, "POST", data)
        
        # 解析响应
        if "choices" in response and len(response["choices"]) > 0:
            return response["choices"][0]["message"]["content"]
        else:
            logger.error(f"豆包API响应格式错误: {response}")
            raise Exception("豆包API响应格式错误")
    
    async def generate_content(self, topic: Dict[str, str], **kwargs) -> Dict[str, Any]:
        """
        生成文案内容
        
        Args:
            topic: 选题信息，包含title和description
            **kwargs: 其他参数
            
        Returns:
            生成的文案内容，包含titles, body, tags
        """
        topic_text = f"标题：{topic.get('title', '')}\n描述：{topic.get('description', '')}"
        prompt = f"根据以下选题：'{topic_text}'，生成小红书笔记内容，包括：\n1. 3-5个吸引人的标题选项\n2. 符合小红书风格的正文内容（包含emoji、分段、互动引导等）\n3. 相关标签建议（5-8个）\n\n请确保内容原创、有价值，符合小红书平台调性。"
        
        response = await self.generate_response(prompt, **kwargs)
        
        # 解析响应
        result = {
            "titles": [],
            "body": "",
            "tags": []
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # 检测标题部分
            if '标题' in line and ('选项' in line or ':' in line):
                current_section = "titles"
                continue
            # 检测正文部分
            elif '正文' in line or '内容' in line:
                current_section = "body"
                continue
            # 检测标签部分
            elif '标签' in line:
                current_section = "tags"
                continue
            
            # 根据当前部分处理内容
            if current_section == "titles" and line:
                # 提取标题（可能以数字、符号开头）
                title = line
                # 移除可能的序号前缀
                if title and (title[0].isdigit() or title[0] in ['-', '•', '*', '·']):
                    parts = title.split(' ', 1)
                    if len(parts) > 1:
                        title = parts[1]
                if title:
                    result["titles"].append(title)
            elif current_section == "body" and line:
                # 收集正文内容
                if result["body"]:
                    result["body"] += "\n"
                result["body"] += line
            elif current_section == "tags" and line:
                # 提取标签（可能以#开头）
                tag = line
                if tag.startswith('#'):
                    tag = tag[1:].strip()
                if tag:
                    result["tags"].append(tag)
        
        # 如果没有解析出标题，尝试其他方法
        if not result["titles"]:
            # 尝试从响应中提取可能的标题
            import re
            title_pattern = r'["""]([^"""]+)["""]'
            matches = re.findall(title_pattern, response)
            if matches:
                result["titles"] = matches[:5]
        
        # 如果没有解析出标签，尝试其他方法
        if not result["tags"]:
            # 尝试从响应中提取可能的标签
            import re
            tag_pattern = r'#(\w+)'
            matches = re.findall(tag_pattern, response)
            if matches:
                result["tags"] = matches
        
        # 确保至少有一个标题
        if not result["titles"] and topic.get("title"):
            result["titles"] = [topic["title"]]
        
        # 确保有正文内容
        if not result["body"]:
            result["body"] = response
        
        # 确保有标签
        if not result["tags"]:
            result["tags"] = ["小红书", "笔记", "分享"]
        
        return result