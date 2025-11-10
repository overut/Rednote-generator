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

from src.publish.publisher import XiaohongshuPublisher

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
        publisher = XiaohongshuPublisher('test_account')
        
        # 初始化浏览器和发布器
        await publisher._initialize()
        
        # 获取页面
        page = await publisher.browser_manager.get_page()
        
        # 打开小红书共创平台
        await page.goto('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image', timeout=60000)
        await page.wait_for_load_state('networkidle', timeout=30000)
        
        # 这里可以添加图片上传和内容填充的代码
        # await publisher._upload_images(page, ["test_image.jpg"])
        # await publisher._fill_content(page, note_result)
        
        # 测试发布按钮查找和点击
        logger.info("开始测试发布按钮查找和点击...")
        # 注意：这里只是测试，实际发布需要先上传图片和填充内容
        # result = await publisher._publish_note(page)
        
        logger.info("测试完成（未实际发布）")
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭浏览器
        if 'publisher' in locals() and hasattr(publisher, 'browser_manager') and publisher.browser_manager:
            await publisher.browser_manager.close()

if __name__ == "__main__":
    asyncio.run(test_publish_button())