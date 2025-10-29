#!/bin/bash

# 小红书笔记生成器启动脚本

echo "小红书笔记生成器"
echo "=================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3环境，请先安装Python 3.8或更高版本"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
if ! python3 -c "import requests" &> /dev/null; then
    echo "安装依赖中..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "错误: 依赖安装失败"
        exit 1
    fi
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    if [ -f "config.yaml.example" ]; then
        echo "复制配置文件..."
        cp config.yaml.example config.yaml
        echo "警告: 请编辑config.yaml文件，填入您的API密钥"
    else
        echo "错误: 未找到配置文件config.yaml或config.yaml.example"
        exit 1
    fi
fi

# 创建输出目录
mkdir -p output/images
mkdir -p output/content
mkdir -p logs

# 选择运行模式
echo ""
echo "请选择运行模式:"
echo "1. Web界面模式 (推荐)"
echo "2. 命令行模式"
echo "3. 退出"
echo ""
read -p "请输入选项 (1-3): " mode

case $mode in
    1)
        echo ""
        echo "启动Web界面..."
        echo "浏览器将自动打开 http://localhost:8501"
        echo ""
        python3 main.py --mode web
        ;;
    2)
        echo ""
        echo "启动命令行模式..."
        echo ""
        python3 main.py --mode cli
        ;;
    3)
        echo "退出程序"
        exit 0
        ;;
    *)
        echo "无效选项，退出程序"
        exit 1
        ;;
esac