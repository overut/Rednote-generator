# 小红书笔记生成器

一个功能强大的自动化小红书笔记生成工具，支持选题、文案和配图的AI辅助创作，提供命令行和Web两种使用方式。

## 功能特点

- **多模式支持**：提供命令行(CLI)和Web界面两种使用方式
- **AI驱动创作**：集成多种大语言模型和图像生成API，包括DeepSeek、Doubao、Jimeng等
- **完整笔记生成**：支持从选题、文案到配图的全流程自动化生成
- **批量处理**：支持批量生成多篇笔记，提高创作效率
- **自定义配置**：灵活的参数设置，满足不同创作需求
- **可扩展架构**：模块化设计，易于扩展新功能和支持新的API

## 技术栈

- **Python 3.8+**：项目基础语言
- **异步处理**：使用asyncio实现高效异步操作
- **API集成**：与多个AI服务提供商的API集成
- **Streamlit**：Web界面实现
- **YAML**：配置文件管理

## 项目结构

```
小红书笔记生成/
├── src/              # 源代码目录
│   ├── api/          # API客户端实现
│   ├── config/       # 配置管理
│   ├── generators/   # 生成器模块
│   ├── ui/           # 用户界面
│   └── utils/        # 工具函数
├── tests/            # 测试代码
├── config.yaml       # 配置文件
├── config.yaml.example # 配置文件示例
├── main.py           # 主程序入口
├── requirements.txt  # 依赖列表
├── run.bat           # Windows启动脚本
├── run.sh            # Linux/Mac启动脚本
└── README.md         # 项目说明文档
```

## 安装指南

### 前置要求

- Python 3.8或更高版本
- pip包管理器

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://your-repository-url/xiaohongshu-generator.git
   cd xiaohongshu-generator
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置API密钥**
   - 复制示例配置文件：`cp config.yaml.example config.yaml`
   - 编辑`config.yaml`文件，填入你的API密钥和配置信息

## 使用说明

### 命令行模式

项目提供了多种命令，满足不同的使用需求：

#### 1. 生成选题

```bash
python main.py --mode cli topic --category "生活分享" --count 5
```

#### 2. 生成文案

```bash
python main.py --mode cli content --topic "如何提高工作效率" --style "职场分享"
```

#### 3. 生成图片

```bash
python main.py --mode cli image --prompt "简约现代风格的工作桌面" --width 1080 --height 1920
```

#### 4. 生成完整笔记

```bash
python main.py --mode cli note --topic "如何提高工作效率" --category "职场分享" --style "实用干货" --image-count 2
```

#### 5. 批量生成笔记

```bash
python main.py --mode cli batch --count 3 --category "生活分享" --style "治愈系" --image-count 1
```

#### 6. 交互式模式

```bash
python main.py --mode cli interactive
```

### Web模式

启动Web界面：

```bash
python main.py --mode web --port 8501
```

然后在浏览器中访问 `http://localhost:8501` 即可使用Web界面。

## 配置说明

配置文件 `config.yaml` 包含以下主要配置项：

### API配置

配置各AI服务提供商的API信息：

```yaml
api:
  deepseek:
    base_url: "https://api.deepseek.com/v1"
    api_key: "your_api_key"
    model: "deepseek-chat"
  
  jimeng:
    base_url: "https://visual.volcengineapi.com"
    api_key: "your_access_key"
    secret_key: "your_secret_key"
    model: "jimeng_t2i_v40"
  # 其他API配置...
```

### 提示词配置

自定义生成选题、文案和图片的提示词模板：

```yaml
prompts:
  topic_generation: |
    请生成{count}个关于{category}的小红书选题...
  
  content_generation: |
    请为我的小红书账号生成一篇关于{topic}的笔记文案...
  
  image_generation: |
    请生成一张小红书配图，极简主义，扁平插画风格...
```

### 输出配置

设置输出目录和格式：

```yaml
output:
  image_dir: "output/images"
  content_dir: "output/content"
  note_format: "json"
```

## 核心功能详解

### 1. 选题生成

自动生成符合指定类别的小红书选题，包括标题、描述和标签。支持自定义选题数量和类别。

### 2. 文案生成

根据给定的选题和风格，生成结构化的小红书笔记文案，包含吸引人的标题、段落内容、互动引导和话题标签。

### 3. 图片生成

基于给定的提示词生成符合小红书风格的配图，支持自定义尺寸和风格。图片默认使用竖屏比例（9:16），适合社交媒体展示。

### 4. 笔记合成

将选题、文案和图片整合为完整的小红书笔记，支持保存为JSON或Markdown格式。

### 5. 批量处理

高效批量生成多篇笔记，适合内容创作者一次性生成多组素材。

## 故障排除

### 常见问题

1. **API调用失败**
   - 检查API密钥是否正确
   - 确认网络连接正常
   - 查看日志文件了解详细错误信息

2. **图片生成尺寸错误**
   - 确保使用的尺寸符合API要求，推荐使用1080x1920
   - 检查CLI参数和默认配置是否一致

3. **生成内容质量不佳**
   - 尝试调整提示词模板
   - 更改风格参数
   - 选择不同的API提供商

## 扩展开发

项目采用模块化设计，便于扩展和定制：

1. **添加新的API客户端**：在`src/api/`目录下创建新的客户端实现
2. **自定义生成逻辑**：修改`src/generators/`目录下的生成器实现
3. **扩展UI功能**：更新`src/ui/`目录下的界面代码

## 许可证

[MIT License](LICENSE)

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目。

## 联系方式

如有任何问题或建议，请通过以下方式联系：

- 项目维护者：[Your Name]
- Email：[your.email@example.com]