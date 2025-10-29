# 小红书笔记生成器

一个基于AI的小红书笔记自动生成工具，支持选题生成、文案撰写和图片生成功能。

## 功能特点

- 🎯 **智能选题生成**：基于Deepseek API生成热门选题
- ✍️ **高质量文案撰写**：使用Deepseek或豆包API生成吸引人的文案
- 🖼️ **精美图片生成**：集成即梦和通义万象API生成配图
- ⚙️ **灵活配置**：支持自定义提示词和API配置
- 🚀 **一键生成**：支持一键生成完整小红书笔记
- 📱 **多种使用方式**：提供命令行和Web界面两种使用方式
- 📦 **批量生成**：支持批量生成多篇笔记

## 系统架构

```
小红书笔记生成器/
├── src/                     # 源代码目录
│   ├── config/             # 配置管理模块
│   │   ├── __init__.py
│   │   └── config_manager.py
│   ├── api/                # API客户端模块
│   │   ├── __init__.py
│   │   ├── base_client.py  # API客户端基类
│   │   ├── deepseek_client.py  # Deepseek API客户端
│   │   ├── doubao_client.py    # 豆包API客户端
│   │   ├── jimeng_client.py    # 即梦API客户端
│   │   └── tongyi_client.py    # 通义万象API客户端
│   ├── generators/         # 生成器模块
│   │   ├── __init__.py
│   │   ├── topic_generator.py  # 选题生成器
│   │   ├── content_generator.py  # 文案生成器
│   │   ├── image_generator.py   # 图片生成器
│   │   └── note_generator.py    # 笔记生成器
│   ├── ui/                 # 用户界面模块
│   │   ├── __init__.py
│   │   ├── streamlit_ui.py     # Streamlit Web界面
│   │   └── cli_ui.py           # 命令行界面
│   └── utils/              # 工具模块
│       ├── __init__.py
│       ├── logger.py       # 日志工具
│       └── utils.py        # 通用工具函数
├── tests/                  # 测试目录
│   ├── __init__.py
│   ├── test_config_manager.py
│   ├── test_api_clients.py
│   ├── test_generators.py
│   └── test_utils.py
├── output/                 # 输出目录
│   ├── images/             # 生成的图片
│   └── content/            # 生成的文案
├── logs/                   # 日志目录
├── config.yaml             # 配置文件
├── config.yaml.example     # 配置文件示例
├── requirements.txt        # 依赖包列表
├── main.py                 # 主程序入口
├── run.bat                 # Windows运行脚本
├── run.sh                  # Linux/macOS运行脚本
├── test_setup.py           # 项目设置验证脚本
└── README.md               # 项目说明文档
```

## 安装与配置

### 环境要求

- Python 3.8+
- 各AI服务的API密钥

### 快速开始

#### Windows用户

1. 双击运行 `run.bat` 脚本
2. 按照提示选择运行模式
3. 编辑生成的 `config.yaml` 文件，填入API密钥

#### Linux/macOS用户

1. 在终端中运行：
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
2. 按照提示选择运行模式
3. 编辑生成的 `config.yaml` 文件，填入API密钥

### 手动安装

1. 克隆项目

```bash
git clone https://github.com/yourusername/xiaohongshu-generator.git
cd xiaohongshu-generator
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置API密钥

复制配置文件模板并根据需要修改：

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml` 文件，填入你的API密钥：

```yaml
api:
  deepseek:
    base_url: "https://api.deepseek.com/v1"
    api_key: "your_deepseek_api_key"
    model: "deepseek-chat"
    timeout: 30
    max_retries: 3
  
  doubao:
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    api_key: "your_doubao_api_key"
    model: "doubao-pro-4k"
    timeout: 30
    max_retries: 3
  
  jimeng:
    base_url: "https://jimeng.jianying.com/api/v1"
    api_key: "your_jimeng_api_key"
    model: "jimeng-v1"
    timeout: 30
    max_retries: 3
  
  tongyi:
    base_url: "https://dashscope.aliyuncs.com/api/v1"
    api_key: "your_tongyi_api_key"
    model: "wanx-v1"
    timeout: 30
    max_retries: 3

prompts:
  topic_generation: |
    请生成{count}个关于{category}的小红书选题，要求：
    1. 选题要吸引人，符合小红书平台特点
    2. 每个选题包含标题、简短描述和相关标签
    3. 格式如下：
    1. 标题：xxx
    描述：xxx
    标签：#xxx #xxx
    
  content_generation: |
    请为以下小红书选题撰写文案，要求：
    1. 标题吸引人，使用表情符号
    2. 正文内容详细，分段清晰
    3. 结尾有互动引导
    4. 包含相关标签
    5. 格式如下：
    标题：xxx
    正文：xxx
    标签：#xxx #xxx
    
  image_generation: |
    请生成一张关于{topic}的小红书配图，要求：
    1. 风格清新、美观
    2. 色彩鲜明，适合小红书平台
    3. 主题明确，与文案内容相符

output:
  image_dir: "output/images"
  content_dir: "output/content"
  note_format: "json"
```

## 使用方法

### 1. Web界面模式（推荐）

```bash
python main.py --mode web --port 8501
```

然后在浏览器中打开 `http://localhost:8501` 即可使用Web界面。

### 2. 命令行模式

#### 生成选题

```bash
python main.py --mode cli generate-topic --category 美妆 --count 5
```

#### 生成文案

```bash
python main.py --mode cli generate-content --topic "夏日护肤必备单品推荐"
```

#### 生成图片

```bash
python main.py --mode cli generate-image --prompt "夏日护肤产品展示图" --api jimeng
```

#### 生成完整笔记

```bash
python main.py --mode cli generate-note --category 美妆 --generate-image
```

#### 批量生成笔记

```bash
python main.py --mode cli batch-generate --category 美妆 --count 5 --generate-image
```

## API支持

### 文本生成API

- **Deepseek**：用于选题和文案生成
  - 官网：https://www.deepseek.com/
  - API文档：https://platform.deepseek.com/api-docs/

- **豆包**：用于文案生成
  - 官网：https://www.doubao.com/
  - API文档：https://www.volcengine.com/docs/82379

### 图片生成API

- **即梦**：用于图片生成
  - 官网：https://jimeng.jianying.com/
  - API文档：https://jimeng.jianying.com/tech-doc

- **通义万象**：用于图片生成
  - 官网：https://tongyi.aliyun.com/wanxiang/
  - API文档：https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-wanxiang-image-generation-api

## 开发与测试

### 验证项目设置

```bash
python test_setup.py
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_config_manager.py

# 运行测试并生成覆盖率报告
python -m pytest --cov=src tests/
```

### 项目结构说明

- **config模块**：负责配置文件的加载、更新和保存
- **api模块**：提供各种API的客户端封装
- **generators模块**：实现选题、文案、图片和笔记的生成逻辑
- **ui模块**：提供用户界面，包括命令行和Web界面
- **utils模块**：提供日志、工具函数等通用功能

## 常见问题

### 1. API密钥如何获取？

- **Deepseek**：注册Deepseek账号后在控制台获取
- **豆包**：注册火山引擎账号后创建应用获取
- **即梦**：注册即梦账号后在开发者中心获取
- **通义万象**：注册阿里云账号后开通DashScope服务获取

### 2. 生成的图片质量不高怎么办？

可以尝试以下方法：
- 调整提示词，更详细地描述图片需求
- 尝试不同的图片生成API
- 在配置文件中调整图片生成参数

### 3. 如何自定义提示词？

编辑 `config.yaml` 文件中的 `prompts` 部分，根据需要修改提示词模板。

### 4. 如何批量生成大量笔记？

使用命令行模式的批量生成功能：
```bash
python main.py --mode cli batch-generate --category 美妆 --count 20 --generate-image
```

## 注意事项

1. 请确保API密钥的安全性，不要将配置文件提交到版本控制系统
2. 使用图片生成功能时，请注意API调用频率限制
3. 生成的内容请进行人工审核，确保符合平台规范
4. 部分API可能有使用限制或收费，请查看相应服务的定价策略

## 更新日志

### v1.0.0 (2023-XX-XX)

- 初始版本发布
- 支持选题、文案和图片生成
- 提供Web和命令行两种界面
- 集成Deepseek、豆包、即梦和通义万象API

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！如果您有任何问题或建议，请随时联系我们。