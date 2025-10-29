"""
选题生成器实现
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from ..config import ConfigManager
from ..api import DeepseekAPIClient


logger = logging.getLogger(__name__)


@dataclass
class Topic:
    """选题数据类"""
    title: str
    description: str
    category: str
    tags: List[str]


class TopicGenerator:
    """选题生成器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化选题生成器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.api_client = None
    
    async def _get_api_client(self) -> DeepseekAPIClient:
        """获取API客户端"""
        if self.api_client is None:
            config = self.config_manager.get_api_config("deepseek")
            self.api_client = DeepseekAPIClient(config)
        return self.api_client
    
    async def generate_topics(self, category: str = None, count: int = 5) -> List[Topic]:
        """
        生成选题列表
        
        Args:
            category: 选题类别
            count: 选题数量
            
        Returns:
            选题列表
        """
        try:
            logger.info(f"开始生成选题，类别: {category}, 数量: {count}")
            
            # 获取API客户端
            api_client = await self._get_api_client()
            logger.info(f"已获取API客户端: {type(api_client).__name__}")
            
            # 如果没有指定类别，使用默认类别
            if not category:
                category = "生活分享"
                logger.info(f"使用默认类别: {category}")
            
            # 构建提示词
            prompt = self._build_topic_prompt(category, count)
            logger.info(f"构建的提示词: {prompt}")
            
            # 调用API生成选题
            topics_data = await api_client.generate_topics(category, count)
            logger.info(f"API返回的选题数据: {topics_data}")
            
            # 转换为Topic对象
            topics = []
            for topic_data in topics_data:
                logger.info(f"处理选题数据: {topic_data}")
                topic = Topic(
                    title=topic_data.get("title", ""),
                    description=topic_data.get("description", ""),
                    category=category,
                    tags=self._extract_tags(topic_data)
                )
                topics.append(topic)
                logger.info(f"创建的Topic对象: {topic}")
            
            logger.info(f"最终生成的选题数量: {len(topics)}")
            return topics
            
        except Exception as e:
            logger.error(f"生成选题失败: {e}")
            raise Exception(f"生成选题失败: {e}")
        finally:
            if self.api_client:
                await self.api_client.close()
                logger.info("已关闭API客户端")
    
    def _build_topic_prompt(self, category: str, count: int = 5) -> str:
        """
        构建选题提示词
        
        Args:
            category: 选题类别
            count: 选题数量
            
        Returns:
            提示词字符串
        """
        # 获取基础提示词模板
        base_prompt = self.config_manager.get_prompt_config("topic_generation")
        
        # 如果没有配置提示词，使用默认提示词
        if not base_prompt:
            base_prompt = "请为小红书平台生成{count}个关于{category}的热门选题，每个选题包括标题和简短描述，格式如下：\n1. 标题：xxx\n描述：xxx\n2. 标题：xxx\n描述：xxx\n..."
        
        # 替换占位符
        prompt = base_prompt.format(category=category, count=count)
        
        return prompt
    
    def _extract_tags(self, topic_data: Dict[str, str]) -> List[str]:
        """
        从选题数据中提取标签
        
        Args:
            topic_data: 选题数据
            
        Returns:
            标签列表
        """
        # 这里可以实现更复杂的标签提取逻辑
        # 目前简单返回一些默认标签
        tags = ["小红书", "分享"]
        
        # 从标题和描述中提取关键词作为标签
        title = topic_data.get("title", "")
        description = topic_data.get("description", "")
        
        # 简单的关键词提取（实际项目中可以使用更复杂的NLP技术）
        text = f"{title} {description}"
        common_words = ["美食", "旅行", "穿搭", "美妆", "生活", "家居", "健身", "学习", "职场", "情感"]
        
        for word in common_words:
            if word in text and word not in tags:
                tags.append(word)
        
        return tags[:5]  # 最多返回5个标签