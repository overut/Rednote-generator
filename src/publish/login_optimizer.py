"""
小红书登录优化方案
解决频繁要求手机号验证码的问题
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from playwright.async_api import Page, BrowserContext
from src.utils.logger import logger


class LoginOptimizer:
    """小红书登录优化器，旨在减少频繁的手机验证码验证"""
    
    def __init__(self, cookies_file: str = None):
        """
        初始化登录优化器
        
        Args:
            cookies_file: cookies文件路径
        """
        self.cookies_file = cookies_file or "accounts/.cookies/default.json"
        self.login_attempts = 0
        self.last_login_time = None
        self.session_cookies = {}
        
    async def initialize(self, browser_manager=None) -> bool:
        """
        初始化登录优化器
        
        Args:
            browser_manager: 浏览器管理器实例（可选）
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            logger.info("正在初始化登录优化器...")
            # 这里可以添加任何需要的初始化逻辑
            # 例如：加载配置、检查环境等
            
            # 如果提供了浏览器管理器，可以在这里进行相关初始化
            if browser_manager:
                logger.info("已提供浏览器管理器，可以进行相关初始化")
                # 可以在这里添加与浏览器管理器相关的初始化逻辑
                
            logger.info("登录优化器初始化成功")
            return True
        except Exception as e:
            logger.error(f"登录优化器初始化失败: {e}")
            return False
        
    async def optimize_browser_session(self, context: BrowserContext) -> None:
        """
        优化浏览器会话，使其更像真实用户
        
        Args:
            context: 浏览器上下文
        """
        try:
            # 设置更真实的用户代理
            await context.add_init_script("""
                // 修改 navigator 属性，使自动化检测更难被发现
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // 修改 plugins 长度
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // 修改 languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en'],
                });
                
                // 添加 chrome 对象
                window.chrome = {
                    runtime: {},
                };
                
                // 修改 permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            # 添加额外的 HTTP 头，模拟真实浏览器
            await context.set_extra_http_headers({
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Cache-Control": "max-age=0",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "sec-ch-ua": '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            })
            
            logger.info("浏览器会话优化完成")
        except Exception as e:
            logger.error(f"优化浏览器会话失败: {e}")
    
    async def enhance_cookie_persistence(self, page: Page) -> None:
        """
        增强 cookie 持久化，尝试保存更多有用的认证信息
        
        Args:
            page: 当前页面实例
        """
        try:
            # 获取当前所有 cookies
            cookies = await page.context.cookies()
            
            # 添加额外的存储信息
            enhanced_cookies = {
                "cookies": cookies,
                "user_agent": await page.evaluate("navigator.userAgent"),
                "timestamp": datetime.now().isoformat(),
                "url": page.url,
                "local_storage": await page.evaluate("() => { let obj = {}; for (let i = 0; i < localStorage.length; i++) { let key = localStorage.key(i); obj[key] = localStorage.getItem(key); } return obj; }"),
                "session_storage": await page.evaluate("() => { let obj = {}; for (let i = 0; i < sessionStorage.length; i++) { let key = sessionStorage.key(i); obj[key] = sessionStorage.getItem(key); } return obj; }")
            }
            
            # 保存到文件
            os.makedirs(os.path.dirname(self.cookies_file), exist_ok=True)
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_cookies, f, ensure_ascii=False, indent=2)
            
            logger.info(f"增强型 cookies 已保存到 {self.cookies_file}")
        except Exception as e:
            logger.error(f"增强 cookie 持久化失败: {e}")
    
    async def load_enhanced_cookies(self, context: BrowserContext) -> bool:
        """
        加载增强型 cookies，包括本地存储和会话存储
        
        Args:
            context: 浏览器上下文
            
        Returns:
            bool: 是否成功加载
        """
        try:
            if not os.path.exists(self.cookies_file):
                logger.info(f"cookies 文件不存在: {self.cookies_file}")
                return False
                
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                enhanced_cookies = json.load(f)
            
            # 处理两种格式的cookies文件
            # 1. 增强型格式（包含cookies、user_agent、timestamp等）
            # 2. 简单格式（直接是cookies数组）
            
            cookies = []
            timestamp = None
            
            if isinstance(enhanced_cookies, dict):
                # 增强型格式
                cookies = enhanced_cookies.get("cookies", [])
                timestamp = enhanced_cookies.get("timestamp")
            elif isinstance(enhanced_cookies, list):
                # 简单格式，直接是cookies数组
                cookies = enhanced_cookies
                logger.info("检测到简单格式的cookies文件，使用直接加载方式")
            else:
                logger.error(f"不支持的cookies文件格式: {type(enhanced_cookies)}")
                return False
            
            # 检查 cookies 是否过期
            if timestamp:
                cookie_time = datetime.fromisoformat(timestamp)
                if datetime.now() - cookie_time > timedelta(days=7):
                    logger.warning("cookies 已超过 7 天，可能已失效")
                    # 不直接返回 False，仍尝试加载，但记录警告
            
            # 先添加 cookies
            if cookies:
                await context.add_cookies(cookies)
                logger.info(f"已加载 {len(cookies)} 个 cookies")
            
            # 只有增强型格式才设置本地存储和会话存储
            if isinstance(enhanced_cookies, dict):
                # 创建一个空白页面来设置本地存储和会话存储
                page = await context.new_page()
                
                # 设置本地存储
                local_storage = enhanced_cookies.get("local_storage", {})
                if local_storage:
                    await page.evaluate(f"""
                        () => {{
                            const data = {json.dumps(local_storage)};
                            for (const key in data) {{
                                localStorage.setItem(key, data[key]);
                            }}
                        }}
                    """)
                    logger.info(f"已设置 {len(local_storage)} 个本地存储项")
                
                # 设置会话存储
                session_storage = enhanced_cookies.get("session_storage", {})
                if session_storage:
                    await page.evaluate(f"""
                        () => {{
                            const data = {json.dumps(session_storage)};
                            for (const key in data) {{
                                sessionStorage.setItem(key, data[key]);
                            }}
                        }}
                    """)
                    logger.info(f"已设置 {len(session_storage)} 个会话存储项")
                
                # 关闭临时页面
                await page.close()
            
            return True
        except Exception as e:
            logger.error(f"加载增强型 cookies 失败: {e}")
            return False
    
    async def try_skip_verification(self, page: Page) -> bool:
        """
        尝试跳过手机验证码验证，通过模拟已登录用户的行为
        
        Args:
            page: 当前页面实例
            
        Returns:
            bool: 是否成功跳过验证
        """
        try:
            # 检查是否在登录页面
            current_url = page.url
            if "login" not in current_url and "signin" not in current_url:
                logger.info("不在登录页面，无需跳过验证")
                return True
                
            # 尝试直接访问创作平台主页
            logger.info("尝试直接访问创作平台主页，看是否已登录")
            await page.goto("https://creator.xiaohongshu.com/publish/publish", wait_until="networkidle")
            
            # 等待页面加载
            await asyncio.sleep(3)
            
            # 检查是否成功跳转到发布页面
            current_url = page.url
            if "publish" in current_url and "login" not in current_url:
                logger.info("成功跳过验证，已登录")
                return True
                
            # 如果还在登录页面，尝试其他方法
            if "login" in current_url:
                # 尝试检查是否有"记住登录状态"或"自动登录"选项
                remember_selectors = [
                    'input[type="checkbox"][id*="remember"]',
                    'input[type="checkbox"][name*="remember"]',
                    'label:has-text("记住")',
                    'label:has-text("自动登录")',
                    '.remember-me',
                    '.auto-login'
                ]
                
                for selector in remember_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            # 检查是否已选中
                            is_checked = await element.get_attribute("checked")
                            if not is_checked:
                                await element.click()
                                logger.info(f"已勾选记住登录状态: {selector}")
                                await asyncio.sleep(1)
                    except Exception as e:
                        logger.debug(f"尝试勾选记住登录状态失败 {selector}: {e}")
            
            return False
        except Exception as e:
            logger.error(f"尝试跳过验证失败: {e}")
            return False
    
    async def implement_login_retry_strategy(self, page: Page) -> bool:
        """
        实现登录重试策略，包括智能等待和多次尝试
        
        Args:
            page: 当前页面实例
            
        Returns:
            bool: 是否成功登录
        """
        try:
            # 记录登录尝试
            self.login_attempts += 1
            self.last_login_time = datetime.now()
            
            # 如果是短时间内多次尝试，增加等待时间
            if self.login_attempts > 1 and self.last_login_time:
                time_diff = datetime.now() - self.last_login_time
                if time_diff.total_seconds() < 300:  # 5分钟内多次尝试
                    wait_time = min(60, 10 * self.login_attempts)  # 最多等待60秒
                    logger.info(f"检测到短时间内多次登录尝试，等待 {wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
            
            # 尝试多种登录检测方法
            login_success_indicators = [
                # URL 指示器
                lambda: "publish" in page.url and "login" not in page.url,
                lambda: "creator.xiaohongshu.com" in page.url and any(kw in page.url for kw in ["dashboard", "publish", "content"]),
                
                # 元素指示器
                lambda: page.query_selector('button:has-text("发布")') is not None,
                lambda: page.query_selector('.publish-btn') is not None,
                lambda: page.query_selector('[data-testid="publish-button"]') is not None,
                lambda: page.query_selector('input[placeholder*="标题"]') is not None,
                
                # 标题指示器
                lambda: asyncio.create_task(page.title()).result() and "登录" not in asyncio.create_task(page.title()).result()
            ]
            
            # 检查登录状态
            for i, indicator in enumerate(login_success_indicators):
                try:
                    if asyncio.iscoroutinefunction(indicator):
                        result = await indicator()
                    else:
                        result = indicator()
                    
                    if result:
                        logger.info(f"登录成功，通过指示器 {i+1} 检测")
                        return True
                except Exception as e:
                    logger.debug(f"登录指示器 {i+1} 检测失败: {e}")
            
            return False
        except Exception as e:
            logger.error(f"登录重试策略失败: {e}")
            return False
    
    async def ensure_login(self, page: Page, browser_manager, cookies_file: str) -> bool:
        """
        确保用户已登录，使用多种策略避免频繁验证码
        
        Args:
            page: Playwright页面实例
            browser_manager: 浏览器管理器实例
            cookies_file: cookies文件路径
            
        Returns:
            bool: 是否成功登录
        """
        try:
            # 更新cookies文件路径
            self.cookies_file = cookies_file
            
            # 1. 优化浏览器会话
            if browser_manager and hasattr(browser_manager, 'context'):
                await self.optimize_browser_session(browser_manager.context)
            
            # 2. 尝试加载增强型cookies
            if browser_manager and hasattr(browser_manager, 'context'):
                cookies_loaded = await self.load_enhanced_cookies(browser_manager.context)
                if cookies_loaded:
                    logger.info("已加载增强型cookies")
            
            # 3. 导航到小红书创作者平台
            await page.goto('https://creator.xiaohongshu.com', wait_until="networkidle")
            await asyncio.sleep(3)  # 等待页面加载
            
            # 4. 检查是否已经登录
            is_logged_in = await self._check_login_status(page)
            if is_logged_in:
                logger.info("检测到已登录状态")
                # 保存当前cookies以备后用
                await self.enhance_cookie_persistence(page)
                return True
            
            # 5. 尝试跳过验证
            skip_success = await self.try_skip_verification(page)
            if skip_success:
                logger.info("成功跳过验证")
                # 保存cookies
                await self.enhance_cookie_persistence(page)
                return True
            
            # 6. 如果无法跳过，提示用户手动登录
            logger.warning("需要手动登录，请在浏览器中完成登录")
            logger.warning("提示：请输入手机号后点击获取验证码按钮，然后输入验证码完成登录")
            
            # 7. 等待用户登录
            login_success = await self._wait_for_manual_login(page)
            if login_success:
                logger.info("手动登录成功")
                # 保存cookies
                await self.enhance_cookie_persistence(page)
                return True
            
            # 8. 如果登录失败，实现重试策略
            retry_success = await self.implement_login_retry_strategy(page)
            if retry_success:
                logger.info("重试策略成功")
                # 保存cookies
                await self.enhance_cookie_persistence(page)
                return True
            
            logger.error("所有登录尝试均失败")
            return False
            
        except Exception as e:
            logger.error(f"确保登录过程中出错: {e}")
            return False
    
    async def _check_login_status(self, page: Page) -> bool:
        """
        检查当前登录状态
        
        Args:
            page: Playwright页面实例
            
        Returns:
            bool: 是否已登录
        """
        try:
            # 检查URL
            current_url = page.url
            if "login" not in current_url and "signin" not in current_url:
                if "creator.xiaohongshu.com" in current_url:
                    return True
            
            # 检查页面元素
            login_indicators = [
                '.user-avatar',
                '[class*="avatar"][class*="user"]',
                '.nav-user-avatar',
                '.profile-avatar',
                '[data-testid="user-avatar"]',
                '.header-user-info',
                '.user-info',
                '.header-user',
                '.user-menu',
                'button:has-text("发布")',
                '.publish-btn',
                '[data-testid="publish-button"]',
                'input[placeholder*="标题"]'
            ]
            
            for selector in login_indicators:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return True
                except Exception as e:
                    logger.debug(f"检查登录指示器失败 {selector}: {e}")
                    continue
            
            # 检查页面标题
            try:
                title = await page.title()
                if "登录" not in title and "Login" not in title:
                    if any(kw in title for kw in ["小红书", "Xiaohongshu", "Dashboard", "Creator"]):
                        return True
            except Exception as e:
                logger.debug(f"获取页面标题失败: {e}")
            
            return False
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    async def _wait_for_manual_login(self, page: Page, timeout: int = 120) -> bool:
        """
        等待用户手动完成登录
        
        Args:
            page: Playwright页面实例
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功登录
        """
        try:
            check_interval = 5  # 每5秒检查一次
            max_attempts = timeout // check_interval
            
            for i in range(max_attempts):
                # 等待一段时间
                await asyncio.sleep(check_interval)
                
                # 检查登录状态
                is_logged_in = await self._check_login_status(page)
                if is_logged_in:
                    logger.info("检测到登录成功")
                    return True
                
                remaining_time = timeout - ((i + 1) * check_interval)
                if remaining_time > 0:
                    logger.info(f"等待登录中，剩余时间: {remaining_time}秒...")
            
            logger.warning(f"等待手动登录超时（{timeout}秒）")
            return False
        except Exception as e:
            logger.error(f"等待手动登录失败: {e}")
            return False

    async def maintain_session(self, page: Page) -> None:
        """
        维护会话，定期执行操作保持登录状态
        
        Args:
            page: 当前页面实例
        """
        try:
            # 执行一些操作来保持会话活跃
            await page.evaluate("""
                // 模拟一些用户活动
                window.dispatchEvent(new Event('mousemove'));
                window.dispatchEvent(new Event('focus'));
            """)
            
            # 访问一个轻量级页面来刷新会话
            current_url = page.url
            if "creator.xiaohongshu.com" in current_url:
                # 尝试访问用户主页或设置页面
                await page.goto("https://creator.xiaohongshu.com/creator-center/home", wait_until="networkidle")
                await asyncio.sleep(2)
                await page.goto(current_url, wait_until="networkidle")
                
            logger.info("会话维护完成")
        except Exception as e:
            logger.error(f"会话维护失败: {e}")


# 全局登录优化器实例
_login_optimizer_instance = None


def get_login_optimizer() -> LoginOptimizer:
    """
    获取全局登录优化器实例
    
    Returns:
        LoginOptimizer: 登录优化器实例
    """
    global _login_optimizer_instance
    if _login_optimizer_instance is None:
        _login_optimizer_instance = LoginOptimizer()
    return _login_optimizer_instance


# 使用示例和集成建议
async def integrate_login_optimizer(publisher_instance) -> None:
    """
    将登录优化器集成到现有的发布器实例中
    
    Args:
        publisher_instance: 发布器实例
    """
    # 创建登录优化器实例
    optimizer = LoginOptimizer(publisher_instance.publish_config.cookies_file)
    
    # 在浏览器初始化后优化浏览器会话
    if hasattr(publisher_instance, 'browser_manager') and publisher_instance.browser_manager:
        context = publisher_instance.browser_manager.context
        await optimizer.optimize_browser_session(context)
        
        # 尝试加载增强型 cookies
        await optimizer.load_enhanced_cookies(context)
    
    # 将优化器实例添加到发布器中，以便其他方法使用
    publisher_instance.login_optimizer = optimizer
    
    logger.info("登录优化器已集成到发布器中")


# 修改现有登录方法的建议
async def enhanced_login_if_needed(self, page: Page) -> bool:
    """
    增强版登录检查方法，集成登录优化器
    
    Args:
        page: Playwright页面实例
        
    Returns:
        bool: 是否已登录
    """
    # 如果有登录优化器，先尝试跳过验证
    if hasattr(self, 'login_optimizer'):
        optimizer = self.login_optimizer
        
        # 尝试加载增强型 cookies
        if hasattr(self, 'browser_manager') and self.browser_manager:
            await optimizer.load_enhanced_cookies(self.browser_manager.context)
        
        # 尝试跳过验证
        if await optimizer.try_skip_verification(page):
            # 实现登录重试策略
            if await optimizer.implement_login_retry_strategy(page):
                # 保存增强型 cookies
                await optimizer.enhance_cookie_persistence(page)
                return True
    
    # 如果无法跳过验证，回退到原始登录方法
    return await self._original_login_if_needed(page)