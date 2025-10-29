"""
小红书笔记生成器 - 主程序入口
"""

import sys
import os
import argparse
import asyncio
from typing import Optional

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import ConfigManager
from src.ui import StreamlitUI, CLIUI
from src.utils import setup_logger, get_logger


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="小红书笔记生成器")
    parser.add_argument("--mode", "-m", choices=["cli", "web"], default="cli", help="运行模式")
    parser.add_argument("--config", "-c", default="config.yaml", help="配置文件路径")
    parser.add_argument("--port", "-p", type=int, default=8501, help="Web界面端口")
    parser.add_argument("--log-level", "-l", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="日志级别")
    parser.add_argument("--log-file", help="日志文件路径")
    
    # 解析已知参数，剩余参数传递给CLI界面
    args, remaining_args = parser.parse_known_args()
    
    return args, remaining_args


def setup_logging(log_level: str, log_file: Optional[str] = None):
    """设置日志"""
    if not log_file:
        log_file = os.path.join("logs", f"generator_{os.path.basename(__file__)}.log")
    
    setup_logger(
        name="xiaohongshu_generator",
        log_level=log_level,
        log_file=log_file
    )


def run_cli_mode(config_path: str, remaining_args):
    """运行命令行模式"""
    logger = get_logger()
    logger.info("启动命令行模式")
    
    # 初始化CLI界面
    cli_ui = CLIUI()
    
    # 运行CLI界面
    cli_ui.run(remaining_args)


def run_web_mode(config_path: str, port: int):
    """运行Web模式"""
    logger = get_logger()
    logger.info(f"启动Web模式，端口: {port}")
    
    # 初始化Streamlit界面
    streamlit_ui = StreamlitUI()
    
    # 运行Streamlit应用
    import subprocess
    import sys
    
    # 构建streamlit命令
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.join(os.path.dirname(__file__), "src", "ui", "streamlit_ui.py"),
        "--server.port", str(port),
        "--server.headless", "false"
    ]
    
    # 启动streamlit
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"启动Streamlit失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("用户中断，退出程序")


def main():
    """主函数"""
    # 解析命令行参数
    args, remaining_args = parse_args()
    
    # 设置日志
    setup_logging(args.log_level, args.log_file)
    logger = get_logger()
    
    try:
        # 检查配置文件
        if not os.path.exists(args.config):
            logger.warning(f"配置文件不存在: {args.config}，将使用默认配置")
        
        # 根据模式运行
        if args.mode == "cli":
            run_cli_mode(args.config, remaining_args)
        elif args.mode == "web":
            run_web_mode(args.config, args.port)
        else:
            logger.error(f"不支持的运行模式: {args.mode}")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()