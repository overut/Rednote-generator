"""
账号管理器模块
负责管理多个小红书账号的登录状态和cookies
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AccountInfo:
    """账号信息数据类"""
    account_name: str  # 账号名称
    display_name: str  # 显示名称
    cookies_file: str  # cookies文件路径
    is_active: bool = False  # 是否已登录激活
    last_login_time: Optional[str] = None  # 最后登录时间
    user_info: Optional[Dict[str, Any]] = None  # 用户信息
    notes_count: int = 0  # 已发布笔记数量


class AccountManager:
    """账号管理器类"""
    
    def __init__(self, accounts_dir: str = "accounts"):
        """
        初始化账号管理器
        
        Args:
            accounts_dir: 账号目录路径
        """
        self.accounts_dir = accounts_dir
        self.cookies_dir = os.path.join(accounts_dir, "cookies")
        self.accounts_file = os.path.join(accounts_dir, "accounts.json")
        
        # 确保目录存在
        os.makedirs(self.cookies_dir, exist_ok=True)
        os.makedirs(accounts_dir, exist_ok=True)
        
        # 加载账号信息
        self.accounts: Dict[str, AccountInfo] = {}
        self._load_accounts()
    
    def _load_accounts(self):
        """从文件加载账号信息"""
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r', encoding='utf-8') as f:
                    accounts_data = json.load(f)
                
                for account_name, account_data in accounts_data.items():
                    self.accounts[account_name] = AccountInfo(**account_data)
                logger.info(f"成功加载 {len(self.accounts)} 个账号信息")
            else:
                logger.info("账号信息文件不存在，将创建新的")
                # 创建默认账号
                self._create_default_account()
        except Exception as e:
            logger.error(f"加载账号信息失败: {str(e)}")
            # 创建默认账号
            self._create_default_account()
    
    def _create_default_account(self):
        """创建默认账号"""
        default_account = AccountInfo(
            account_name="default",
            display_name="默认账号",
            cookies_file=os.path.join(self.cookies_dir, "default.json"),
            is_active=False
        )
        self.accounts["default"] = default_account
        self._save_accounts()
    
    def _save_accounts(self):
        """保存账号信息到文件"""
        try:
            accounts_data = {}
            for account_name, account_info in self.accounts.items():
                accounts_data[account_name] = asdict(account_info)
            
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(accounts_data, f, ensure_ascii=False, indent=2)
            logger.info("账号信息保存成功")
        except Exception as e:
            logger.error(f"保存账号信息失败: {str(e)}")
    
    def get_account(self, account_name: str) -> Optional[AccountInfo]:
        """
        获取指定账号信息
        
        Args:
            account_name: 账号名称
            
        Returns:
            账号信息，如果不存在则返回None
        """
        return self.accounts.get(account_name)
    
    def get_all_accounts(self) -> List[AccountInfo]:
        """
        获取所有账号信息
        
        Returns:
            所有账号信息列表
        """
        return list(self.accounts.values())
    
    def get_active_accounts(self) -> List[AccountInfo]:
        """
        获取所有已激活的账号
        
        Returns:
            已激活账号信息列表
        """
        return [account for account in self.accounts.values() if account.is_active]
    
    def add_account(self, account_name: str, display_name: str = None) -> AccountInfo:
        """
        添加新账号
        
        Args:
            account_name: 账号名称
            display_name: 显示名称，如果为None则使用account_name
            
        Returns:
            新创建的账号信息
        """
        if account_name in self.accounts:
            logger.warning(f"账号 {account_name} 已存在")
            return self.accounts[account_name]
        
        if display_name is None:
            display_name = account_name
        
        new_account = AccountInfo(
            account_name=account_name,
            display_name=display_name,
            cookies_file=os.path.join(self.cookies_dir, f"{account_name}.json"),
            is_active=False
        )
        
        self.accounts[account_name] = new_account
        self._save_accounts()
        logger.info(f"成功添加账号: {account_name}")
        return new_account
    
    def update_account_status(self, account_name: str, is_active: bool, user_info: Dict[str, Any] = None):
        """
        更新账号登录状态
        
        Args:
            account_name: 账号名称
            is_active: 是否已激活
            user_info: 用户信息
        """
        if account_name not in self.accounts:
            logger.warning(f"账号 {account_name} 不存在")
            return
        
        self.accounts[account_name].is_active = is_active
        if is_active:
            self.accounts[account_name].last_login_time = datetime.now().isoformat()
        
        if user_info:
            self.accounts[account_name].user_info = user_info
        
        self._save_accounts()
        logger.info(f"更新账号 {account_name} 状态为: {'已激活' if is_active else '未激活'}")
    
    def increment_notes_count(self, account_name: str):
        """
        增加账号的笔记计数
        
        Args:
            account_name: 账号名称
        """
        if account_name in self.accounts:
            self.accounts[account_name].notes_count += 1
            self._save_accounts()
    
    def delete_account(self, account_name: str) -> bool:
        """
        删除账号
        
        Args:
            account_name: 账号名称
            
        Returns:
            是否删除成功
        """
        if account_name not in self.accounts:
            logger.warning(f"账号 {account_name} 不存在")
            return False
        
        # 删除cookies文件
        try:
            cookies_file = self.accounts[account_name].cookies_file
            if os.path.exists(cookies_file):
                os.remove(cookies_file)
        except Exception as e:
            logger.error(f"删除cookies文件失败: {str(e)}")
        
        # 从账号列表中删除
        del self.accounts[account_name]
        self._save_accounts()
        logger.info(f"成功删除账号: {account_name}")
        return True
    
    def get_cookies_file(self, account_name: str) -> Optional[str]:
        """
        获取指定账号的cookies文件路径
        
        Args:
            account_name: 账号名称
            
        Returns:
            cookies文件路径，如果账号不存在则返回None
        """
        account = self.get_account(account_name)
        if account:
            return account.cookies_file
        return None
    
    def get_account_names(self) -> List[str]:
        """
        获取所有账号名称
        
        Returns:
            所有账号名称列表
        """
        return list(self.accounts.keys())
    
    def has_valid_cookies(self, account_name: str) -> bool:
        """
        检查账号是否有有效的cookies文件
        
        Args:
            account_name: 账号名称
            
        Returns:
            是否有有效的cookies文件
        """
        cookies_file = self.get_cookies_file(account_name)
        if not cookies_file or not os.path.exists(cookies_file):
            return False
        
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
            
            # 检查cookies是否为空
            if isinstance(cookies_data, list) and len(cookies_data) > 0:
                return True
            elif isinstance(cookies_data, dict) and 'cookies' in cookies_data and len(cookies_data['cookies']) > 0:
                return True
            
            return False
        except Exception as e:
            logger.error(f"检查cookies文件有效性失败: {str(e)}")
            return False
    
    def account_exists(self, account_name: str) -> bool:
        """
        检查账号是否存在
        
        Args:
            account_name: 账号名称
            
        Returns:
            账号是否存在
        """
        return account_name in self.accounts