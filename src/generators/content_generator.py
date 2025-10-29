"""
文案生成器实现
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from ..config import ConfigManager
from ..api import DeepseekAPIClient, DoubaoAPIClient


logger = logging.getLogger(__name__)


@dataclass
class Content:
    """文案数据类"""
    title: str
    body: str
    hashtags: List[str]
    call_to_action: str


class ContentGenerator:
    """文案生成器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化文案生成器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.api_client = None
    
    async def _get_api_client(self, provider: str = "deepseek"):
        """
        获取API客户端
        
        Args:
            provider: API提供商，支持"deepseek"和"doubao"
            
        Returns:
            API客户端实例
        """
        if provider == "deepseek":
            config = self.config_manager.get_api_config("deepseek")
            return DeepseekAPIClient(config)
        elif provider == "doubao":
            config = self.config_manager.get_api_config("doubao")
            return DoubaoAPIClient(config)
        else:
            raise ValueError(f"不支持的API提供商: {provider}")
    
    async def generate_content(self, topic: str, style: str = "生活分享", provider: str = "deepseek") -> Content:
        """
        根据选题生成文案
        
        Args:
            topic: 选题
            style: 文案风格
            provider: API提供商
            
        Returns:
            生成的文案
        """
        try:
            # 获取API客户端
            api_client = await self._get_api_client(provider)
            
            # 构建提示词
            prompt = self._build_content_prompt(topic, style)
            
            # 调用API生成响应
            response = await api_client.generate_response(prompt)
            
            # 解析响应为内容数据
            content_data = self._parse_content_response(response)
            
            # 转换为Content对象
            content = Content(
                title=content_data.get("title", ""),
                body=content_data.get("body", ""),
                hashtags=self._extract_hashtags(content_data),
                call_to_action=content_data.get("call_to_action", "")
            )
            
            return content
            
        except Exception as e:
            logger.error(f"生成文案失败: {e}")
            raise Exception(f"生成文案失败: {e}")
        finally:
            if api_client:
                await api_client.close()
    
    def _parse_content_response(self, response: str) -> Dict[str, Any]:
        """
        解析API响应为内容数据
        
        Args:
            response: API响应文本
            
        Returns:
            解析后的内容数据
        """
        result = {
            "title": "",
            "body": "",
            "hashtags": [],
            "call_to_action": ""
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # 检测标题部分
            if '标题' in line and ('：' in line or ':' in line):
                # 提取标题内容
                if '：' in line:
                    title = line.split('：', 1)[1].strip()
                else:
                    title = line.split(':', 1)[1].strip()
                if title:
                    result["title"] = title
                current_section = "body"
                continue
            
            # 检测正文部分
            elif '正文' in line or '内容' in line:
                if '：' in line:
                    body = line.split('：', 1)[1].strip()
                else:
                    body = line.split(':', 1)[1].strip()
                if body:
                    result["body"] = body
                current_section = "body"
                continue
            
            # 检测标签部分
            elif '标签' in line or '话题' in line:
                if '：' in line:
                    tags = line.split('：', 1)[1].strip()
                else:
                    tags = line.split(':', 1)[1].strip()
                if tags:
                    result["hashtags"] = [tag.strip() for tag in tags.replace("#", "").split() if tag.strip()]
                current_section = "tags"
                continue
            
            # 根据当前部分处理内容
            if current_section == "body" and line:
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
                    result["hashtags"].append(tag)
        
        # 如果没有解析出标题，尝试其他方法
        if not result["title"]:
            # 尝试从响应中提取可能的标题
            import re
            title_pattern = r'["""]([^"""]+)["""]'
            matches = re.findall(title_pattern, response)
            if matches:
                result["title"] = matches[0]
        
        # 如果没有解析出标签，尝试其他方法
        if not result["hashtags"]:
            # 尝试从响应中提取可能的标签
            import re
            tag_pattern = r'#(\w+)'
            matches = re.findall(tag_pattern, response)
            if matches:
                result["hashtags"] = [f"#{tag}" for tag in matches]
        
        # 如果没有正文内容，使用整个响应
        if not result["body"]:
            result["body"] = response
        
        return result
    
    def _build_content_prompt(self, topic: str, style: str) -> str:
        """
        构建文案提示词
        
        Args:
            topic: 选题
            style: 文案风格
            
        Returns:
            提示词字符串
        """
        # 获取基础提示词模板
        base_prompt = self.config_manager.get_prompt_config("content_generation")
        
        # 如果没有配置提示词，使用默认提示词
        if not base_prompt:
            base_prompt = "请为小红书平台写一篇关于'{topic}'的文案，风格为'{style}'。文案应包含吸引人的标题、正文内容和相关话题标签。格式如下：\n标题：xxx\n正文：xxx\n话题标签：#xxx #xxx #xxx"
        
        # 替换占位符
        prompt = base_prompt.format(topic=topic, style=style)
        
        return prompt
    
    def _extract_hashtags(self, content_data: Dict[str, str]) -> List[str]:
        """
        从文案数据中提取话题标签
        
        Args:
            content_data: 文案数据
            
        Returns:
            话题标签列表
        """
        # 如果数据中已经有hashtags字段，直接返回
        if "hashtags" in content_data and content_data["hashtags"]:
            hashtags = content_data["hashtags"]
            if isinstance(hashtags, str):
                # 如果是字符串，按空格或逗号分割
                return [tag.strip() for tag in hashtags.replace("#", "").replace(",", " ").split() if tag.strip()]
            elif isinstance(hashtags, list):
                # 如果是列表，直接返回
                return hashtags
        
        # 否则从正文中提取
        body = content_data.get("body", "")
        hashtags = []
        
        # 简单的话题标签提取（查找#开头的词）
        import re
        matches = re.findall(r"#([^\s#]+)", body)
        hashtags = [f"#{tag}" for tag in matches]
        
        # 如果没有找到标签，添加一些默认标签
        if not hashtags:
            hashtags = ["#小红书", "#分享"]
        
        return hashtags[:5]  # 最多返回5个标签