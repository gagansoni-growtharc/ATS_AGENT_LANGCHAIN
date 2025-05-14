import logging
from pydantic import BaseModel
from typing import Dict, Any
from pymongo import MongoClient
from config.settings import get_settings
import datetime

settings = get_settings()

class LogEntry(BaseModel):
    timestamp: datetime.datetime
    level: str
    message: str
    module: str
    metadata: Dict[str, Any] = {}

class LogManager:
    _instance = None
    _logger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Internal initialization"""
        self._logger = logging.getLogger("ATS")
        self._logger.handlers = []
        self._logger.setLevel(logging.INFO)

    def configure(self, debug: bool = False):
        """Public configuration method"""
        # Clear existing handlers
        self._logger.handlers = []
        
        # Set level
        level = logging.DEBUG if debug else logging.INFO
        self._logger.setLevel(level)
        
        # Add handlers
        self._add_mongo_handler()
        self._add_console_handler(level)

    def _add_mongo_handler(self):
        handler = MongoDBHandler()
        self._logger.addHandler(handler)

    def _add_console_handler(self, level):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

    @property
    def logger(self):
        return self._logger

class MongoDBHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.client = MongoClient(settings.MONGO_URI)
        self.collection = self.client[settings.LOG_DB_NAME][settings.LOG_COLLECTION]
        
    def emit(self, record):
        try:
            entry = LogEntry(
                timestamp=datetime.datetime.utcnow(),
                level=record.levelname,
                message=record.getMessage(),
                module=record.module,
                metadata=getattr(record, "metadata", {})
            )
            self.collection.insert_one(entry.model_dump())
        except Exception as e:
            print(f"Failed to log to MongoDB: {str(e)}")

def log_with_context(level: str, message: str, **context: Dict[str, Any]):
    logger = LogManager().logger
    extra = {"metadata": context}
    
    if level == "debug":
        logger.debug(message, extra=extra)
    elif level == "info":
        logger.info(message, extra=extra)
    elif level == "warning":
        logger.warning(message, extra=extra)
    elif level == "error":
        logger.error(message, extra=extra)
    elif level == "critical":
        logger.critical(message, extra=extra)

# Shortcut functions
def log_debug(message: str, **kwargs):
    log_with_context("debug", message, **kwargs)

def log_info(message: str, **kwargs):
    log_with_context("info", message, **kwargs)

def log_warn(message: str, **kwargs):
    log_with_context("warning", message, **kwargs)

def log_error(message: str, **kwargs):
    log_with_context("error", message, **kwargs)