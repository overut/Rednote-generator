"""
命令行用户界面实现
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..config import ConfigManager
from ..generators import TopicGenerator, ContentGenerator, ImageGenerator, NoteGenerator


class CLIUI:
    """命令行用户界面"""
    
    def __init__(self):
        """初始化命令行用户界面"""
        self.config_manager = ConfigManager()
        self.note_generator = NoteGenerator(self.config_manager)
        self.topic_generator = TopicGenerator(self.config_manager)
        self.content_generator = ContentGenerator(self.config_manager)
        self.image_generator = ImageGenerator(self.config_manager)
    
    def run(self, args=None):
        """运行命令行界面"""
        parser = argparse.ArgumentParser(description="小红书笔记生成器")
        subparsers = parser.add_subparsers(dest="command", help="可用命令")
        
        # 生成选题命令
        topic_parser = subparsers.add_parser("topic", help="生成选题")
        topic_parser.add_argument("--category", "-c", default="生活分享", help="选题类别")
        topic_parser.add_argument("--count", "-n", type=int, default=5, help="选题数量")
        topic_parser.add_argument("--output", "-o", help="输出文件路径")
        
        # 生成文案命令
        content_parser = subparsers.add_parser("content", help="生成文案")
        content_parser.add_argument("--topic", "-t", required=True, help="选题")
        content_parser.add_argument("--style", "-s", default="生活分享", help="文案风格")
        content_parser.add_argument("--provider", "-p", choices=["deepseek", "doubao"], default="deepseek", help="API提供商")
        content_parser.add_argument("--output", "-o", help="输出文件路径")
        
        # 生成图片命令
        image_parser = subparsers.add_parser("image", help="生成图片")
        image_parser.add_argument("--prompt", "-p", required=True, help="图片提示词")
        image_parser.add_argument("--provider", "-pr", choices=["jimeng", "tongyi"], default="jimeng", help="API提供商")
        image_parser.add_argument("--width", "-w", type=int, default=1080, help="图片宽度")
        image_parser.add_argument("--height", type=int, default=1920, help="图片高度")
        image_parser.add_argument("--output", "-o", help="输出目录路径")
        
        # 生成选题并生成文案命令
        topic_content_parser = subparsers.add_parser("topic-content", help="生成选题并生成文案")
        topic_content_parser.add_argument("--category", "-c", default="生活分享", help="选题类别")
        topic_content_parser.add_argument("--count", "-n", type=int, default=5, help="选题数量")
        topic_content_parser.add_argument("--style", "-s", default="生活分享", help="文案风格")
        topic_content_parser.add_argument("--provider", "-p", choices=["deepseek", "doubao"], default="deepseek", help="API提供商")
        topic_content_parser.add_argument("--output", "-o", help="输出文件路径")
        
        # 生成笔记命令
        note_parser = subparsers.add_parser("note", help="生成完整笔记")
        note_parser.add_argument("--topic", "-t", help="选题")
        note_parser.add_argument("--category", "-c", default="生活分享", help="选题类别")
        note_parser.add_argument("--style", "-s", default="生活分享", help="文案风格")
        note_parser.add_argument("--content-provider", "-cp", choices=["deepseek", "doubao"], default="deepseek", help="文案API提供商")
        note_parser.add_argument("--image-provider", "-ip", choices=["jimeng", "tongyi"], default="jimeng", help="图片API提供商")
        note_parser.add_argument("--image-count", "-ic", type=int, default=1, help="图片数量")
        note_parser.add_argument("--image-prompts", "-ips", nargs="+", help="自定义图片提示词")
        note_parser.add_argument("--output", "-o", help="输出目录路径")
        
        # 批量生成命令
        batch_parser = subparsers.add_parser("batch", help="批量生成笔记")
        batch_parser.add_argument("--count", "-n", type=int, default=5, help="生成数量")
        batch_parser.add_argument("--category", "-c", default="生活分享", help="选题类别")
        batch_parser.add_argument("--style", "-s", default="生活分享", help="文案风格")
        batch_parser.add_argument("--content-provider", "-cp", choices=["deepseek", "doubao"], default="deepseek", help="文案API提供商")
        batch_parser.add_argument("--image-provider", "-ip", choices=["jimeng", "tongyi"], default="jimeng", help="图片API提供商")
        batch_parser.add_argument("--image-count", "-ic", type=int, default=1, help="每篇笔记的图片数量")
        batch_parser.add_argument("--output", "-o", help="输出目录路径")
        
        # 交互式模式
        interactive_parser = subparsers.add_parser("interactive", help="交互式模式")
        
        # 解析参数
        args = parser.parse_args(args)
        
        # 执行命令
        if args.command == "topic":
            self._generate_topics(args)
        elif args.command == "content":
            self._generate_content(args)
        elif args.command == "topic-content":
            self._generate_topics_and_content(args)
        elif args.command == "image":
            self._generate_image(args)
        elif args.command == "note":
            self._generate_note(args)
        elif args.command == "batch":
            self._batch_generate(args)
        elif args.command == "interactive":
            self._interactive_mode()
        else:
            parser.print_help()
    
    def _generate_topics(self, args):
        """生成选题"""
        print(f"正在生成 {args.count} 个关于 '{args.category}' 的选题...")
        
        try:
            topics = asyncio.run(self.topic_generator.generate_topics(args.category, args.count))
            
            print(f"\n成功生成 {len(topics)} 个选题:")
            for i, topic in enumerate(topics):
                print(f"\n{i+1}. 标题: {topic.title}")
                print(f"   描述: {topic.description}")
                print(f"   类别: {topic.category}")
                print(f"   标签: {', '.join(topic.tags)}")
            
            # 保存到文件
            if args.output:
                self._save_topics_to_file(topics, args.output)
                print(f"\n选题已保存到: {args.output}")
                
        except Exception as e:
            print(f"生成选题失败: {e}")
            sys.exit(1)
    
    def _generate_content(self, args):
        """生成文案"""
        print(f"正在为选题 '{args.topic}' 生成文案...")
        
        try:
            content = asyncio.run(self.content_generator.generate_content(args.topic, args.style, args.provider))
            
            print(f"\n标题: {content.title}")
            print(f"内容: {content.body}")
            print(f"标签: {', '.join(content.hashtags)}")
            if content.call_to_action:
                print(f"行动号召: {content.call_to_action}")
            
            # 保存到文件
            if args.output:
                self._save_content_to_file(content, args.output)
                print(f"\n文案已保存到: {args.output}")
                
        except Exception as e:
            print(f"生成文案失败: {e}")
            sys.exit(1)
    
    def _generate_topics_and_content(self, args):
        """生成选题并生成文案"""
        print(f"正在生成 {args.count} 个关于 '{args.category}' 的选题...")
        
        try:
            # 1. 生成选题
            topics = asyncio.run(self.topic_generator.generate_topics(args.category, args.count))
            
            print(f"\n成功生成 {len(topics)} 个选题:")
            for i, topic in enumerate(topics):
                print(f"\n{i+1}. 标题: {topic.title}")
                print(f"   描述: {topic.description}")
                print(f"   类别: {topic.category}")
                print(f"   标签: {', '.join(topic.tags)}")
            
            # 2. 为每个选题生成文案
            print("\n正在为每个选题生成文案...")
            contents = []
            for i, topic in enumerate(topics):
                print(f"\n正在为选题 '{topic.title}' 生成文案...")
                try:
                    # 使用topic.title作为选题字符串
                    content = asyncio.run(self.content_generator.generate_content(
                        topic.title,  # 传递字符串
                        args.style, 
                        args.provider
                    ))
                    contents.append(content)
                    print(f"  标题: {content.title}")
                    print(f"  标签: {', '.join(content.hashtags)}")
                except Exception as e:
                    print(f"  生成文案失败: {e}")
                    contents.append(None)
            
            # 3. 保存到文件
            if args.output:
                self._save_topics_and_content_to_file(topics, contents, args.output)
                print(f"\n选题和文案已保存到: {args.output}")
            else:
                # 显示所有文案内容
                print("\n所有文案内容:")
                for i, (topic, content) in enumerate(zip(topics, contents)):
                    if content:
                        print(f"\n=== 选题 {i+1} ===")
                        print(f"标题: {topic.title}")
                        print(f"描述: {topic.description}")
                        print(f"\n文案标题: {content.title}")
                        print(f"文案内容: {content.body}")
                        print(f"标签: {', '.join(content.hashtags)}")
                        if content.call_to_action:
                            print(f"行动号召: {content.call_to_action}")
                        print("-" * 50)
                
        except Exception as e:
            print(f"生成选题和文案失败: {e}")
            sys.exit(1)
    
    def _generate_image(self, args):
        """生成图片"""
        print(f"正在根据提示词 '{args.prompt}' 生成图片...")
        
        try:
            image_result = asyncio.run(self.image_generator.generate_image(
                args.prompt, 
                args.provider, 
                width=args.width, 
                height=args.height
            ))
            
            print(f"\n图片已生成并保存到: {image_result.image_path}")
            print(f"提示词: {image_result.prompt}")
            print(f"提供商: {image_result.provider}")
            
            # 如果指定了输出目录，复制图片到该目录
            if args.output and args.output != os.path.dirname(image_result.image_path):
                import shutil
                os.makedirs(args.output, exist_ok=True)
                filename = os.path.basename(image_result.image_path)
                dest_path = os.path.join(args.output, filename)
                shutil.copy2(image_result.image_path, dest_path)
                print(f"图片已复制到: {dest_path}")
                
        except Exception as e:
            print(f"生成图片失败: {e}")
            sys.exit(1)
    
    def _save_topics_and_content_to_file(self, topics, contents, output_path):
        """保存选题和文案到文件"""
        data = {
            "generated_at": datetime.now().isoformat(),
            "topics": [],
            "contents": []
        }
        
        # 保存选题
        for topic in topics:
            data["topics"].append({
                "title": topic.title,
                "description": topic.description,
                "category": topic.category,
                "tags": topic.tags
            })
        
        # 保存文案
        for content in contents:
            if content:
                data["contents"].append({
                    "title": content.title,
                    "body": content.body,
                    "hashtags": content.hashtags,
                    "call_to_action": content.call_to_action
                })
            else:
                data["contents"].append(None)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_note(self, args):
        """生成完整笔记"""
        print(f"正在生成笔记...")
        
        try:
            note = asyncio.run(self.note_generator.generate_note(
                topic=args.topic,
                category=args.category,
                style=args.style,
                content_provider=args.content_provider,
                image_provider=args.image_provider,
                image_count=args.image_count,
                custom_image_prompts=args.image_prompts
            ))
            
            print(f"\n笔记生成成功!")
            print(f"ID: {note.id}")
            print(f"标题: {note.title}")
            print(f"内容: {note.content}")
            print(f"标签: {', '.join(note.hashtags)}")
            if note.call_to_action:
                print(f"行动号召: {note.call_to_action}")
            print(f"图片数量: {len(note.images)}")
            for i, img in enumerate(note.images):
                print(f"  图片 {i+1}: {img.image_path}")
            
            # 如果指定了输出目录，复制文件到该目录
            if args.output:
                self._copy_note_to_output(note, args.output)
                print(f"\n笔记已保存到: {args.output}")
                
        except Exception as e:
            print(f"生成笔记失败: {e}")
            sys.exit(1)
    
    def _batch_generate(self, args):
        """批量生成笔记"""
        print(f"正在批量生成 {args.count} 篇笔记...")
        
        try:
            notes = asyncio.run(self.note_generator.batch_generate_notes(
                count=args.count,
                category=args.category,
                style=args.style,
                content_provider=args.content_provider,
                image_provider=args.image_provider,
                image_count=args.image_count
            ))
            
            print(f"\n成功生成 {len(notes)} 篇笔记:")
            for i, note in enumerate(notes):
                print(f"\n{i+1}. ID: {note.id}")
                print(f"   标题: {note.title}")
                print(f"   类别: {note.category}")
                print(f"   图片数量: {len(note.images)}")
            
            # 如果指定了输出目录，复制文件到该目录
            if args.output:
                for note in notes:
                    self._copy_note_to_output(note, args.output)
                print(f"\n所有笔记已保存到: {args.output}")
                
        except Exception as e:
            print(f"批量生成失败: {e}")
            sys.exit(1)
    
    def _interactive_mode(self):
        """交互式模式"""
        print("进入交互式模式 (输入 'exit' 退出)")
        
        while True:
            print("\n请选择操作:")
            print("1. 生成选题")
            print("2. 生成文案")
            print("3. 生成图片")
            print("4. 生成完整笔记")
            print("5. 批量生成笔记")
            print("0. 退出")
            
            choice = input("请输入选项 (0-5): ").strip()
            
            if choice == "0" or choice.lower() == "exit":
                print("再见!")
                break
            elif choice == "1":
                self._interactive_generate_topics()
            elif choice == "2":
                self._interactive_generate_content()
            elif choice == "3":
                self._interactive_generate_image()
            elif choice == "4":
                self._interactive_generate_note()
            elif choice == "5":
                self._interactive_batch_generate()
            else:
                print("无效选项，请重新输入")
    
    def _interactive_generate_topics(self):
        """交互式生成选题"""
        category = input("请输入选题类别 (默认: 生活分享): ").strip() or "生活分享"
        count = int(input("请输入选题数量 (默认: 5): ").strip() or "5")
        
        print(f"正在生成 {count} 个关于 '{category}' 的选题...")
        
        try:
            topics = asyncio.run(self.topic_generator.generate_topics(category, count))
            
            print(f"\n成功生成 {len(topics)} 个选题:")
            for i, topic in enumerate(topics):
                print(f"\n{i+1}. 标题: {topic.title}")
                print(f"   描述: {topic.description}")
                print(f"   类别: {topic.category}")
                print(f"   标签: {', '.join(topic.tags)}")
                
        except Exception as e:
            print(f"生成选题失败: {e}")
    
    def _interactive_generate_content(self):
        """交互式生成文案"""
        topic = input("请输入选题: ").strip()
        style = input("请输入文案风格 (默认: 生活分享): ").strip() or "生活分享"
        provider = input("请选择API提供商 (deepseek/doubao, 默认: deepseek): ").strip() or "deepseek"
        
        if provider not in ["deepseek", "doubao"]:
            print("无效的API提供商，使用默认值: deepseek")
            provider = "deepseek"
        
        print(f"正在为选题 '{topic}' 生成文案...")
        
        try:
            content = asyncio.run(self.content_generator.generate_content(topic, style, provider))
            
            print(f"\n标题: {content.title}")
            print(f"内容: {content.body}")
            print(f"标签: {', '.join(content.hashtags)}")
            if content.call_to_action:
                print(f"行动号召: {content.call_to_action}")
                
        except Exception as e:
            print(f"生成文案失败: {e}")
    
    def _interactive_generate_image(self):
        """交互式生成图片"""
        prompt = input("请输入图片提示词: ").strip()
        provider = input("请选择API提供商 (jimeng/tongyi, 默认: jimeng): ").strip() or "jimeng"
        
        if provider not in ["jimeng", "tongyi"]:
            print("无效的API提供商，使用默认值: jimeng")
            provider = "jimeng"
        
        print(f"正在根据提示词 '{prompt}' 生成图片...")
        
        try:
            image_result = asyncio.run(self.image_generator.generate_image(prompt, provider))
            
            print(f"\n图片已生成并保存到: {image_result.image_path}")
            print(f"提示词: {image_result.prompt}")
            print(f"提供商: {image_result.provider}")
                
        except Exception as e:
            print(f"生成图片失败: {e}")
    
    def _interactive_generate_note(self):
        """交互式生成完整笔记"""
        topic = input("请输入选题 (留空自动生成): ").strip() or None
        category = input("请输入选题类别 (默认: 生活分享): ").strip() or "生活分享"
        style = input("请输入文案风格 (默认: 生活分享): ").strip() or "生活分享"
        content_provider = input("请选择文案API提供商 (deepseek/doubao, 默认: deepseek): ").strip() or "deepseek"
        image_provider = input("请选择图片API提供商 (jimeng/tongyi, 默认: jimeng): ").strip() or "jimeng"
        image_count = int(input("请输入图片数量 (默认: 1): ").strip() or "1")
        
        if content_provider not in ["deepseek", "doubao"]:
            print("无效的文案API提供商，使用默认值: deepseek")
            content_provider = "deepseek"
        
        if image_provider not in ["jimeng", "tongyi"]:
            print("无效的图片API提供商，使用默认值: jimeng")
            image_provider = "jimeng"
        
        print("正在生成笔记...")
        
        try:
            note = asyncio.run(self.note_generator.generate_note(
                topic=topic,
                category=category,
                style=style,
                content_provider=content_provider,
                image_provider=image_provider,
                image_count=image_count
            ))
            
            print(f"\n笔记生成成功!")
            print(f"ID: {note.id}")
            print(f"标题: {note.title}")
            print(f"内容: {note.content}")
            print(f"标签: {', '.join(note.hashtags)}")
            if note.call_to_action:
                print(f"行动号召: {note.call_to_action}")
            print(f"图片数量: {len(note.images)}")
            for i, img in enumerate(note.images):
                print(f"  图片 {i+1}: {img.image_path}")
                
        except Exception as e:
            print(f"生成笔记失败: {e}")
    
    def _interactive_batch_generate(self):
        """交互式批量生成笔记"""
        count = int(input("请输入生成数量 (默认: 5): ").strip() or "5")
        category = input("请输入选题类别 (默认: 生活分享): ").strip() or "生活分享"
        style = input("请输入文案风格 (默认: 生活分享): ").strip() or "生活分享"
        content_provider = input("请选择文案API提供商 (deepseek/doubao, 默认: deepseek): ").strip() or "deepseek"
        image_provider = input("请选择图片API提供商 (jimeng/tongyi, 默认: jimeng): ").strip() or "jimeng"
        image_count = int(input("请输入每篇笔记的图片数量 (默认: 1): ").strip() or "1")
        
        if content_provider not in ["deepseek", "doubao"]:
            print("无效的文案API提供商，使用默认值: deepseek")
            content_provider = "deepseek"
        
        if image_provider not in ["jimeng", "tongyi"]:
            print("无效的图片API提供商，使用默认值: jimeng")
            image_provider = "jimeng"
        
        print(f"正在批量生成 {count} 篇笔记...")
        
        try:
            notes = asyncio.run(self.note_generator.batch_generate_notes(
                count=count,
                category=category,
                style=style,
                content_provider=content_provider,
                image_provider=image_provider,
                image_count=image_count
            ))
            
            print(f"\n成功生成 {len(notes)} 篇笔记:")
            for i, note in enumerate(notes):
                print(f"\n{i+1}. ID: {note.id}")
                print(f"   标题: {note.title}")
                print(f"   类别: {note.category}")
                print(f"   图片数量: {len(note.images)}")
                
        except Exception as e:
            print(f"批量生成失败: {e}")
    
    def _save_topics_to_file(self, topics, file_path):
        """保存选题到文件"""
        data = []
        for topic in topics:
            data.append({
                "title": topic.title,
                "description": topic.description,
                "category": topic.category,
                "tags": topic.tags
            })
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_content_to_file(self, content, file_path):
        """保存文案到文件"""
        data = {
            "title": content.title,
            "body": content.body,
            "hashtags": content.hashtags,
            "call_to_action": content.call_to_action
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _copy_note_to_output(self, note, output_dir):
        """复制笔记到输出目录"""
        # 复制笔记JSON文件
        output_config = self.config_manager.get_output_config()
        content_dir = output_config.get("content_dir", "./output/content")
        note_file = f"{note.id[:8]}_{note.title.replace(' ', '_')}.json"
        src_path = os.path.join(content_dir, note_file)
        
        if os.path.exists(src_path):
            os.makedirs(output_dir, exist_ok=True)
            dest_path = os.path.join(output_dir, note_file)
            import shutil
            shutil.copy2(src_path, dest_path)
        
        # 复制图片文件
        for img in note.images:
            if os.path.exists(img.image_path):
                filename = os.path.basename(img.image_path)
                dest_path = os.path.join(output_dir, filename)
                import shutil
                shutil.copy2(img.image_path, dest_path)


def main():
    """主函数"""
    ui = CLIUI()
    ui.run()


if __name__ == "__main__":
    main()