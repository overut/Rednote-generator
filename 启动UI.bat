@echo off
chcp 65001 >nul
title 小红书笔记生成器 - UI模式

echo ========================================
echo 小红书笔记生成器 - UI模式
echo ========================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python环境
    echo 请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

REM 检查是否在正确的目录
if not exist "src\ui\streamlit_ui.py" (
    echo 错误: 未找到项目文件
    echo 请确保在项目根目录运行此脚本
    pause
    exit /b 1
)

echo 正在启动小红书笔记生成器UI...
echo.

REM 启动Python脚本
python start_ui.py

REM 如果脚本异常退出，暂停以查看错误信息
if errorlevel 1 (
    echo.
    echo 启动失败，请检查错误信息
    pause
)