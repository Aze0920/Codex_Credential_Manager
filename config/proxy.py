# -*- coding: utf-8 -*-
"""
代理池配置。

默认空代理池，表示直连外网。如果部署环境需要代理，把代理 URL 加到
PROXY_POOL 即可，例如：
    "socks5h://user:pass@host:port"
"""
import random


PROXY_POOL: list[str] = []


def set_proxy_pool(proxies: list[str]) -> None:
    PROXY_POOL.clear()
    PROXY_POOL.extend(proxies)


def pick_proxy() -> str:
    """从代理池中随机抽取一个代理 URL；池为空时返回空串（即不使用代理）。"""
    return random.choice(PROXY_POOL) if PROXY_POOL else ""


PROXY = pick_proxy()
