#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试发布模块，定位'title'未定义错误"""
import sys
import traceback
from src.publish.publisher import XiaohongshuPublisher
from src.config.config_manager import ConfigManager
import asyncio

def debug_publish():
    """调试发布过程"""
    print("开始调试发布模块...")
    
    try:
        # 创建配置管理器实例
        config_manager = ConfigManager()
        print("配置管理器创建成功")
        
        # 创建发布器实例
        publisher = XiaohongshuPublisher(config_manager)
        print("发布器实例创建成功")
        
        # 构造测试数据，模拟note_result对象
        class MockTopic:
            def __init__(self):
                self.title = "测试标题"
        
        class MockContent:
            def __init__(self):
                self.text = "测试内容"
        
        class MockNoteResult:
            def __init__(self):
                # 测试不同情况：
                # 1. 正常情况 - 有topic和title
                # self.topic = MockTopic()
                # self.content = MockContent()
                
                # 2. 没有topic属性
                # self.content = MockContent()
                
                # 3. topic没有title属性
                self.topic = object()
                self.content = MockContent()
        
        # 创建测试对象
        note_result = MockNoteResult()
        images = []
        tags = ["测试标签1", "测试标签2"]
        
        print("开始调用publish_note方法...")
        # 异步调用发布方法
        success = asyncio.run(publisher.publish_note(note_result, images, tags))
        print(f"发布结果: {success}")
        
    except Exception as e:
        print(f"捕获到异常: {type(e).__name__}: {e}")
        print("详细堆栈信息:")
        traceback.print_exc()
    finally:
        if 'publisher' in locals():
            print("清理浏览器资源...")
            publisher.close()

if __name__ == "__main__":
    debug_publish()