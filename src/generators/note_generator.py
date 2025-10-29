"""
笔记生成器实现
"""

import logging
import os
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from ..config import ConfigManager
from .topic_generator import TopicGenerator, Topic
from .content_generator import ContentGenerator, Content
from .image_generator import ImageGenerator, ImageResult


logger = logging.getLogger(__name__)


@dataclass
class NoteResult:
    """笔记生成结果数据类"""
    id: str
    title: str
    content: str
    hashtags: List[str]
    call_to_action: str
    images: List[ImageResult]
    created_at: str
    topic: str
    category: str
    metadata: Dict[str, Any]


class NoteGenerator:
    """笔记生成器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化笔记生成器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.topic_generator = TopicGenerator(config_manager)
        self.content_generator = ContentGenerator(config_manager)
        self.image_generator = ImageGenerator(config_manager)
    
    async def generate_note(
        self,
        topic: str = None,
        category: str = "生活分享",
        style: str = "生活分享",
        content_provider: str = "deepseek",
        image_provider: str = "jimeng",
        image_count: int = 1,
        custom_image_prompts: List[str] = None
    ) -> NoteResult:
        """
        生成完整的小红书笔记
        
        Args:
            topic: 指定选题，如果为None则自动生成
            category: 选题类别
            style: 文案风格
            content_provider: 文案API提供商
            image_provider: 图片API提供商
            image_count: 图片数量
            custom_image_prompts: 自定义图片提示词列表
            
        Returns:
            笔记生成结果
        """
        try:
            # 1. 生成或使用指定选题
            if not topic:
                topics = await self.topic_generator.generate_topics(category, count=1)
                if not topics:
                    raise Exception("无法生成选题")
                topic_obj = topics[0]
                topic = topic_obj.title
            else:
                topic_obj = Topic(title=topic, description="", category=category, tags=[])
            
            logger.info(f"使用选题: {topic}")
            
            # 2. 生成文案
            content = await self.content_generator.generate_content(topic, style, content_provider)
            logger.info(f"生成文案: {content.title}")
            
            # 3. 生成图片
            images = []
            if custom_image_prompts:
                # 使用自定义图片提示词
                for prompt in custom_image_prompts[:image_count]:
                    try:
                        image_result = await self.image_generator.generate_image(prompt, image_provider)
                        images.append(image_result)
                    except Exception as e:
                        logger.error(f"生成图片失败: {prompt}, 错误: {e}")
            else:
                # 根据内容自动生成图片提示词
                image_prompts = self._generate_image_prompts(content, image_count)
                for prompt in image_prompts:
                    try:
                        image_result = await self.image_generator.generate_image(prompt, image_provider)
                        images.append(image_result)
                    except Exception as e:
                        logger.error(f"生成图片失败: {prompt}, 错误: {e}")
            
            logger.info(f"生成图片数量: {len(images)}")
            
            # 4. 创建笔记结果
            note_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            
            note_result = NoteResult(
                id=note_id,
                title=content.title,
                content=content.body,
                hashtags=content.hashtags,
                call_to_action=content.call_to_action,
                images=images,
                created_at=created_at,
                topic=topic,
                category=category,
                metadata={
                    "style": style,
                    "content_provider": content_provider,
                    "image_provider": image_provider,
                    "topic_obj": asdict(topic_obj) if topic_obj else None
                }
            )
            
            # 5. 保存笔记到本地
            await self._save_note(note_result)
            
            return note_result
            
        except Exception as e:
            logger.error(f"生成笔记失败: {e}")
            raise Exception(f"生成笔记失败: {e}")
    
    def _generate_image_prompts(self, content: Content, count: int) -> List[str]:
        """
        根据文案内容生成图片提示词
        
        Args:
            content: 文案内容
            count: 图片数量
            
        Returns:
            图片提示词列表
        """
        # 简单的提示词生成逻辑，实际项目中可以使用更复杂的NLP技术
        prompts = []
        
        # 从标题中提取关键词
        title_words = content.title.split()
        if title_words:
            prompts.append(f"{title_words[0]}相关场景")
        
        # 从正文中提取关键词
        body_words = content.body.split()
        if len(body_words) > 5:
            prompts.append(f"{body_words[0]} {body_words[1]} {body_words[2]}")
        
        # 如果提示词不够，添加一些通用提示词
        while len(prompts) < count:
            generic_prompts = [
                "小红书风格精美图片",
                "生活场景高清图片",
                "时尚生活方式图片"
            ]
            prompts.append(generic_prompts[len(prompts) % len(generic_prompts)])
        
        return prompts[:count]
    
    async def _save_note(self, note: NoteResult) -> None:
        """
        保存笔记到本地
        
        Args:
            note: 笔记结果
        """
        # 确保输出目录存在
        output_dir = self.config_manager.get_output_config("content_dir")
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        filename = f"{note.id[:8]}_{note.title.replace(' ', '_')}.json"
        file_path = os.path.join(output_dir, filename)
        
        # 准备保存的数据
        note_data = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "hashtags": note.hashtags,
            "call_to_action": note.call_to_action,
            "images": [
                {
                    "path": img.image_path,
                    "provider": img.provider,
                    "prompt": img.prompt
                }
                for img in note.images
            ],
            "created_at": note.created_at,
            "topic": note.topic,
            "category": note.category,
            "metadata": note.metadata
        }
        
        # 保存到JSON文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(note_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"笔记已保存到: {file_path}")
    
    async def batch_generate_notes(
        self,
        count: int,
        category: str = "生活分享",
        style: str = "生活分享",
        content_provider: str = "deepseek",
        image_provider: str = "jimeng",
        image_count: int = 1
    ) -> List[NoteResult]:
        """
        批量生成笔记
        
        Args:
            count: 笔记数量
            category: 选题类别
            style: 文案风格
            content_provider: 文案API提供商
            image_provider: 图片API提供商
            image_count: 每篇笔记的图片数量
            
        Returns:
            笔记生成结果列表
        """
        results = []
        
        # 先生成一批选题
        topics = await self.topic_generator.generate_topics(category, count)
        
        for i, topic in enumerate(topics):
            try:
                logger.info(f"生成第 {i+1}/{count} 篇笔记: {topic.title}")
                note = await self.generate_note(
                    topic=topic.title,
                    category=category,
                    style=style,
                    content_provider=content_provider,
                    image_provider=image_provider,
                    image_count=image_count
                )
                results.append(note)
            except Exception as e:
                logger.error(f"生成笔记失败: {topic.title}, 错误: {e}")
                # 继续处理其他笔记
                continue
        
        return results