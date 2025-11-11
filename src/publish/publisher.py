import asyncio
import os
import re
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from src.config.config_manager import ConfigManager
from src.publish.browser_manager import BrowserManager, get_browser_manager
from src.publish.publish_utils import publish_utils
from src.publish.login_optimizer import LoginOptimizer, get_login_optimizer
from src.publish.account_manager import AccountManager
from src.utils.logger import logger


@dataclass
class PublishResult:
    """发布结果数据类"""
    note_id: str  # 笔记ID
    status: str  # 发布状态：success, failed, pending
    publish_url: str = None  # 发布后的笔记链接
    error_message: str = None  # 错误信息
    publish_time: datetime = None  # 发布时间
    platform_data: Dict[str, Any] = None  # 平台返回的额外数据


@dataclass
class PublishConfig:
    """发布配置数据类"""
    account_name: str  # 账号名称
    cookies_file: str  # cookies文件路径
    headless_mode: bool = False  # 是否无头模式
    retry_count: int = 3  # 失败重试次数
    retry_interval: int = 5  # 重试间隔（秒）
    enable_comments: bool = True  # 是否允许评论
    sync_to_other_platforms: bool = False  # 是否同步到其他平台


class XiaohongshuPublisher:
    """小红书发布器，负责自动发布笔记到小红书平台"""
    
    def __init__(self, config_manager: ConfigManager):
        """初始化小红书发布器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.browser_manager: BrowserManager = get_browser_manager()
        self.login_optimizer: LoginOptimizer = get_login_optimizer()
        self.account_manager = AccountManager()
        self.publish_config = self._load_publish_config()
        self.is_initialized = False
    
    def _load_publish_config(self) -> PublishConfig:
        """加载发布配置
        
        Returns:
            PublishConfig: 发布配置对象
        """
        try:
            config = self.config_manager.get_config()
            publish_config = config.get('publish', {})
            
            # 获取cookies目录
            cookies_dir = publish_utils.create_cookies_dir()
            
            return PublishConfig(
                account_name=publish_config.get('account_name', 'default'),
                cookies_file=os.path.join(cookies_dir, f"{publish_config.get('account_name', 'default')}.json"),
                headless_mode=publish_config.get('headless_mode', False),
                retry_count=publish_config.get('retry_count', 3),
                retry_interval=publish_config.get('retry_interval', 5),
                enable_comments=publish_config.get('enable_comments', True),
                sync_to_other_platforms=publish_config.get('sync_to_other_platforms', False)
            )
        except Exception as e:
            logger.error(f"加载发布配置失败: {e}")
            # 返回默认配置
            return PublishConfig(
                account_name='default',
                cookies_file=os.path.join(publish_utils.create_cookies_dir(), 'default.json')
            )
    
    async def _initialize(self) -> bool:
        """初始化发布器
        
        Returns:
            bool: 是否初始化成功
        """
        try:
            # 确保浏览器管理器存在
            if not hasattr(self, 'browser_manager') or self.browser_manager is None:
                from src.publish.browser_manager import get_browser_manager
                logger.info("获取浏览器管理器实例")
                self.browser_manager = get_browser_manager()
                
                if self.browser_manager is None:
                    logger.error("获取浏览器管理器失败: 返回None")
                    return False
                    
                logger.info("成功获取浏览器管理器实例")
            
            # 检查浏览器管理器是否已初始化
            if not hasattr(self.browser_manager, 'is_initialized') or not self.browser_manager.is_initialized:
                logger.info("初始化浏览器")
                await self.browser_manager.init_browser(self.publish_config.headless_mode)
            
            # 初始化登录优化器
            if not hasattr(self, 'login_optimizer') or self.login_optimizer is None:
                from src.publish.login_optimizer import get_login_optimizer
                logger.info("获取登录优化器实例")
                self.login_optimizer = get_login_optimizer()
                
                if self.login_optimizer is None:
                    logger.error("获取登录优化器失败: 返回None")
                    return False
                    
                logger.info("成功获取登录优化器实例")
            
            # 初始化登录优化器
            await self.login_optimizer.initialize(self.browser_manager)
            
            # 加载cookies
            logger.info("加载cookies")
            await self.browser_manager.load_cookies(self.publish_config.cookies_file)
            
            self.is_initialized = True
            logger.info("发布器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化发布器失败: {e}")
            # 重置浏览器管理器，下次尝试重新获取
            self.browser_manager = None
            self.login_optimizer = None
            return False
    
    async def publish_note(self, note_result=None, 
                          publish_params=None, 
                          title=None, 
                          content=None, 
                          image_paths=None, 
                          hashtags=None, 
                          config=None) -> PublishResult:
        """发布单篇笔记到小红书平台
        
        支持两种调用方式：
        1. 传统方式：传入note_result对象
        2. 兼容UI方式：传入title, content, image_paths, hashtags, config
        
        Args:
            note_result: 笔记生成结果对象
            publish_params: 发布参数（是否允许评论、是否同步等）
            title: 笔记标题（UI调用方式）
            content: 笔记内容（UI调用方式）
            image_paths: 图片路径列表（UI调用方式）
            hashtags: 标签列表（UI调用方式）
            config: 发布配置（UI调用方式）
            
        Returns:
            PublishResult: 发布结果
        """
        # 参数格式兼容处理
        # 判断是否使用UI调用方式
        use_ui_format = title is not None or content is not None
        
        # 准备发布结果
        if use_ui_format:
            # UI调用方式
            note_id = publish_utils.generate_note_id()
            # 合并发布配置
            if config:
                publish_config_dict = self.publish_config.__dict__.copy()
                # 从UI的config对象复制属性
                for key in ['account_name', 'enable_comments', 'sync_to_other_platforms']:
                    if hasattr(config, key):
                        publish_config_dict[key] = getattr(config, key)
                self.publish_config = PublishConfig(**publish_config_dict)
        else:
            # 传统调用方式
            note_id = note_result.note_id or publish_utils.generate_note_id()
            # 合并发布参数
            if publish_params:
                publish_config_dict = self.publish_config.__dict__.copy()
                publish_config_dict.update(publish_params)
                self.publish_config = PublishConfig(**publish_config_dict)
        
        publish_result = PublishResult(
            note_id=note_id,
            status='failed'
        )
        
        # 创建一个统一的内部笔记数据结构
        class MockNoteResult:
            pass
        
        internal_note_result = MockNoteResult()
        
        if use_ui_format:
            # 构建内部数据结构（兼容UI参数）
            class MockTopic:
                def __init__(self, title_value=""):
                    self.title = title_value if isinstance(title_value, str) else ""
            
            class MockContent:
                def __init__(self, text_value=""):
                    self.text = text_value if isinstance(text_value, str) else ""
            
            # 修复：当use_ui_format=True时，title和content参数才是真正的值
            internal_note_result.topic = MockTopic(title)
            internal_note_result.content = MockContent(content)
            
            # 处理图片
            class MockImage:
                def __init__(self, path):
                    self.path = path
            
            internal_note_result.images = [MockImage(path) for path in image_paths or []]
            
            # 保存标签供后续使用
            self._current_hashtags = hashtags or []
        else:
            # 使用原始note_result
            internal_note_result = note_result
            self._current_hashtags = None
        
        # 重试机制
        page = None
        for attempt in range(self.publish_config.retry_count):
            try:
                logger.info(f"开始发布笔记 {publish_result.note_id}, 尝试 {attempt + 1}/{self.publish_config.retry_count}")
                
                # 确保初始化
                if not self.is_initialized and not await self._initialize():
                    raise RuntimeError("发布器初始化失败")
                
                # 确保浏览器管理器存在且已初始化
                if not hasattr(self, 'browser_manager') or self.browser_manager is None:
                    raise RuntimeError("浏览器管理器未初始化")
                    
                if not hasattr(self.browser_manager, 'is_initialized') or not self.browser_manager.is_initialized:
                    raise RuntimeError("浏览器管理器未初始化")
                
                # 再次检查browser_manager是否存在且可用
                if not hasattr(self, 'browser_manager') or self.browser_manager is None:
                    raise RuntimeError("浏览器管理器为None")
                
                # 获取页面
                page = await self.browser_manager.get_page()
                
                # 确保页面有效
                if page is None:
                    raise RuntimeError("获取的页面为None")
                
                # 检查是否需要登录
                if not await self._login_if_needed(page):
                    raise RuntimeError("登录失败或未登录")
                
                # 导航到发布页面
                await page.goto('https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image', timeout=60000)
                await page.wait_for_load_state('networkidle', timeout=30000)
                
                # 首先上传图片 - 根据小红书界面流程，需要先上传图片再进入内容编辑页面
                if hasattr(internal_note_result, 'images') and internal_note_result.images:
                    if not await self._upload_images(page, internal_note_result.images):
                        raise RuntimeError("上传图片失败")
                else:
                    logger.info("没有图片需要上传")
                
                # 等待图片上传后进入编辑页面
                try:
                    # 减少超时时间，避免长时间等待
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except Exception as e:
                    logger.warning(f"等待网络空闲状态超时，继续执行: {e}")
                    # 不抛出异常，继续执行
                
                await asyncio.sleep(3)  # 额外等待确保页面完全加载
                
                # 填充内容（标题和正文）
                if not await self._fill_content(page, internal_note_result):
                    raise RuntimeError("填充内容失败")
                
                # 添加标签
                if self._current_hashtags is not None:
                    # 使用UI传入的标签
                    tags = self._current_hashtags
                else:
                    # 确保content和text存在
                    if hasattr(internal_note_result, 'content') and hasattr(internal_note_result.content, 'text'):
                        tags = publish_utils.extract_tags(internal_note_result.content.text)
                    else:
                        tags = []
                
                # 只有有标签时才添加
                if tags:
                    if not await self._add_tags(page, tags):
                        raise RuntimeError("添加标签失败")
                else:
                    logger.info("没有标签需要添加")
                    
                # 设置发布参数
                if not await self._set_publish_params(page, self.publish_config.__dict__):
                    raise RuntimeError("设置发布参数失败")
                
                # 执行发布
                publish_data = await self._execute_publish(page)
                
                # 更新发布结果
                publish_result.status = 'success'
                publish_result.publish_time = datetime.now()
                publish_result.platform_data = publish_data
                
                # 提取发布链接
                if publish_data and 'url' in publish_data:
                    publish_result.publish_url = publish_data['url']
                    
                    logger.info(f"笔记发布成功: {publish_result.publish_url}")
                break
                
            except Exception as e:
                error_msg = f"发布失败: {e}"
                publish_result.error_message = error_msg
                logger.error(error_msg)
                
                # 最后一次尝试失败，不再重试
                if attempt == self.publish_config.retry_count - 1:
                    break
                
                # 等待重试
                logger.info(f"{self.publish_config.retry_interval}秒后重试...")
                await asyncio.sleep(self.publish_config.retry_interval)
                
            finally:
                # 关闭页面，确保page不为None
                if page is not None:
                    try:
                        await page.close()
                    except Exception as close_error:
                        logger.error(f"关闭页面失败: {close_error}")
        
        # 保存cookies
        try:
            if hasattr(self, 'browser_manager') and self.browser_manager is not None:
                try:
                    await self.browser_manager.save_cookies(self.publish_config.cookies_file)
                except Exception as save_error:
                    logger.error(f"保存cookies失败: {save_error}")
        except Exception as e:
            logger.error(f"执行最终资源清理时出错: {e}")
        
        return publish_result
    
    async def batch_publish_notes(self, note_results=None,
                                publish_params=None,
                                notes=None,
                                config=None,
                                interval_seconds=60) -> List[PublishResult]:
        """批量发布笔记到小红书平台
        
        支持两种调用方式：
        1. 传统方式：传入note_results列表
        2. 兼容UI方式：传入notes列表、config和interval_seconds
        
        Args:
            note_results: 笔记生成结果列表（传统方式）
            publish_params: 发布参数（传统方式）
            notes: 笔记列表（UI调用方式，包含title、content、image_paths、hashtags）
            config: 发布配置（UI调用方式）
            interval_seconds: 发布间隔秒数（UI调用方式）
            
        Returns:
            List[PublishResult]: 发布结果列表
        """
        results = []
        
        # 判断是否使用UI调用方式
        use_ui_format = notes is not None
        
        # 确保初始化
        if not self.is_initialized and not await self._initialize():
            logger.error("批量发布失败：发布器初始化失败")
            
            # 为所有笔记返回失败结果
            if use_ui_format:
                for _ in notes:
                    results.append(PublishResult(
                        note_id=publish_utils.generate_note_id(),
                        status='failed',
                        error_message='发布器初始化失败'
                    ))
            else:
                for note in note_results:
                    results.append(PublishResult(
                        note_id=note.note_id or publish_utils.generate_note_id(),
                        status='failed',
                        error_message='发布器初始化失败'
                    ))
            return results
        
        try:
            if use_ui_format:
                # UI调用方式
                for i, note in enumerate(notes):
                    logger.info(f"批量发布进度: {i + 1}/{len(notes)}")
                    
                    # 使用UI兼容的参数调用publish_note
                    result = await self.publish_note(
                        title=note.get('title'),
                        content=note.get('content'),
                        image_paths=note.get('image_paths', []),
                        hashtags=note.get('hashtags', []),
                        config=config
                    )
                    results.append(result)
                    
                    # 使用指定的间隔时间
                    if i < len(notes) - 1:
                        wait_time = interval_seconds
                        logger.info(f"等待{wait_time}秒后发布下一篇...")
                        await asyncio.sleep(wait_time)
            else:
                # 传统调用方式
                for i, note_result in enumerate(note_results):
                    logger.info(f"批量发布进度: {i + 1}/{len(note_results)}")
                    
                    # 发布单篇笔记
                    result = await self.publish_note(note_result, publish_params)
                    results.append(result)
                    
                    # 避免频繁操作被平台检测，每发布一篇休息几秒
                    if i < len(note_results) - 1:
                        wait_time = 10  # 10秒间隔
                        logger.info(f"等待{wait_time}秒后发布下一篇...")
                        await asyncio.sleep(wait_time)
                    
        finally:
            # 保存cookies
            if hasattr(self, 'browser_manager') and self.browser_manager is not None:
                try:
                    await self.browser_manager.save_cookies(self.publish_config.cookies_file)
                except Exception as save_error:
                    logger.error(f"保存cookies失败: {save_error}")
        
        return results
    
    def switch_account(self, account_name: str) -> bool:
        """切换到指定账号
        
        Args:
            account_name: 账号名称
            
        Returns:
            bool: 是否切换成功
        """
        try:
            # 检查账号是否存在
            if not self.account_manager.account_exists(account_name):
                logger.error(f"账号 {account_name} 不存在")
                return False
            
            # 更新发布配置中的账号名称
            self.publish_config.account_name = account_name
            self.publish_config.cookies_file = f"accounts/cookies/{account_name}.json"
            
            # 重置初始化状态，强制重新初始化
            self.is_initialized = False
            
            logger.info(f"已切换到账号: {account_name}")
            return True
        except Exception as e:
            logger.error(f"切换账号失败: {e}")
            return False
    
    def get_available_accounts(self) -> List[str]:
        """获取所有可用账号列表
        
        Returns:
            List[str]: 账号名称列表
        """
        try:
            return self.account_manager.get_account_names()
        except Exception as e:
            logger.error(f"获取账号列表失败: {e}")
            return []
    
    def get_current_account(self) -> str:
        """获取当前使用的账号名称
        
        Returns:
            str: 当前账号名称
        """
        return self.publish_config.account_name
    
    async def _login_if_needed(self, page: Page) -> bool:
        """如果需要，执行登录操作
        
        Args:
            page: Playwright页面实例
            
        Returns:
            bool: 是否已登录
        """
        # 优先使用登录优化器处理登录逻辑
        if hasattr(self, 'login_optimizer') and self.login_optimizer is not None:
            try:
                logger.info("使用登录优化器处理登录逻辑...")
                # 使用登录优化器确保登录状态
                login_result = await self.login_optimizer.ensure_login(
                    page, 
                    self.browser_manager, 
                    self.publish_config.cookies_file
                )
                
                if login_result:
                    logger.info("登录优化器成功处理登录")
                    return True
                else:
                    logger.warning("登录优化器处理失败，将使用原始登录逻辑")
            except Exception as e:
                logger.warning(f"登录优化器处理出错: {e}，将使用原始登录逻辑")
        
        # 原始登录逻辑作为后备方案
        return await self._login_if_needed_fallback(page)
    
    async def _login_if_needed_fallback(self, page: Page) -> bool:
        """原始登录逻辑，作为登录优化器的后备方案
        
        Args:
            page: Playwright页面实例
            
        Returns:
            bool: 是否已登录
        """
        try:
            # 导航到首页检查是否登录
            logger.info("导航到小红书创作者平台...")
            await page.goto('https://creator.xiaohongshu.com', timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=20000)
            
            # 增加详细日志
            current_url = page.url
            logger.info(f"当前URL: {current_url}")
            
            # 检查是否存在登录按钮或用户头像
            try:
                # 增加更多可能的用户头像或已登录元素选择器
                login_success_selectors = [
                    '.user-avatar, .login-success',
                    '[class*="avatar"][class*="user"]',
                    '.nav-user-avatar',
                    '.profile-avatar',
                    '[data-testid="user-avatar"]',
                    '.header-user-info',
                    '.account-avatar',
                    '.nav-profile',
                    '.profile-btn',
                    '.user-info',
                    '.header-user',
                    '[class*="user"].avatar',
                    '#userAvatar',
                    '.user-menu'
                ]
                
                # 尝试多种选择器检测登录状态
                logger.info(f"尝试{len(login_success_selectors)}种选择器检测登录状态...")
                for selector in login_success_selectors:
                    try:
                        if await page.wait_for_selector(selector, timeout=2000):
                            logger.info(f"已登录状态，检测到元素: {selector}")
                            return True
                    except PlaywrightTimeoutError:
                        logger.debug(f"未检测到元素: {selector}")
                        continue
                
                # 使用query_selector额外检查一次，避免wait_for_selector的严格超时
                logger.info("使用query_selector额外检查已登录元素...")
                for selector in login_success_selectors:
                    element = await page.query_selector(selector)
                    if element:
                        logger.info(f"query_selector检测到元素: {selector}")
                        return True
                
                # 更完善的URL检测逻辑
                current_url = page.url
                logger.info(f"检查URL: {current_url}")
                
                # 检查是否在创作者平台的非登录页面
                if ('creator.xiaohongshu.com' in current_url or 'xiaohongshu.com/creator' in current_url):
                    # 排除登录页面URL
                    is_login_page = any(kw in current_url for kw in ['login', 'signin', 'auth', 'verify'])
                    if not is_login_page:
                        # 检查是否包含dashboard、post、content等关键词
                        if any(kw in current_url for kw in ['dashboard', 'post', 'content', 'article', 'note', 'profile']):
                            logger.info(f"已登录状态，通过URL检测: {current_url}")
                            return True
                    else:
                        logger.info(f"检测到登录页面URL: {current_url}")
            except PlaywrightTimeoutError:
                # 未登录，需要提示用户手动登录
                logger.warning("未登录，请手动完成登录...")
                logger.warning("请在浏览器中完成登录，登录后请等待程序自动检测")
                logger.warning("提示：请输入手机号后点击获取验证码按钮，然后输入验证码完成登录")
                
                # 检查是否处于登录页面
                is_login_page = False
                try:
                    # 尝试识别登录页面的元素
                    login_elements = ['input[placeholder*="手机号"]', 
                                     'input[placeholder*="验证码"]', 
                                     'button >> text=获取验证码',
                                     '.login-form']
                    
                    for selector in login_elements:
                        if await page.query_selector(selector):
                            is_login_page = True
                            logger.info(f"检测到登录页面元素: {selector}")
                            break
                except Exception as e:
                    logger.warning(f"检测登录页面元素时出错: {e}")
                
                # 等待用户登录（给120秒时间，避免频繁刷新）
                login_timeout = 120
                check_interval = 5  # 每5秒检查一次，而不是每秒刷新
                
                logger.info(f"将在{login_timeout}秒内等待您完成登录，每{check_interval}秒检查一次登录状态...")
                
                for _ in range(login_timeout // check_interval):
                    # 等待一段时间让用户操作
                    await asyncio.sleep(check_interval)
                    
                    # 检查是否已登录，不刷新页面以避免打断用户操作
                    try:
                        # 尝试多种选择器检测登录状态
                        is_logged_in = False
                        
                        # 首先检查URL变化
                        current_url = page.url
                        logger.info(f"检查登录状态 - 当前URL: {current_url}")
                        
                        # URL检测
                        if ('creator.xiaohongshu.com' in current_url or 'xiaohongshu.com/creator' in current_url):
                            is_login_page = any(kw in current_url for kw in ['login', 'signin', 'auth', 'verify'])
                            if not is_login_page:
                                if any(kw in current_url for kw in ['dashboard', 'post', 'content', 'article', 'note', 'profile']):
                                    logger.info(f"登录成功，通过URL检测: {current_url}")
                                    is_logged_in = True
                        
                        # 元素检测
                        if not is_logged_in:
                            logger.info("尝试通过页面元素检测登录状态...")
                            for selector in login_success_selectors:
                                element = await page.query_selector(selector)
                                if element:
                                    logger.info(f"登录成功，检测到元素: {selector}")
                                    is_logged_in = True
                                    break
                        
                        # 额外检查：尝试获取页面标题
                        try:
                            page_title = await page.title()
                            logger.info(f"当前页面标题: {page_title}")
                            if '登录' not in page_title and 'Login' not in page_title:
                                # 如果标题不包含登录关键词，可能已登录
                                if any(kw in page_title for kw in ['小红书', 'Xiaohongshu', 'Dashboard', 'Creator']):
                                    logger.info(f"登录成功，通过页面标题检测: {page_title}")
                                    is_logged_in = True
                        except Exception as e:
                            logger.warning(f"获取页面标题失败: {e}")
                        
                        if is_logged_in:
                            logger.info("登录检测通过，确认登录成功")
                            # 保存cookies
                            if hasattr(self, 'browser_manager') and self.browser_manager is not None:
                                await self.browser_manager.save_cookies(self.publish_config.cookies_file)
                            else:
                                logger.error("browser_manager为None，无法保存cookies")
                            return True
                        
                        # 如果还没登录，继续等待
                        remaining_time = login_timeout - ((_ + 1) * check_interval)
                        if remaining_time > 0:
                            logger.info(f"等待登录中，剩余时间: {remaining_time}秒...")
                    except Exception as check_error:
                        logger.warning(f"检查登录状态时出错: {check_error}")
                
                # 最后再检查一次并刷新页面
                logger.info("最后检查登录状态...")
                try:
                    logger.info("最后刷新页面检查登录状态...")
                    await page.reload(timeout=10000)
                    await page.wait_for_load_state('networkidle', timeout=20000)
                    
                    # 获取刷新后的URL
                    current_url = page.url
                    logger.info(f"刷新后URL: {current_url}")
                    
                    # URL检测
                    is_logged_in = False
                    if ('creator.xiaohongshu.com' in current_url or 'xiaohongshu.com/creator' in current_url):
                        is_login_page = any(kw in current_url for kw in ['login', 'signin', 'auth', 'verify'])
                        if not is_login_page:
                            if any(kw in current_url for kw in ['dashboard', 'post', 'content', 'article', 'note', 'profile']):
                                logger.info(f"登录成功，通过URL检测: {current_url}")
                                is_logged_in = True
                    
                    # 元素检测
                    if not is_logged_in:
                        logger.info("最后尝试通过页面元素检测登录状态...")
                        for selector in login_success_selectors:
                            try:
                                if await page.wait_for_selector(selector, timeout=1000):
                                    logger.info(f"登录成功，检测到元素: {selector}")
                                    is_logged_in = True
                                    break
                            except PlaywrightTimeoutError:
                                logger.debug(f"未检测到元素: {selector}")
                                continue
                    
                    # query_selector额外检查
                    if not is_logged_in:
                        for selector in login_success_selectors:
                            element = await page.query_selector(selector)
                            if element:
                                logger.info(f"query_selector检测到元素: {selector}")
                                is_logged_in = True
                                break
                    
                    # 页面标题检查
                    if not is_logged_in:
                        try:
                            page_title = await page.title()
                            logger.info(f"当前页面标题: {page_title}")
                            if '登录' not in page_title and 'Login' not in page_title:
                                if any(kw in page_title for kw in ['小红书', 'Xiaohongshu', 'Dashboard', 'Creator']):
                                    logger.info(f"登录成功，通过页面标题检测: {page_title}")
                                    is_logged_in = True
                        except Exception as e:
                            logger.warning(f"获取页面标题失败: {e}")
                    
                    # 打印更多调试信息
                    if not is_logged_in:
                        logger.warning("所有检测方法都未能确认登录状态")
                        logger.warning(f"当前URL: {current_url}")
                    
                    if is_logged_in:
                        logger.info("最后检查登录成功")
                        if hasattr(self, 'browser_manager') and self.browser_manager is not None:
                            await self.browser_manager.save_cookies(self.publish_config.cookies_file)
                        return True
                except:
                    logger.error("登录超时")
                    return False
                
        except Exception as e:
            logger.error(f"登录检查失败: {e}")
            return False
    
    async def _fill_content(self, page: Page, note_result: Any) -> bool:
        """填充内容
        
        Args:
            page: Playwright页面实例
            note_result: 笔记结果对象
            
        Returns:
            bool: 是否成功
        """
        try:
            # 确保页面加载完成
            await page.wait_for_load_state('networkidle', timeout=30000)
            await asyncio.sleep(2)  # 额外等待2秒确保页面完全渲染
            
            # 确保content存在
            content_text = ""
            if hasattr(note_result, 'content') and note_result.content and hasattr(note_result.content, 'text'):
                content_text = str(note_result.content.text or "")
            
            # 预处理内容
            content = publish_utils.preprocess_content(content_text)
            
            # 查找标题输入框（扩展多种可能性，适配小红书新界面）
            title_selector_options = [
                'input[placeholder="添加标题"]',
                'input[placeholder="请输入标题"]',
                'input[data-testid="title-input"]',
                '.title-input input',
                '.editor-title input',
                '[data-type="title"] input',
                '.publish-title input',
                'input.title-input',
                'input[id*="title"]',
                'input[class*="title"]',
                '//input[contains(@placeholder, "标题")]',  # XPath选择器
                '//input[@data-testid="title"]',
                # 适配小红书新界面的标题选择器
                '.input-area input[placeholder="输入标题"]',
                '.title-editor input',
                '[data-input="title"]',
                '[aria-label="标题输入框"]',
                '#title-input-field',
                '.publish-form input[name="title"]'
            ]
            
            # 尝试填充标题
            title_found = False
            try:
                # 安全地获取标题文本
                title_text = ""
                if hasattr(note_result, 'topic') and note_result.topic and hasattr(note_result.topic, 'title'):
                    title_text = str(note_result.topic.title or "")
                # 兼容直接传入的title参数
                elif hasattr(note_result, 'title'):
                    title_text = str(note_result.title or "")
                # 兼容UI调用方式
                elif hasattr(note_result, 'get') and callable(note_result.get):
                    title_text = note_result.get('title', '')
                    
                if title_text:
                    logging.info(f"准备填充标题: {title_text[:20]}...")
                    
                    # 尝试所有选择器
                    for selector in title_selector_options:
                        try:
                            logging.debug(f"尝试标题选择器: {selector}")
                            await page.wait_for_selector(selector, timeout=1000)
                            
                            # 优先使用JavaScript方式填充标题，因为根据用户反馈这是最有效的方式
                            fill_success = await self._fill_with_js(page, selector, title_text[:50])
                            if not fill_success:
                                # 如果JavaScript失败，再尝试其他方式
                                fill_success = await self._fill_with_typing(page, selector, title_text[:50])
                            if not fill_success:
                                fill_success = await self._fill_directly(page, selector, title_text[:50])
                            
                            if fill_success:
                                # 尝试按Tab键移动到下一个字段
                                try:
                                    await page.press(selector, 'Tab')
                                except:
                                    pass
                                title_found = True
                                logging.info("标题填充完成")
                                break
                        except Exception as selector_error:
                            logging.debug(f"标题选择器 {selector} 失败: {selector_error}")
                            continue
                    
                    # 如果wait_for_selector都失败了，尝试直接使用query_selector
                    if not title_found:
                        logging.info("使用query_selector重试标题填充...")
                        for selector in title_selector_options:
                            try:
                                element = await page.query_selector(selector)
                                if element:
                                    # 尝试多种填充方式
                                    fill_success = await self._fill_element(element, title_text[:50])
                                    if fill_success:
                                        try:
                                            await element.press('Tab')
                                        except:
                                            pass
                                        title_found = True
                                        logging.info("通过query_selector标题填充完成")
                                        break
                            except Exception as e:
                                logging.debug(f"query_selector标题填充失败: {e}")
                                continue
                    
                    # 最后尝试找出页面上所有可能的输入框
                    if not title_found:
                        try:
                            inputs = await page.evaluate('''() => {
                                return Array.from(document.querySelectorAll("input")).map(el => ({
                                    outerHTML: el.outerHTML.substring(0, 100),
                                    placeholder: el.placeholder,
                                    className: el.className,
                                    id: el.id,
                                    type: el.type
                                })).filter(el => el.type !== "hidden");
                            }''')
                            if inputs:
                                logging.info(f"页面上找到{len(inputs)}个可见输入框，尝试第一个可能是标题的输入框")
                                # 尝试第一个文本输入框
                                first_text_input = next((i for i in inputs if i['type'] == 'text'), None)
                                if first_text_input:
                                    # 尝试使用id或class选择器
                                    if first_text_input['id']:
                                        test_selector = f"#{first_text_input['id']}"
                                    elif first_text_input['className']:
                                        test_selector = f".{first_text_input['className'].split()[0]}"
                                    else:
                                        test_selector = "input[type='text']:first-child"
                                        
                                    logging.info(f"尝试使用第一个文本输入框作为标题: {test_selector}")
                                    element = await page.query_selector(test_selector)
                                    if element:
                                        fill_success = await self._fill_element(element, title_text[:50])
                                        if fill_success:
                                            title_found = True
                                            logging.info("通过第一个文本输入框完成标题填充")
                        except Exception as e:
                            logging.warning(f"查找所有输入框失败: {e}")
                    
                    if not title_found:
                        logging.warning("所有标题输入框都未找到，跳过标题填充")
                        # 这里不再直接失败，而是继续尝试填充内容
            except Exception as title_error:
                logging.error(f"处理标题时出错: {title_error}")
            
            # 查找内容输入框（扩展多种可能性，适配小红书新界面）
            content_selector_options = [
                'textarea[placeholder="分享你的体验，添加更多细节会让内容更吸引人..."]',
                'textarea[placeholder="请输入内容"]',
                'textarea[placeholder="正文"]',
                'textarea[data-testid="content-input"]',
                'textarea[data-testid="content"]',
                'textarea.content-input',
                'textarea[id*="content"]',
                'textarea[class*="content"]',
                'textarea#content',
                '#content-input',
                '.content',
                '[role="textbox"]',
                'div[contenteditable="true"]',
                '.content-editable',
                '.rich-text-editor',
                '.editor',
                '.note-content',
                '.article-content',
                # 更复杂的选择器
                '.content-input textarea',
                '.editor-content textarea',
                '.publish-content textarea',
                '.note-editor textarea',
                '.article-editor textarea',
                '[data-type="content"] textarea',
                '[data-role="content"] textarea',
                '[name="content"]',
                '[data-name="content"]',
                '[aria-label*="内容"]',
                '[aria-label="请输入内容"]',
                '[aria-label="正文"]',
                '.editor-main',
                '.editor-container',
                '.editor-wrapper',
                '.content-wrapper',
                '.content-container',
                '.rich-text-wrapper',
                # XPath选择器
                '//textarea[contains(@placeholder, "内容")]',
                '//textarea[contains(@placeholder, "正文")]',
                '//textarea[contains(@class, "content")]',
                '//textarea[@name="content"]',
                '//div[@role="textbox"]',
                '//div[contains(@class, "editor") and contains(@class, "content")]',
                '//div[contains(@class, "rich-text")]',
                # 适配小红书新界面的内容选择器
                '.content-area textarea',
                '.main-content textarea[placeholder="输入正文内容"]',
                '#content-editor',
                '.editor-wrapper textarea',
                '[data-input="content"]',
                '[aria-label="内容输入区域"]',
                '.publish-form textarea[name="content"]',
                '.article-content-editor textarea'
            ]
            
            content_selector = None
            # 尝试所有选择器
            for selector in content_selector_options:
                try:
                    logging.debug(f"尝试内容选择器: {selector}")
                    await page.wait_for_selector(selector, timeout=1000)
                    content_selector = selector
                    logging.info(f"找到内容输入框: {selector}")
                    break
                except Exception as e:
                    logging.debug(f"内容选择器 {selector} 失败: {e}")
                    continue
            
            # 如果wait_for_selector都失败了，尝试直接使用query_selector
            if not content_selector:
                logging.info("使用query_selector重试内容输入框查找...")
                for selector in content_selector_options:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            content_selector = selector
                            logging.info(f"通过query_selector找到内容输入框: {selector}")
                            break
                    except Exception as e:
                        logging.debug(f"query_selector内容选择器 {selector} 失败: {e}")
                        continue
            
            # 查找所有可能的内容输入元素
            if not content_selector:
                try:
                    # 优先查找符合小红书新界面特征的元素
                    xhs_specific_elements = await page.evaluate('''() => {
                        const elements = [];
                        // 查找标题和内容输入区域
                        const titleArea = document.querySelector('.title-area') || 
                                          document.querySelector('.input-area[aria-label*="标题"]');
                        const contentArea = document.querySelector('.content-area') || 
                                          document.querySelector('.main-content') ||
                                          document.querySelector('.editor-wrapper');
                        
                        if (titleArea) {
                            elements.push({
                                type: 'titleArea',
                                outerHTML: titleArea.outerHTML.substring(0, 100),
                                children: Array.from(titleArea.querySelectorAll('input, textarea')).length
                            });
                        }
                        
                        if (contentArea) {
                            elements.push({
                                type: 'contentArea',
                                outerHTML: contentArea.outerHTML.substring(0, 100),
                                children: Array.from(contentArea.querySelectorAll('textarea, [contenteditable]')).length
                            });
                        }

                        return elements;
                    }''')
                    
                    if xhs_specific_elements:
                        logging.info(f"找到小红书特定区域元素: {xhs_specific_elements}")
                        # 尝试直接使用这些区域内的输入元素
                        for area in xhs_specific_elements:
                            if area['type'] == 'contentArea' and area['children'] > 0:
                                # 尝试使用内容区域内的第一个输入元素
                                content_selector = '.content-area textarea, .main-content textarea, .editor-wrapper textarea, .content-area [contenteditable], .main-content [contenteditable], .editor-wrapper [contenteditable]'
                                logging.info(f"尝试使用小红书内容区域: {content_selector}")
                                break
                    
                    # 如果没有找到特定区域，查找所有textarea元素
                    textareas = await page.evaluate('''() => Array.from(document.querySelectorAll("textarea")).map(el => ({
  outerHTML: el.outerHTML.substring(0, 100),
  placeholder: el.placeholder,
  className: el.className,
  id: el.id
}))''')
                    
                    if textareas:
                        logging.info(f"页面上找到{len(textareas)}个textarea元素:")
                        for i, ta in enumerate(textareas):
                            logging.info(f"  {i+1}: {ta}")
                        # 尝试使用第一个textarea
                        content_selector = 'textarea:first-of-type'
                        logging.info(f"尝试使用第一个textarea: {content_selector}")
                    else:
                        logging.warning("页面上未找到任何textarea元素")
                        
                        # 查找所有contenteditable元素
                        editables = await page.evaluate('''() => Array.from(document.querySelectorAll("[contenteditable]"))
                            .filter(el => el.getAttribute("contenteditable") !== "false")
                            .map(el => ({
                                tagName: el.tagName,
                                outerHTML: el.outerHTML.substring(0, 100),
                                className: el.className,
                                id: el.id
                            }))''')
                        
                        if editables:
                            logging.info(f"页面上找到{len(editables)}个可编辑元素:")
                            for i, ed in enumerate(editables):
                                logging.info(f"  {i+1}: {ed}")
                            # 尝试使用第一个可编辑元素
                            content_selector = '[contenteditable]:first-of-type'
                            logging.info(f"尝试使用第一个可编辑元素: {content_selector}")
                        else:
                            logging.error("页面上未找到任何textarea或可编辑元素")
                except Exception as e:
                    logging.error(f"检查页面输入元素失败: {e}")
                
                # 最终确认是否找到选择器
                if content_selector:
                    # 再次验证选择器是否有效
                    test_element = await page.query_selector(content_selector)
                    if not test_element:
                        content_selector = None
                
                # 最终确认
                if not content_selector:
                    # 尝试收集更多页面信息用于调试
                    try:
                        page_html = await page.content()
                        logging.debug(f"页面HTML片段: {page_html[:1000]}")
                        # 尝试查找所有表单元素
                        form_elements = await page.evaluate('() => Array.from(document.querySelectorAll("form *")).map(el => el.tagName).filter((v, i, a) => a.indexOf(v) === i)')
                        logging.info(f"表单中发现的元素类型: {form_elements}")
                    except:
                        pass
                    
                    logging.error("未找到内容输入框")
                    return False
            
            # 确保获取到了需要填充的内容
            if not content:
                logging.warning("没有内容需要填充")
                return True if title_found else False
            
            logging.info(f"准备填充内容，长度: {len(content)} 字符")
            
            # 尝试多种填充方式以提高兼容性
            fill_success = False
            
            # 先点击输入框激活它
            try:
                await page.click(content_selector)
                logger.debug("已点击激活内容输入框")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"点击内容输入框失败: {e}")
            
            # 优先使用JavaScript方式填充内容，因为这种方式通常更可靠
            try:
                logger.debug("尝试方式1: 使用JavaScript填充")
                # 检查选择器类型
                if '>>' in content_selector:
                    # Playwright选择器，不能直接用于JavaScript
                    logger.warning("内容选择器包含Playwright语法，跳过JavaScript填充")
                    raise Exception("Playwright选择器不能用于JavaScript")
                
                # 对于不同类型的输入框使用不同的填充方法
                if 'textarea' in content_selector.lower():
                    # 对于textarea，使用value属性，保留换行符
                    await page.evaluate(f"document.querySelector('{content_selector}').value = `{content.replace('`', '\\`')}`;")
                    # 触发输入事件
                    await page.evaluate(f"document.querySelector('{content_selector}').dispatchEvent(new Event('input', { bubbles: true }));")
                elif '[contenteditable="true"]' in content_selector or 'div' in content_selector.lower():
                    # 对于可编辑的div，使用innerHTML并保留换行符
                    # 将换行符转换为<br>标签以在HTML中正确显示
                    content_with_br = content.replace('\n', '<br>')
                    await page.evaluate(f"document.querySelector('{content_selector}').innerHTML = `{content_with_br.replace('`', '\\`')}`;")
                    # 触发输入事件
                    await page.evaluate(f"document.querySelector('{content_selector}').dispatchEvent(new Event('input', { bubbles: true }));")
                else:
                    await page.evaluate(f"document.querySelector('{content_selector}').value = `{content.replace('`', '\\`')}`;")
                
                # 触发必要的事件
                await page.evaluate(f"document.querySelector('{content_selector}').dispatchEvent(new Event('input', {{ bubbles: true }}));")
                await page.evaluate(f"document.querySelector('{content_selector}').dispatchEvent(new Event('change', {{ bubbles: true }}));")
                
                fill_success = True
                logger.info("通过JavaScript完成内容填充")
            except Exception as e:
                logger.warning(f"JavaScript填充失败: {e}")
            
            # 如果JavaScript失败，再尝试其他方式
            # 方式2: 尝试直接填充
            if not fill_success:
                try:
                    logger.debug("尝试方式2: 直接填充内容")
                    await page.fill(content_selector, content)
                    fill_success = True
                    logger.info("通过直接填充完成内容填充")
                except Exception as e:
                    logger.warning(f"直接填充失败: {e}")
            
            # 方式3: 尝试模拟打字输入
            if not fill_success:
                try:
                    logger.debug("尝试方式3: 模拟用户打字")
                    await publish_utils.simulate_user_typing(page, content_selector, content)
                    fill_success = True
                    logger.info("通过模拟用户打字完成内容填充")
                except Exception as e:
                    logger.warning(f"模拟打字失败: {e}")
            
            # 方式4: 尝试通过选择器获取元素后填充
            if not fill_success:
                try:
                    logger.debug("尝试方式4: 通过query_selector获取元素后填充")
                    element = await page.query_selector(content_selector)
                    if element:
                        await element.fill(content)
                        fill_success = True
                        logger.info("通过query_selector获取元素后完成内容填充")
                except Exception as e:
                    logger.warning(f"query_selector填充失败: {e}")
            
            # 触发一些额外的事件以确保内容被正确处理
            if fill_success:
                try:
                    # 检查选择器类型
                    if '>>' in content_selector:
                        # Playwright选择器，使用locator处理
                        await page.locator(content_selector).focus()
                        await page.locator(content_selector).blur()
                        await page.locator(content_selector).focus()
                    else:
                        # 标准CSS选择器，使用JavaScript处理
                        await page.evaluate(f"document.querySelector('{content_selector}').focus();")
                        await page.evaluate(f"document.querySelector('{content_selector}').blur();")
                        await page.evaluate(f"document.querySelector('{content_selector}').focus();")
                    logger.debug("已触发额外的focus和blur事件")
                    await asyncio.sleep(1)
                except:
                    pass
            
            # 检查是否至少成功了标题或内容的填充
            if fill_success or title_found:
                status_msg = []
                if title_found:
                    status_msg.append("标题")
                if fill_success:
                    status_msg.append("内容")
                logger.info(f"{'、'.join(status_msg)}填充完成")
                return True
            else:
                logger.error("标题和内容都填充失败")
                return False
            
        except Exception as e:
                logger.error(f"填充内容失败: {e}")
                
                # 尝试最后的应急方案 - 打印页面结构帮助调试
                try:
                    page_structure = await page.evaluate('() => document.body.innerHTML.substring(0, 2000)')
                    logger.debug(f"页面结构预览: {page_structure}")
                    
                    # 收集所有可能的输入元素信息
                    try:
                        all_inputs = await page.evaluate('''() => Array.from(document.querySelectorAll("input, textarea, [contenteditable]"))
                            .map(el => ({
                                tagName: el.tagName,
                                outerHTML: el.outerHTML.substring(0, 150),
                                placeholder: el.placeholder || "",
                                className: el.className,
                                id: el.id,
                                contenteditable: el.getAttribute("contenteditable") || "false"
                            }))''')
                        logging.info(f"页面上所有可能的输入元素 ({len(all_inputs)}个):")
                        for i, inp in enumerate(all_inputs[:5]):  # 只记录前5个
                              logger.info(f"  {i+1}: {inp}")
                    except:
                        pass
                except Exception as debug_error:
                    logging.warning(f"收集调试信息失败: {debug_error}")
                    
                return False
    
    async def _upload_images(self, page: Page, images: List[Any]) -> bool:
        """上传图片到小红书创作平台
        
        Args:
            page: Playwright页面实例
            images: 图片列表
            
        Returns:
            bool: 是否成功
        """
        import time
        import traceback
        
        try:
            # 验证图片
            valid_images = publish_utils.validate_images([{"path": img.path} for img in images])
            
            if not valid_images:
                logger.error("没有有效的图片可以上传")
                return False
            
            # 小红书新界面的图片上传按钮和输入框选择器 - 基于截图优化
            upload_button_selectors = [
                'button >> text=上传图片',  # 截图中看到的主要上传按钮
                '.upload-btn',
                '.btn-upload',
                '[data-testid="upload-button"]',
                'button >> text=上传照片',
                '#upload-btn',
                '.upload-button-container button',
                'button >> text=选择图片',
                '.primary-button.upload',
                '[aria-label="上传图片"]',
                # 新增小红书新界面专用上传按钮选择器
                '.image-upload-button',
                '.upload-action button',
                '.upload-section button',
                'button:has(.upload-icon)',
                '.main-upload-button',
                '.publish-upload-btn',
                '.note-upload-button'
            ]
            
            # 拖拽区域选择器 - 新界面的主要上传区域
            drop_area_selectors = [
                '.upload-area',  # 截图中的拖拽区域
                '.drop-area',
                '.upload-container',
                '[data-testid="upload-area"]',
                '.upload-box',
                # 新增小红书新界面拖拽区域选择器
                '.image-uploader',
                '.drag-drop-area',
                '.upload-panel',
                '.upload-placeholder',
                '.image-drop-container',
                # 优化拖拽区域选择器
                '.upload-section',
                '.main-upload-area',
                '[id*="upload-area"]',
                '[class*="upload"][class*="area"]',
                '.note-upload-container',
                '.publish-upload-area'
            ]
            
            file_input_selectors = [
                'input[type="file"]',  # 通用文件输入框
                '.upload-input input[type="file"]',
                '[data-testid="file-upload-input"]',
                '.image-upload input[type="file"]',
                '.uploader-input',
                # 新增小红书新界面文件输入框选择器
                '.image-uploader input[type="file"]',
                '.upload-button-container input[type="file"]',
                '[name="image-upload"]',
                '[name="file-upload"]',
                '#image-upload-input',
                '#file-upload-input',
                '[class*="upload"][type="file"]',
                '[id*="upload"][type="file"]'
            ]
            
            # 尝试点击上传按钮
            upload_button_found = False
            for selector in upload_button_selectors:
                try:
                    logger.info(f"尝试点击上传按钮: {selector}")
                    # 先检查元素是否可见
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await page.evaluate('(el) => el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden"', element=element)
                        if is_visible:
                            await page.click(selector, timeout=2000)
                            upload_button_found = True
                            logger.info(f"成功点击上传按钮: {selector}")
                            # 等待上传对话框出现
                            await page.wait_for_timeout(1000)
                            break
                except Exception as e:
                    logger.warning(f"点击上传按钮失败: {selector}, 错误: {e}")
                    continue
            
            # 如果没找到可见的上传按钮，尝试使用JavaScript查找并点击
            if not upload_button_found:
                try:
                    logger.info("尝试使用JavaScript查找并点击上传按钮")
                    upload_button_found = await page.evaluate('''() => {
                        // 查找所有可能的上传按钮
                        const buttons = [
                            ...document.querySelectorAll('button'),
                            ...document.querySelectorAll('[role="button"]')
                        ];
                        
                        // 优先查找包含上传文本的按钮
                        const uploadTexts = ['上传图片', '选择图片', '上传照片', '添加图片'];
                        for (const button of buttons) {
                            // 检查是否可见
                            if (button.offsetParent === null || button.style.display === 'none' || button.style.visibility === 'hidden') {
                                continue;
                            }
                            
                            // 检查按钮文本或aria-label
                            const text = (button.textContent || button.innerText || '').toLowerCase();
                            const ariaLabel = (button.getAttribute('aria-label') || '').toLowerCase();
                            
                            if (uploadTexts.some(t => text.includes(t) || ariaLabel.includes(t.toLowerCase()))) {
                                button.click();
                                return true;
                            }
                        }
                        
                        // 查找包含上传图标的按钮
                        const iconTexts = ['upload', 'image', 'file', '添加', '上传'];
                        for (const button of buttons) {
                            if (button.offsetParent === null || button.style.display === 'none' || button.style.visibility === 'hidden') {
                                continue;
                            }
                            
                            // 检查按钮内的图标类名
                            const hasIcon = Array.from(button.querySelectorAll('*')).some(el => {
                                const className = el.className || '';
                                return iconTexts.some(t => className.toLowerCase().includes(t));
                            });
                            
                            if (hasIcon) {
                                button.click();
                                return true;
                            }
                        }
                        
                        return false;
                    }''')
                    
                    if upload_button_found:
                        logger.info("通过JavaScript成功点击上传按钮")
                        await page.wait_for_timeout(1000)
                except Exception as e:
                    logger.warning(f"JavaScript查找上传按钮失败: {e}")
            
            # 如果没找到上传按钮，尝试点击拖拽区域
            drop_area_found = False
            if not upload_button_found:
                for selector in drop_area_selectors:
                    try:
                        logger.info(f"尝试点击拖拽区域: {selector}")
                        # 先检查元素是否可见
                        element = await page.query_selector(selector)
                        if element:
                            is_visible = await page.evaluate('(el) => el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden"', element=element)
                            if is_visible:
                                await page.click(selector)
                                drop_area_found = True
                                logger.info(f"成功点击拖拽区域: {selector}")
                                # 等待上传对话框出现
                                await page.wait_for_timeout(1000)
                                break
                    except Exception as e:
                        logger.warning(f"点击拖拽区域失败: {selector}, 错误: {e}")
                        continue
                
                # 如果没找到拖拽区域，尝试使用JavaScript查找
                if not drop_area_found:
                    try:
                        logger.info("尝试使用JavaScript查找拖拽区域")
                        drop_area_found = await page.evaluate('''() => {
                            // 查找可能的拖拽区域元素
                            const dropElements = document.querySelectorAll('.upload, .drop, .area, .container, .uploader, .upload-box');
                            
                            for (const element of dropElements) {
                                // 检查是否可见
                                if (element.offsetParent === null || element.style.display === 'none' || element.style.visibility === 'hidden') {
                                    continue;
                                }
                                
                                // 检查是否有拖拽相关的属性或文本
                                const text = (element.textContent || element.innerText || '').toLowerCase();
                                const hasDropAttr = element.hasAttribute('dropzone') || 
                                                 element.getAttribute('aria-label')?.includes('拖拽') ||
                                                 element.getAttribute('data-testid')?.includes('upload');
                                
                                if (text.includes('拖拽') || text.includes('上传') || text.includes('拖放') || hasDropAttr) {
                                    element.click();
                                    return true;
                                }
                            }
                            
                            return false;
                        }''')
                        
                        if drop_area_found:
                            logger.info("通过JavaScript成功点击拖拽区域")
                            await page.wait_for_timeout(1000)
                    except Exception as e:
                        logger.warning(f"JavaScript查找拖拽区域失败: {e}")
            
            # 尝试直接找文件输入框
            file_input = None
            # 如果按钮或拖拽区域点击后没有找到文件输入框，或者没有点击成功，尝试直接查找
            for selector in file_input_selectors:
                try:
                    logger.info(f"尝试查找文件输入框: {selector}")
                    file_input = await page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"成功找到文件输入框: {selector}")
                    break
                except Exception as e:
                    logger.warning(f"查找文件输入框失败: {selector}, 错误: {e}")
                    
            # 如果还是没找到，尝试查找隐藏的文件输入框
            if not file_input:
                try:
                    logger.info("尝试查找隐藏的文件输入框")
                    file_input = await page.evaluate_handle('''() => {
                        const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
                        return inputs.find(input => input.offsetParent === null || 
                                           window.getComputedStyle(input).display === 'none');
                    }''')
                    if file_input:
                        logger.info("找到隐藏的文件输入框")
                except Exception as e:
                    logger.warning(f"查找隐藏文件输入框失败: {e}")
            
            # 新增：基于截图优化，尝试查找新界面的文件输入框
            if not file_input:
                try:
                    logger.info("尝试查找新界面的文件输入框")
                    new_ui_inputs = [
                        '[data-testid="image-upload-input"]',
                        '.upload-container input[type="file"]',
                        '.image-uploader input[type="file"]',
                        '[class*="upload"] input[type="file"]',
                        '.drop-area input[type="file"]',
                        '.upload-button input[type="file"]',
                        'input[type="file"][accept*="image/"]'
                    ]
                    for input_selector in new_ui_inputs:
                        try:
                            file_input = await page.query_selector(input_selector)
                            if file_input:
                                logger.info(f"成功找到新界面文件输入框: {input_selector}")
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"查找新界面文件输入框失败: {e}")
            
            if not file_input:
                logger.error("无法找到文件上传输入框")
                # 尝试使用JavaScript直接触发文件选择对话框
                try:
                    logger.info("尝试使用JavaScript触发文件选择对话框")
                    # 优化JavaScript触发逻辑，针对新界面
                    trigger_success = await page.evaluate('''() => {
                        // 优先查找并点击上传按钮
                        const uploadButtons = document.querySelectorAll(
                            '.upload-button, [data-testid="upload-button"], button:contains("上传图片")'
                        );
                        for (const btn of uploadButtons) {
                            if (btn.offsetParent !== null) {
                                btn.click();
                                return true;
                            }
                        }
                        
                        // 查找文件输入框并触发
                        const fileInputs = document.querySelectorAll('input[type="file"]');
                        if (fileInputs.length > 0) {
                            fileInputs[0].click();
                            return true;
                        }
                        return false;
                    }''')
                    
                    if trigger_success:
                        logger.info("成功触发文件选择对话框")
                        # 等待输入框出现
                        file_input = await page.wait_for_selector('input[type="file"]', timeout=3000)
                except Exception as e:
                    logger.error(f"JavaScript触发文件选择对话框失败: {e}")
                    return False
            
            # 上传图片
            file_paths = [img["path"] for img in valid_images]
            logger.info(f"准备上传 {len(file_paths)} 张图片")
            
            # 处理文件上传
            try:
                # 确保file_input是正确的Playwright元素
                if hasattr(file_input, 'set_input_files'):
                    await file_input.set_input_files(file_paths)
                else:
                    # 处理evaluate_handle返回的JSHandle对象
                    js_handle = file_input
                    file_input = await js_handle.as_element()
                    if file_input:
                        await file_input.set_input_files(file_paths)
                    else:
                        raise Exception("无法获取有效的文件输入框元素")
                
                logger.info(f"成功设置文件路径: {file_paths}")
            except Exception as e:
                logger.error(f"设置文件路径失败: {e}")
                # 尝试使用JavaScript方法上传
                try:
                    logger.info("尝试使用JavaScript方法上传图片")
                    logger.warning("JavaScript上传图片在自动化环境中有限制，建议使用set_input_files")
                    
                    # 新增：更智能的JavaScript上传尝试
                    upload_result = await page.evaluate('''(filePaths) => {
                        console.log('尝试使用JavaScript上传图片，但在浏览器环境中通常受限');
                        return false;
                    }''', file_paths)
                    
                    if not upload_result:
                        logger.warning("JavaScript上传方法不可用，尝试替代方案")
                        
                        # 替代方案：查找是否有隐藏的上传区域可以拖拽
                        await page.evaluate('''(data) => {
                            const { filePaths } = data;
                            const dropZones = document.querySelectorAll('.drop-area, .upload-area, [dropzone]');
                            for (const zone of dropZones) {
                                if (zone.offsetParent !== null) {
                                    zone.click();
                                    return true;
                                }
                            }
                            return false;
                        }''', {"filePaths": file_paths})
                except Exception as js_error:
                    logger.error(f"JavaScript上传失败: {js_error}")
                    return False
            
            # 等待上传完成 - 根据新界面截图优化
            upload_complete = False
            
            # 新增：基于截图的上传完成指示器，优先检测新界面元素
            upload_indicators = [
                # 新界面主要指示器
                '.image-preview-item:visible',  # 新界面中的预览项
                '[data-testid="image-preview"]:visible',
                '.image-edit-container:visible',  # 图片编辑容器
                '.publish-header',  # 发布页头部
                '.content-header',  # 内容页头部
                '.upload-success',
                
                # 进度指示器
                '.upload-progress[style*="width: 100%"]',
                '.progress-bar[style*="width: 100%"]',
                
                # 成功标记
                '.success-mark',
                '.check-mark',
                '[data-testid="upload-complete"]',
                
                # 编辑页面元素
                '.title-input',  # 标题输入框
                '.content-area',  # 内容区域
                '.editor-wrapper',
                
                # 通用指示器
                '.image-uploaded',
                '.uploading-done'
            ]
            
            # 页面跳转检测 - 上传后会进入编辑页面
            page_transition_selectors = [
                # 新界面主要容器
                '.publish-container:visible',  # 发布容器
                '.editor-container:visible',  # 编辑器容器
                '.note-editor:visible',
                
                # 功能区域
                '.editor-header',  # 编辑器头部
                '.publish-sidebar',  # 发布侧边栏
                
                # 数据测试ID
                '[data-testid="publish-editor"]',
                '[data-testid="note-editor"]',
                
                # 核心输入区域
                '.title-input',  # 标题输入框
                '.content-area',  # 内容区域
                '[placeholder="输入标题"]',
                '[placeholder="输入正文内容"]'
            ]
            
            # 先等待一段时间让上传开始
            await asyncio.sleep(3)  # 增加初始等待时间
            
            # 最多等待90秒 - 增加超时时间以适应大图片上传
            start_time = time.time()
            max_wait_time = 90
            check_interval = 1.5  # 稍微增加检查间隔
            last_progress = 0
            preview_check_count = 0  # 预览检查计数
            
            # 新增：基于截图的错误元素检测
            error_selectors = [
                '.upload-error',
                '.error-message', 
                '.error-tip',
                '[data-testid="upload-error"]',
                '.upload-fail',
                '.error-alert',
                '[class*="error"][class*="upload"]'
            ]
            
            while time.time() - start_time < max_wait_time:
                # 检查是否有上传错误
                try:
                    for selector in error_selectors:
                        error_elements = await page.query_selector_all(selector)
                        if error_elements:
                            error_text = await page.evaluate('(elements) => elements.map(el => el.textContent).join("\n")', elements=error_elements)
                            logger.error(f"上传过程中出现错误: {error_text}")
                            return False
                except Exception as e:
                    logger.warning(f"检查上传错误时出错: {e}")
                
                # 检查是否上传完成
                for indicator in upload_indicators:
                    try:
                        if await page.is_visible(indicator):
                            upload_complete = True
                            logger.info(f"检测到上传完成指示器: {indicator}")
                            break
                    except Exception as e:
                        logger.debug(f"检查指示器 {indicator} 时出错: {e}")
                
                # 检查是否有图片预览出现（另一种判断上传完成的方式）
                if not upload_complete and (time.time() - start_time) % 3 < check_interval:
                    try:
                        previews = await page.query_selector_all('.image-preview-item, .preview-image, .uploaded-image, .image-item')
                        if len(previews) >= len(valid_images):
                            preview_check_count += 1
                            logger.info(f"检测到足够的图片预览: {len(previews)}/{len(valid_images)} (确认计数: {preview_check_count})")
                            
                            # 需要连续两次确认预览数量，避免误判
                            if preview_check_count >= 2:
                                upload_complete = True
                                break
                        else:
                            # 重置计数
                            preview_check_count = 0
                    except Exception as e:
                        logger.warning(f"检查图片预览时出错: {e}")
                
                # 检查是否页面已跳转到编辑页面（小红书的流程是先上传再进入编辑页）
                if not upload_complete:
                    try:
                        for transition_selector in page_transition_selectors:
                            if await page.is_visible(transition_selector):
                                upload_complete = True
                                logger.info(f"检测到页面已跳转到编辑页面，找到元素: {transition_selector}")
                                break
                    except Exception as e:
                        logger.debug(f"检查页面跳转时出错: {e}")
                
                # 检查URL变化 - 有时上传完成会直接跳转
                if not upload_complete:
                    try:
                        current_url = page.url
                        if '/publish' in current_url or '/edit' in current_url or '/note' in current_url:
                            upload_complete = True
                            logger.info(f"检测到URL变化表示进入编辑页面: {current_url}")
                            break
                    except Exception as e:
                        logger.warning(f"检查URL变化时出错: {e}")
                
                # 检查上传进度条（如果有）
                if not upload_complete and (time.time() - start_time) % 3 < check_interval:
                    try:
                        progress_elements = await page.query_selector_all('.upload-progress, .progress-bar, .uploading-indicator, .progress-item')
                        for el in progress_elements:
                            try:
                                # 尝试多种方式获取进度
                                progress = 0
                                
                                # 方式1: 通过style.width获取
                                style = await page.evaluate('(el) => window.getComputedStyle(el).width', element=el)
                                if style and style.endswith('%'):
                                    progress = int(style[:-1])
                                else:
                                    # 方式2: 通过aria-valuenow获取
                                    progress = await page.evaluate('''(el) => {
                                        const aria_value = el.getAttribute("aria-valuenow");
                                        if (aria_value && !isNaN(aria_value)) {
                                            return parseInt(aria_value);
                                        }
                                        return null;
                                    }''', element=el)
                                    if progress is None:
                                        continue
                                
                                if progress > last_progress:
                                    last_progress = progress
                                    logger.info(f"上传进度: {progress}%")
                                if progress >= 100:
                                    upload_complete = True
                                    logger.info("上传进度达到100%")
                                    break
                            except Exception:
                                continue
                    except Exception as e:
                        logger.warning(f"检查上传进度时出错: {e}")
                
                # 新增：基于截图的额外检查 - 发布按钮出现通常表示上传完成
                if not upload_complete and (time.time() - start_time) > 10:
                    try:
                        publish_buttons = await page.query_selector_all(
                            '.publish-btn, [data-testid="publish-button"], button >> text=发布'
                        )
                        if publish_buttons:
                            for btn in publish_buttons:
                                if await page.is_visible(btn):
                                    upload_complete = True
                                    logger.info("检测到发布按钮，认为上传已完成")
                                    break
                    except Exception:
                        pass
                
                if upload_complete:
                    break
                
                await asyncio.sleep(check_interval)
            
            if upload_complete:
                logger.info("所有图片上传完成")
                # 等待页面跳转或加载完成
                await asyncio.sleep(3)  # 减少等待时间从5秒到3秒
                
                # 新增：确认上传结果的额外检查
                try:
                    # 检查是否所有图片都已正确加载
                    loaded_images = await page.query_selector_all('.image-preview-item img, .uploaded-image img')
                    if loaded_images:
                        logger.info(f"确认到 {len(loaded_images)} 张图片已成功加载")
                    
                    # 检查是否已进入编辑模式
                    edit_mode_indicators = ['.title-input', '.content-area', '.editor-wrapper']
                    for indicator in edit_mode_indicators:
                        if await page.is_visible(indicator):
                            logger.info(f"已确认进入编辑模式: {indicator}")
                            break
                except Exception as e:
                    logger.warning(f"确认上传结果时出错: {e}")
                    
                return True
            else:
                # 新增：超时前的最后尝试
                try:
                    logger.info("上传检测超时，尝试最后一次检查")
                    # 强制检查页面状态
                    current_state = await page.evaluate('''() => {
                        const state = {
                            hasPreview: document.querySelectorAll('.image-preview-item, .preview-image').length > 0,
                            hasEditor: document.querySelectorAll('.title-input, .content-area').length > 0,
                            hasPublishButton: document.querySelectorAll('.publish-btn, button:contains("发布")').length > 0
                        };
                        return state;
                    }''')
                    
                    logger.info(f"最终页面状态: {current_state}")
                    
                    # 基于最终状态做出判断
                    if current_state['hasPreview'] or current_state['hasEditor'] or current_state['hasPublishButton']:
                        logger.info("基于最终页面状态，认为上传可能已完成")
                        await asyncio.sleep(3)
                        return True
                except Exception as e:
                    logger.warning(f"执行最终检查时出错: {e}")
                
                logger.error("图片上传超时或未检测到上传完成")
                return False
            
        except Exception as e:
            logger.error(f"上传图片时发生异常: {e}")
            traceback.print_exc()
            return False
    
    async def _add_tags(self, page: Page, tags: List[str]) -> bool:
        """添加标签 - 小红书标签直接添加到正文内容中
        
        Args:
            page: Playwright页面实例
            tags: 标签列表
            
        Returns:
            bool: 是否成功
        """
        try:
            # 记录开始时间和页面状态
            start_time = time.time()
            logger.info(f"[标签添加] 开始添加标签流程，当前页面URL: {page.url}")
            
            if not tags:
                logger.info("[标签添加] 没有标签需要添加")
                return True
            
            logger.info(f"[标签添加] 开始添加{len(tags)}个标签到正文内容中: {tags}")
            
            # 小红书标签直接添加到正文内容中，不需要专门的标签输入框
            # 构建标签字符串，每个标签前添加#字符
            tag_strings = []
            for i, tag in enumerate(tags[:10]):  # 限制最多添加10个标签
                clean_tag = tag.strip()
                if not clean_tag:
                    logger.debug(f"[标签添加] 跳过空标签，索引: {i}")
                    continue
                
                # 确保标签以#开头
                if not clean_tag.startswith('#'):
                    clean_tag = '#' + clean_tag
                    logger.debug(f"[标签添加] 为标签添加#前缀: {clean_tag}")
                
                # 限制标签长度
                if len(clean_tag) > 21:
                    original_tag = clean_tag
                    clean_tag = clean_tag[:21]  # 包括#字符，小红书标签长度限制
                    logger.debug(f"[标签添加] 标签过长，从 {original_tag} 截断为 {clean_tag}")
                
                tag_strings.append(clean_tag)
                logger.debug(f"[标签添加] 处理后的标签 {i+1}: {clean_tag}")
            
            if not tag_strings:
                logger.warning("[标签添加] 没有有效的标签可添加")
                return True
            
            # 将标签添加到正文内容末尾
            tags_text = ' ' + ' '.join(tag_strings)
            logger.info(f"[标签添加] 构建的标签文本: {tags_text}")
            
            # 查找正文内容输入框
            content_selectors = [
                # 小红书最新界面内容选择器 - 基于截图优化优先尝试
                '.publish-content textarea',
                '.publish-content [placeholder="输入正文内容"]',
                '.main-content-editor textarea',
                '.publish-panel .content-input',
                '.content-editor-area textarea',
                '[data-testid="publish-content-input"]',
                '[data-cy="publish-content-input"]',
                '#publish-content-input',
                '.publish-content-input',
                # 小红书新界面内容选择器
                '.content-area textarea',
                '.main-content textarea[placeholder="输入正文内容"]',
                '.article-content-editor',
                '.editor-wrapper',
                '.content-editor',
                '#content-editor',
                '[placeholder="输入正文内容"]',
                # 新增小红书最新界面专用选择器
                '#article-content',
                '.article-body',
                '[name="noteContent"]',
                '[data-testid="note-content"]',
                '.editor-content-container',
                '.note-content-input',
                '.main-content-editor',
                '.content-input-area',
                '[data-input="content"]',
                '[data-placeholder="输入正文内容"]',
                '.content-wrapper textarea',
                '[aria-label="正文内容"]',
                '.publish-area .content-input',
                '.note-editor-content textarea',
                '.content-editor-wrapper textarea',
                '.main-editor-area',
                # 富文本编辑器选择器
                'div[contenteditable="true"]',
                'div[role="textbox"]',
                '.ql-editor, .ProseMirror',
                # 通用内容选择器
                'textarea[placeholder*="正文"]',
                'textarea[placeholder*="内容"]',
                '.editor, .content, .rich-text-editor, .content-editor',
                '[id*="content"]'
            ]
            
            content_found = False
            selector_count = 0
            logger.info(f"[标签添加] 开始尝试 {len(content_selectors)} 个选择器查找内容输入框")
            
            for selector in content_selectors:
                selector_count += 1
                logger.debug(f"[标签添加] 尝试选择器 {selector_count}/{len(content_selectors)}: {selector}")
                
                try:
                    # 检查元素是否存在且可见
                    element = await page.query_selector(selector)
                    if not element:
                        logger.debug(f"[标签添加] 选择器未找到元素: {selector}")
                        continue
                        
                    is_visible = await page.evaluate('(el) => el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden"', element)
                    if not is_visible:
                        logger.debug(f"[标签添加] 元素不可见: {selector}")
                        continue
                    
                    # 获取元素类型
                    element_type = await page.evaluate('(element) => element.tagName.toLowerCase()', element)
                    logger.debug(f"[标签添加] 找到元素，类型: {element_type}, 选择器: {selector}")
                    
                    # 获取当前内容
                    if element_type == 'textarea' or element_type == 'input':
                        current_content = await page.evaluate('(element) => element.value || ""', element)
                    else:
                        current_content = await page.evaluate('(element) => element.textContent || element.innerText || ""', element)
                    
                    logger.debug(f"[标签添加] 当前内容长度: {len(current_content)}, 前50字符: {current_content[:50]}")
                    
                    # 检查是否已经包含了这些标签
                    all_tags_present = True
                    missing_tags = []
                    for tag_str in tag_strings:
                        if tag_str not in current_content:
                            all_tags_present = False
                            missing_tags.append(tag_str)
                    
                    if all_tags_present:
                        logger.info(f"[标签添加] 所有标签已存在于内容中，无需重复添加，选择器: {selector}")
                        return True
                    else:
                        logger.debug(f"[标签添加] 缺失的标签: {missing_tags}")
                    
                    # 添加标签到内容末尾
                    if element_type == 'textarea' or element_type == 'input':
                        # 对于textarea和input元素
                        new_content = current_content + tags_text
                        logger.debug(f"[标签添加] 使用fill方法更新textarea/input内容")
                        await page.fill(selector, new_content)
                    else:
                        # 对于contenteditable元素
                        logger.debug(f"[标签添加] 使用JavaScript方法更新contenteditable元素")
                        await page.click(selector)
                        await page.evaluate('''(data) => { 
                            const { element, tagsText } = data;
                            // 将光标移动到末尾
                            element.focus();
                            const selection = window.getSelection();
                            const range = document.createRange();
                            range.selectNodeContents(element);
                            range.collapse(false); // 光标移动到末尾
                            selection.removeAllRanges();
                            selection.addRange(range);
                            
                            // 插入标签文本
                            document.execCommand("insertText", false, tagsText); 
                            element.dispatchEvent(new Event("input", { bubbles: true }));
                            element.dispatchEvent(new Event("change", { bubbles: true }));
                        }''', {"element": element, "tagsText": tags_text})
                    
                    # 验证标签是否成功添加
                    if element_type == 'textarea' or element_type == 'input':
                        updated_content = await page.evaluate('(element) => element.value || ""', element)
                    else:
                        updated_content = await page.evaluate('(element) => element.textContent || element.innerText || ""', element)
                    
                    logger.debug(f"[标签添加] 更新后内容长度: {len(updated_content)}, 前50字符: {updated_content[:50]}")
                    
                    # 检查标签是否成功添加
                    tags_added = all(tag_str in updated_content for tag_str in tag_strings)
                    added_tags = [tag for tag in tag_strings if tag in updated_content]
                    still_missing = [tag for tag in tag_strings if tag not in updated_content]
                    
                    if tags_added:
                        elapsed_time = time.time() - start_time
                        logger.info(f"[标签添加] 成功将标签添加到正文内容中，使用选择器: {selector}, 耗时: {elapsed_time:.2f}秒")
                        content_found = True
                        break
                    else:
                        logger.warning(f"[标签添加] 标签添加验证失败，选择器: {selector}, 已添加: {added_tags}, 仍缺失: {still_missing}")
                except Exception as e:
                    logger.warning(f"[标签添加] 添加标签失败，选择器: {selector}, 错误: {e}")
                    continue
            
            if not content_found:
                logger.warning(f"[标签添加] 所有选择器都失败，尝试使用JavaScript方式添加标签")
                # 尝试使用JavaScript方式添加标签
                try:
                    js_start_time = time.time()
                    logger.info(f"[标签添加] 开始JavaScript方式添加标签，标签列表: {tag_strings}")
                    
                    success = await page.evaluate("""(tagStrings) => {
                        console.log('[JS标签添加] 开始JavaScript方式添加标签，标签列表:', tagStrings);
                        
                        // 查找所有可能的内容编辑区域
                        const contentSelectors = [
                            // 小红书最新界面内容选择器 - 基于截图优化优先尝试
                            '.publish-content textarea',
                            '.publish-content [placeholder="输入正文内容"]',
                            '.main-content-editor textarea',
                            '.publish-panel .content-input',
                            '.content-editor-area textarea',
                            '[data-testid="publish-content-input"]',
                            '[data-cy="publish-content-input"]',
                            '#publish-content-input',
                            '.publish-content-input',
                            // 小红书新界面内容选择器
                            '.content-area textarea',
                            '.main-content textarea[placeholder="输入正文内容"]',
                            '.article-content-editor',
                            '.editor-wrapper',
                            '.content-editor',
                            '#content-editor',
                            '[placeholder="输入正文内容"]',
                            // 新增小红书最新界面专用选择器
                            '#article-content',
                            '.article-body',
                            '[name="noteContent"]',
                            '[data-testid="note-content"]',
                            '.editor-content-container',
                            '.note-content-input',
                            '.main-content-editor',
                            '.content-input-area',
                            '[data-input="content"]',
                            '[data-placeholder="输入正文内容"]',
                            '.content-wrapper textarea',
                            '[aria-label="正文内容"]',
                            '.publish-area .content-input',
                            '.note-editor-content textarea',
                            '.content-editor-wrapper textarea',
                            '.main-editor-area',
                            // 通用富文本编辑器选择器
                            'div[contenteditable="true"]',
                            'div[role="textbox"]',
                            '.ql-editor, .ProseMirror',
                            // 通用内容选择器
                            'textarea[placeholder*="正文"]',
                            'textarea[placeholder*="内容"]',
                            '.editor, .content, .rich-text-editor, .content-editor',
                            '[id*="content"]'
                        ];
                        
                        // 尝试每个选择器
                        for (let i = 0; i < contentSelectors.length; i++) {
                            const selector = contentSelectors[i];
                            console.log(`[JS标签添加] 尝试选择器 ${i+1}/${contentSelectors.length}: ${selector}`);
                            
                            try {
                                const element = document.querySelector(selector);
                                if (!element) {
                                    console.log(`[JS标签添加] 选择器未找到元素: ${selector}`);
                                    continue;
                                }
                                
                                // 检查元素是否可见和可编辑
                                const isVisible = element.offsetParent !== null && 
                                                  element.style.display !== 'none' && 
                                                  element.style.visibility !== 'hidden';
                                
                                if (!isVisible) {
                                    console.log(`[JS标签添加] 元素不可见: ${selector}`);
                                    continue;
                                }
                                
                                // 检查元素是否被禁用或只读
                                const isDisabled = element.disabled || element.readOnly;
                                if (isDisabled) {
                                    console.log(`[JS标签添加] 元素被禁用或只读: ${selector}`);
                                    continue;
                                }
                                
                                console.log(`[JS标签添加] 尝试使用选择器添加标签: ${selector}`);
                                
                                // 获取当前内容
                                let currentContent = '';
                                const tagName = element.tagName.toLowerCase();
                                if (tagName === 'textarea' || tagName === 'input') {
                                    currentContent = element.value || '';
                                } else {
                                    currentContent = element.textContent || element.innerText || '';
                                }
                                
                                console.log(`[JS标签添加] 元素类型: ${tagName}, 当前内容长度: ${currentContent.length}, 前50字符: ${currentContent.substring(0, 50)}`);
                                
                                // 检查是否已经包含了这些标签
                                let allTagsPresent = true;
                                const missingTags = [];
                                for (const tagStr of tagStrings) {
                                    if (!currentContent.includes(tagStr)) {
                                        allTagsPresent = false;
                                        missingTags.push(tagStr);
                                    }
                                }
                                
                                if (allTagsPresent) {
                                    console.log('[JS标签添加] 所有标签已存在于内容中，无需重复添加');
                                    return true;
                                } else {
                                    console.log(`[JS标签添加] 缺失的标签: ${missingTags}`);
                                }
                                
                                // 构建标签文本
                                const tagsText = ' ' + tagStrings.join(' ');
                                console.log(`[JS标签添加] 准备添加标签文本: ${tagsText}`);
                                
                                // 添加标签到内容末尾
                                if (tagName === 'textarea' || tagName === 'input') {
                                    // 对于textarea和input元素
                                    console.log(`[JS标签添加] 使用直接赋值方式添加标签到${tagName}元素`);
                                    element.value = currentContent + tagsText;
                                    console.log('[JS标签添加] 已更新textarea/input元素的值');
                                } else {
                                    // 对于可编辑div
                                    console.log(`[JS标签添加] 使用execCommand方式添加标签到${tagName}元素`);
                                    element.focus();
                                    
                                    // 将光标移动到末尾
                                    console.log('[JS标签添加] 将光标移动到元素末尾');
                                    const selection = window.getSelection();
                                    const range = document.createRange();
                                    range.selectNodeContents(element);
                                    range.collapse(false); // 光标移动到末尾
                                    selection.removeAllRanges();
                                    selection.addRange(range);
                                    
                                    // 插入标签文本
                                    console.log('[JS标签添加] 使用execCommand插入标签文本');
                                    try {
                                        document.execCommand('insertText', false, tagsText);
                                        console.log('[JS标签添加] 已使用execCommand插入标签文本');
                                    } catch (e) {
                                        console.error(`[JS标签添加] execCommand插入文本失败: ${e.message}`);
                                        // 尝试使用其他方法插入文本
                                        try {
                                            const textNode = document.createTextNode(tagsText);
                                            range.insertNode(textNode);
                                            console.log('[JS标签添加] 已使用insertNode方法插入标签文本');
                                        } catch (e2) {
                                            console.error(`[JS标签添加] insertNode方法也失败: ${e2.message}`);
                                            // 最后尝试直接修改innerHTML
                                            element.innerHTML = currentContent + tagsText;
                                            console.log('[JS标签添加] 已使用innerHTML方法插入标签文本');
                                        }
                                    }
                                }
                                
                                // 触发多个事件以确保框架能检测到变更
                                console.log('[JS标签添加] 触发input事件');
                                element.dispatchEvent(new Event('input', { bubbles: true }));
                                console.log('[JS标签添加] 触发change事件');
                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                console.log('[JS标签添加] 触发blur事件');
                                element.dispatchEvent(new Event('blur', { bubbles: true }));
                                
                                // 对于某些框架，可能需要额外的事件
                                if (tagName !== 'textarea' && tagName !== 'input') {
                                    console.log('[JS标签添加] 触发paste事件');
                                    element.dispatchEvent(new Event('paste', { bubbles: true }));
                                    console.log('[JS标签添加] 触发keyup事件');
                                    element.dispatchEvent(new Event('keyup', { bubbles: true }));
                                }
                                
                                console.log(`[JS标签添加] 成功添加标签，使用选择器: ${selector}`);
                                return true;
                                
                            } catch (e) {
                                console.error(`使用选择器 ${selector} 添加标签时出错:`, e);
                                continue;
                            }
                        }
                        
                        // 如果所有选择器都失败，尝试查找所有可能的文本输入元素
                        console.log('所有选择器都失败，尝试查找所有可能的文本输入元素');
                        const allInputs = document.querySelectorAll('textarea, input[type="text"], div[contenteditable="true"]');
                        console.log(`找到 ${allInputs.length} 个可能的文本输入元素`);
                        
                        for (let i = 0; i < allInputs.length; i++) {
                            const element = allInputs[i];
                            
                            // 检查元素是否可见
                            if (element.offsetParent === null) continue;
                            
                            try {
                                const tagName = element.tagName.toLowerCase();
                                let currentContent = '';
                                
                                if (tagName === 'textarea' || tagName === 'input') {
                                    currentContent = element.value || '';
                                } else {
                                    currentContent = element.textContent || element.innerText || '';
                                }
                                
                                // 如果内容不为空，认为可能是正文输入框
                                if (currentContent.length > 10) {
                                    console.log(`尝试使用通用元素添加标签，索引: ${i}, 内容长度: ${currentContent.length}`);
                                    
                                    const tagsText = ' ' + tagStrings.join(' ');
                                    
                                    if (tagName === 'textarea' || tagName === 'input') {
                                        element.value = currentContent + tagsText;
                                    } else {
                                        element.focus();
                                        const selection = window.getSelection();
                                        const range = document.createRange();
                                        range.selectNodeContents(element);
                                        range.collapse(false);
                                        selection.removeAllRanges();
                                        selection.addRange(range);
                                        document.execCommand('insertText', false, tagsText);
                                    }
                                    
                                    element.dispatchEvent(new Event('input', { bubbles: true }));
                                    element.dispatchEvent(new Event('change', { bubbles: true }));
                                    element.dispatchEvent(new Event('blur', { bubbles: true }));
                                    
                                    console.log(`使用通用元素成功添加标签，索引: ${i}`);
                                    return true;
                                }
                            } catch (e) {
                                console.error(`使用通用元素添加标签时出错，索引: ${i}`, e);
                                continue;
                            }
                        }
                        
                        console.log('所有尝试都失败了，无法添加标签');
                        return false;
                    }""", tag_strings)
                    
                    if success:
                        logger.info("使用JavaScript方式成功添加标签到正文内容")
                        content_found = True
                    else:
                        logger.error("JavaScript方式添加标签失败")
                        
                        # 尝试备用方案：直接查找并填充内容输入框
                        try:
                            logger.info("尝试备用方案：直接查找并填充内容输入框")
                            
                            # 尝试找到内容输入框并直接添加标签
                            content_selectors = [
                                'textarea[placeholder*="正文"]',
                                'textarea[placeholder*="内容"]',
                                'textarea',
                                'div[contenteditable="true"]',
                                'div[role="textbox"]'
                            ]
                            
                            for selector in content_selectors:
                                try:
                                    content_element = await page.wait_for_selector(selector, timeout=2000)
                                    if content_element:
                                        # 检查元素是否可见
                                        is_visible = await page.evaluate("""(element) => {
                                            return element.offsetParent !== null && 
                                                   element.style.display !== 'none' && 
                                                   element.style.visibility !== 'hidden';
                                        }""", content_element)
                                        
                                        if not is_visible:
                                            logger.info(f"元素不可见，跳过: {selector}")
                                            continue
                                        
                                        # 获取当前内容
                                        current_content = await content_element.evaluate("""(element) => {
                                            const tagName = element.tagName.toLowerCase();
                                            if (tagName === 'textarea' || tagName === 'input') {
                                                return element.value || '';
                                            } else {
                                                return element.textContent || element.innerText || '';
                                            }
                                        }""")
                                        
                                        logger.info(f"找到内容输入框，当前内容长度: {len(current_content)}")
                                        
                                        # 检查是否已包含标签
                                        all_tags_present = all(tag in current_content for tag in tag_strings)
                                        if all_tags_present:
                                            logger.info("所有标签已存在于内容中")
                                            content_found = True
                                            break
                                        
                                        # 添加标签
                                        tags_text = ' ' + ' '.join(tag_strings)
                                        
                                        # 根据元素类型添加标签
                                        tag_name = await content_element.evaluate("""(element) => {
                                            return element.tagName.toLowerCase();
                                        }""")
                                        
                                        if tag_name in ['textarea', 'input']:
                                            logger.info(f"[备用方案] 使用fill方法添加标签到{tag_name}元素")
                                            await content_element.fill(current_content + tags_text)
                                        else:
                                            logger.info(f"[备用方案] 使用键盘输入方式添加标签到{tag_name}元素")
                                            await content_element.click()
                                            await page.keyboard.press('End')
                                            await page.keyboard.type(tags_text)
                                        
                                        # 触发事件
                                        logger.info("[备用方案] 触发input事件")
                                        await content_element.evaluate("""(element) => {
                                            element.dispatchEvent(new Event('input', { bubbles: true }));
                                        }""")
                                        logger.info("[备用方案] 触发change事件")
                                        await content_element.evaluate("""(element) => {
                                            element.dispatchEvent(new Event('change', { bubbles: true }));
                                        }""")
                                        logger.info("[备用方案] 触发blur事件")
                                        await content_element.evaluate("""(element) => {
                                            element.dispatchEvent(new Event('blur', { bubbles: true }));
                                        }""")
                                        
                                        logger.info(f"使用备用方案成功添加标签，选择器: {selector}")
                                        content_found = True
                                        break
                                        
                                except Exception as e:
                                    logger.info(f"选择器 {selector} 失败: {e}")
                                    continue
                                    
                        except Exception as e:
                            logger.error(f"备用方案添加标签异常: {e}")
                            
                            # 最后尝试：模拟用户手动输入标签
                            try:
                                logger.info("尝试最后方案：模拟用户手动输入标签")
                                
                                # 查找所有可能的文本输入区域
                                all_inputs = await page.query_selector_all('textarea, input[type="text"], div[contenteditable="true"]')
                                logger.info(f"找到 {len(all_inputs)} 个可能的文本输入元素")
                                
                                for i, input_element in enumerate(all_inputs):
                                    try:
                                        # 检查元素是否可见
                                        is_visible = await page.evaluate("""(element) => {
                                            return element.offsetParent !== null && 
                                                   element.style.display !== 'none' && 
                                                   element.style.visibility !== 'hidden';
                                        }""", input_element)
                                        
                                        if not is_visible:
                                            continue
                                        
                                        # 获取当前内容
                                        current_content = await input_element.evaluate("""(element) => {
                                            const tagName = element.tagName.toLowerCase();
                                            if (tagName === 'textarea' || tagName === 'input') {
                                                return element.value || '';
                                            } else {
                                                return element.textContent || element.innerText || '';
                                            }
                                        }""")
                                        
                                        # 如果内容不为空，认为可能是正文输入框
                                        if len(current_content) > 10:
                                            logger.info(f"尝试手动输入标签，元素索引: {i}, 内容长度: {len(current_content)}")
                                            
                                            # 检查是否已包含标签
                                            all_tags_present = all(tag in current_content for tag in tag_strings)
                                            if all_tags_present:
                                                logger.info("所有标签已存在于内容中")
                                                content_found = True
                                                break
                                            
                                            # 点击元素并输入标签
                                            logger.info(f"[手动输入] 点击元素 {i}")
                                            await input_element.click()
                                            logger.info("[手动输入] 按下End键将光标移到末尾")
                                            await page.keyboard.press('End')
                                            
                                            # 输入标签
                                            tags_text = ' ' + ' '.join(tag_strings)
                                            logger.info(f"[手动输入] 输入标签文本: {tags_text}")
                                            await page.keyboard.type(tags_text)
                                            
                                            # 触发事件
                                            logger.info("[手动输入] 触发input事件")
                                            await input_element.evaluate("""(element) => {
                                                element.dispatchEvent(new Event('input', { bubbles: true }));
                                            }""")
                                            logger.info("[手动输入] 触发change事件")
                                            await input_element.evaluate("""(element) => {
                                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                            }""")
                                            logger.info("[手动输入] 触发blur事件")
                                            await input_element.evaluate("""(element) => {
                                                element.dispatchEvent(new Event('blur', { bubbles: true }));
                                            }""")
                                            
                                            logger.info(f"手动输入标签成功，元素索引: {i}")
                                            content_found = True
                                            break
                                            
                                    except Exception as e:
                                        logger.info(f"手动输入标签失败，元素索引: {i}, 错误: {e}")
                                        continue
                                        
                            except Exception as e:
                                logger.error(f"手动输入标签异常: {e}")
                                
                except Exception as e:
                    logger.error(f"JavaScript方式添加标签异常: {e}")
                    
                    # 尝试最基本的回退方案
                    try:
                        logger.info("尝试最基本的回退方案")
                        
                        # 尝试通过键盘快捷键添加标签
                        logger.info("[键盘快捷键] 按下End键将光标移到末尾")
                        await page.keyboard.press('End')
                        tags_text = ' ' + ' '.join(tag_strings)
                        logger.info(f"[键盘快捷键] 输入标签文本: {tags_text}")
                        await page.keyboard.type(tags_text)
                        
                        logger.info("[键盘快捷键] 使用键盘快捷键添加标签完成")
                        content_found = True
                        
                    except Exception as e:
                        logger.error(f"键盘快捷键添加标签异常: {e}")
                        logger.error("所有标签添加方案都失败了")
            
            if not content_found:
                logger.warning("无法找到内容输入框，标签添加失败")
                # 尝试截图以便调试
                try:
                    await page.screenshot(path='content_input_debug.png')
                    logger.info("已保存内容输入框调试截图: content_input_debug.png")
                except:
                    pass
                return True
            
            logger.info(f"成功将{len(tag_strings)}个标签添加到正文内容中")
            return True
            
        except Exception as e:
            logger.error(f"添加标签异常: {e}")
            # 标签添加失败不应阻止发布
            return True
    
    async def _set_publish_params(self, page: Page, params: Dict[str, Any]) -> bool:
        """设置发布参数
        
        Args:
            page: Playwright页面实例
            params: 发布参数
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始设置发布参数")
            
            # 查找并设置评论开关 - 适配小红书新界面
            comment_toggle_selectors = [
                '[data-testid="comment-toggle"]',
                '.comment-switch',
                '.switch-comment',
                '.toggle-comment',
                '[class*="comment"][class*="switch"]',
                '[class*="comment"][class*="toggle"]',
                '#comment-toggle',
                'input[name="allowComments"]',
                'input[class*="comment"]',
                'label >> text=评论 + div',
                'label >> text=允许评论 + div',
                '.setting-item:has-text("评论") .switch'
            ]
            
            # 尝试设置评论开关
            comment_setting_success = False
            for selector in comment_toggle_selectors:
                try:
                    # 检查元素是否存在
                    element = await page.query_selector(selector)
                    if not element:
                        continue
                    
                    # 检查元素是否可见
                    is_visible = await page.evaluate('(el) => el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden"', element)
                    if not is_visible:
                        continue
                    
                    # 判断是否需要点击切换状态
                    current_state = await page.evaluate('''(el) => {
                        if (el.checked !== undefined) return el.checked;
                        if (el.classList.contains("active") || el.classList.contains("on")) return true;
                        if (el.querySelector(".active") || el.querySelector(".on")) return true;
                        return false;
                    }''', element)
                    
                    desired_state = params.get('enable_comments', True)
                    
                    if current_state != desired_state:
                        await element.click()
                        await asyncio.sleep(0.5)  # 等待状态切换
                    
                    logger.info(f"成功设置评论开关，选择器: {selector}, 状态: {'开启' if desired_state else '关闭'}")
                    comment_setting_success = True
                    break
                except Exception as e:
                    logger.debug(f"尝试评论开关选择器 {selector} 失败: {e}")
                    continue
            
            if not comment_setting_success:
                logger.warning("未能找到并设置评论开关")
            
            # 设置同步到其他平台选项 - 适配小红书新界面
            sync_toggle_selectors = [
                '[data-testid="sync-toggle"]',
                '.sync-switch',
                '.switch-sync',
                '.toggle-sync',
                '[class*="sync"][class*="switch"]',
                '[class*="sync"][class*="toggle"]',
                '#sync-toggle',
                'input[name="syncToOtherPlatforms"]',
                'input[class*="sync"]',
                'label >> text=同步 + div',
                'label >> text=同步到其他平台 + div',
                '.setting-item:has-text("同步") .switch'
            ]
            
            # 尝试设置同步选项
            sync_setting_success = False
            for selector in sync_toggle_selectors:
                try:
                    element = await page.query_selector(selector)
                    if not element:
                        continue
                    
                    is_visible = await page.evaluate('(el) => el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden"', element)
                    if not is_visible:
                        continue
                    
                    current_state = await page.evaluate('''(el) => {
                        if (el.checked !== undefined) return el.checked;
                        if (el.classList.contains("active") || el.classList.contains("on")) return true;
                        if (el.querySelector(".active") || el.querySelector(".on")) return true;
                        return false;
                    }''', element)
                    
                    desired_state = params.get('sync_to_other_platforms', False)
                    
                    if current_state != desired_state:
                        await element.click()
                        await asyncio.sleep(0.5)
                    
                    logger.info(f"成功设置同步选项，选择器: {selector}, 状态: {'开启' if desired_state else '关闭'}")
                    sync_setting_success = True
                    break
                except Exception as e:
                    logger.debug(f"尝试同步开关选择器 {selector} 失败: {e}")
                    continue
            
            if not sync_setting_success:
                logger.debug("未能找到并设置同步选项")
            
            # 设置隐私选项 - 适配小红书新界面
            visibility_selectors = [
                '.visibility-setting',
                '.privacy-setting',
                '[data-testid="visibility-setting"]',
                '[class*="privacy"][class*="setting"]',
                '[class*="visibility"][class*="setting"]',
                '#visibility-select',
                '#privacy-select',
                'select[name="visibility"]',
                'select[name="privacy"]',
                '.setting-item:has-text("可见性")',
                '.setting-item:has-text("隐私")'
            ]
            
            # 尝试设置可见性
            visibility_setting_success = False
            visibility = params.get('visibility', 'public')  # 默认公开
            
            for selector in visibility_selectors:
                try:
                    element = await page.query_selector(selector)
                    if not element:
                        continue
                    
                    is_visible = await page.evaluate('(el) => el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden"', element)
                    if not is_visible:
                        continue
                    
                    # 根据元素类型采取不同的设置策略
                    tag_name = await page.evaluate('(el) => el.tagName.toLowerCase()', element)
                    
                    if tag_name == 'select':
                        # 如果是select元素
                        if visibility == 'public':
                            await page.select_option(selector, 'public')
                        elif visibility == 'private':
                            await page.select_option(selector, 'private')
                        elif visibility == 'friends':
                            await page.select_option(selector, 'friends')
                    else:
                        # 如果是按钮或链接，点击后选择相应选项
                        await element.click()
                        await asyncio.sleep(0.5)
                        
                        # 尝试选择相应的选项
                        if visibility == 'public':
                            public_option = await page.query_selector('.option-public, .public-option, :text("公开")')
                            if public_option:
                                await public_option.click()
                        elif visibility == 'private':
                            private_option = await page.query_selector('.option-private, .private-option, :text("仅自己可见")')
                            if private_option:
                                await private_option.click()
                        elif visibility == 'friends':
                            friends_option = await page.query_selector('.option-friends, .friends-option, :text("仅好友可见")')
                            if friends_option:
                                await friends_option.click()
                    
                    logger.info(f"成功设置可见性，选择器: {selector}, 状态: {visibility}")
                    visibility_setting_success = True
                    break
                except Exception as e:
                    logger.debug(f"尝试可见性设置选择器 {selector} 失败: {e}")
                    continue
            
            if not visibility_setting_success:
                logger.debug("未能找到并设置可见性选项")
            
            # 处理其他可能的发布参数
            # 例如：是否允许保存图片、是否允许转发等
            
            logger.info("发布参数设置完成")
            return True
            
        except Exception as e:
            logger.error(f"设置发布参数失败: {e}")
            # 参数设置失败不应阻止发布
            return True
    
    async def _execute_publish(self, page: Page) -> Dict[str, Any]:
        """执行发布操作
        
        Args:
            page: Playwright页面实例
            
        Returns:
            Dict[str, Any]: 发布结果数据
        """
        try:
            # 查找发布按钮 - 适配小红书新界面
            publish_button_selectors = [
                # 小红书新界面可能的发布按钮选择器 - 基于最新界面优化
                'button[type="button"].publish-btn',
                'button[type="button"][class*="publish"][class*="btn"]',
                'button[type="button"].submit-button',
                'button[type="submit"]',
                '.publish-button',
                '.btn-publish',
                '[data-testid="publish-button"]',
                '.publish-action button',
                '#publish-btn',
                '.operation-buttons .primary-btn',
                '.action-buttons button:nth-child(2)',
                '.footer-actions .publish-btn',
                'button >> text=发布',
                'button >> text=发布笔记',
                '.submit-actions button',
                # 新增小红书最新界面专用选择器 - 基于用户反馈优化
                '.btn-wrapper .btn-primary',
                '.bottom-actions .btn-primary',
                '.publish-footer .btn-primary',
                '.editor-footer .btn-primary',
                '.note-publish-footer .btn-primary',
                '.publish-container .btn-primary',
                '.editor-container .btn-primary',
                '.note-editor-footer .btn-primary',
                '.publish-panel .btn-primary',
                '.note-publish-panel .btn-primary',
                '.publish-actions .btn-primary',
                '.editor-actions .btn-primary',
                '.note-publish-actions .btn-primary',
                'button[class*="primary"][class*="btn"]',
                'button[class*="publish"][class*="primary"]',
                'button[class*="submit"][class*="primary"]',
                'button[class*="send"]',
                'button[class*="confirm"]',
                'button[class*="done"]',
                'button[aria-label*="发布"]',
                'button[aria-label*="提交"]',
                'button[title*="发布"]',
                'button[title*="提交"]',
                # 基于用户反馈的特定选择器
                '.btn-primary:has-text("发布")',
                '.btn-primary:has-text("发布笔记")',
                '.btn-primary:has-text("提交")',
                'button.primary:has-text("发布")',
                'button.primary:has-text("发布笔记")',
                'button.primary:has-text("提交")',
                # 通用选择器
                'button:has-text("发布")',
                'button:has-text("发布笔记")',
                'button:has-text("提交")',
                'button:has-text("完成")',
                'button:has-text("发送")'
            ]
            
            publish_button_selector = None
            
            # 优先使用query_selector查找可见的发布按钮
            for selector in publish_button_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        # 检查元素是否可见
                        is_visible = await page.evaluate('(el) => el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden"', element)
                        if is_visible:
                            # 检查按钮文本是否包含发布相关内容
                            text = await element.text_content()
                            if '发布' in text or 'publish' in text.lower():
                                publish_button_selector = selector
                                logger.info(f"找到可见的发布按钮: {selector}, 文本: {text.strip()}")
                                break
                    if publish_button_selector:
                        break
                except Exception as e:
                    logger.debug(f"尝试发布按钮选择器 {selector} 失败: {e}")
                    continue
            
            # 如果query_selector没找到，尝试使用wait_for_selector
            if not publish_button_selector:
                for selector in publish_button_selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=2000)
                        # 再次检查按钮是否可见
                        if ">>" in selector:
                            # 使用Playwright的locator处理Playwright特有语法
                            is_visible = await page.locator(selector).is_visible()
                        else:
                            # 使用JavaScript处理标准CSS选择器
                            is_visible = await page.evaluate('(selector) => {\n                            const el = document.querySelector(selector);\n                            return el && el.offsetParent !== null && el.style.display !== "none" && el.style.visibility !== "hidden";\n                        }', selector)
                        
                        if is_visible:
                            # 检查按钮文本
                            if ">>" in selector:
                                # 使用Playwright的locator处理Playwright特有语法
                                text = await page.locator(selector).inner_text()
                            else:
                                # 使用JavaScript处理标准CSS选择器
                                text = await page.evaluate('(selector) => document.querySelector(selector).textContent', selector)
                                
                            if '发布' in text or 'publish' in text.lower():
                                publish_button_selector = selector
                                logger.info(f"通过wait_for_selector找到发布按钮: {selector}")
                                break
                    except:
                        continue
            
            # 如果仍然找不到，尝试使用JavaScript查找
            if not publish_button_selector:
                try:
                    publish_button_selector = await page.evaluate('''() => {
                        // 查找所有按钮
                        const buttons = document.querySelectorAll('button');
                        
                        for (const button of buttons) {
                            // 检查是否可见
                            if (button.offsetParent === null) continue;
                            
                            // 检查按钮文本
                            const text = button.textContent.trim();
                            if (text.includes('发布') || text.toLowerCase().includes('publish') || 
                                text.includes('提交') || text.includes('完成') || text.includes('发送')) {
                                // 获取选择器
                                if (button.id) return '#' + button.id;
                                if (button.dataset.testid) return `[data-testid="${button.dataset.testid}"]`;
                                if (button.className) return `.${button.className.split(' ').join('.')}`;
                            }
                        }
                        
                        // 如果还没找到，尝试查找包含特定类名的按钮
                        const primaryButtons = document.querySelectorAll('button[class*="primary"], button[class*="btn-primary"]');
                        for (const button of primaryButtons) {
                            if (button.offsetParent === null) continue;
                            
                            const text = button.textContent.trim();
                            if (text.includes('发布') || text.toLowerCase().includes('publish') || 
                                text.includes('提交') || text.includes('完成') || text.includes('发送')) {
                                if (button.id) return '#' + button.id;
                                if (button.dataset.testid) return `[data-testid="${button.dataset.testid}"]`;
                                if (button.className) return `.${button.className.split(' ').join('.')}`;
                            }
                        }
                        
                        // 最后尝试查找所有可见按钮中的最后一个（通常是发布按钮）
                        const allVisibleButtons = Array.from(document.querySelectorAll('button')).filter(btn => {
                            return btn.offsetParent !== null && 
                                   btn.style.display !== 'none' && 
                                   btn.style.visibility !== 'hidden';
                        });
                        
                        if (allVisibleButtons.length > 0) {
                            const lastButton = allVisibleButtons[allVisibleButtons.length - 1];
                            if (lastButton.id) return '#' + lastButton.id;
                            if (lastButton.dataset.testid) return `[data-testid="${lastButton.dataset.testid}"]`;
                            if (lastButton.className) return `.${lastButton.className.split(' ').join('.')}`;
                        }
                        
                        return null;
                    }''')
                    if publish_button_selector:
                        logger.info(f"通过JavaScript找到发布按钮: {publish_button_selector}")
                except Exception as e:
                    logger.debug(f"JavaScript查找发布按钮失败: {e}")
            
            if not publish_button_selector:
                logger.error("未找到发布按钮，尝试截图以便调试")
                try:
                    # 保存当前页面截图用于调试
                    screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "publish_button_debug.png")
                    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                    await page.screenshot(path=screenshot_path)
                    logger.info(f"已保存调试截图: {screenshot_path}")
                    
                    # 获取页面HTML内容用于调试
                    html_content = await page.content()
                    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "publish_button_debug.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    logger.info(f"已保存页面HTML: {html_path}")
                    
                    # 获取当前URL
                    current_url = page.url
                    logger.info(f"当前页面URL: {current_url}")
                    
                    # 尝试获取页面标题
                    page_title = await page.title()
                    logger.info(f"当前页面标题: {page_title}")
                    
                    # 尝试获取页面中所有可见的文本
                    try:
                        visible_text = await page.evaluate("""
                            () => {
                                const elements = Array.from(document.querySelectorAll('*'));
                                return elements
                                    .filter(el => {
                                        const style = window.getComputedStyle(el);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               el.offsetWidth > 0 && 
                                               el.offsetHeight > 0;
                                    })
                                    .map(el => el.innerText.trim())
                                    .filter(text => text.length > 0)
                                    .slice(0, 20); // 只取前20个文本元素
                            }
                        """)
                        logger.info(f"页面可见文本: {visible_text}")
                    except Exception as e:
                        logger.debug(f"获取页面可见文本时出错: {e}")
                    
                    # 尝试获取所有按钮的文本和选择器
                    try:
                        buttons_info = await page.evaluate("""
                            () => {
                                const buttons = Array.from(document.querySelectorAll('button, .btn, [role="button"]'));
                                return buttons
                                    .filter(btn => {
                                        const style = window.getComputedStyle(btn);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               btn.offsetWidth > 0 && 
                                               btn.offsetHeight > 0;
                                    })
                                    .map(btn => {
                                        let selector = '';
                                        if (btn.id) selector = '#' + btn.id;
                                        else if (btn.dataset.testid) selector = `[data-testid="${btn.dataset.testid}"]`;
                                        else if (btn.className) selector = '.' + btn.className.split(' ').join('.');
                                        
                                        return {
                                            text: btn.innerText.trim(),
                                            selector: selector,
                                            className: btn.className,
                                            id: btn.id || '',
                                            ariaLabel: btn.getAttribute('aria-label') || '',
                                            title: btn.getAttribute('title') || ''
                                        };
                                    });
                            }
                        """)
                        logger.info(f"页面按钮信息: {buttons_info}")
                    except Exception as e:
                        logger.debug(f"获取页面按钮信息时出错: {e}")
                    
                    # 尝试获取所有表单元素的文本
                    try:
                        forms_text = await page.evaluate("""
                            () => {
                                const inputs = Array.from(document.querySelectorAll('input, textarea, select'));
                                return inputs
                                    .filter(input => {
                                        const style = window.getComputedStyle(input);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               input.offsetWidth > 0 && 
                                               input.offsetHeight > 0;
                                    })
                                    .map(input => ({
                                        type: input.type || input.tagName.toLowerCase(),
                                        placeholder: input.placeholder || '',
                                        value: input.value || '',
                                        name: input.name || '',
                                        id: input.id || ''
                                    }));
                            }
                        """)
                        logger.info(f"页面表单元素: {forms_text}")
                    except Exception as e:
                        logger.debug(f"获取页面表单元素时出错: {e}")
                    
                    # 尝试获取所有链接的文本
                    try:
                        links_text = await page.evaluate("""
                            () => {
                                const links = Array.from(document.querySelectorAll('a'));
                                return links
                                    .filter(link => {
                                        const style = window.getComputedStyle(link);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               link.offsetWidth > 0 && 
                                               link.offsetHeight > 0;
                                    })
                                    .map(link => ({
                                        text: link.innerText.trim(),
                                        href: link.href || ''
                                    }))
                                    .filter(link => link.text.length > 0);
                            }
                        """)
                        logger.info(f"页面链接: {links_text}")
                    except Exception as e:
                        logger.debug(f"获取页面链接时出错: {e}")
                    
                    # 尝试获取所有弹窗或模态框的信息
                    try:
                        modals_info = await page.evaluate("""
                            () => {
                                const modals = Array.from(document.querySelectorAll('.modal, .dialog, .popup, .overlay, [role="dialog"], [role="modal"]'));
                                return modals
                                    .filter(modal => {
                                        const style = window.getComputedStyle(modal);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               modal.offsetWidth > 0 && 
                                               modal.offsetHeight > 0;
                                    })
                                    .map(modal => ({
                                        className: modal.className,
                                        id: modal.id || '',
                                        text: modal.innerText.trim()
                                    }));
                            }
                        """)
                        logger.info(f"页面弹窗/模态框: {modals_info}")
                    except Exception as e:
                        logger.debug(f"获取页面弹窗/模态框时出错: {e}")
                    
                    # 尝试获取所有消息或通知的信息
                    try:
                        notifications_info = await page.evaluate("""
                            () => {
                                const notifications = Array.from(document.querySelectorAll('.message, .notification, .toast, .alert, .notice'));
                                return notifications
                                    .filter(notification => {
                                        const style = window.getComputedStyle(notification);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               notification.offsetWidth > 0 && 
                                               notification.offsetHeight > 0;
                                    })
                                    .map(notification => ({
                                        className: notification.className,
                                        id: notification.id || '',
                                        text: notification.innerText.trim()
                                    }));
                            }
                        """)
                        logger.info(f"页面消息/通知: {notifications_info}")
                    except Exception as e:
                        logger.debug(f"获取页面消息/通知时出错: {e}")
                    
                except Exception as e:
                    logger.error(f"保存调试信息时出错: {e}")
                
                raise RuntimeError("未找到发布按钮")
            
            # 点击发布按钮前先滚动到按钮位置
            # 检查选择器是否为Playwright特有语法，如果是，则使用Playwright的scroll_into_view方法
            if ">>" in publish_button_selector:
                # 使用Playwright的scroll_into_view方法处理Playwright特有语法
                await page.locator(publish_button_selector).scroll_into_view_if_needed()
            else:
                # 使用JavaScript的scrollIntoView方法处理标准CSS选择器
                await page.evaluate('''(selector) => {
                    const button = document.querySelector(selector);
                    if (button) {
                        button.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }''', selector=publish_button_selector)
            await asyncio.sleep(0.5)
            
            # 尝试多种方式点击发布按钮
            click_success = False
            
            # 方法1：标准点击（使用locator处理Playwright特有语法）
            try:
                if ">>" in publish_button_selector:
                    await page.locator(publish_button_selector).click()
                else:
                    await page.click(publish_button_selector)
                logger.info("使用方法1(标准点击)成功点击发布按钮")
                click_success = True
            except Exception as e:
                logger.debug(f"点击方法1失败: {e}")
            
            # 方法2：强制点击
            if not click_success:
                try:
                    if ">>" in publish_button_selector:
                        await page.locator(publish_button_selector).click(force=True)
                    else:
                        await page.click(publish_button_selector, force=True)
                    logger.info("使用方法2(强制点击)成功点击发布按钮")
                    click_success = True
                except Exception as e:
                    logger.debug(f"点击方法2失败: {e}")
            
            # 方法3：JavaScript点击（仅对标准CSS选择器使用）
            if not click_success and ">>" not in publish_button_selector:
                try:
                    await page.evaluate(f'(selector) => document.querySelector(selector).click()', selector=publish_button_selector)
                    logger.info("使用方法3(JavaScript点击)成功点击发布按钮")
                    click_success = True
                except Exception as e:
                    logger.debug(f"点击方法3失败: {e}")
            
            # 方法4：双击（某些界面需要）
            if not click_success:
                try:
                    if ">>" in publish_button_selector:
                        await page.locator(publish_button_selector).dblclick()
                    else:
                        await page.dblclick(publish_button_selector)
                    logger.info("使用方法4(双击)成功点击发布按钮")
                    click_success = True
                except Exception as e:
                    logger.debug(f"点击方法4失败: {e}")
            
            # 方法5：先聚焦再点击
            if not click_success:
                try:
                    if ">>" in publish_button_selector:
                        await page.locator(publish_button_selector).focus()
                    else:
                        await (await page.query_selector(publish_button_selector)).focus()
                    await page.keyboard.press('Enter')
                    logger.info("使用方法5(聚焦后回车)成功点击发布按钮")
                    click_success = True
                except Exception as e:
                    logger.debug(f"点击方法5失败: {e}")
            
            if not click_success:
                logger.error("所有点击方法均失败")
                raise RuntimeError("无法点击发布按钮")
                
            logger.info("已点击发布按钮，等待发布完成...")
            
            # 等待发布完成的多种可能指标
            success_indicators = [
                # 通用成功提示
                '.publish-success',  # 成功提示
                '[data-testid="publish-success"]',
                '.success-message',
                '.success-tip',
                '.dialog-success',
                '.alert-success',
                '[class*="success"][class*="publish"]',
                'h2 >> text=发布成功',
                'div >> text=发布成功',
                
                # 小红书特定成功提示
                '.publish-success-modal',
                '.publish-success-toast',
                '.publish-complete',
                '.note-published',
                '.note-publish-success',
                '.redbook-success',
                '.xiaohongshu-success',
                '.ant-message-success',
                '.el-message--success',
                '.toast-success',
                '.notification-success',
                
                # 文本内容提示
                'text=发布成功',
                'text=笔记已发布',
                'text=发布完成',
                'text=提交成功',
                'text=已成功发布',
                'text=笔记发布成功',
                'text=发布成功啦',
                'text=已发布',
                'text=Successfully published',
                'text=Publish successful',
                'text=Published successfully',
                
                # 可能的URL变化
                'url=**/success**',
                'url=**/complete**',
                'url=**/published**',
                'url=**/note/**',
                'url=**/explore/**',
                'url=**/creator**'
            ]
            
            # 检查发布是否成功的状态变量
            publish_success = False
            note_id = None
            start_time = time.time()
            max_wait_time = 30  # 减少等待时间到30秒
            check_interval = 0.5  # 减少检查间隔到0.5秒
            fast_check_count = 0  # 快速检查计数器
            fast_check_limit = 10  # 前10次使用快速检查模式
            
            # 循环检查发布状态
            while time.time() - start_time < max_wait_time:
                # 检查是否有成功提示
                # 前10次检查只检查最常见的指示器，加快响应速度
                if fast_check_count < fast_check_limit:
                    # 快速检查模式：只检查最常见的成功指示器
                    priority_indicators = [
                        'text=发布成功',
                        'text=笔记已发布',
                        'text=发布完成',
                        'url=**/success**',
                        'url=**/note/**',
                        'url=**/explore/**'
                    ]
                    indicators_to_check = priority_indicators
                    timeout = 500  # 快速检查使用更短的超时
                else:
                    # 全面检查模式：检查所有指示器
                    indicators_to_check = success_indicators
                    timeout = 1000  # 正常检查使用标准超时
                
                fast_check_count += 1
                
                for indicator in indicators_to_check:
                    try:
                        # 处理不同类型的指示器
                        if indicator.startswith('text='):
                            # 文本内容检查
                            text = indicator[5:]  # 移除 'text=' 前缀
                            if await page.locator(f"text={text}").is_visible(timeout=timeout):
                                logger.info(f"检测到发布成功文本: {text}")
                                publish_success = True
                                break
                        elif indicator.startswith('url='):
                            # URL变化检查
                            current_url = page.url
                            url_pattern = indicator[4:]  # 移除 'url=' 前缀
                            # 简单的通配符匹配
                            pattern = url_pattern.replace('**', '.*').replace('*', '[^/]*')
                            if re.search(pattern, current_url):
                                logger.info(f"检测到URL变化，可能发布成功: {current_url}")
                                publish_success = True
                                # 尝试从URL提取笔记ID
                                note_id_match = re.search(r'noteId=(\w+)|/note/(\w+)|/explore/(\w+)', current_url)
                                if note_id_match:
                                    note_id = note_id_match.group(1) or note_id_match.group(2) or note_id_match.group(3)
                                    logger.info(f"从URL提取到笔记ID: {note_id}")
                                break
                        else:
                            # CSS选择器检查
                            if await page.is_visible(indicator, timeout=timeout):
                                logger.info(f"检测到发布成功提示: {indicator}")
                                publish_success = True
                                break
                    except Exception as e:
                        logger.debug(f"检查发布指标 {indicator} 时出错: {e}")
                        continue
                
                if publish_success:
                    break
                
                # 检查URL是否变化（可能跳转到成功页面）
                current_url = page.url
                if 'publish/success' in current_url or 'note/' in current_url or 'explore/' in current_url:
                    logger.info(f"检测到URL变化，可能发布成功: {current_url}")
                    publish_success = True
                    # 尝试从URL提取笔记ID
                    note_id_match = re.search(r'noteId=(\w+)|/note/(\w+)|/explore/(\w+)', current_url)
                    if note_id_match:
                        note_id = note_id_match.group(1) or note_id_match.group(2) or note_id_match.group(3)
                        logger.info(f"从URL提取到笔记ID: {note_id}")
                    break
                
                # 检查是否有错误提示
                try:
                    error_selectors = [
                        '.error-message',
                        '.publish-error',
                        '.error-tip',
                        '.dialog-error',
                        '.alert-error',
                        '.ant-message-error',
                        '.el-message--error',
                        '.toast-error',
                        '.notification-error',
                        'text=发布失败',
                        'text=发布错误',
                        'text=发布异常',
                        'text=发布失败，请重试',
                        'text=Publish failed',
                        'text=Publish error'
                    ]
                    
                    for error_selector in error_selectors:
                        if error_selector.startswith('text='):
                            text = error_selector[5:]
                            if await page.locator(f"text={text}").is_visible(timeout=timeout):
                                logger.error(f"检测到发布错误: {text}")
                                raise RuntimeError(f"发布失败: {text}")
                        else:
                            error_element = await page.query_selector(error_selector)
                            if error_element and await error_element.is_visible():
                                error_text = await error_element.text_content()
                                logger.error(f"检测到发布错误: {error_text}")
                                raise RuntimeError(f"发布失败: {error_text}")
                except Exception as e:
                    if "发布失败" in str(e):
                        raise
                    logger.debug(f"检查错误提示时出错: {e}")
                
                # 检查是否回到了笔记列表或主页
                try:
                    # 检查是否在笔记列表页面
                    list_indicators = [
                        ".note-list",
                        ".note-grid",
                        ".my-notes",
                        ".notes-container",
                        "[data-testid='note-list']",
                        ".creator-center",
                        ".content-management",
                        "text=我的笔记",
                        "text=笔记管理",
                        "text=创作中心"
                    ]
                    
                    for indicator in list_indicators:
                        if indicator.startswith('text='):
                            text = indicator[5:]
                            if await page.locator(f"text={text}").is_visible(timeout=timeout):
                                logger.info(f"检测到已返回笔记列表页面: {text}")
                                publish_success = True
                                break
                        else:
                            if await page.is_visible(indicator, timeout=timeout):
                                logger.info(f"检测到已返回笔记列表页面: {indicator}")
                                publish_success = True
                                break
                    
                    if publish_success:
                        break
                except Exception as e:
                    logger.debug(f"检查笔记列表页面时出错: {e}")
                
                await asyncio.sleep(check_interval)
            
            # 如果检测到发布成功
            if publish_success:
                logger.info("发布成功")
                result = {"status": "success"}
                
                # 如果没有从URL获取到笔记ID，尝试从页面元素获取
                if not note_id:
                    try:
                        # 尝试从成功提示中提取笔记ID
                        note_id_element = await page.query_selector('[data-note-id], [class*="note-id"], [id*="note-id"]')
                        if note_id_element:
                            note_id = await note_id_element.get_attribute('data-note-id')
                            if not note_id:
                                # 尝试从元素文本提取
                                text = await note_id_element.text_content()
                                note_id_match = re.search(r'\b[A-Za-z0-9]{16,}\b', text)  # 假设笔记ID是16位以上的字母数字组合
                                if note_id_match:
                                    note_id = note_id_match.group(0)
                    except Exception as e:
                        logger.debug(f"尝试从页面元素提取笔记ID失败: {e}")
                
                # 设置笔记ID和URL
                if note_id:
                    result['note_id'] = note_id
                    result['publish_url'] = f"https://www.xiaohongshu.com/explore/{note_id}"
                
                return result
            else:
                # 超时但可能已发布成功，再次检查URL
                current_url = page.url
                if 'publish/success' in current_url or 'note/' in current_url or 'explore/' in current_url:
                    logger.info(f"超时但URL显示可能已发布成功: {current_url}")
                    result = {"status": "success"}
                    note_id_match = re.search(r'noteId=(\w+)|/note/(\w+)|/explore/(\w+)', current_url)
                    if note_id_match:
                        note_id = note_id_match.group(1) or note_id_match.group(2) or note_id_match.group(3)
                        result['note_id'] = note_id
                        result['publish_url'] = f"https://www.xiaohongshu.com/explore/{note_id}"
                    return result
                
                # 尝试截图记录当前状态
                try:
                    # 保存当前页面截图用于调试
                    screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "publish_timeout_debug.png")
                    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                    await page.screenshot(path=screenshot_path)
                    logger.info(f"已保存调试截图: {screenshot_path}")
                    
                    # 获取页面HTML内容用于调试
                    html_content = await page.content()
                    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "publish_timeout_debug.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    logger.info(f"已保存页面HTML: {html_path}")
                    
                    # 获取当前URL
                    current_url = page.url
                    logger.info(f"当前页面URL: {current_url}")
                    
                    # 尝试获取页面标题
                    page_title = await page.title()
                    logger.info(f"当前页面标题: {page_title}")
                    
                    # 尝试获取页面中所有可见的文本
                    try:
                        visible_text = await page.evaluate("""
                            () => {
                                const elements = Array.from(document.querySelectorAll('*'));
                                return elements
                                    .filter(el => {
                                        const style = window.getComputedStyle(el);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               el.offsetWidth > 0 && 
                                               el.offsetHeight > 0;
                                    })
                                    .map(el => el.innerText.trim())
                                    .filter(text => text.length > 0)
                                    .slice(0, 20); // 只取前20个文本元素
                            }
                        """)
                        logger.info(f"页面可见文本: {visible_text}")
                    except Exception as e:
                        logger.debug(f"获取页面可见文本时出错: {e}")
                    
                    # 尝试获取所有按钮的文本
                    try:
                        buttons_text = await page.evaluate("""
                            () => {
                                const buttons = Array.from(document.querySelectorAll('button, .btn, [role="button"]'));
                                return buttons
                                    .filter(btn => {
                                        const style = window.getComputedStyle(btn);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               btn.offsetWidth > 0 && 
                                               btn.offsetHeight > 0;
                                    })
                                    .map(btn => btn.innerText.trim())
                                    .filter(text => text.length > 0);
                            }
                        """)
                        logger.info(f"页面按钮文本: {buttons_text}")
                    except Exception as e:
                        logger.debug(f"获取页面按钮文本时出错: {e}")
                    
                    # 尝试获取所有表单元素的文本
                    try:
                        forms_text = await page.evaluate("""
                            () => {
                                const inputs = Array.from(document.querySelectorAll('input, textarea, select'));
                                return inputs
                                    .filter(input => {
                                        const style = window.getComputedStyle(input);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               input.offsetWidth > 0 && 
                                               input.offsetHeight > 0;
                                    })
                                    .map(input => ({
                                        type: input.type || input.tagName.toLowerCase(),
                                        placeholder: input.placeholder || '',
                                        value: input.value || '',
                                        name: input.name || '',
                                        id: input.id || ''
                                    }));
                            }
                        """)
                        logger.info(f"页面表单元素: {forms_text}")
                    except Exception as e:
                        logger.debug(f"获取页面表单元素时出错: {e}")
                    
                    # 尝试获取所有链接的文本
                    try:
                        links_text = await page.evaluate("""
                            () => {
                                const links = Array.from(document.querySelectorAll('a'));
                                return links
                                    .filter(link => {
                                        const style = window.getComputedStyle(link);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               link.offsetWidth > 0 && 
                                               link.offsetHeight > 0;
                                    })
                                    .map(link => ({
                                        text: link.innerText.trim(),
                                        href: link.href || ''
                                    }))
                                    .filter(link => link.text.length > 0);
                            }
                        """)
                        logger.info(f"页面链接: {links_text}")
                    except Exception as e:
                        logger.debug(f"获取页面链接时出错: {e}")
                    
                    # 尝试获取所有弹窗或模态框的信息
                    try:
                        modals_info = await page.evaluate("""
                            () => {
                                const modals = Array.from(document.querySelectorAll('.modal, .dialog, .popup, .overlay, [role="dialog"], [role="modal"]'));
                                return modals
                                    .filter(modal => {
                                        const style = window.getComputedStyle(modal);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               modal.offsetWidth > 0 && 
                                               modal.offsetHeight > 0;
                                    })
                                    .map(modal => ({
                                        className: modal.className,
                                        id: modal.id || '',
                                        text: modal.innerText.trim()
                                    }));
                            }
                        """)
                        logger.info(f"页面弹窗/模态框: {modals_info}")
                    except Exception as e:
                        logger.debug(f"获取页面弹窗/模态框时出错: {e}")
                    
                    # 尝试获取所有消息或通知的信息
                    try:
                        notifications_info = await page.evaluate("""
                            () => {
                                const notifications = Array.from(document.querySelectorAll('.message, .notification, .toast, .alert, .notice'));
                                return notifications
                                    .filter(notification => {
                                        const style = window.getComputedStyle(notification);
                                        return style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               notification.offsetWidth > 0 && 
                                               notification.offsetHeight > 0;
                                    })
                                    .map(notification => ({
                                        className: notification.className,
                                        id: notification.id || '',
                                        text: notification.innerText.trim()
                                    }));
                            }
                        """)
                        logger.info(f"页面消息/通知: {notifications_info}")
                    except Exception as e:
                        logger.debug(f"获取页面消息/通知时出错: {e}")
                    
                except Exception as e:
                    logger.error(f"保存调试信息时出错: {e}")
                
                raise RuntimeError("发布超时，未检测到发布成功指标")
                
        except Exception as e:
            logger.error(f"执行发布失败: {e}")
            raise
    
    async def close(self) -> None:
        """关闭发布器，释放资源"""
        try:
            if hasattr(self, 'browser_manager') and self.browser_manager is not None:
                await self.browser_manager.close()
            self.is_initialized = False
            logger.info("发布器已关闭")
        except Exception as e:
            logger.error(f"关闭发布器失败: {e}")
    
    async def _fill_content(self, page, note_data):
        """填充笔记内容，包括标题和正文
        
        Args:
            page: Playwright页面实例
            note_data: 笔记数据，可以是字典或对象，包含标题和内容
        """
        try:
            logger.info("开始填充笔记内容")
            
            # 预处理内容 - 兼容字典和对象类型
            if isinstance(note_data, dict):
                title = note_data.get('title', '').strip()
                content = publish_utils.preprocess_content(note_data.get('content', ''))
            else:
                # 处理对象类型
                if hasattr(note_data, 'topic') and hasattr(note_data.topic, 'title'):
                    title = str(note_data.topic.title).strip() if note_data.topic.title else ''
                elif hasattr(note_data, 'title'):
                    title = str(note_data.title).strip() if note_data.title else ''
                else:
                    title = ''
                    
                if hasattr(note_data, 'content') and hasattr(note_data.content, 'text'):
                    content = publish_utils.preprocess_content(note_data.content.text if note_data.content.text else '')
                elif hasattr(note_data, 'content'):
                    content = publish_utils.preprocess_content(note_data.content if note_data.content else '')
                else:
                    content = ''
            
            logger.info(f"标题长度: {len(title)}, 内容长度: {len(content)}")
            
            # 智能选择器检测函数 - 预先检测选择器有效性
            async def smart_selector_check(page, selectors, timeout=500):
                """智能检测选择器，返回可见且可交互的选择器列表"""
                valid_selectors = []
                try:
                    # 使用JavaScript快速检测所有选择器
                    results = await page.evaluate(f'''(selectors) => {{
                        return selectors.map(selector => {{
                            try {{
                                const elements = document.querySelectorAll(selector);
                                for (const element of elements) {{
                                    // 检查元素是否可见和可交互
                                    const style = window.getComputedStyle(element);
                                    const isVisible = style.display !== 'none' && 
                                                     style.visibility !== 'hidden' && 
                                                     element.offsetWidth > 0 && 
                                                     element.offsetHeight > 0;
                                    
                                    if (isVisible) {{
                                        // 检查是否可交互
                                        const isEditable = element.tagName.toLowerCase() === 'input' || 
                                                         element.tagName.toLowerCase() === 'textarea' || 
                                                         element.isContentEditable || 
                                                         element.getAttribute('contenteditable') === 'true';
                                        
                                        if (isEditable) {{
                                            return {{ selector, valid: true, tagName: element.tagName, type: element.type || 'N/A' }};
                                        }}
                                    }}
                                }}
                                return {{ selector, valid: false }};
                            }} catch (e) {{
                                return {{ selector, valid: false, error: e.message }};
                            }}
                        }});
                    }}''', selectors)
                    
                    # 过滤出有效的选择器
                    for result in results:
                        if result.get('valid', False):
                            valid_selectors.append(result['selector'])
                            logger.debug(f"有效选择器: {result['selector']} ({result.get('tagName', 'unknown')})")
                        else:
                            logger.debug(f"无效选择器: {result['selector']}")
                    
                    logger.info(f"智能检测完成，找到 {len(valid_selectors)}/{len(selectors)} 个有效选择器")
                    return valid_selectors
                    
                except Exception as e:
                    logger.warning(f"智能选择器检测失败: {e}")
                    # 如果智能检测失败，返回原始选择器列表
                    return selectors
            
            # 定义标题选择器列表（基于截图优化适配小红书最新界面）
            title_selectors = [
            # 小红书最新界面标题选择器 - 基于截图优化
            '.publish-header input[type="text"]',
            '.publish-header input[placeholder="输入标题"]',
            '.main-content-header .title-input',
            '.input-title-area input',
            '.publish-panel .title-input',
            '[data-testid="publish-title-input"]',
            '[data-cy="publish-title-input"]',
            '#publish-title-input',
            '.publish-title-input',
            # 小红书新界面标题选择器 - 基于截图分析
            '.content-header .title-input',
            '.input-area input[placeholder="输入标题"]',
            '.main-title input',
            '.title-container input',
            '[placeholder="输入标题"]',
            '#article-title',
            '.title-editor input',
            '[name="noteTitle"]',
            '[data-testid="note-title"]',
            # 新增小红书最新界面专用选择器 - 基于截图优化
            '.publish-header .title-input',
            '.editor-header .title-input',
            '.edit-title-input',
            '[data-input="title"]',
            '[data-placeholder="输入标题"]',
            '.title-input-box input',
            '.note-title-input',
            '[aria-label="标题输入框"]',
            '.input-area .title-input',
            '.note-editor-title input',
            # 通用标题选择器
            'input[placeholder*="标题"]',
            'textarea[placeholder*="标题"]',
            'input.title',
            'textarea.title',
            '[class*="title"][role="textbox"]',
            '[id*="title"]'
            ]
            
            # 定义内容选择器列表（基于截图优化适配小红书最新界面）
            content_selectors = [
            # 小红书最新界面内容选择器 - 基于截图优化
            '.publish-content textarea',
            '.publish-content [placeholder="输入正文内容"]',
            '.main-content-editor textarea',
            '.publish-panel .content-input',
            '.content-editor-area textarea',
            '[data-testid="publish-content-input"]',
                '[data-cy="publish-content-input"]',
                '#publish-content-input',
                '.publish-content-input',
                # 小红书新界面内容选择器 - 基于截图分析
                '.content-area textarea',
            '.main-content textarea[placeholder="输入正文内容"]',
            '.article-content-editor',
            '.editor-wrapper',
            '.content-editor',
            '#content-editor',
            '[placeholder="输入正文内容"]',
            '#article-content',
            '.article-body',
            '[name="noteContent"]',
            '[data-testid="note-content"]',
            # 新增小红书最新界面专用选择器 - 基于截图优化
            '.editor-content-container',
            '.note-content-input',
            '.main-content-editor',
            '.content-input-area',
            '[data-input="content"]',
            '[data-placeholder="输入正文内容"]',
            '.content-wrapper textarea',
            '[aria-label="正文内容"]',
            '.publish-area .content-input',
            '.note-editor-content textarea',
            '.content-editor-wrapper textarea',
            '.main-editor-area',
            # 富文本编辑器选择器
            '.rich-content-editor',
            '.prose-editor',
            '.ql-editor',
            '.ProseMirror',
            'div[contenteditable="true"]',
            'div[role="textbox"]',
            # 通用内容选择器
            'textarea[placeholder*="正文"]',
            'textarea[placeholder*="内容"]',
            '[class*="content"][role="textbox"]',
            '[id*="content"]'
            ]
            
            # 等待页面加载完成
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(1)
        
            # 尝试填充标题
            if title:
                logger.info("开始填充标题")
                title_input_found = False
                
                # 1. 优先使用JavaScript方式填充标题（更快、更可靠）
                logger.info("尝试使用JavaScript查找并填充标题")
                try:
                    title_filled = await page.evaluate('''(title) => {
                        // 查找所有可能的标题输入元素 - 基于截图优化
                        const titleElements = [
                            // 小红书最新界面标题选择器 - 基于截图优化优先尝试
                            document.querySelector('.publish-header input[type="text"]'),
                            document.querySelector('.publish-header input[placeholder="输入标题"]'),
                            document.querySelector('.main-content-header .title-input'),
                            document.querySelector('.input-title-area input'),
                            document.querySelector('.publish-panel .title-input'),
                            document.querySelector('[data-testid="publish-title-input"]'),
                            document.querySelector('[data-cy="publish-title-input"]'),
                            document.querySelector('#publish-title-input'),
                            document.querySelector('.publish-title-input'),
                            // 小红书新界面标题选择器
                            document.querySelector('.content-header .title-input'),
                            document.querySelector('.input-area input[placeholder="输入标题"]'),
                            document.querySelector('.main-title input'),
                            document.querySelector('.title-container input'),
                            document.querySelector('[placeholder="输入标题"]'),
                            document.querySelector('#article-title'),
                            // 新增小红书最新界面专用选择器
                            document.querySelector('[name="noteTitle"]'),
                            document.querySelector('[data-testid="note-title"]'),
                            document.querySelector('.publish-header .title-input'),
                            document.querySelector('.editor-header .title-input'),
                            document.querySelector('.edit-title-input'),
                            document.querySelector('[data-input="title"]'),
                            document.querySelector('[data-placeholder="输入标题"]'),
                            document.querySelector('.title-input-box input'),
                            document.querySelector('.note-title-input'),
                            document.querySelector('[aria-label="标题输入框"]'),
                            document.querySelector('.input-area .title-input'),
                            document.querySelector('.note-editor-title input'),
                            // 通用标题选择器
                            ...document.querySelectorAll('input[placeholder*="标题"]'),
                            ...document.querySelectorAll('textarea[placeholder*="标题"]'),
                            ...document.querySelectorAll('input.title, textarea.title'),
                            ...document.querySelectorAll('[class*="title"][role="textbox"]'),
                            ...document.querySelectorAll('[id*="title"]')
                        ].filter(Boolean); // 过滤掉null元素

                        for (const element of titleElements) {
                                if (element.offsetParent !== null) { // 只找可见元素
                                    try {
                                        // 点击激活
                                        element.click();

                                        // 清空并设置值
                                        const tagName = element.tagName.toLowerCase();
                                        if (tagName === 'input' || tagName === 'textarea') {
                                            element.value = '';
                                            element.value = title;
                                        } else if (element.isContentEditable || element.getAttribute('contenteditable') === 'true') {
                                            // 处理可编辑div
                                            element.innerHTML = '';
                                            element.focus();
                                            document.execCommand('insertText', false, title);
                                        }

                                        // 触发更多事件以确保框架能检测到变更
                                        element.dispatchEvent(new Event('input', { bubbles: true }));
                                        element.dispatchEvent(new Event('change', { bubbles: true }));
                                        element.dispatchEvent(new Event('blur', { bubbles: true }));

                                        // 模拟键盘事件
                                        element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
                                        element.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter' }));

                                        // 添加额外事件
                                        element.dispatchEvent(new Event('paste', { bubbles: true }));

                                        // 稍微延迟确认效果
                                        setTimeout(() => {
                                            if (element.value === title || element.textContent === title) {
                                                console.log('标题填充确认成功');
                                            }
                                        }, 100);

                                        return true;
                                    } catch (e) {
                                        console.error('填充标题出错:', e);
                                        continue;
                                    }
                                }
                            }
                        return false;
                    }''', title)

                    if title_filled:
                        logger.info("通过JavaScript成功填充标题")
                        title_input_found = True
                except Exception as e:
                    logger.error("JavaScript填充标题失败: {}".format(str(e)))
                
                # 2. 如果JavaScript方式失败，使用智能选择器检测
                if not title_input_found:
                    logger.info("使用智能选择器检测填充标题")
                    # 先进行智能选择器检测
                    valid_title_selectors = await smart_selector_check(page, title_selectors)
                    
                    # 只尝试有效的选择器
                    for selector in valid_title_selectors:
                        try:
                            # 先点击激活输入框
                            await page.click(selector)
                            
                            # 清空输入框并输入标题
                            await page.fill(selector, '')
                            
                            # 使用分段打字方式输入标题
                            await publish_utils.simulate_user_typing(page, selector, title)
                            
                            # 验证是否成功输入
                            element = await page.query_selector(selector)
                            input_value = await page.evaluate('(element) => element.value || ""', element)
                            
                            if input_value.strip() == title.strip():
                                logger.info(f"标题填充成功，使用选择器: {selector}")
                                title_input_found = True
                                break
                        except Exception as e:
                            logger.debug(f"尝试标题选择器 {selector} 失败: {e}")
                            continue

                # 3. 作为最后的备选方案,使用更通用的方法查找可见的input和textarea
                if not title_input_found:
                    logger.info("尝试使用通用方法查找可见的标题输入框")
                    try:
                        # 使用三引号解决引号嵌套问题
                        title_filled = await page.evaluate('''(title) => {
                            // 查找所有可见的input和textarea
                            const allInputs = [...document.querySelectorAll("input, textarea")]
                                .filter(el => el.offsetParent !== null && 
                                           el.style.display !== "none" && 
                                           el.style.visibility !== "hidden" &&
                                           // 过滤掉密码框和隐藏字段
                                           el.type !== "password" && 
                                           el.type !== "hidden");

                            // 优先检查有placeholder的元素
                            for (const input of allInputs) {
                                const placeholder = input.getAttribute("placeholder") || "";
                                const className = input.className || "";
                                const id = input.id || "";

                                if (placeholder.includes("标题") || 
                                    className.includes("title") || 
                                    id.includes("title") ||
                                    // 检查是否在标题相关的容器中
                                    input.closest(".title") || 
                                    input.closest("[class*=\"title\"]")) {
                                    
                                    input.click();
                                    input.value = "";
                                    input.value = title;
                                    input.dispatchEvent(new Event("input", { bubbles: true }));
                                    input.dispatchEvent(new Event("change", { bubbles: true }));
                                    input.dispatchEvent(new Event("blur", { bubbles: true }));
                                    return true;
                                }
                            }

                            // 如果没有找到明显的标题输入框, 尝试第一个可见的input或textarea
                            if (allInputs.length > 0) {
                                const firstInput = allInputs[0];
                                firstInput.click();
                                firstInput.value = "";
                                firstInput.value = title;
                                firstInput.dispatchEvent(new Event("input", { bubbles: true }));
                                firstInput.dispatchEvent(new Event("change", { bubbles: true }));
                                firstInput.dispatchEvent(new Event("blur", { bubbles: true }));
                                return true;
                            }

                            return false;
                        }''', title)

                        if title_filled:
                            logger.info("通过通用方法成功填充标题")
                            title_input_found = True
                    except Exception as e:
                        logger.error("通用方法填充标题失败: {}".format(str(e)))

                # 4. 如果仍然失败，尝试截图以便调试
                if not title_input_found:
                    logger.error("未找到并填充标题输入框，尝试截图以便调试")
                    try:
                        await page.screenshot(path='title_input_debug.png')
                        logger.info("已保存标题输入框调试截图: title_input_debug.png")
                    except:
                        pass
            
                if not title_input_found:
                    # 尝试使用JavaScript方式填充标题
                    try:
                        await page.evaluate("(title) => {\n" +
                            "    const titleElements = [\n" +
                            "        // 小红书新界面标题选择器\n" +
                            "        document.querySelector('.input-area input[placeholder=\"输入标题\"]'),\n" +
                            "        document.querySelector('.title-editor input'),\n" +
                            "        document.querySelector('[data-input=\"title\"]'),\n" +
                            "        document.querySelector('[aria-label=\"标题输入框\"]'),\n" +
                            "        document.querySelector('#title-input-field'),\n" +
                            "        document.querySelector('.publish-form input[name=\"title\"]'),\n" +
                            "        // 通用标题选择器\n" +
                            "        ...document.querySelectorAll('input[placeholder*=\"标题\"]'),\n" +
                            "        ...document.querySelectorAll('textarea[placeholder*=\"标题\"]'),\n" +
                            "        ...document.querySelectorAll('input.title, textarea.title')\n" +
                            "    ].filter(Boolean); // 过滤掉null元素\n" +
                            "    \n" +
                            "    for (const element of titleElements) {\n" +
                            "        if (element.offsetParent !== null) { // 只找可见元素\n" +
                            "            element.value = title;\n" +
                            "            // 触发更多事件以确保框架能检测到变更\n" +
                            "            element.dispatchEvent(new Event('input', { bubbles: true }));\n" +
                            "            element.dispatchEvent(new Event('change', { bubbles: true }));\n" +
                            "            element.dispatchEvent(new Event('blur', { bubbles: true }));\n" +
                            "            return true;\n" +
                            "        }\n" +
                            "    }\n" +
                            "    return false;\n" +
                            "}", title)
                        logger.info("使用JavaScript方式填充标题")
                        title_input_found = True
                    except Exception as e:
                        logger.error(f"JavaScript方式填充标题失败: {e}")
            
            if not title_input_found:
                logger.error("无法找到并填充标题输入框")
        
            # 尝试填充内容
            if content:
                logger.info("开始填充内容")
                content_input_found = False
                
                # 将选择器分为常见选择器和备选选择器
                common_selectors = [
                    'textarea[placeholder*="正文"]', 'textarea[placeholder*="内容"]', 
                    'textarea[placeholder*="写笔记"]', 'textarea[placeholder*="分享"]',
                    'div[contenteditable="true"][data-placeholder*="正文"]',
                    'div[contenteditable="true"][data-placeholder*="内容"]',
                    'textarea', 'div[contenteditable="true"]'
                ]
                
                # 备选选择器（剩余的选择器）
                backup_selectors = [s for s in content_selectors if s not in common_selectors]
                
                # 使用智能选择器检测函数，优先尝试可能有效的选择器
                try:
                    logger.info("使用智能选择器检测内容输入框...")
                    smart_selectors = await smart_selector_check(page, content_selectors, "内容输入框")
                    if smart_selectors and smart_selectors != content_selectors:
                        logger.info(f"智能检测到 {len(smart_selectors)} 个有效内容选择器")
                        content_selectors = smart_selectors
                except Exception as e:
                    logger.warning(f"智能选择器检测失败: {e}")
                
                # 使用智能检测后的选择器列表进行填充
                if not content_input_found:
                    logger.info(f"使用智能检测后的选择器列表进行填充，共 {len(content_selectors)} 个选择器")
                    for selector in content_selectors:
                        try:
                            # 直接尝试查找元素，无需等待
                            element = await page.query_selector(selector)
                            if not element:
                                continue
                            
                            # 根据元素类型使用不同的填充方法
                            element_type = await page.evaluate('(element) => element.tagName.toLowerCase()', element)
                            
                            if element_type == 'textarea' or element_type == 'input':
                                # 对于textarea和input元素
                                await page.fill(selector, '')
                                
                                # 使用分段打字方式输入内容
                                await publish_utils.simulate_user_typing(page, selector, content)
                            else:
                                # 对于contenteditable元素
                                element = await page.query_selector(selector)
                                await page.click(selector)
                                await page.evaluate('''(element, content) => { 
                                    element.innerHTML = ""; 
                                    element.focus(); 
                                    document.execCommand("insertText", false, content); 
                                    element.dispatchEvent(new Event("input", { bubbles: true }));
                                }''', element, content)
                            
                            # 验证是否成功输入
                            element = await page.query_selector(selector)
                            if element_type == 'textarea' or element_type == 'input':
                                input_value = await page.evaluate('(element) => element.value || ""', element)
                            else:
                                input_value = await page.evaluate('(element) => element.textContent || element.innerText || ""', element)
                            
                            if input_value and (content[:50] in input_value or content[-50:] in input_value):
                                logger.info(f"内容填充成功，使用智能检测选择器: {selector}")
                                content_input_found = True
                                break
                            else:
                                logger.warning(f"内容填充但验证失败，智能检测选择器: {selector}")
                        except Exception as e:
                            logger.warning(f"填充内容失败，智能检测选择器: {selector}, 错误: {e}")
                
                if not content_input_found:
                    # 尝试使用JavaScript方式填充内容
                    try:
                        await page.evaluate("""(content) => {
                                // 查找所有可能的内容编辑区域 - 基于截图优化
                            const contentElements = [
                                // 小红书最新界面内容选择器 - 基于截图优化优先尝试
                                document.querySelector('.publish-content textarea'),
                                document.querySelector('.publish-content [placeholder="输入正文内容"]'),
                                document.querySelector('.main-content-editor textarea'),
                                document.querySelector('.publish-panel .content-input'),
                                document.querySelector('.content-editor-area textarea'),
                                document.querySelector('[data-testid="publish-content-input"]'),
                                document.querySelector('[data-cy="publish-content-input"]'),
                                document.querySelector('#publish-content-input'),
                                document.querySelector('.publish-content-input'),
                                // 小红书新界面内容选择器
                                document.querySelector('.content-area textarea'),
                                document.querySelector('.main-content textarea[placeholder="输入正文内容"]'),
                                document.querySelector('.article-content-editor'),
                                document.querySelector('.editor-wrapper'),
                                document.querySelector('.content-editor'),
                                document.querySelector('#content-editor'),
                                document.querySelector('[placeholder="输入正文内容"]'),
                                // 新增小红书最新界面专用选择器
                                document.querySelector('#article-content'),
                                document.querySelector('.article-body'),
                                document.querySelector('[name="noteContent"]'),
                                document.querySelector('[data-testid="note-content"]'),
                                document.querySelector('.editor-content-container'),
                                document.querySelector('.note-content-input'),
                                document.querySelector('.main-content-editor'),
                                document.querySelector('.content-input-area'),
                                document.querySelector('[data-input="content"]'),
                                document.querySelector('[data-placeholder="输入正文内容"]'),
                                document.querySelector('.content-wrapper textarea'),
                                document.querySelector('[aria-label="正文内容"]'),
                                document.querySelector('.publish-area .content-input'),
                                document.querySelector('.note-editor-content textarea'),
                                document.querySelector('.content-editor-wrapper textarea'),
                                document.querySelector('.main-editor-area'),
                                // 富文本编辑器选择器
                                ...document.querySelectorAll('div[contenteditable="true"]'),
                                ...document.querySelectorAll('div[role="textbox"]'),
                                ...document.querySelectorAll('.ql-editor, .ProseMirror'),
                                // 通用内容选择器
                                ...document.querySelectorAll('textarea[placeholder*="正文"]'),
                                ...document.querySelectorAll('textarea[placeholder*="内容"]'),
                                ...document.querySelectorAll('.editor, .content, .rich-text-editor, .content-editor'),
                                ...document.querySelectorAll('[id*="content"]')
                            ].filter(Boolean); // 过滤掉null元素
                                
                                for (const element of contentElements) {
                                    if (element.offsetParent !== null) { // 只找可见元素
                                        try {
                                            // 点击激活
                                            element.click();
                                            
                                            const tagName = element.tagName.toLowerCase();
                                            if (tagName === 'textarea' || tagName === 'input') {
                                                element.value = '';
                                                // 对于textarea，需要确保换行符被正确处理
                                                if (tagName === 'textarea') {
                                                    // 使用模板字符串保留换行符
                                                    element.value = `${content}`;
                                                    // 触发input事件确保换行符被识别
                                                    element.dispatchEvent(new Event('input', { bubbles: true }));
                                                    // 触发change事件确保内容被保存
                                                    element.dispatchEvent(new Event('change', { bubbles: true }));
                                                } else {
                                                    element.value = `${content}`;
                                                }
                                            } else {
                                                // 对于可编辑div，使用更可靠的填充方式
                                                element.innerHTML = '';
                                                element.focus();
                                                
                                                // 将换行符转换为<br>标签以在HTML中正确显示
                                                const contentWithBr = content.replace(/\\n/g, '<br>');
                                                
                                                // 分段填充长内容
                                                if (content.length > 500) {
                                                    // 对于长内容，分段插入
                                                    const chunks = [];
                                                    let chunk = '';
                                                    for (let i = 0; i < content.length; i++) {
                                                        chunk += content[i];
                                                        if (chunk.length >= 200 || i === content.length - 1) {
                                                            chunks.push(chunk);
                                                            chunk = '';
                                                        }
                                                    }
                                                    
                                                    // 逐段插入，正确处理换行符
                                                    chunks.forEach((chunk, index) => {
                                                        setTimeout(() => {
                                                            // 对于包含换行符的块，先按换行符分割
                                                            const lines = chunk.split('\\n');
                                                            lines.forEach((line, lineIndex) => {
                                                                document.execCommand('insertText', false, line);
                                                                // 如果不是最后一行，插入换行
                                                                if (lineIndex < lines.length - 1) {
                                                                    document.execCommand('insertLineBreak', false, null);
                                                                }
                                                            });
                                                        }, index * 50);
                                                    });
                                                } else {
                                                    // 短内容分段插入，正确处理换行符
                                                    const lines = content.split('\\n');
                                                    lines.forEach((line, index) => {
                                                        document.execCommand('insertText', false, line);
                                                        // 如果不是最后一行，插入换行
                                                        if (index < lines.length - 1) {
                                                            document.execCommand('insertLineBreak', false, null);
                                                        }
                                                    });
                                                }
                                                
                                                // 检查是否成功填充，添加更多回退方案
                                                if (element.textContent !== content && element.innerText !== content) {
                                                    // 如果execCommand失败，尝试设置textContent
                                                    element.textContent = content;
                                                    // 再次检查
                                                    if (element.textContent !== content && element.innerText !== content) {
                                                        // 最后回退到设置innerHTML，保留换行
                                                        element.innerHTML = contentWithBr;
                                                    }
                                                }
                                            }
                                            
                                            // 触发多个事件以确保框架能检测到变更
                                            element.dispatchEvent(new Event('input', { bubbles: true }));
                                            element.dispatchEvent(new Event('change', { bubbles: true }));
                                            element.dispatchEvent(new Event('blur', { bubbles: true }));
                                            
                                            // 添加额外事件
                                            element.dispatchEvent(new Event('paste', { bubbles: true }));
                                            element.dispatchEvent(new Event('compositionend', { bubbles: true }));
                                            
                                            // 稍微延迟确认效果
                                            setTimeout(() => {
                                                const currentContent = element.value || element.textContent || element.innerText;
                                                if (currentContent.includes(content.substring(0, 50))) {
                                                    console.log('内容填充部分确认成功');
                                                }
                                            }, 200);
                                            
                                            return true;
                                        } catch (e) {
                                            console.error('填充内容出错:', e);
                                            continue;
                                        }
                                    }
                                }
                                return false;
                        }""", content)
                        logger.info("使用JavaScript方式填充内容")
                        content_input_found = True
                    except Exception as e:
                        logger.error(f"JavaScript方式填充内容失败: {e}")
                
                if not content_input_found:
                    logger.error("无法找到并填充内容输入框")
            
                # 添加短暂延迟，确保内容完全加载
                await asyncio.sleep(2)
                logger.info("内容填充完成")
                return True
        except Exception as e:
            logger.error(f"填充内容失败: {e}")
        
        # 尝试最后的应急方案 - 打印页面结构帮助调试
        try:
            page_structure = await page.evaluate('() => document.body.innerHTML.substring(0, 2000)')
            logger.debug(f"页面结构预览: {page_structure}")
            
            # 收集所有可能的输入元素信息
            try:
                all_inputs = await page.evaluate('''() => Array.from(document.querySelectorAll("input, textarea, [contenteditable]")).map(el => ({
  tagName: el.tagName,
  outerHTML: el.outerHTML.substring(0, 150),
  placeholder: el.placeholder || "",
  className: el.className,
  id: el.id,
  contenteditable: el.getAttribute("contenteditable") || "false"
}))''')
                logger.info(f"页面上所有可能的输入元素 ({len(all_inputs)}个):")
                for i, inp in enumerate(all_inputs[:5]):  # 只记录前5个
                    logger.info(f"  {i+1}: {inp}")
            except Exception as debug_error:
                logger.warning(f"收集调试信息失败: {debug_error}")
                
                # 尝试备用方法收集输入元素
                try:
                    all_inputs = await page.evaluate('''() => {
                        return [...document.querySelectorAll('input, textarea, [contenteditable="true"]')]
                            .filter(el => el.offsetParent !== null)
                            .map(el => ({
                                tagName: el.tagName,
                                outerHTML: el.outerHTML.substring(0, 150),
                                placeholder: el.placeholder || "",
                                className: el.className,
                                id: el.id,
                                contenteditable: el.getAttribute("contenteditable") || "false"
                            }));
                    }''')
                    logger.info(f"页面上所有可能的输入元素 ({len(all_inputs)}个):")
                    for i, inp in enumerate(all_inputs[:5]):  # 只记录前5个
                        logger.info(f"  {i+1}: {inp}")
                except:
                    pass
        except Exception as debug_error:
            logger.warning(f"收集调试信息失败: {debug_error}")
        
        # 修复：return 语句只能在函数中使用，因此将其封装在函数内部
        # 原代码逻辑已合并到上层函数中，此处无需单独 return
        pass
    
    async def _fill_with_typing(self, page, selector, text):
        """使用模拟打字方式填充内容
        
        Args:
            page: Playwright页面实例
            selector: 元素选择器
            text: 要填充的文本
            
        Returns:
            bool: 是否成功填充
        """
        try:
            # 使用publish_utils中的simulate_user_typing方法
            await publish_utils.simulate_user_typing(page, selector, text)
            return True
        except Exception as e:
            logger.warning(f"模拟打字填充失败: {e}")
            return False
    
    async def _fill_with_js(self, page, selector, text):
        """使用JavaScript方式填充内容
        
        Args:
            page: Playwright页面实例
            selector: 元素选择器
            text: 要填充的文本
            
        Returns:
            bool: 是否成功填充
        """
        try:
            # 检查选择器类型
            if '>>' in selector:
                # Playwright选择器，不能直接用于JavaScript
                logger.warning("选择器包含Playwright语法，跳过JavaScript填充")
                return False
            
            # 使用函数参数传递文本，避免模板字符串中的反引号问题
            await page.evaluate("""
                (params) => {
                    const { selector, text } = params;
                    const element = document.querySelector(selector);
                    if (!element) return false;
                    
                    // 对于不同类型的输入框使用不同的填充方法
                    if (element.tagName.toLowerCase() === 'textarea') {
                        // 对于textarea，使用value属性，保留换行符
                        element.value = text;
                        // 触发input事件确保换行符被识别
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        // 触发change事件确保内容被保存
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                    } else if (element.getAttribute('contenteditable') === 'true' || element.tagName.toLowerCase() === 'div') {
                        // 对于可编辑的div，使用innerHTML并保留换行符
                        // 将换行符转换为<br>标签以在HTML中正确显示
                        const textWithBr = text.replace(/\\n/g, '<br>');
                        element.innerHTML = textWithBr;
                        // 触发input和change事件
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                    } else {
                        element.value = text;
                        // 触发input和change事件
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    
                    return true;
                }
            """, {"selector": selector, "text": text})
            
            return True
        except Exception as e:
            logger.warning(f"JavaScript填充失败: {e}")
            return False
    
    async def _fill_directly(self, page, selector, text):
        """使用Playwright的fill方法直接填充内容
        
        Args:
            page: Playwright页面实例
            selector: 元素选择器
            text: 要填充的文本
            
        Returns:
            bool: 是否成功填充
        """
        try:
            # 使用Playwright的fill方法直接填充
            await page.fill(selector, text)
            return True
        except Exception as e:
            logger.warning(f"直接填充失败: {e}")
            return False
    
    async def _fill_element(self, element, text):
        """直接填充已获取的元素
        
        Args:
            element: 已获取的页面元素
            text: 要填充的文本
            
        Returns:
            bool: 是否成功填充
        """
        try:
            # 尝试使用fill方法
            await element.fill(text)
            return True
        except Exception as e:
            logger.warning(f"元素填充失败: {e}")
            return False
