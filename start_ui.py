#!/usr/bin/env python3
"""
小红书笔记生成器启动脚本
以UI方式启动应用并监听任务
"""

import os
import sys
import logging
import asyncio
import traceback
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ["PYTHONPATH"] = str(project_root)

# 导入项目模块
from src.utils.logger import setup_logger
from src.config.config_manager import ConfigManager

def setup_environment():
    """设置运行环境"""
    # 确保必要的目录存在
    directories = [
        "output",
        "output/images",
        "output/content",
        "logs",
        "accounts",
        "accounts/cookies"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # 检查配置文件
    config_file = "config.yaml"
    if not os.path.exists(config_file):
        print(f"警告: 配置文件 {config_file} 不存在")
        if os.path.exists("config.yaml.example"):
            print("发现示例配置文件，正在复制...")
            import shutil
            shutil.copy("config.yaml.example", config_file)
            print("配置文件已创建，请根据需要修改配置")
        else:
            print("错误: 未找到示例配置文件")
            return False
    
    return True

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import streamlit
        import playwright
        import yaml
        import requests
        import aiohttp
        print("✓ 所有必要的依赖已安装")
        return True
    except ImportError as e:
        print(f"✗ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def start_ui():
    """启动Streamlit UI"""
    try:
        print("=" * 50)
        print("小红书笔记生成器 - UI模式")
        print("=" * 50)
        print("正在启动Web界面...")
        
        # 设置日志
        logger = setup_logger(
            name="xiaohongshu_ui",
            log_level="INFO",
            log_file="logs/ui.log",
            console_output=True
        )
        
        # 启动Streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run",
            "src/ui/streamlit_ui.py",
            "--server.port=8501",
            "--server.address=0.0.0.0",
            "--browser.gatherUsageStats=false"
        ]
        
        logger.info(f"启动命令: {' '.join(cmd)}")
        print(f"访问地址: http://localhost:8501")
        print("按 Ctrl+C 停止服务")
        
        # 启动进程
        process = subprocess.Popen(cmd, cwd=project_root)
        
        # 等待进程结束
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n正在停止服务...")
            process.terminate()
            process.wait()
            print("服务已停止")
        
        return True
        
    except Exception as e:
        print(f"启动UI失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("小红书笔记生成器启动检查...")
    
    # 设置环境
    if not setup_environment():
        print("环境设置失败，退出")
        sys.exit(1)
    
    # 检查依赖
    if not check_dependencies():
        print("依赖检查失败，退出")
        sys.exit(1)
    
    # 启动UI
    if not start_ui():
        print("UI启动失败，退出")
        sys.exit(1)

if __name__ == "__main__":
    main()