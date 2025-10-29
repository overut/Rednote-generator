"""
通用工具函数实现
"""

import os
import json
import yaml
import uuid
import re
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image


def load_config(file_path: str) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        file_path: 配置文件路径
        
    Returns:
        配置字典
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"配置文件不存在: {file_path}")
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        if file_ext == '.json':
            return json.load(f)
        elif file_ext in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {file_ext}")


def save_config(config: Dict[str, Any], file_path: str) -> None:
    """
    保存配置文件
    
    Args:
        config: 配置字典
        file_path: 配置文件路径
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        if file_ext == '.json':
            json.dump(config, f, ensure_ascii=False, indent=2)
        elif file_ext in ['.yaml', '.yml']:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"不支持的配置文件格式: {file_ext}")


def validate_config(config: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    验证配置
    
    Args:
        config: 配置字典
        schema: 验证模式
        
    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []
    
    def _validate_recursive(data: Dict[str, Any], schema: Dict[str, Any], path: str = ""):
        for key, value_schema in schema.items():
            current_path = f"{path}.{key}" if path else key
            
            # 检查必需字段
            if isinstance(value_schema, dict) and value_schema.get("required", False):
                if key not in data:
                    errors.append(f"缺少必需字段: {current_path}")
                    continue
            
            # 如果字段不存在但不是必需的，跳过验证
            if key not in data:
                continue
            
            value = data[key]
            
            # 检查类型
            if "type" in value_schema:
                expected_type = value_schema["type"]
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"字段 {current_path} 应为字符串类型")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"字段 {current_path} 应为数字类型")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"字段 {current_path} 应为整数类型")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"字段 {current_path} 应为布尔类型")
                elif expected_type == "array" and not isinstance(value, list):
                    errors.append(f"字段 {current_path} 应为数组类型")
                elif expected_type == "object" and not isinstance(value, dict):
                    errors.append(f"字段 {current_path} 应为对象类型")
            
            # 检查嵌套对象
            if isinstance(value_schema, dict) and "properties" in value_schema:
                if not isinstance(value, dict):
                    errors.append(f"字段 {current_path} 应为对象类型")
                else:
                    _validate_recursive(value, value_schema["properties"], current_path)
    
    _validate_recursive(config, schema)
    
    return len(errors) == 0, errors


def format_prompt(template: str, **kwargs) -> str:
    """
    格式化提示词
    
    Args:
        template: 提示词模板
        **kwargs: 格式化参数
        
    Returns:
        格式化后的提示词
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"提示词模板缺少参数: {e}")


def extract_hashtags(text: str) -> List[str]:
    """
    从文本中提取话题标签
    
    Args:
        text: 文本内容
        
    Returns:
        话题标签列表
    """
    # 匹配 #标签 格式
    pattern = r'#([^\s#]+)'
    matches = re.findall(pattern, text)
    
    # 返回完整标签格式
    return [f"#{tag}" for tag in matches]


def extract_keywords(text: str, max_count: int = 10) -> List[str]:
    """
    从文本中提取关键词
    
    Args:
        text: 文本内容
        max_count: 最大关键词数量
        
    Returns:
        关键词列表
    """
    # 简单的关键词提取，实际项目中可以使用更复杂的NLP技术
    # 这里使用词频统计的方法
    
    # 移除标点符号和特殊字符
    cleaned_text = re.sub(r'[^\w\s]', ' ', text)
    
    # 分词
    words = cleaned_text.split()
    
    # 过滤停用词和短词
    stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
    filtered_words = [word for word in words if len(word) > 1 and word not in stop_words]
    
    # 统计词频
    word_freq = {}
    for word in filtered_words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # 按词频排序
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    
    # 返回前N个关键词
    return [word for word, freq in sorted_words[:max_count]]


def generate_unique_id(prefix: str = "") -> str:
    """
    生成唯一ID
    
    Args:
        prefix: ID前缀
        
    Returns:
        唯一ID
    """
    unique_id = str(uuid.uuid4())
    return f"{prefix}_{unique_id}" if prefix else unique_id


def ensure_directory_exists(directory: str) -> None:
    """
    确保目录存在
    
    Args:
        directory: 目录路径
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件扩展名（包含点号）
    """
    return os.path.splitext(file_path)[1].lower()


def resize_image(
    image_path: str,
    output_path: str,
    width: int,
    height: int,
    maintain_aspect_ratio: bool = True
) -> None:
    """
    调整图片大小
    
    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径
        width: 目标宽度
        height: 目标高度
        maintain_aspect_ratio: 是否保持宽高比
    """
    with Image.open(image_path) as img:
        if maintain_aspect_ratio:
            # 计算保持宽高比的新尺寸
            img_ratio = img.width / img.height
            target_ratio = width / height
            
            if img_ratio > target_ratio:
                # 以宽度为准
                new_height = int(width / img_ratio)
                new_width = width
            else:
                # 以高度为准
                new_width = int(height * img_ratio)
                new_height = height
            
            img = img.resize((new_width, new_height), Image.LANCZOS)
        else:
            img = img.resize((width, height), Image.LANCZOS)
        
        # 确保输出目录存在
        ensure_directory_exists(os.path.dirname(output_path))
        
        # 保存图片
        img.save(output_path)


def crop_to_aspect_ratio(
    image_path: str,
    output_path: str,
    target_ratio: float = 9/16  # 小红书常用比例 9:16
) -> None:
    """
    裁剪图片到指定宽高比
    
    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径
        target_ratio: 目标宽高比 (宽度/高度)
    """
    with Image.open(image_path) as img:
        width, height = img.size
        current_ratio = width / height
        
        if current_ratio > target_ratio:
            # 图片太宽，需要裁剪宽度
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            right = left + new_width
            img = img.crop((left, 0, right, height))
        elif current_ratio < target_ratio:
            # 图片太高，需要裁剪高度
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            bottom = top + new_height
            img = img.crop((0, top, width, bottom))
        
        # 确保输出目录存在
        ensure_directory_exists(os.path.dirname(output_path))
        
        # 保存图片
        img.save(output_path)