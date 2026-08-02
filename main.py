"""
B站UP主视频监控服务 - 主入口

功能：
- 加载配置
- 处理命令行参数
- 启动登录流程
- 启动监控服务
"""
import argparse
import logging
import sys
from pathlib import Path

import yaml


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    # TODO: 读取YAML配置
    raise NotImplementedError


def setup_logging(config: dict) -> logging.Logger:
    """
    配置日志

    Args:
        config: 配置字典

    Returns:
        Logger实例
    """
    # TODO: 配置日志格式、文件、级别
    raise NotImplementedError


def run_login_flow(config: dict) -> bool:
    """
    执行登录流程

    Args:
        config: 配置字典

    Returns:
        登录成功返回True
    """
    # TODO: 创建BilibiliLogin实例 -> login()
    raise NotImplementedError


def start_monitor(config: dict) -> None:
    """
    启动监控服务

    Args:
        config: 配置字典
    """
    # TODO: 初始化各模块 -> 启动调度器
    raise NotImplementedError


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="B站UP主视频监控服务")
    parser.add_argument(
        "--login",
        action="store_true",
        help="执行扫码登录",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只执行一次检查（不循环）",
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 配置日志
    logger = setup_logging(config)

    if args.login:
        # 登录模式
        success = run_login_flow(config)
        if success:
            print("登录成功")
            sys.exit(0)
        else:
            print("登录失败")
            sys.exit(1)

    # 启动监控
    if args.once:
        # TODO: 单次执行
        pass
    else:
        start_monitor(config)


if __name__ == "__main__":
    main()