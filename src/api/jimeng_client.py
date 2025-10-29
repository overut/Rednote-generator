"""
即梦API客户端实现 - 基于火山引擎官方文档
"""

import json
import logging
import base64
import time
import hashlib
import hmac
import datetime
import random
from typing import Dict, Any, Optional
from .base_client import ImageGenerationClient


# 设置日志级别为DEBUG，确保详细信息被记录
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class JimengAPIClient(ImageGenerationClient):
    """即梦API客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化即梦API客户端
        
        Args:
            config: API配置
        """
        super().__init__(config)
        # 使用火山引擎的API地址
        self.base_url = config.get("base_url", "https://visual.volcengineapi.com")
        # 获取火山引擎的SecretKey
        self.secret_key = config.get("secret_key", "")
        # 获取火山引擎的AccessKey
        self.access_key = config.get("api_key", "")
        # 即梦API的模型名称
        self.model = config.get("model", "jimeng_t2i_v31")
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """
        生成响应（即梦API主要用于图片生成，此方法仅用于兼容基类）
        
        Args:
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            生成的响应文本
        """
        # 即梦API主要用于图片生成，此方法仅用于兼容基类
        # 实际使用中应该调用generate_image方法
        return "即梦API主要用于图片生成，请使用generate_image方法"
    
    async def generate_image(self, prompt: str, **kwargs) -> bytes:
        """
        生成图片
        
        Args:
            prompt: 图片生成提示词
            **kwargs: 其他参数，如width、height等
            
        Returns:
            生成的图片二进制数据
        """
        import aiohttp
        
        # 构建请求体
        req_key = kwargs.get("req_key", self.model)
        use_pre_llm = kwargs.get("use_pre_llm", True)
        seed = kwargs.get("seed", -1)
        width = kwargs.get("width", 1328)
        height = kwargs.get("height", 1328)
        
        print(f"[INFO] 准备生成图片: prompt={prompt[:50]}..., width={width}, height={height}, model={req_key}")
        logger.info(f"准备生成图片: prompt={prompt[:50]}..., width={width}, height={height}, model={req_key}")
        
        # 构建请求体
        body = {
            "req_key": req_key,
            "prompt": prompt,
            "use_pre_llm": use_pre_llm,
            "seed": seed,
            "width": width,
            "height": height
        }
        
        # 生成时间戳
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            "Host": "visual.volcengineapi.com",
            "X-Date": timestamp
        }
        
        # 计算请求体的SHA256哈希
        body_str = json.dumps(body)
        body_hash = hashlib.sha256(body_str.encode('utf-8')).hexdigest()
        headers['X-Content-Sha256'] = body_hash
        
        # 生成签名
        authorization = self._generate_signature(timestamp, headers, body_hash, "CVSync2AsyncSubmitTask")
        headers["Authorization"] = authorization
        
        # 发送请求 - 使用异步接口
        url = f"{self.base_url}?Action=CVSync2AsyncSubmitTask&Version=2022-08-31"
        
        try:
            async with aiohttp.ClientSession() as session:
                print(f"[INFO] 发送API请求到: {url}")
                logger.info(f"发送API请求到: {url}")
                # 不打印完整的headers和body，避免暴露敏感信息
                
                async with session.post(url, headers=headers, json=body) as response:
                    response_text = await response.text()
                    print(f"[INFO] API响应状态码: {response.status}")
                    print(f"[INFO] API响应内容: {response_text}")
                    logger.info(f"API响应状态码: {response.status}")
                    logger.debug(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        try:
                            result = json.loads(response_text)
                            print(f"[INFO] 即梦API提交任务: code={result.get('code')}, message={result.get('message')}")
                            logger.info(f"即梦API提交任务成功: code={result.get('code')}, message={result.get('message')}")
                            
                            # 获取任务ID
                            if "code" in result and result["code"] == 10000 and "data" in result and "task_id" in result["data"]:
                                task_id = result["data"]["task_id"]
                                print(f"[INFO] 获取到任务ID: {task_id}")
                                logger.info(f"任务ID: {task_id}")
                                return await self._get_task_result(task_id)
                            else:
                                error_msg = f"响应格式错误: code={result.get('code')}, message={result.get('message')}, data={result.get('data')}"
                                print(f"[ERROR] {error_msg}")
                                logger.error(error_msg)
                                # 尝试使用备用方案
                                print(f"[INFO] 尝试使用备用图片生成方案...")
                                return await self._generate_fallback_image(prompt, width, height)
                        except json.JSONDecodeError as e:
                            error_msg = f"解析JSON响应失败: {response_text}"
                            print(f"[ERROR] {error_msg}")
                            logger.error(error_msg)
                            # 尝试使用备用方案
                            print(f"[INFO] 尝试使用备用图片生成方案...")
                            return await self._generate_fallback_image(prompt, width, height)
                    else:
                        error_msg = f"API请求失败，状态码: {response.status}, 错误: {response_text}"
                        print(f"[ERROR] {error_msg}")
                        logger.error(error_msg)
                        # 尝试使用备用方案
                        print(f"[INFO] 尝试使用备用图片生成方案...")
                        return await self._generate_fallback_image(prompt, width, height)
        except Exception as e:
            error_msg = f"即梦API图片生成失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            logger.error(error_msg, exc_info=True)
            # 尝试使用备用方案
            print(f"[INFO] 尝试使用备用图片生成方案...")
            return await self._generate_fallback_image(prompt, width, height)
    
    async def _generate_fallback_image(self, prompt: str, width: int, height: int) -> bytes:
        """
        备用图片生成方案 - 当即梦API失败时使用
        
        Args:
            prompt: 图片生成提示词
            width: 图片宽度
            height: 图片高度
            
        Returns:
            占位图片的二进制数据
        """
        import aiohttp
        import io
        from PIL import Image, ImageDraw, ImageFont
        
        print(f"[INFO] 生成备用占位图片")
        
        try:
            # 使用PIL创建一个简单的占位图片
            image = Image.new('RGB', (width, height), color=(240, 240, 240))
            draw = ImageDraw.Draw(image)
            
            # 尝试加载字体，如果失败则使用默认字体
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except:
                font = ImageFont.load_default()
            
            # 添加文本
            text = "图片生成失败\n备用图片"
            text_position = (width // 2, height // 2)
            
            # 计算文本大小并居中
            lines = text.split('\n')
            total_text_height = len(lines) * 40
            start_y = text_position[1] - total_text_height // 2
            
            for i, line in enumerate(lines):
                # 简单估算文本宽度
                text_width = len(line) * 20
                x = text_position[0] - text_width // 2
                y = start_y + i * 40
                draw.text((x, y), line, fill=(100, 100, 100), font=font)
            
            # 添加提示信息
            prompt_preview = f"提示词: {prompt[:50]}..." if len(prompt) > 50 else f"提示词: {prompt}"
            draw.text((20, height - 50), prompt_preview, fill=(150, 150, 150), font=ImageFont.load_default())
            
            # 保存为二进制数据
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            
            print(f"[INFO] 备用图片生成成功，大小: {len(img_byte_arr.getvalue())}字节")
            return img_byte_arr.getvalue()
        except Exception as e:
            error_msg = f"生成备用图片失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            logger.error(error_msg)
            # 如果连备用图片都生成失败，返回一个最小的黑色图片
            image = Image.new('RGB', (100, 100), color=(0, 0, 0))
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            return img_byte_arr.getvalue()
    
    async def _get_task_result(self, task_id: str, max_retries: int = 10, retry_interval: int = 2) -> bytes:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）
            
        Returns:
            生成的图片二进制数据
        """
        import aiohttp
        import datetime
        import asyncio
        
        # 构建请求体
        body = {
            "req_key": self.model,
            "task_id": task_id
        }
        
        # 生成时间戳
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            "Host": "visual.volcengineapi.com",
            "X-Date": timestamp
        }
        
        # 计算请求体的SHA256哈希
        body_str = json.dumps(body)
        body_hash = hashlib.sha256(body_str.encode('utf-8')).hexdigest()
        headers['X-Content-Sha256'] = body_hash
        
        # 生成签名
        authorization = self._generate_signature(timestamp, headers, body_hash, "CVSync2AsyncGetResult")
        headers["Authorization"] = authorization
        
        # 发送请求
        url = f"{self.base_url}?Action=CVSync2AsyncGetResult&Version=2022-08-31"
        
        for i in range(max_retries):
            print(f"[INFO] 查询任务结果 (尝试 {i+1}/{max_retries}): task_id={task_id}")
            logger.info(f"查询任务结果 (尝试 {i+1}/{max_retries}): task_id={task_id}")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=body) as response:
                        response_text = await response.text()
                        print(f"[INFO] 查询任务结果响应状态码: {response.status}")
                        print(f"[INFO] 查询任务结果响应内容: {response_text}")
                        logger.info(f"查询任务结果响应状态码: {response.status}")
                        logger.debug(f"查询任务结果响应内容: {response_text}")
                        
                        if response.status == 200:
                            try:
                                result = json.loads(response_text)
                                print(f"[INFO] 查询任务结果: code={result.get('code')}, message={result.get('message')}")
                                logger.info(f"查询任务结果: code={result.get('code')}, message={result.get('message')}")
                                
                                # 检查任务状态
                                if "code" in result and result["code"] == 10000 and "data" in result:
                                    data = result["data"]
                                    if "status" in data:
                                        status = data["status"]
                                        status_msg = data.get("message", "")
                                        print(f"[INFO] 任务状态: {status}, 消息: {status_msg}")
                                        logger.info(f"任务状态: {status}, 消息: {status_msg}")
                                        
                                        if status == "done":  # 成功
                                            if "image_urls" in data and data["image_urls"] is not None:
                                                image_url = data["image_urls"][0]
                                                print(f"[INFO] 获取到图片URL: {image_url}")
                                                logger.info(f"获取到图片URL: {image_url}")
                                                # 下载图片并返回二进制数据
                                                return await self._download_image(image_url)
                                            elif "binary_data_base64" in data:
                                                # 如果返回的是base64编码，解码后返回二进制数据
                                                print(f"[INFO] 获取到base64编码图片")
                                                logger.info("获取到base64编码图片")
                                                return base64.b64decode(data["binary_data_base64"][0])
                                            else:
                                                error_msg = f"响应中未找到图片URL或base64数据: {list(data.keys())}"
                                                print(f"[ERROR] {error_msg}")
                                                logger.error(error_msg)
                                                # 如果在最后一次重试失败，使用备用方案
                                                if i == max_retries - 1:
                                                    return await self._generate_fallback_image("", 1328, 1328)
                                                raise ValueError(error_msg)
                                        elif status == 0:  # 处理中
                                            print(f"[INFO] 任务处理中，等待{retry_interval}秒后重试...")
                                            logger.info(f"任务处理中，等待{retry_interval}秒后重试...")
                                            await asyncio.sleep(retry_interval)
                                            continue
                                        else:  # 失败
                                            error_msg = data.get("message", "未知错误")
                                            print(f"[ERROR] 任务失败: {error_msg}")
                                            logger.error(f"任务失败: {error_msg}")
                                            # 如果在最后一次重试失败，使用备用方案
                                            if i == max_retries - 1:
                                                return await self._generate_fallback_image("", 1328, 1328)
                                            raise Exception(f"任务失败: {error_msg}")
                                    else:
                                        error_msg = f"响应中未找到任务状态字段: {list(data.keys())}"
                                        print(f"[ERROR] {error_msg}")
                                        logger.error(error_msg)
                                        # 如果在最后一次重试失败，使用备用方案
                                        if i == max_retries - 1:
                                            return await self._generate_fallback_image("", 1328, 1328)
                                        raise ValueError(error_msg)
                                else:
                                    error_msg = f"响应格式错误: code={result.get('code')}, message={result.get('message')}"
                                    print(f"[ERROR] {error_msg}")
                                    logger.error(error_msg)
                                    # 如果在最后一次重试失败，使用备用方案
                                    if i == max_retries - 1:
                                        return await self._generate_fallback_image("", 1328, 1328)
                                    raise ValueError(error_msg)
                            except json.JSONDecodeError as e:
                                error_msg = f"解析任务结果JSON失败: {response_text}"
                                print(f"[ERROR] {error_msg}")
                                logger.error(error_msg)
                                # 如果在最后一次重试失败，使用备用方案
                                if i == max_retries - 1:
                                    return await self._generate_fallback_image("", 1328, 1328)
                                raise Exception(error_msg) from e
                        else:
                            error_msg = f"查询任务结果API请求失败，状态码: {response.status}, 错误: {response_text}"
                            print(f"[ERROR] {error_msg}")
                            logger.error(error_msg)
                            # 如果在最后一次重试失败，使用备用方案
                            if i == max_retries - 1:
                                return await self._generate_fallback_image("", 1328, 1328)
                            raise Exception(error_msg)
            except Exception as e:
                print(f"[WARNING] 查询任务结果失败 (尝试 {i+1}/{max_retries}): {str(e)}")
                logger.warning(f"查询任务结果失败 (尝试 {i+1}/{max_retries}): {str(e)}")
                if i == max_retries - 1:
                    print(f"[ERROR] 任务处理超时，已重试{max_retries}次，最终失败: {str(e)}")
                    logger.error(f"任务处理超时，已重试{max_retries}次，最终失败: {str(e)}")
                    # 使用备用方案
                    return await self._generate_fallback_image("", 1328, 1328)
                print(f"[INFO] 等待{retry_interval}秒后重试...")
                logger.info(f"等待{retry_interval}秒后重试...")
                await asyncio.sleep(retry_interval)
        
        # 这里理论上不会走到，但为了安全，返回备用图片
        return await self._generate_fallback_image("", 1328, 1328)
    
    async def _download_image(self, url: str) -> bytes:
        """
        下载图片并返回二进制数据
        
        Args:
            url: 图片URL
            
        Returns:
            图片二进制数据
        """
        import aiohttp
        
        logger.info(f"开始下载图片: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30, allow_redirects=True) as response:
                    logger.info(f"图片下载响应状态码: {response.status}")
                    if response.status == 200:
                        # 获取内容类型
                        content_type = response.headers.get('Content-Type', '')
                        logger.info(f"图片内容类型: {content_type}")
                        
                        image_data = await response.read()
                        logger.info(f"成功下载图片，大小: {len(image_data)}字节")
                        return image_data
                    else:
                        error_text = await response.text()
                        error_msg = f"下载图片失败，状态码: {response.status}, 响应: {error_text}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
        except Exception as e:
            logger.error(f"下载图片失败: {str(e)}", exc_info=True)
            raise
    
    async def close(self):
        """关闭客户端连接（兼容性方法）"""
        pass
    
    def _generate_signature(self, timestamp: str, headers: Dict[str, str], body_hash: str, action: str) -> str:
        """
        生成火山引擎API签名
        
        Args:
            timestamp: 时间戳
            headers: 请求头
            body_hash: 请求体哈希
            action: API操作名称
            
        Returns:
            签名字符串
        """
        # 获取当前日期
        date_stamp = timestamp[:8]
        
        # 构建规范请求
        method = "POST"
        uri = "/"
        query_string = f"Action={action}&Version=2022-08-31"
        
        # 构建规范头部
        canonical_headers = []
        signed_headers = []
        
        # 添加需要签名的头
        for key in sorted(headers.keys()):
            lower_key = key.lower()
            if lower_key in ['content-type', 'content-md5', 'host'] or lower_key.startswith('x-'):
                canonical_headers.append(f"{lower_key}:{headers[key].strip()}\n")
                signed_headers.append(lower_key)
        
        canonical_headers_str = ''.join(canonical_headers)
        signed_headers_str = ';'.join(signed_headers)
        
        # 构建规范请求
        canonical_request = f"{method}\n{uri}\n{query_string}\n{canonical_headers_str}\n{signed_headers_str}\n{body_hash}"
        
        # 计算规范请求的哈希
        canonical_request_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        
        # 构建凭证作用域
        credential_scope = f"{date_stamp}/cn-north-1/cv/request"
        
        # 构建待签名字符串
        string_to_sign = f"HMAC-SHA256\n{timestamp}\n{credential_scope}\n{canonical_request_hash}"
        
        # 计算签名
        signing_key = self._signing_key(self.secret_key, date_stamp, "cn-north-1", "cv")
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # 构建授权头
        authorization = f"HMAC-SHA256 Credential={self.access_key}/{credential_scope}, SignedHeaders={signed_headers_str}, Signature={signature}"
        
        return authorization
    
    def _signing_key(self, key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
        """
        生成签名密钥
        
        Args:
            key: 密钥
            date_stamp: 日期戳
            region_name: 区域名称
            service_name: 服务名称
            
        Returns:
            签名密钥
        """
        k_date = hmac.new(key.encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region_name.encode('utf-8'), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service_name.encode('utf-8'), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, 'request'.encode('utf-8'), hashlib.sha256).digest()
        return k_signing