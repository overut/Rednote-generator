"""
Streamlit用户界面实现
"""

import streamlit as st
import os
import sys
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from PIL import Image

# 添加项目根目录到系统路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.config import ConfigManager
from src.generators import TopicGenerator, ContentGenerator, ImageGenerator, NoteGenerator


class StreamlitUI:
    """Streamlit用户界面"""
    
    def __init__(self):
        """初始化Streamlit用户界面"""
        self.config_manager = ConfigManager()
        self.note_generator = NoteGenerator(self.config_manager)
        self.topic_generator = TopicGenerator(self.config_manager)
        self.content_generator = ContentGenerator(self.config_manager)
        self.image_generator = ImageGenerator(self.config_manager)
    
    def run(self):
        """运行Streamlit应用"""
        st.set_page_config(
            page_title="小红书笔记生成器",
            page_icon="📝",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("📝 小红书笔记生成器")
        st.markdown("---")
        
        # 侧边栏配置
        self._render_sidebar()
        
        # 主界面
        tab1, tab2, tab3, tab4 = st.tabs(["单篇生成", "批量生成", "历史记录", "设置"])
        
        with tab1:
            self._render_single_generation()
        
        with tab2:
            self._render_batch_generation()
        
        with tab3:
            self._render_history()
        
        with tab4:
            self._render_settings()
    
    def _render_sidebar(self):
        """渲染侧边栏"""
        st.sidebar.header("⚙️ 配置选项")
        
        # API配置
        st.sidebar.subheader("API配置")
        self.content_provider = st.sidebar.selectbox(
            "文案生成API",
            ["deepseek", "doubao"],
            index=0
        )
        
        self.image_provider = st.sidebar.selectbox(
            "图片生成API",
            ["jimeng", "tongyi"],
            index=0
        )
        
        # 生成选项
        st.sidebar.subheader("生成选项")
        self.default_category = st.sidebar.text_input("默认类别", value="生活分享")
        self.default_style = st.sidebar.text_input("默认风格", value="生活分享")
        self.default_image_count = st.sidebar.slider("默认图片数量", min_value=0, max_value=5, value=1)
        
        # 输出配置
        st.sidebar.subheader("输出配置")
        self.auto_save = st.sidebar.checkbox("自动保存", value=True)
        self.save_format = st.sidebar.selectbox("保存格式", ["JSON", "Markdown"], index=0)
    
    def _render_single_generation(self):
        """渲染单篇生成界面"""
        st.header("📝 单篇笔记生成")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # 选题选项
            st.subheader("选题设置")
            topic_option = st.radio("选题方式", ["自动生成", "自定义"], key="single_topic_option")
            
            if topic_option == "自动生成":
                category = st.text_input("类别", value=self.default_category, key="single_category")
                topic_count = st.slider("选题数量", min_value=1, max_value=10, value=5, key="single_topic_count")
                
                if st.button("生成选题", key="single_generate_topics"):
                    with st.spinner("正在生成选题..."):
                        topics = asyncio.run(self.topic_generator.generate_topics(category, topic_count))
                        self.current_topics = topics
                        st.success(f"已生成 {len(topics)} 个选题")
                
                # 显示选题
            if hasattr(self, 'current_topics') and self.current_topics:
                st.subheader("生成的选题")
                for i, topic in enumerate(self.current_topics):
                    if st.button(f"{i+1}. {topic.title}", key=f"single_topic_{i}"):
                        self.selected_topic = topic.title
                        st.session_state.selected_topic = topic.title
                        st.session_state.show_content_generation = True
                        st.rerun()
            else:
                self.selected_topic = st.text_input("自定义选题", key="single_custom_topic")
            
            # 文案设置
            st.subheader("文案设置")
            style = st.text_input("文案风格", value=self.default_style, key="single_style")
            
            # 显示已生成的文案
            if hasattr(self, 'generated_content') and self.generated_content:
                st.subheader("已生成的文案")
                self._display_content(self.generated_content)
            
            # 图片设置
            st.subheader("图片设置")
            image_count = st.slider("图片数量", min_value=0, max_value=5, value=self.default_image_count, key="single_image_count")
            
            if image_count > 0:
                image_prompt_option = st.radio("图片提示词", ["自动生成", "自定义"], key="single_image_prompt_option")
                
                if image_prompt_option == "自定义":
                    custom_prompts = []
                    for i in range(image_count):
                        prompt = st.text_input(f"图片 {i+1} 提示词", key=f"single_custom_prompt_{i}")
                        if prompt:
                            custom_prompts.append(prompt)
                    self.custom_image_prompts = custom_prompts
                else:
                    self.custom_image_prompts = None
        
        with col2:
            # 生成结果
            st.subheader("生成结果")
            
            # 获取当前选中的选题
            selected_topic = st.session_state.get('selected_topic', None)
            
            # 检查是否应该显示内容生成区域
            show_content_generation = st.session_state.get('show_content_generation', False)
            
            if selected_topic and show_content_generation:
                st.info(f"当前选题: {selected_topic}")
                
                # 检查是否已生成文案
                if hasattr(self, 'generated_content') and self.generated_content:
                    st.success("文案已生成，可以直接生成完整笔记")
                    
                    # 显示已生成的文案
                    st.subheader("已生成的文案")
                    self._display_content(self.generated_content)
                    
                    if st.button("生成完整笔记", type="primary", key="single_generate_note"):
                        with st.spinner("正在生成完整笔记..."):
                            try:
                                # 使用已生成的文案创建笔记
                                note = asyncio.run(self._create_note_from_content(
                                    self.generated_content,
                                    selected_topic,
                                    category if topic_option == "自动生成" else self.default_category,
                                    style,
                                    image_count,
                                    getattr(self, 'custom_image_prompts', None)
                                ))
                                
                                # 显示结果
                                st.success("笔记生成成功!")
                                self._display_note(note)
                                
                                # 保存到历史记录
                                if self.auto_save:
                                    self._save_to_history(note)
                                    
                            except Exception as e:
                                st.error(f"生成失败: {str(e)}")
                else:
                    # 添加生成文案按钮
                    if st.button("生成文案", type="primary", key="single_generate_content"):
                        with st.spinner("正在生成文案..."):
                            try:
                                content = asyncio.run(self.content_generator.generate_content(
                                    selected_topic, 
                                    style, 
                                    self.content_provider
                                ))
                                self.generated_content = content
                                st.success("文案生成成功!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"生成文案失败: {str(e)}")
                    
                    st.info("请先生成文案，然后生成完整笔记")
            else:
                st.info("请先选择或输入选题")
    
    def _render_batch_generation(self):
        """渲染批量生成界面"""
        st.header("📚 批量笔记生成")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("批量设置")
            batch_count = st.slider("生成数量", min_value=1, max_value=20, value=5, key="batch_count")
            category = st.text_input("类别", value=self.default_category, key="batch_category")
            style = st.text_input("风格", value=self.default_style, key="batch_style")
            image_count = st.slider("每篇图片数量", min_value=0, max_value=5, value=self.default_image_count, key="batch_image_count")
            
            if st.button("批量生成", type="primary", key="batch_generate"):
                with st.spinner(f"正在生成 {batch_count} 篇笔记..."):
                    try:
                        notes = asyncio.run(self.note_generator.batch_generate_notes(
                            count=batch_count,
                            category=category,
                            style=style,
                            content_provider=self.content_provider,
                            image_provider=self.image_provider,
                            image_count=image_count
                        ))
                        
                        st.success(f"成功生成 {len(notes)} 篇笔记")
                        self.batch_notes = notes
                        
                        # 保存到历史记录
                        if self.auto_save:
                            for note in notes:
                                self._save_to_history(note)
                                
                    except Exception as e:
                        st.error(f"批量生成失败: {str(e)}")
        
        with col2:
            st.subheader("生成结果")
            
            if hasattr(self, 'batch_notes') and self.batch_notes:
                for i, note in enumerate(self.batch_notes):
                    with st.expander(f"笔记 {i+1}: {note.title}"):
                        self._display_note(note)
    
    def _render_history(self):
        """渲染历史记录界面"""
        st.header("📖 历史记录")
        
        # 获取历史记录
        output_config = self.config_manager.get_output_config()
        history_dir = output_config.get("content_dir", "./output/content")
        if os.path.exists(history_dir):
            history_files = [f for f in os.listdir(history_dir) if f.endswith('.json')]
            
            if history_files:
                # 按修改时间排序
                history_files.sort(key=lambda x: os.path.getmtime(os.path.join(history_dir, x)), reverse=True)
                
                for filename in history_files[:10]:  # 只显示最近10条
                    file_path = os.path.join(history_dir, filename)
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        note_data = json.load(f)
                    
                    with st.expander(f"{note_data['title']} - {note_data['created_at']}"):
                        st.markdown(f"**类别**: {note_data['category']}")
                    st.markdown(f"**内容**: {note_data['content']}")
                    st.markdown(f"**标签**: {', '.join(note_data['hashtags'])}")
                    
                    # 显示图片
                    if note_data['images']:
                        st.markdown("**图片**:")
                        for j, img in enumerate(note_data['images']):
                            if os.path.exists(img['path']):
                                st.image(img['path'], width=200, caption=f"图片 {j+1}")
                            else:
                                st.warning(f"图片不存在: {img['path']}")
            else:
                st.info("暂无历史记录")
        else:
            st.info("暂无历史记录")
    
    def _display_content(self, content):
        """显示文案内容"""
        # 标题
        st.markdown(f"### {content.title}")
        
        # 内容
        st.markdown(content.body)
        
        # 标签
        if content.hashtags:
            st.markdown(f"**标签**: {' '.join(content.hashtags)}")
        
        # 行动号召
        if content.call_to_action:
            st.markdown(f"**行动号召**: {content.call_to_action}")
    
    async def _create_note_from_content(
        self,
        content,
        topic,
        category,
        style,
        image_count,
        custom_image_prompts=None
    ):
        """使用已生成的文案创建笔记"""
        # 生成图片
        images = []
        if custom_image_prompts:
            # 使用自定义图片提示词
            for prompt in custom_image_prompts[:image_count]:
                try:
                    image_result = await self.image_generator.generate_image(prompt, self.image_provider)
                    images.append(image_result)
                except Exception as e:
                    logger.error(f"生成图片失败: {prompt}, 错误: {e}")
        else:
            # 根据内容自动生成图片提示词
            from ..generators.note_generator import NoteGenerator
            note_gen = NoteGenerator(self.config_manager)
            image_prompts = note_gen._generate_image_prompts(content, image_count)
            for prompt in image_prompts:
                try:
                    image_result = await self.image_generator.generate_image(prompt, self.image_provider)
                    images.append(image_result)
                except Exception as e:
                    logger.error(f"生成图片失败: {prompt}, 错误: {e}")
        
        logger.info(f"生成图片数量: {len(images)}")
        
        # 创建笔记结果
        from datetime import datetime
        import uuid
        from ..generators.note_generator import NoteResult
        
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
                "content_provider": self.content_provider,
                "image_provider": self.image_provider
            }
        )
        
        # 保存笔记到本地
        from ..generators.note_generator import NoteGenerator
        note_gen = NoteGenerator(self.config_manager)
        await note_gen._save_note(note_result)
        
        return note_result
    
    def _display_note(self, note):
        """显示笔记内容"""
        # 标题
        st.markdown(f"### {note.title}")
        
        # 内容
        st.markdown(note.content)
        
        # 标签
        if note.hashtags:
            st.markdown(f"**标签**: {' '.join(note.hashtags)}")
        
        # 行动号召
        if note.call_to_action:
            st.markdown(f"**行动号召**: {note.call_to_action}")
        
        # 图片
        if note.images:
            st.markdown("**图片**:")
            cols = st.columns(min(len(note.images), 3))
            for i, img in enumerate(note.images):
                with cols[i % 3]:
                    if os.path.exists(img.image_path):
                        st.image(img.image_path, caption=f"图片 {i+1}", use_column_width=True)
                    else:
                        st.warning(f"图片不存在: {img.image_path}")
        
        # 元数据
        with st.expander("元数据"):
            st.json(note.metadata)
    
    def _render_settings(self):
        """渲染设置界面"""
        st.header("⚙️ 设置")
        
        # API配置
        st.subheader("API配置")
        
        # Deepseek配置
        with st.expander("Deepseek API", expanded=True):
            deepseek_config = self.config_manager.get_api_config('deepseek')
            deepseek_base_url = st.text_input("Base URL", value=deepseek_config.get('base_url', ''), key="deepseek_base_url")
            deepseek_api_key = st.text_input("API Key", value=deepseek_config.get('api_key', ''), type="password", key="deepseek_api_key")
            deepseek_model = st.text_input("Model", value=deepseek_config.get('model', ''), key="deepseek_model")
            deepseek_timeout = st.slider("Timeout (秒)", min_value=5, max_value=60, value=deepseek_config.get('timeout', 30), key="deepseek_timeout")
            deepseek_max_retries = st.slider("Max Retries", min_value=1, max_value=5, value=deepseek_config.get('max_retries', 3), key="deepseek_max_retries")
        
        # 豆包配置
        with st.expander("豆包 API"):
            doubao_config = self.config_manager.get_api_config('doubao')
            doubao_base_url = st.text_input("Base URL", value=doubao_config.get('base_url', ''), key="doubao_base_url")
            doubao_api_key = st.text_input("API Key", value=doubao_config.get('api_key', ''), type="password", key="doubao_api_key")
            doubao_model = st.text_input("Model", value=doubao_config.get('model', ''), key="doubao_model")
            doubao_timeout = st.slider("Timeout (秒)", min_value=5, max_value=60, value=doubao_config.get('timeout', 30), key="doubao_timeout")
            doubao_max_retries = st.slider("Max Retries", min_value=1, max_value=5, value=doubao_config.get('max_retries', 3), key="doubao_max_retries")
        
        # 即梦配置
        with st.expander("即梦 API"):
            jimeng_config = self.config_manager.get_api_config('jimeng')
            jimeng_base_url = st.text_input("Base URL", value=jimeng_config.get('base_url', ''), key="jimeng_base_url")
            jimeng_api_key = st.text_input("API Key", value=jimeng_config.get('api_key', ''), type="password", key="jimeng_api_key")
            jimeng_model = st.text_input("Model", value=jimeng_config.get('model', ''), key="jimeng_model")
            jimeng_timeout = st.slider("Timeout (秒)", min_value=5, max_value=60, value=jimeng_config.get('timeout', 30), key="jimeng_timeout")
            jimeng_max_retries = st.slider("Max Retries", min_value=1, max_value=5, value=jimeng_config.get('max_retries', 3), key="jimeng_max_retries")
        
        # 通义万象配置
        with st.expander("通义万象 API"):
            tongyi_config = self.config_manager.get_api_config('tongyi')
            tongyi_base_url = st.text_input("Base URL", value=tongyi_config.get('base_url', ''), key="tongyi_base_url")
            tongyi_api_key = st.text_input("API Key", value=tongyi_config.get('api_key', ''), type="password", key="tongyi_api_key")
            tongyi_model = st.text_input("Model", value=tongyi_config.get('model', ''), key="tongyi_model")
            tongyi_timeout = st.slider("Timeout (秒)", min_value=5, max_value=60, value=tongyi_config.get('timeout', 30), key="tongyi_timeout")
            tongyi_max_retries = st.slider("Max Retries", min_value=1, max_value=5, value=tongyi_config.get('max_retries', 3), key="tongyi_max_retries")
        
        # 生成配置
        st.subheader("生成配置")
        generation_config = self.config_manager.get_generation_config()
        default_topic_count = st.slider("默认选题数量", min_value=1, max_value=10, value=generation_config.get('default_topic_count', 5), key="default_topic_count")
        default_image_count = st.slider("默认图片数量", min_value=0, max_value=5, value=generation_config.get('default_image_count', 3), key="default_image_count")
        max_retries = st.slider("最大重试次数", min_value=1, max_value=5, value=generation_config.get('max_retries', 3), key="max_retries")
        timeout = st.slider("超时时间 (秒)", min_value=5, max_value=60, value=generation_config.get('timeout', 30), key="timeout")
        
        # 保存配置按钮
        if st.button("保存配置", type="primary", key="save_config"):
            # 更新API配置
            self.config_manager.update_api_config('deepseek', {
                'base_url': deepseek_base_url,
                'api_key': deepseek_api_key,
                'model': deepseek_model,
                'timeout': deepseek_timeout,
                'max_retries': deepseek_max_retries
            })
            
            self.config_manager.update_api_config('doubao', {
                'base_url': doubao_base_url,
                'api_key': doubao_api_key,
                'model': doubao_model,
                'timeout': doubao_timeout,
                'max_retries': doubao_max_retries
            })
            
            self.config_manager.update_api_config('jimeng', {
                'base_url': jimeng_base_url,
                'api_key': jimeng_api_key,
                'model': jimeng_model,
                'timeout': jimeng_timeout,
                'max_retries': jimeng_max_retries
            })
            
            self.config_manager.update_api_config('tongyi', {
                'base_url': tongyi_base_url,
                'api_key': tongyi_api_key,
                'model': tongyi_model,
                'timeout': tongyi_timeout,
                'max_retries': tongyi_max_retries
            })
            
            # 更新生成配置
            self.config_manager.update_generation_config({
                'default_topic_count': default_topic_count,
                'default_image_count': default_image_count,
                'max_retries': max_retries,
                'timeout': timeout
            })
            
            st.success("配置已保存")
    
    def _save_to_history(self, note):
        """保存笔记到历史记录"""
        # 笔记已经在NoteGenerator中保存，这里可以添加额外的处理逻辑
        pass


def main():
    """主函数"""
    ui = StreamlitUI()
    ui.run()


if __name__ == "__main__":
    main()