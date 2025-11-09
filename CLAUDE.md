# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Xiaohongshu (Little Red Book) note generation system that uses multiple AI APIs to automatically generate complete social media posts including topics, content, and images. The system is built with Python and supports both CLI and Web interfaces.

## Key Commands

### Running the Application

**CLI Mode (Interactive):**
```bash
python main.py --mode cli interactive
```

**CLI Mode (Generate specific content):**
```bash
# Generate topics
python main.py --mode cli topic --category "生活分享" --count 5

# Generate content
python main.py --mode cli content --topic "如何提高工作效率" --style "职场分享"

# Generate images
python main.py --mode cli image --prompt "简约现代风格的工作桌面" --width 1080 --height 1920

# Generate complete note
python main.py --mode cli note --topic "如何提高工作效率" --category "职场分享" --style "实用干货" --image-count 2

# Batch generate notes
python main.py --mode cli batch --count 3 --category "生活分享" --style "治愈系" --image-count 1
```

**Web Mode:**
```bash
python main.py --mode web --port 8501
```

### Testing

Run tests using pytest (if configured):
```bash
python -m pytest tests/
```

Run specific test files:
```bash
python test_setup.py
python -m pytest tests/test_api_clients.py
python -m pytest tests/test_generators.py
```

### Installation

```bash
pip install -r requirements.txt
```

## Architecture Overview

### Core Module Structure

The system follows a layered architecture with clear separation of concerns:

1. **API Layer** (`src/api/`): Handles all external API integrations
   - `base_client.py`: Abstract base classes for API clients with retry logic and session management
   - `deepseek_client.py`: DeepSeek API for text generation (topics and content)
   - `doubao_client.py`: Doubao API for alternative text generation
   - `jimeng_client.py`: Jimeng API for image generation (supports v4)
   - `tongyi_client.py`: Tongyi Wanxiang API for alternative image generation

2. **Generator Layer** (`src/generators/`): Business logic for content generation
   - `topic_generator.py`: Generates Xiaohongshu post topics based on categories
   - `content_generator.py`: Creates post content (title, body, hashtags, CTA)
   - `image_generator.py`: Generates images based on content using configured prompts
   - `note_generator.py`: Orchestrates the complete note generation workflow

3. **Configuration Layer** (`src/config/`): Centralized configuration management
   - `config_manager.py`: Loads and manages YAML configuration including API keys, prompts, and output settings

4. **UI Layer** (`src/ui/`): User interfaces
   - `cli_ui.py`: Command-line interface with multiple subcommands
   - `streamlit_ui.py`: Web-based interface using Streamlit

5. **Utilities** (`src/utils/`): Common utilities
   - `logger.py`: Logging configuration
   - `utils.py`: Helper functions

### Data Flow

The typical note generation flow:
```
User Input → NoteGenerator → TopicGenerator (if no topic provided)
                           → ContentGenerator (with topic)
                           → ImageGenerator (with content)
                           → Save to output/content/ (JSON)
```

### Key Design Patterns

- **Async/Await**: All API calls use asyncio for non-blocking I/O
- **Retry Logic**: API clients use tenacity for automatic retry with exponential backoff
- **Factory Pattern**: Generators select appropriate API clients based on provider configuration
- **Dataclasses**: Structured data models (Topic, Content, ImageResult, NoteResult)
- **Configuration-Driven**: All prompts and API settings are externalized in `config.yaml`

## Configuration

### API Configuration (`config.yaml`)

The system requires API keys for:
- **deepseek**: Text generation (topics and content)
- **doubao**: Alternative text generation
- **jimeng**: Image generation (currently using v4 model: `jimeng_t2i_v40`)
- **tongyi**: Alternative image generation

Each API section includes:
- `base_url`: API endpoint
- `api_key`: Authentication key (jimeng also requires `secret_key`)
- `model`: Model identifier
- `timeout`: Request timeout in seconds
- `max_retries`: Number of retry attempts

### Prompt Configuration

Three main prompt templates in `config.yaml`:
- `topic_generation`: Template for generating post topics
- `content_generation`: Template for generating post content (includes detailed formatting requirements)
- `image_generation`: Template for generating images (specifies minimalist flat illustration style)

All prompts support variable substitution (e.g., `{topic}`, `{category}`, `{style}`, `{title}`).

### Output Configuration

- `image_dir`: Directory for generated images (default: `output/images`)
- `content_dir`: Directory for generated content JSON files (default: `output/content`)
- `note_format`: Output format (currently JSON)

## Important Implementation Details

### Async Session Management

All API clients inherit from `BaseAPIClient` which manages aiohttp sessions:
- Sessions are created lazily and reused
- Automatic cleanup in `close()` method
- Retry logic with exponential backoff (3 attempts, 4-10 second wait)

### Image Generation

The `ImageGenerator` uses the prompt template from config to create images:
- Extracts Chinese text from titles (removes non-Chinese elements)
- Applies minimalist flat illustration style
- Default aspect ratio: 9:16 (vertical for mobile)
- Images saved with UUID-based filenames

### Content Generation

The `ContentGenerator` produces structured content:
- Title (plain text, no emojis)
- Body (with emojis, formatting, bullet points)
- Hashtags (5-8 tags: broad, specific, and personalized)
- Call-to-action (engagement prompt)

### Note Persistence

Generated notes are saved as JSON files in `output/content/`:
- Filename format: `{uuid[:8]}_{title}.json`
- Includes all metadata (providers, timestamps, prompts)
- Images referenced by path

## Development Workflow

### Adding a New API Provider

1. Create new client in `src/api/` inheriting from `BaseAPIClient` or `ImageGenerationClient`
2. Implement required abstract methods (`generate_response` or `generate_image`)
3. Add configuration section in `config.yaml`
4. Update generator to support new provider option
5. Add tests in `tests/test_api_clients.py`

### Modifying Prompts

Edit the prompt templates in `config.yaml`. The system uses Python string formatting with named placeholders:
- Topic generation: `{count}`, `{category}`
- Content generation: `{topic}`, `{style}`
- Image generation: `{title}`, `{topic}`

### Batch Processing

The `NoteGenerator.batch_generate_notes()` method:
1. Generates all topics first
2. Iterates through topics sequentially
3. Continues on individual failures (logged but not fatal)
4. Returns list of successfully generated notes

## Common Issues

### API Key Configuration

Ensure all required API keys are set in `config.yaml`. The system will fail gracefully with clear error messages if keys are missing or invalid.

### Image Generation Failures

Image generation may fail due to:
- API rate limits
- Invalid prompts
- Network timeouts

The system logs errors but continues processing other images/notes in batch mode.

### Async Context

When working with generators, always use `await` for async methods:
```python
note = await note_generator.generate_note(topic="example")
```

## File Naming Conventions

- Generated content: `{uuid[:8]}_{title}.json` in `output/content/`
- Generated images: `{uuid}.png` in `output/images/`
- Logs: `generator_{script_name}.log` in `logs/`
