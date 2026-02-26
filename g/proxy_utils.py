"""
代理配置管理工具
统一从 .env 文件加载代理配置
"""

import os
from dotenv import load_dotenv, get_key


def get_env_path():
    """获取 .env 文件路径"""
    # 从当前文件所在目录向上查找 .env
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 尝试在项目根目录找到 .env
    env_path = os.path.join(current_dir, ".env")
    if not os.path.exists(env_path):
        # 如果在子目录，向上查找一级
        parent_dir = os.path.dirname(current_dir)
        env_path = os.path.join(parent_dir, ".env")
    return env_path


def load_proxies_from_env():
    """
    从 .env 文件加载代理配置
    返回: dict 包含 http 和 https 代理，如果没有配置则返回空字典
    """
    env_path = get_env_path()

    # 使用 get_key 直接从 .env 文件读取（避免被系统环境变量覆盖）
    http_proxy = get_key(env_path, "HTTP_PROXY") or ""
    https_proxy = get_key(env_path, "HTTPS_PROXY") or ""

    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy

    return proxies


def get_proxy_config():
    """
    获取代理配置，优先从 .env 文件加载
    返回: tuple (http_proxy, https_proxy, proxies_dict)
    """
    env_path = get_env_path()

    # 使用 get_key 直接从 .env 文件读取
    http_proxy = get_key(env_path, "HTTP_PROXY") or ""
    https_proxy = get_key(env_path, "HTTPS_PROXY") or ""

    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy

    return http_proxy, https_proxy, proxies


# 全局代理配置（延迟加载，确保在导入时不会立即执行）
_proxies_cache = None


def get_proxies():
    """
    获取代理字典（带缓存）
    返回: dict 包含 http 和 https 代理
    """
    global _proxies_cache
    if _proxies_cache is None:
        _proxies_cache = load_proxies_from_env()
    return _proxies_cache


def reload_proxies():
    """
    重新加载代理配置（用于运行时更新）
    """
    global _proxies_cache
    _proxies_cache = load_proxies_from_env()
    return _proxies_cache


# 兼容性导出
PROXIES = get_proxies()
