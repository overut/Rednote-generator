"""
测试运行脚本 - 验证项目设置
"""

import os
import sys
import traceback
from pathlib import Path

# 添加项目根目录到系统路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    
    try:
        from src.config import ConfigManager
        print("✓ 配置管理模块导入成功")
    except Exception as e:
        print(f"✗ 配置管理模块导入失败: {e}")
        return False
    
    try:
        from src.api import DeepseekAPIClient, JimengAPIClient
        print("✓ API客户端模块导入成功")
    except Exception as e:
        print(f"✗ API客户端模块导入失败: {e}")
        return False
    
    try:
        from src.generators import TopicGenerator, ContentGenerator, ImageGenerator
        print("✓ 生成器模块导入成功")
    except Exception as e:
        print(f"✗ 生成器模块导入失败: {e}")
        return False
    
    try:
        from src.ui import StreamlitUI, CLIUI
        print("✓ UI模块导入成功")
    except Exception as e:
        print(f"✗ UI模块导入失败: {e}")
        return False
    
    try:
        from src.utils import setup_logger, get_logger
        print("✓ 工具模块导入成功")
    except Exception as e:
        print(f"✗ 工具模块导入失败: {e}")
        return False
    
    return True

def test_config():
    """测试配置文件"""
    print("\n测试配置文件...")
    
    config_file = project_root / "config.yaml"
    if not config_file.exists():
        print("✗ 配置文件不存在")
        return False
    
    try:
        from src.config import ConfigManager
        config_manager = ConfigManager(str(config_file))
        
        # 测试获取API配置
        deepseek_config = config_manager.get_api_config("deepseek")
        if deepseek_config:
            print("✓ Deepseek配置读取成功")
        else:
            print("✗ Deepseek配置读取失败")
            return False
        
        # 测试获取提示词配置
        topic_prompt = config_manager.get_prompt_config("topic_generation")
        if topic_prompt:
            print("✓ 提示词配置读取成功")
        else:
            print("✗ 提示词配置读取失败")
            return False
        
        return True
    except Exception as e:
        print(f"✗ 配置文件测试失败: {e}")
        return False

def test_directories():
    """测试目录结构"""
    print("\n测试目录结构...")
    
    required_dirs = [
        "src",
        "src/config",
        "src/api",
        "src/generators",
        "src/ui",
        "src/utils",
        "tests",
        "output",
        "output/images",
        "output/content",
        "logs"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            print(f"✓ {dir_path} 目录存在")
        else:
            print(f"✗ {dir_path} 目录不存在")
            all_exist = False
    
    return all_exist

def test_dependencies():
    """测试依赖包"""
    print("\n测试依赖包...")
    
    required_packages = [
        ("requests", "requests"),
        ("pyyaml", "yaml"),
        ("streamlit", "streamlit"),
        ("pillow", "PIL"),
        ("jinja2", "jinja2")
    ]
    
    all_installed = True
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✓ {package_name} 已安装")
        except ImportError:
            print(f"✗ {package_name} 未安装")
            all_installed = False
    
    return all_installed

def main():
    """主函数"""
    print("小红书笔记生成器 - 项目设置验证")
    print("=" * 40)
    
    # 测试目录结构
    dirs_ok = test_directories()
    
    # 测试依赖包
    deps_ok = test_dependencies()
    
    # 测试模块导入
    imports_ok = test_imports()
    
    # 测试配置文件
    config_ok = test_config()
    
    # 输出测试结果
    print("\n" + "=" * 40)
    print("测试结果总结:")
    print(f"目录结构: {'✓ 通过' if dirs_ok else '✗ 失败'}")
    print(f"依赖包: {'✓ 通过' if deps_ok else '✗ 失败'}")
    print(f"模块导入: {'✓ 通过' if imports_ok else '✗ 失败'}")
    print(f"配置文件: {'✓ 通过' if config_ok else '✗ 失败'}")
    
    if all([dirs_ok, deps_ok, imports_ok, config_ok]):
        print("\n🎉 所有测试通过！项目设置正确。")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查上述错误。")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试过程中发生未知错误: {e}")
        traceback.print_exc()
        sys.exit(1)