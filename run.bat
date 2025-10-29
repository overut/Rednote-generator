@echo off
chcp 65001 >nul
echo 小红书笔记生成器
echo ==================

:: 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python环境，请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

:: 检查依赖
echo 检查依赖...
pip show requests >nul 2>&1
if %errorlevel% neq 0 (
    echo 安装依赖中...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

:: 检查配置文件
if not exist "config.yaml" (
    if exist "config.yaml.example" (
        echo 复制配置文件...
        copy config.yaml.example config.yaml >nul
        echo 警告: 请编辑config.yaml文件，填入您的API密钥
    ) else (
        echo 错误: 未找到配置文件config.yaml或config.yaml.example
        pause
        exit /b 1
    )
)

:: 创建输出目录
if not exist "output" mkdir output
if not exist "output\images" mkdir output\images
if not exist "output\content" mkdir output\content
if not exist "logs" mkdir logs

:: 选择运行模式
echo.
echo 请选择运行模式:
echo 1. Web界面模式 (推荐)
echo 2. 命令行模式
echo 3. 退出
echo.
set /p mode="请输入选项 (1-3): "

if "%mode%"=="1" (
    echo.
    echo 启动Web界面...
    echo 浏览器将自动打开 http://localhost:8501
    echo.
    python main.py --mode web
) else if "%mode%"=="2" (
    echo.
    echo 启动命令行模式...
    echo.
    python main.py --mode cli
) else if "%mode%"=="3" (
    echo 退出程序
    exit /b 0
) else (
    echo 无效选项，退出程序
    exit /b 1
)

pause