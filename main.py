"""
B站UP主视频监控服务 - 主入口

功能:
- 加载配置
- 处理命令行参数
- 启动登录流程
- 启动监控服务
- 启动Web服务（v2.1+）
"""
import argparse
import logging
import sys
from pathlib import Path

import yaml

from src.login import BilibiliLogin


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    path = Path(config_path)
    if not path.exists():
        print(f"配置文件不存在: {config_path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"加载配置失败: {e}")
        return {}


def setup_logging(config: dict) -> logging.Logger:
    """
    配置日志

    Args:
        config: 配置字典

    Returns:
        Logger实例
    """
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO")
    log_format = log_config.get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # 清除已有 handler（避免重复）
    root_logger.handlers.clear()

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # 文件 handler（如果配置了日志文件）
    log_file = log_config.get("file")
    if log_file:
        from logging.handlers import RotatingFileHandler
        from pathlib import Path

        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 从配置读取轮转参数
        max_size_mb = log_config.get("max_size_mb", 10)
        backup_count = log_config.get("backup_count", 5)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, log_level, logging.INFO))
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)

    return logging.getLogger("monitor")


def run_login_flow(config: dict) -> bool:
    """
    执行登录流程

    Args:
        config: 配置字典

    Returns:
        登录成功返回True
    """
    login = BilibiliLogin()
    return login.login()


def start_monitor(config: dict, use_database: bool = True) -> None:
    """
    启动监控服务

    Args:
        config: 配置字典
        use_database: 是否使用数据库（默认True）
    """
    logger = logging.getLogger("monitor")

    # 1. 初始化数据库（如果启用）
    db = None
    if use_database:
        from src.database import Database

        db_path = config.get("database", {}).get("path", "data/monitor.db")
        logger.info(f"初始化数据库: {db_path}")

        db = Database(db_path)
        db.init_db()
        logger.info("数据库初始化成功")

    # 2. 加载Cookie
    from src.login import BilibiliLogin

    login = BilibiliLogin()
    cookies = login.load_cookies()

    if not cookies:
        logger.error("未找到Cookie，请先运行 'python main.py --login' 完成登录")
        print("请先运行 'python main.py --login' 完成登录")
        return

    # 3. 初始化客户端
    from src.bilibili import BilibiliClient

    client = BilibiliClient(cookies)

    # 4. 验证Cookie
    logger.info("正在验证Cookie...")
    if not client.check_cookie_valid():
        logger.error("Cookie已过期，请重新登录")
        print("Cookie已过期，请运行 'python main.py --login' 重新登录")
        return

    logger.info("Cookie验证通过")
    print("Cookie验证通过 ✓")

    # 5. 初始化飞书推送器
    from src.feishu import FeishuNotifier

    webhook_url = config.get("feishu", {}).get("webhook_url", "")
    if webhook_url:
        notifier = FeishuNotifier(webhook_url)
        logger.info("飞书推送器初始化成功")
    else:
        logger.warning("未配置飞书 Webhook URL，将跳过推送功能")
        notifier = None

    # 6. 初始化调度器
    from src.scheduler import MonitorScheduler

    monitor_config = config.get("monitor", {})
    scheduler = MonitorScheduler(
        bilibili_client=client,
        feishu_notifier=notifier,
        history_file="data/video_history.json",
        check_interval_minutes=monitor_config.get("check_interval_minutes", 30),
        max_ups=monitor_config.get("max_follows_to_check", 50),
        history_retention_days=180,
        database=db,  # 传入数据库实例
    )

    # 7. 启动监控循环
    logger.info("启动监控调度器")
    print("\n监控服务已启动，按 Ctrl+C 退出")
    print("-" * 40)

    scheduler.start()


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="B站UP主视频监控服务")
    parser.add_argument(
        "--login",
        action="store_true",
        help="执行扫码登录",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="启动Web服务",
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只执行一次检查(不循环)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3231,
        help="Web服务端口（默认3231）",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Web服务监听地址（默认0.0.0.0）",
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

    if args.web:
        # Web服务模式
        logger.info("启动Web服务模式")
        print(f"启动Web服务: http://{args.host}:{args.port}")
        print(f"API文档: http://{args.host}:{args.port}/docs")

        from src.web import run_web_server
        run_web_server(host=args.host, port=args.port)
        return

    # 启动监控
    if args.once:
        # TODO: 单次执行
        pass
    else:
        start_monitor(config)


if __name__ == "__main__":
    main()