# logger/logger.py
import logging
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel
from typing import Dict, Any, Optional
from pathlib import Path
import datetime
import uuid
import threading

# Create logs directory if it doesn't exist
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

class LogEntry(BaseModel):
    timestamp: datetime.datetime
    level: str
    message: str
    module: str
    session_id: Optional[str] = None
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
        self._logger.addFilter(SessionFilter())

    def configure(self, debug: bool = False):
        """Public configuration method"""
        # Clear existing handlers
        self._logger.handlers = []
        
        # Set level
        level = logging.DEBUG if debug else logging.INFO
        self._logger.setLevel(level)
        
        # Add rotating file handler
        self._add_file_handler(level)

    def _add_file_handler(self, level):
        """Add rotating file handler with 10MB size limit"""
        log_file = LOG_DIR / "ats_system.log"
        handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=100*1024*1024,  # 10MB
            backupCount=2,
            encoding='utf-8'
        )
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - [%(session_id)s] - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    @property
    def logger(self):
        return self._logger
    
    @staticmethod
    def set_session_id(session_id: str = None):
        """Set the session ID for the current thread"""
        if session_id is None:
            session_id = str(uuid.uuid4())
        _session_context.session_id = session_id
        return session_id
    
    @staticmethod
    def get_session_id() -> str:
        """Get the current session ID or create a new one"""
        if not hasattr(_session_context, 'session_id'):
            _session_context.session_id = str(uuid.uuid4())
        return _session_context.session_id
    
    @staticmethod
    def clear_session_id():
        """Clear the session ID for the current thread"""
        if hasattr(_session_context, 'session_id'):
            delattr(_session_context, 'session_id')

class SessionFilter(logging.Filter):
    """Filter that adds session_id to log records"""
    def filter(self, record):
        record.session_id = getattr(record, "session_id", LogManager.get_session_id())
        return True

def log_with_context(level: str, message: str, session_id: str = None, **context: Dict[str, Any]):
    logger = LogManager().logger
    
    # Use provided session_id or get from context
    if session_id is None:
        session_id = LogManager.get_session_id()
    
    extra = {
        "metadata": context,
        "session_id": session_id
    }
    
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
def log_debug(message: str, session_id: str = None, **kwargs):
    log_with_context("debug", message, session_id, **kwargs)

def log_info(message: str, session_id: str = None, **kwargs):
    log_with_context("info", message, session_id, **kwargs)

def log_warn(message: str, session_id: str = None, **kwargs):
    log_with_context("warning", message, session_id, **kwargs)

def log_error(message: str, session_id: str = None, **kwargs):
    log_with_context("error", message, session_id, **kwargs)

# Thread-local storage initialization
_session_context = threading.local()