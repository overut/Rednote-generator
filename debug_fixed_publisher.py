import asyncio
import sys
from src.publish.publisher import XiaohongshuPublisher
from src.config.config_manager import ConfigManager
from src.utils.logger import logger

async def test_publisher():
    """测试发布器功能"""
    logger.info("开始测试修复后的发布器...")
    
    try:
        # 初始化配置管理器
        config_manager = ConfigManager()
        
        # 初始化发布器
        publisher = XiaohongshuPublisher(config_manager)
        logger.info("发布器初始化成功")
        
        # 测试资源管理
        logger.info("测试资源管理...")
        
        # 尝试使用publish_note方法，不使用UI格式
        result = await publisher.publish_note(
            title="测试标题",
            content="测试内容",
            image_paths=[]
        )
        
        logger.info(f"发布结果: {result}")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保关闭资源
        try:
            if 'publisher' in locals() and publisher is not None:
                await publisher.close()
                logger.info("发布器已关闭")
        except Exception as close_error:
            logger.error(f"关闭发布器失败: {close_error}")

if __name__ == "__main__":
    # 确保正确的事件循环策略
    if sys.platform == 'win32':
        try:
            if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            elif hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception as e:
            print(f"设置事件循环策略失败: {e}")
    
    # 运行测试
    asyncio.run(test_publisher())