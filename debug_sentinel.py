import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

class QuantLogger:
    """
    量化系统统一点亮 Debug Sentinel (Debug 监控分发系统)
    取代散落的 print()，提供多线程安全的结构化日志。
    """
    _instance = None
    _is_initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QuantLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._is_initialized:
            return
            
        self.log_dir = "logs"
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # 全局 Logger 设定
        self.logger = logging.getLogger("DeepSeekQuant")
        self.logger.setLevel(logging.DEBUG)

        # 格式化器: 包含时间, 等级, 文件名, 行号, 详细信息
        formatter = logging.Formatter(
            "[{asctime}] [{levelname:^7}] [{filename}:{lineno}] - {message}",
            style='{',
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 1. 输出到控制台 (Console)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO) # 控制台只看 INFO 及以上
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

        # 2. 输出到滚动文件 (File) 10MB x 5 个轮转
        file_handler = RotatingFileHandler(
            filename=os.path.join(self.log_dir, f"system_running.log"),
            mode='a',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG) # 文件全记录
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        self._is_initialized = True

    @classmethod
    def info(cls, msg):
        cls().logger.info(msg)

    @classmethod
    def warning(cls, msg):
        cls().logger.warning(msg)

    @classmethod
    def error(cls, msg):
        cls().logger.error(msg)
        
    @classmethod
    def debug(cls, msg):
        cls().logger.debug(msg)

# 直接暴露函数，方便其他模块使用
log_info = QuantLogger.info
log_warn = QuantLogger.warning
log_error = QuantLogger.error
log_debug = QuantLogger.debug
