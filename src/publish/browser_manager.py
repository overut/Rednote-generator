import asyncio
import json
import os
import sys
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from src.utils.logger import logger

# Windows平台特殊处理 - 在导入时就设置正确的事件循环策略
if sys.platform == 'win32':
    try:
        # 优先使用ProactorEventLoopPolicy
        if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.info("已设置WindowsProactorEventLoopPolicy")
        else:
            # 降级使用SelectorEventLoopPolicy
            if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                logger.info("已设置WindowsSelectorEventLoopPolicy")
    except Exception as e:
        logger.warning(f"设置事件循环策略失败: {e}")


class BrowserManager:
    """浏览器管理器，负责Playwright浏览器实例的创建和管理"""
    
    def __init__(self):
        """初始化浏览器管理器"""
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self.is_initialized = False
        self.headless_mode = False  # 保存headless模式状态
    
    async def init_browser(self, headless: bool = False) -> None:
        """初始化浏览器实例
        
        Args:
            headless: 是否使用无头模式
        """
        try:
            # 保存headless模式
            self.headless_mode = headless
            
            # 清理现有资源
            await self.close()
            
            # 确保有可用的事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    asyncio.set_event_loop(asyncio.new_event_loop())
            except:
                asyncio.set_event_loop(asyncio.new_event_loop())
            
            self.playwright = await async_playwright().start()
            
            # 设置一些反检测参数
            args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
            
            # 简化启动参数，提高兼容性
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=args,
                slow_mo=50,  # 降低放慢速度
                chromium_sandbox=False,
                handle_sigint=False,
                handle_sigterm=False,
                handle_sighup=False
            )
            
            # 创建新的浏览上下文
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            # 添加一些拦截器，防止自动化检测
            await self._setup_interceptors()
            
            self.is_initialized = True
            logger.info(f"浏览器初始化成功，无头模式: {headless}")
            
        except NotImplementedError:
            # 处理NotImplementedError，这通常是asyncio在特定环境下的兼容性问题
            logger.error("浏览器初始化失败: 检测到asyncio兼容性问题")
            logger.info("尝试使用不同的事件循环策略...")
            # 尝试不同的事件循环策略
            try:
                if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                await self._retry_init(headless)
            except Exception as retry_error:
                logger.error(f"重试初始化失败: {retry_error}")
                raise
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise
    
    async def _retry_init(self, headless: bool = False) -> None:
        """重试初始化浏览器"""
        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass
        
        self.playwright = await async_playwright().start()
        # 使用更简单的配置重试
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            chromium_sandbox=False
        )
        self.context = await self.browser.new_context()
        self.is_initialized = True
    
    async def _setup_interceptors(self) -> None:
        """设置请求拦截器，修改请求头以避免被检测"""
        if self.context:
            async def intercept_request(route, request):
                # 修改请求头，移除自动化特征
                headers = dict(request.headers)
                headers.pop('X-Playwright-Id', None)
                headers.pop('Sec-Fetch-Dest', None)
                await route.continue_(headers=headers)
            
            await self.context.route('**/*', intercept_request)
    
    async def get_page(self) -> Page:
        """获取新的页面实例
        
        Returns:
            Page: Playwright页面实例
        """
        try:
            # 尝试获取页面，最多重试3次
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"尝试{attempt+1}/{max_retries}创建新页面")
                    
                    # 检查并修复浏览器实例
                    if not self.browser or not hasattr(self.browser, 'new_context') or not callable(self.browser.new_context):
                        logger.error("浏览器实例无效或没有new_context方法")
                        # 重新初始化浏览器
                        await self._reinitialize_browser()
                        continue
                    
                    # 确保有有效的上下文
                    if not self.context:
                        logger.info("上下文不存在，创建新上下文")
                        try:
                            self.context = await self.browser.new_context(
                                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                                viewport={'width': 1920, 'height': 1080}
                            )
                            await self._setup_interceptors()
                        except Exception as context_error:
                            logger.error(f"创建新上下文失败: {context_error}")
                            await self._reinitialize_browser()
                            continue
                    
                    # 再次检查上下文和new_page方法
                    if not self.context or not hasattr(self.context, 'new_page') or not callable(self.context.new_page):
                        logger.error("上下文无效或没有new_page方法")
                        await self._reset_context()
                        continue
                    
                    # 创建新页面 - 这是最关键的部分，确保不会对None进行await
                    try:
                        # 在调用前再次验证
                        if self.context is None:
                            raise RuntimeError("上下文为None，无法创建页面")
                        if not hasattr(self.context, 'new_page'):
                            raise RuntimeError("上下文没有new_page方法")
                        if not callable(self.context.new_page):
                            raise RuntimeError("new_page不是可调用方法")
                        
                        # 安全调用new_page
                        page = await self.context.new_page()
                        
                        # 确保page不为None
                        if page is None:
                            raise RuntimeError("创建的页面为None")
                        
                        # 设置超时和反检测 - 每项操作都添加检查
                        try:
                            if hasattr(page, 'set_default_navigation_timeout') and callable(page.set_default_navigation_timeout):
                                page.set_default_navigation_timeout(60000)
                        except Exception as timeout_error:
                            logger.warning(f"设置导航超时失败: {timeout_error}")
                        
                        try:
                            if hasattr(page, 'set_default_timeout') and callable(page.set_default_timeout):
                                page.set_default_timeout(60000)
                        except Exception as timeout_error:
                            logger.warning(f"设置默认超时失败: {timeout_error}")
                        
                        try:
                            if hasattr(page, 'evaluate') and callable(page.evaluate):
                                await page.evaluate("""
                                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
                                    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                                """)
                        except Exception as eval_error:
                            logger.warning(f"设置页面反检测失败: {eval_error}")
                        
                        logger.info("成功创建新页面")
                        return page
                    except Exception as page_error:
                        logger.error(f"创建页面失败: {page_error}")
                        # 尝试重置上下文
                        await self._reset_context()
                        
                except Exception as e:
                    logger.error(f"尝试{attempt+1}/{max_retries}创建页面失败: {e}")
                    if attempt < max_retries - 1:
                        logger.info(f"等待2秒后重试...")
                        await asyncio.sleep(2)
                    else:
                        logger.error("达到最大重试次数，获取页面失败")
                        raise
            
        except Exception as e:
            logger.error(f"获取页面失败: {e}")
            raise
            
    async def _ensure_valid_context(self) -> None:
        """确保浏览器上下文是有效的"""
        try:
            # 检查context是否存在且有效
            if not self.context or not hasattr(self.context, 'new_page'):
                logger.info("浏览器上下文无效或不存在，尝试重置")
                await self._reset_context()
        except Exception as e:
            logger.error(f"检查浏览器上下文有效性失败: {e}")
            await self._reset_context()
            
    async def _reset_context(self) -> None:
        """重置浏览器上下文"""
        try:
            logger.info("开始重置浏览器上下文")
            
            # 关闭当前上下文
            if self.context:
                try:
                    await self.context.close()
                except Exception as close_error:
                    logger.error(f"关闭当前上下文失败: {close_error}")
                self.context = None
            
            # 创建新的上下文
            if self.browser and hasattr(self.browser, 'new_context') and callable(self.browser.new_context):
                try:
                    self.context = await self.browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                        viewport={'width': 1920, 'height': 1080}
                    )
                    # 重新设置拦截器
                    await self._setup_interceptors()
                    logger.info("成功重置浏览器上下文")
                except Exception as new_context_error:
                    logger.error(f"创建新上下文失败: {new_context_error}")
                    # 浏览器可能已经失效，需要重新初始化
                    await self._reinitialize_browser()
            else:
                logger.error("浏览器实例无效，无法创建新上下文")
                # 尝试重新初始化整个浏览器
                await self._reinitialize_browser()
        except Exception as e:
            logger.error(f"重置浏览器上下文失败: {e}")
            raise
    
    async def _reinitialize_browser(self) -> None:
        """重新初始化浏览器"""
        logger.info(f"重新初始化浏览器，无头模式: {self.headless_mode}")
        try:
            await self.init_browser(headless=self.headless_mode)
            logger.info("浏览器重新初始化成功")
        except Exception as e:
            logger.error(f"浏览器重新初始化失败: {e}")
            raise
        except Exception as e:
            logger.error(f"重置浏览器上下文失败: {e}")
            raise
    
    async def close(self) -> None:
        """关闭浏览器实例"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("浏览器实例已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
    
    async def load_cookies(self, cookies_file: str) -> bool:
        """加载cookies文件
        
        Args:
            cookies_file: cookies文件路径
            
        Returns:
            bool: 是否加载成功
        """
        try:
            if not self.context:
                logger.error("浏览器上下文未初始化")
                return False
            
            if not os.path.exists(cookies_file):
                logger.warning(f"Cookies文件不存在: {cookies_file}")
                return False
            
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # 确保cookies格式正确
            if not isinstance(cookies, list):
                logger.error(f"Cookies格式错误: {cookies_file}")
                return False
            
            # 加载cookies到上下文
            for cookie in cookies:
                # 确保cookie格式正确
                if 'name' not in cookie or 'value' not in cookie:
                    continue
                try:
                    await self.context.add_cookies([cookie])
                except Exception as e:
                    logger.warning(f"添加cookie失败: {e}")
            
            logger.info(f"成功加载cookies: {cookies_file}")
            return True
            
        except Exception as e:
            logger.error(f"加载cookies失败: {e}")
            return False
    
    async def save_cookies(self, cookies_file: str) -> bool:
        """保存cookies到文件
        
        Args:
            cookies_file: cookies文件路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if not self.context:
                logger.error("浏览器上下文未初始化")
                return False
            
            # 确保目录存在
            os.makedirs(os.path.dirname(cookies_file), exist_ok=True)
            
            # 获取所有cookies
            cookies = await self.context.cookies()
            
            # 保存到文件
            with open(cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功保存cookies: {cookies_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存cookies失败: {e}")
            return False


# 单例模式实现
_browser_manager_instance = None


def get_browser_manager() -> BrowserManager:
    """获取浏览器管理器单例
    
    Returns:
        BrowserManager: 浏览器管理器实例，保证不会返回None
    """
    global _browser_manager_instance
    try:
        if _browser_manager_instance is None:
            logger.info("创建新的浏览器管理器实例")
            _browser_manager_instance = BrowserManager()
            # 确保创建成功
            if _browser_manager_instance is None:
                logger.error("创建浏览器管理器实例失败")
                # 强制创建一个实例
                _browser_manager_instance = BrowserManager()
        return _browser_manager_instance
    except Exception as e:
        logger.error(f"获取浏览器管理器实例时出错: {e}")
        # 在异常情况下，强制创建一个新实例
        _browser_manager_instance = BrowserManager()
        return _browser_manager_instance