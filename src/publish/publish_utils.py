import re
import os
import hashlib
import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import base64
from cryptography.fernet import Fernet
from src.utils.logger import logger


class PublishUtils:
    """发布工具类，提供发布相关的通用功能"""
    
    @staticmethod
    def extract_tags(content: str, max_tags: int = 5) -> List[str]:
        """从内容中提取标签
        
        Args:
            content: 笔记内容
            max_tags: 最大标签数量
            
        Returns:
            List[str]: 提取的标签列表
        """
        # 尝试从#标签格式中提取
        tags = re.findall(r'#([^\s#]+)', content)
        
        if len(tags) < max_tags:
            # 如果标签不足，尝试从内容中提取关键词（简单实现）
            # 这里可以使用更复杂的NLP方法改进
            # 移除标点和空白字符
            clean_content = re.sub(r'[\s\n\r\t\u3000]+', ' ', content)
            clean_content = re.sub(r'[，。！？；："\'（）\[\]{}【】《》、]+', ' ', clean_content)
            
            # 简单分词（按空格）
            words = clean_content.split()
            
            # 过滤掉太短的词和常见词
            common_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
            keywords = [word for word in words if len(word) >= 2 and word not in common_words and word not in tags]
            
            # 统计词频（简单实现）
            word_freq = {}
            for word in keywords:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # 取频率最高的词作为补充标签
            sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            for word, _ in sorted_keywords:
                if word not in tags:
                    tags.append(word)
                if len(tags) >= max_tags:
                    break
        
        # 确保标签不超过最大数量，并且去除重复
        tags = list(set(tags))[:max_tags]
        
        # 确保每个标签不超过10个字符（小红书限制）
        tags = [tag[:10] for tag in tags]
        
        return tags
    
    @staticmethod
    def preprocess_content(content: str) -> str:
        """预处理发布内容，确保符合平台规范
        
        Args:
            content: 原始内容
            
        Returns:
            str: 处理后的内容
        """
        # 处理None值和空值
        if content is None:
            return ""
        
        # 保留换行符，只替换其他多余空白字符
        # 将连续的空格、制表符、全角空格等替换为单个空格，但保留换行符
        content = re.sub(r'[ \t\u3000]+', ' ', content)
        # 将连续的换行符替换为单个换行符，避免过多空行
        content = re.sub(r'\n+', '\n', content)
        # 去除首尾空白，但保留中间换行
        content = content.strip()
        
        # 限制内容长度（小红书限制1000字）
        if len(content) > 1000:
            logger.warning(f"内容过长，已截断: {len(content)} -> 1000")
            content = content[:997] + '...'
        
        # 移除可能的敏感词（简单实现，实际应用中应使用更完善的敏感词库）
        sensitive_words = ['违规', '广告', '推广', '假货', '代购']
        for word in sensitive_words:
            content = content.replace(word, '*' * len(word))
        
        return content
    
    @staticmethod
    def validate_images(images: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """验证图片路径是否存在
        
        Args:
            images: 图片列表，每个元素包含path键
            
        Returns:
            List[Dict[str, str]]: 有效的图片列表
        """
        valid_images = []
        
        if not images:
            logger.warning("未提供图片")
            return valid_images
        
        for img in images:
            if isinstance(img, dict) and 'path' in img:
                path = img['path']
                if os.path.exists(path):
                    # 检查文件是否为图片
                    if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        valid_images.append(img)
                        logger.info(f"验证通过的图片: {path}")
                    else:
                        logger.warning(f"文件不是有效的图片格式: {path}")
                else:
                    logger.warning(f"图片文件不存在: {path}")
            else:
                logger.warning(f"无效的图片数据: {img}")
        
        logger.info(f"有效图片数量: {len(valid_images)}/{len(images)}")
        return valid_images
    
    @staticmethod
    async def simulate_user_typing(page, selector, text, min_delay=30, max_delay=100):
        """异步模拟用户打字输入，更加真实地模拟人类输入行为
        
        Args:
            page: Playwright页面实例
            selector: 目标元素选择器
            text: 要输入的文本内容
            min_delay: 最小延迟时间（毫秒）
            max_delay: 最大延迟时间（毫秒）
        """
        import random
        import asyncio
        import re
        
        # 确保文本不为空且为字符串类型
        if not text or not isinstance(text, str):
            return
        
        # 尝试获取元素并确保其可见
        element = await page.query_selector(selector)
        if not element:
            logger.warning(f"无法找到元素: {selector}")
            return
        
        # 尝试点击元素以获取焦点
        try:
            await element.click()
        except Exception as e:
            logger.warning(f"点击元素失败: {e}")
        
        # 分段输入文本，提高可靠性
        chunks = split_text_for_typing(text)
        
        for chunk in chunks:
            # 对于每个段落，按字符逐个输入
            for char in chunk:
                try:
                    # 特殊处理换行符
                    if char == '\n':
                        # 使用键盘按下回车键来创建换行
                        await page.keyboard.press('Enter')
                    else:
                        # 输入单个字符
                        await page.type(selector, char, delay=random.randint(min_delay, max_delay))
                except Exception as e:
                    # 如果直接type失败，尝试使用JavaScript输入
                    try:
                        # 特殊处理换行符
                        if char == '\n':
                            await page.evaluate(
                                '''(params) => {
                                    const { selector } = params;
                                    const element = document.querySelector(selector);
                                    if (element) {
                                        // 创建并输入换行符
                                        const event = new KeyboardEvent('keydown', {
                                            key: 'Enter',
                                            code: 'Enter',
                                            keyCode: 13,
                                            which: 13,
                                            bubbles: true
                                        });
                                        element.dispatchEvent(event);
                                        
                                        // 对于contenteditable元素，还需要插入换行符
                                        if (element.isContentEditable) {
                                            document.execCommand('insertLineBreak', false, null);
                                        }
                                        
                                        return true;
                                    }
                                    return false;
                                }''',
                                {"selector": selector}
                            )
                        else:
                            await page.evaluate(
                                '''(params) => {
                                    const { selector, char } = params;
                                    const element = document.querySelector(selector);
                                    if (element) {
                                        if (element.tagName.toLowerCase() === 'input' || element.tagName.toLowerCase() === 'textarea') {
                                            element.value += char;
                                        } else if (element.isContentEditable) {
                                            document.execCommand('insertText', false, char);
                                        }
                                        element.dispatchEvent(new Event('input', { bubbles: true }));
                                        return true;
                                    }
                                    return false;
                                }''',
                                {"selector": selector, "char": char}
                            )
                    except Exception as js_error:
                        logger.warning(f"JavaScript输入字符失败: {js_error}")
                
                # 随机模拟用户思考和停顿
                if random.random() < 0.1:  # 10%的概率稍作停顿
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                elif random.random() < 0.02:  # 2%的概率稍长时间停顿
                    await asyncio.sleep(random.uniform(0.5, 1.2))
            
            # 每个段落之间添加停顿
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
        # 最后触发一次input事件确保内容被正确处理
        try:
            await page.evaluate(
                '''(params) => {
                    const { selector } = params;
                    const element = document.querySelector(selector);
                    if (element) {
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }''',
                {"selector": selector}
            )
        except:
            pass
        
        logger.info(f"模拟用户输入完成，输入了{len(text)}个字符")
        return True
    
    # 兼容性函数：保持原有接口但内部调用异步版本
    def simulate_user_typing_sync(page, selector, text):
        """同步版本的模拟用户打字输入，保持向后兼容
        
        Args:
            page: Playwright页面实例
            selector: 目标元素选择器
            text: 要输入的文本内容
        """
        import asyncio
        
        # 创建一个事件循环并运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(simulate_user_typing(page, selector, text))
        finally:
            loop.close()
    
    # 为保持向后兼容，将原函数名指向同步版本
    simulate_user_typing = simulate_user_typing_sync
    
    
    def split_text_for_typing(text):
        """将文本分割成适合打字模拟的段落
        
        Args:
            text: 输入文本
        
        Returns:
            list: 分割后的文本段落列表，保留换行符
        """
        import re
        
        # 确保输入为字符串
        if not isinstance(text, str):
            return [str(text)]
        
        # 按换行符分割为段落，但保留换行符作为分隔符
        # 使用re.split捕获分隔符，这样换行符会保留在结果中
        parts = re.split('(\n+)', text)
        
        # 重新组合文本，确保换行符与前面的内容在一起
        result = []
        current_chunk = ""
        
        for i, part in enumerate(parts):
            if i % 2 == 0:  # 文本内容
                current_chunk += part
            else:  # 换行符
                current_chunk += part  # 将换行符添加到当前块
                # 如果当前块不为空，添加到结果中
                if current_chunk.strip():
                    result.append(current_chunk)
                current_chunk = ""
        
        # 添加最后一个块（如果存在）
        if current_chunk.strip():
            result.append(current_chunk)
        
        # 进一步处理过长的段落
        final_result = []
        for chunk in result:
            # 如果段落过长，进一步分割成更小的块，但保留换行符
            if len(chunk) > 200:
                # 按句子分割（粗略实现），但保留换行符
                sentences = re.split(r'(。|！|？|\.|!|\?|\n+)', chunk)
                current_part = ''
                
                for i in range(0, len(sentences), 2):
                    if i+1 < len(sentences):
                        sentence = sentences[i] + sentences[i+1]  # 包含标点或换行符
                    else:
                        sentence = sentences[i]
                    
                    # 如果当前部分加上新句子超过150字符，则分割
                    if len(current_part + sentence) > 150 and current_part:
                        final_result.append(current_part)
                        current_part = sentence
                    else:
                        current_part += sentence
                
                if current_part:
                    final_result.append(current_part)
            else:
                final_result.append(chunk)
        
        return final_result
    
    @staticmethod
    def generate_note_id() -> str:
        """生成笔记唯一标识符
        
        Returns:
            str: 笔记ID
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
        return f"note_{timestamp}_{random_part}"
    
    @staticmethod
    def create_cookies_dir(base_dir: str = None) -> str:
        """创建cookies存储目录
        
        Args:
            base_dir: 基础目录，如果不提供则使用默认目录
            
        Returns:
            str: cookies目录路径
        """
        if not base_dir:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'accounts')
        
        cookies_dir = os.path.join(base_dir, '.cookies')
        os.makedirs(cookies_dir, exist_ok=True)
        
        # 创建.gitignore文件，防止cookies被提交
        gitignore_path = os.path.join(base_dir, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write('.cookies/\n')
        
        return cookies_dir
    
    @staticmethod
    def encrypt_credentials(credentials: Dict[str, str], key: str = None) -> str:
        """加密账号凭证
        
        Args:
            credentials: 凭证字典
            key: 加密密钥
            
        Returns:
            str: 加密后的字符串
        """
        try:
            # 如果未提供密钥，生成一个新的
            if not key:
                key = Fernet.generate_key()
            else:
                # 确保密钥长度正确（使用base64编码）
                key = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
            
            f = Fernet(key)
            encrypted = f.encrypt(json.dumps(credentials).encode())
            
            # 返回加密数据和密钥（实际应用中密钥应单独存储）
            return base64.urlsafe_b64encode(encrypted).decode()
            
        except Exception as e:
            logger.error(f"加密凭证失败: {e}")
            raise
    
    @staticmethod
    def decrypt_credentials(encrypted_data: str, key: str) -> Dict[str, str]:
        """解密账号凭证
        
        Args:
            encrypted_data: 加密数据
            key: 解密密钥
            
        Returns:
            Dict[str, str]: 解密后的凭证
        """
        try:
            # 确保密钥长度正确
            key = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
            
            f = Fernet(key)
            decrypted = f.decrypt(base64.urlsafe_b64decode(encrypted_data)).decode()
            
            return json.loads(decrypted)
            
        except Exception as e:
            logger.error(f"解密凭证失败: {e}")
            raise


# json模块已在文件顶部导入

# 导出工具实例
publish_utils = PublishUtils()