#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
小红书发布功能测试脚本
用于测试发布按钮查找和点击功能
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.publish.publisher import Publisher

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_publish.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

async def test_publish_button():
    """测试发布按钮查找和点击功能"""
    try:
        # 创建发布器实例
        publisher = Publisher()
        
        # 初始化浏览器
        await publisher.init_browser()
        
        # 打开小红书共创平台
        await publisher.open_publish_page()
        
        # 这里可以添加图片上传和内容填充的代码
        # await publisher.upload_images(["test_image.jpg"])
        # await publisher.fill_content("测试标题", "测试内容")
        
        # 测试发布按钮查找和点击
        logger.info("开始测试发布按钮查找和点击...")
        result = await publisher.publish()
        
        if result:
            logger.info("发布成功！")
            logger.info(f"发布结果: {result}")
        else:
            logger.error("发布失败！")
            
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
    finally:
        # 关闭浏览器
        if 'publisher' in locals():
            await publisher.close()

if __name__ == "__main__":
    asyncio.run(test_publish_button())