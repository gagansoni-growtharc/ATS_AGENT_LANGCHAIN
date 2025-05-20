import logging
from pydantic import BaseModel
from typing import Dict, Any, Optional
from pymongo import MongoClient
from config.settings import get_settings
import datetime
import uuid
import threading

settings = get_settings()

# Thread-local storage for session context
_session_context = threading.local()

class LogEntry(BaseModel):
    timestamp: datetime.datetime
    level: str
    message: str
    module: str
    session_id: Optional[str] = None  # Added session_id field
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
        formatter = logging.Formatter('%(asctime)s - [%(session_id)s] - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

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

class MongoDBHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.client = MongoClient(settings.MONGO_URI)
        self.collection = self.client[settings.LOG_DB_NAME][settings.LOG_COLLECTION]
        
    def emit(self, record):
        try:
            # Get session_id from record or default
            session_id = getattr(record, "session_id", LogManager.get_session_id())
            
            entry = LogEntry(
                timestamp=datetime.datetime.utcnow(),
                level=record.levelname,
                message=record.getMessage(),
                module=record.module,
                session_id=session_id,  # Include session_id in log entry
                metadata=getattr(record, "metadata", {})
            )
            self.collection.insert_one(entry.model_dump())
        except Exception as e:
            print(f"Failed to log to MongoDB: {str(e)}")


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