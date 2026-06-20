"""
Enterprise Utility Layer for AI DDR Platform
Centralized infrastructure for validation, logging, security, and observability
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, TypeVar, Generic
import functools

import aiofiles
from pydantic import BaseModel, Field, field_validator
import psutil

# ============================================================================
# CONFIGURATION UTILITIES
# ============================================================================

class Environment(str, Enum):
    """Environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseModel):
    """Centralized application settings"""
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    
    # Paths
    upload_dir: Path = Field(default=Path("uploads"))
    output_dir: Path = Field(default=Path("generated_reports"))
    extracted_images_dir: Path = Field(default=Path("generated_reports/extracted_images"))
    log_dir: Path = Field(default=Path("logs"))
    temp_dir: Path = Field(default=Path("temp"))
    
    # File limits
    max_file_size_bytes: int = Field(default=500 * 1024 * 1024)  # 500MB
    max_image_size_bytes: int = Field(default=50 * 1024 * 1024)  # 50MB
    allowed_extensions: List[str] = Field(default=[".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".gif"])
    
    # Security
    secret_key: str = Field(default="")
    session_timeout_minutes: int = Field(default=60)
    rate_limit_per_minute: int = Field(default=100)
    
    # Performance
    max_concurrent_tasks: int = Field(default=10)
    cache_ttl_seconds: int = Field(default=3600)
    
    # API
    api_version: str = Field(default="v1")
    api_timeout_seconds: int = Field(default=30)
    
    # Models - Default to Gemini model
    default_model: str = Field(default="models/gemini-2.5-flash")
    model_timeout_seconds: int = Field(default=60)
    
    # Hugging Face support
    hf_token: Optional[str] = Field(default=None)
    hf_model: str = Field(default="Qwen/Qwen2.5-VL-72B-Instruct")
    
    @field_validator('environment', mode='before')
    @classmethod
    def validate_environment(cls, v):
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                return Environment.DEVELOPMENT
        return v
    
    @field_validator('allowed_extensions', mode='before')
    @classmethod
    def validate_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(',') if ext.strip()]
        return v
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "environment": "development",
                "debug": True,
                "upload_dir": "uploads",
                "output_dir": "generated_reports",
                "max_file_size_bytes": 524288000,
                "default_model": "models/gemini-2.5-flash"
            }
        }
    }


class SettingsManager:
    """Singleton settings manager with environment support"""
    
    _instance = None
    _settings: Optional[Settings] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, env_file: Optional[Path] = None) -> Settings:
        """Initialize settings from environment variables or file"""
        if self._settings is None:
            if env_file and env_file.exists():
                self._settings = Settings(_env_file=str(env_file))
            else:
                self._settings = Settings()
        return self._settings
    
    def get(self) -> Settings:
        """Get current settings"""
        if self._settings is None:
            self.initialize()
        return self._settings
    
    def reload(self) -> Settings:
        """Reload settings from environment"""
        self._settings = None
        return self.initialize()


settings_manager = SettingsManager()

def get_settings() -> Settings:
    """Get application settings"""
    return settings_manager.get()


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

class ValidationError(Exception):
    """Base validation error"""
    pass


class FileValidationError(ValidationError):
    """File validation error"""
    pass


class SchemaValidationError(ValidationError):
    """Schema validation error"""
    pass


class FileProcessingError(Exception):
    """File processing error"""
    pass


def validate_pdf_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate PDF file integrity and format.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path.exists():
        return False, "File does not exist"
    
    if file_path.stat().st_size == 0:
        return False, "File is empty"
    
    if file_path.stat().st_size > get_settings().max_file_size_bytes:
        return False, f"File size exceeds limit: {file_path.stat().st_size} > {get_settings().max_file_size_bytes}"
    
    # Check file extension
    if file_path.suffix.lower() != ".pdf":
        return False, f"Invalid file extension: {file_path.suffix}"
    
    # Check PDF magic bytes
    try:
        with open(file_path, 'rb') as f:
            header = f.read(5)
        if header != b'%PDF-':
            return False, "Invalid PDF header"
    except Exception as e:
        return False, f"Failed to read PDF header: {str(e)}"
    
    return True, None


def validate_file_size(file_path: Path, max_size: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate file size.
    
    Args:
        file_path: Path to file
        max_size: Maximum size in bytes (default from settings)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    max_size = max_size or get_settings().max_file_size_bytes
    
    if not file_path.exists():
        return False, "File does not exist"
    
    file_size = file_path.stat().st_size
    if file_size > max_size:
        return False, f"File size {file_size} exceeds maximum {max_size}"
    
    return True, None


def validate_file_extension(file_path: Path, allowed_extensions: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate file extension.
    
    Args:
        file_path: Path to file
        allowed_extensions: List of allowed extensions (default from settings)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    allowed_extensions = allowed_extensions or get_settings().allowed_extensions
    
    ext = file_path.suffix.lower()
    if ext not in allowed_extensions:
        return False, f"Invalid extension: {ext}. Allowed: {allowed_extensions}"
    
    return True, None


def validate_filename(filename: str) -> Tuple[bool, Optional[str]]:
    """
    Validate filename for safety.
    
    Args:
        filename: Filename to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filename:
        return False, "Filename is empty"
    
    if len(filename) > 255:
        return False, "Filename too long"
    
    if any(c in filename for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        return False, "Filename contains invalid characters"
    
    return True, None


def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate JSON data against schema.
    
    Args:
        data: JSON data to validate
        schema: JSON schema to validate against
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        from jsonschema import validate, ValidationError as SchemaValidationError
        validate(instance=data, schema=schema)
        return True, None
    except ImportError:
        # Fallback to basic validation
        return _basic_schema_validation(data, schema)
    except SchemaValidationError as e:
        return False, str(e)


def _basic_schema_validation(data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Basic schema validation fallback"""
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"
    
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    properties = schema.get("properties", {})
    for field, field_schema in properties.items():
        if field in data:
            field_type = field_schema.get("type")
            if field_type == "string" and not isinstance(data[field], str):
                return False, f"Field {field} must be string"
            elif field_type == "number" and not isinstance(data[field], (int, float)):
                return False, f"Field {field} must be number"
            elif field_type == "array" and not isinstance(data[field], list):
                return False, f"Field {field} must be array"
            elif field_type == "object" and not isinstance(data[field], dict):
                return False, f"Field {field} must be object"
    
    return True, None


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate required fields are present.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    missing = [field for field in required_fields if field not in data]
    if missing:
        return False, f"Missing required fields: {missing}"
    return True, None


# ============================================================================
# FILE UTILITIES
# ============================================================================

@dataclass
class FileMetadata:
    """File metadata container"""
    path: Path
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    checksum: str
    mime_type: Optional[str] = None
    extension: str = ""


def generate_unique_filename(original_filename: str, prefix: str = "") -> str:
    """
    Generate a unique filename with UUID.
    
    Args:
        original_filename: Original filename
        prefix: Optional prefix for filename
        
    Returns:
        Unique filename
    """
    ext = Path(original_filename).suffix
    unique_id = uuid.uuid4().hex[:12]
    if prefix:
        return f"{prefix}_{unique_id}{ext}"
    return f"{unique_id}{ext}"


def generate_report_id() -> str:
    """Generate unique report ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"DDR_{timestamp}_{unique_id}"


def generate_request_id() -> str:
    """Generate unique request ID for tracing"""
    return uuid.uuid4().hex[:16]


async def safe_file_save(content: bytes, file_path: Path, overwrite: bool = False) -> Path:
    """
    Safely save file with validation.
    
    Args:
        content: File content as bytes
        file_path: Destination path
        overwrite: Whether to overwrite existing file
        
    Returns:
        Path to saved file
        
    Raises:
        FileValidationError: If file is invalid or already exists
    """
    if file_path.exists() and not overwrite:
        raise FileValidationError(f"File already exists: {file_path}")
    
    # Validate filename
    valid, error = validate_filename(file_path.name)
    if not valid:
        raise FileValidationError(f"Invalid filename: {error}")
    
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    return file_path


async def safe_file_delete(file_path: Path, ignore_missing: bool = False) -> bool:
    """
    Safely delete file.
    
    Args:
        file_path: Path to file
        ignore_missing: Whether to ignore if file doesn't exist
        
    Returns:
        True if deleted, False if not found
    """
    try:
        if file_path.exists():
            await aiofiles.os.remove(file_path)
            return True
        elif ignore_missing:
            return False
        else:
            raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise FileProcessingError(f"Failed to delete file {file_path}: {str(e)}")


def file_checksum(file_path: Path, algorithm: str = "md5") -> str:
    """
    Calculate file checksum.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256)
        
    Returns:
        Checksum string
    """
    hash_func = getattr(hashlib, algorithm)()
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def file_metadata(file_path: Path) -> FileMetadata:
    """
    Get file metadata.
    
    Args:
        file_path: Path to file
        
    Returns:
        FileMetadata object
    """
    stat = file_path.stat()
    return FileMetadata(
        path=file_path,
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_ctime),
        modified_at=datetime.fromtimestamp(stat.st_mtime),
        checksum=file_checksum(file_path),
        extension=file_path.suffix.lower()
    )


# ============================================================================
# DIRECTORY UTILITIES
# ============================================================================

def create_directory(path: Path) -> Path:
    """
    Create directory if it doesn't exist.
    
    Args:
        path: Directory path
        
    Returns:
        Path to created directory
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_project_directories() -> Dict[str, Path]:
    """
    Ensure all project directories exist.
    
    Returns:
        Dictionary of directory paths
    """
    settings = get_settings()
    
    directories = {
        "uploads": create_directory(settings.upload_dir),
        "output": create_directory(settings.output_dir),
        "images": create_directory(settings.extracted_images_dir),
        "logs": create_directory(settings.log_dir),
        "temp": create_directory(settings.temp_dir),
    }
    
    return directories


async def cleanup_temp_files(max_age_hours: int = 24) -> int:
    """
    Clean up temporary files older than max_age.
    
    Args:
        max_age_hours: Maximum age in hours
        
    Returns:
        Number of files cleaned up
    """
    settings = get_settings()
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    cleaned = 0
    
    for file_path in settings.temp_dir.glob("*"):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff_time:
                await safe_file_delete(file_path, ignore_missing=True)
                cleaned += 1
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to clean {file_path}: {e}")
    
    return cleaned


async def cleanup_old_reports(max_age_days: int = 30) -> int:
    """
    Clean up old reports.
    
    Args:
        max_age_days: Maximum age in days
        
    Returns:
        Number of files cleaned up
    """
    settings = get_settings()
    cutoff_time = datetime.now() - timedelta(days=max_age_days)
    cleaned = 0
    
    for file_path in settings.output_dir.glob("*.pdf"):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff_time:
                await safe_file_delete(file_path, ignore_missing=True)
                cleaned += 1
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to clean {file_path}: {e}")
    
    return cleaned


async def cleanup_old_images(max_age_days: int = 7) -> int:
    """
    Clean up old extracted images.
    
    Args:
        max_age_days: Maximum age in days
        
    Returns:
        Number of files cleaned up
    """
    settings = get_settings()
    cutoff_time = datetime.now() - timedelta(days=max_age_days)
    cleaned = 0
    
    for file_path in settings.extracted_images_dir.glob("*"):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff_time:
                await safe_file_delete(file_path, ignore_missing=True)
                cleaned += 1
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to clean {file_path}: {e}")
    
    return cleaned


# ============================================================================
# TEXT UTILITIES
# ============================================================================

def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and control characters.
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove control characters
    text = remove_control_characters(text)
    
    # Normalize whitespace
    text = normalize_whitespace(text)
    
    return text.strip()


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace characters.
    
    Args:
        text: Input text
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    
    # Replace multiple whitespace with single space
    return ' '.join(text.split())


def remove_control_characters(text: str) -> str:
    """
    Remove control characters from text.
    
    Args:
        text: Input text
        
    Returns:
        Text without control characters
    """
    if not text:
        return ""
    
    # Remove all control characters except newline and tab
    return ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')


def truncate_text(text: str, max_length: int = 1000, ellipsis: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Input text
        max_length: Maximum length
        ellipsis: Ellipsis string to append
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis


def safe_string(value: Any, default: str = "") -> str:
    """
    Safely convert any value to string.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        String representation
    """
    try:
        return str(value)
    except Exception:
        return default


def format_paragraphs(text: str, max_line_length: int = 80) -> str:
    """
    Format text into paragraphs with line wrapping.
    
    Args:
        text: Input text
        max_line_length: Maximum line length
        
    Returns:
        Formatted text
    """
    if not text:
        return ""
    
    lines = []
    for paragraph in text.split('\n\n'):
        words = paragraph.split()
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= max_line_length:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        lines.append('')
    
    return '\n'.join(lines)


# ============================================================================
# LOGGING UTILITIES
# ============================================================================

class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: LogLevel
    logger: str
    message: str
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StructuredLogger:
    """Enterprise structured logger"""
    
    def __init__(self, name: str, log_file: Optional[Path] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.log_file = log_file
        
        # Configure logger
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(console_handler)
        
        # Add file handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(self._get_formatter())
            self.logger.addHandler(file_handler)
    
    def _get_formatter(self) -> logging.Formatter:
        """Get structured formatter"""
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal log method"""
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            logger=self.name,
            message=message,
            request_id=kwargs.get('request_id'),
            correlation_id=kwargs.get('correlation_id'),
            metadata=kwargs.get('metadata', {})
        )
        
        # Add structured data to log
        structured_message = json.dumps({
            'timestamp': log_entry.timestamp.isoformat(),
            'level': log_entry.level.value,
            'logger': log_entry.logger,
            'message': log_entry.message,
            'request_id': log_entry.request_id,
            'correlation_id': log_entry.correlation_id,
            'metadata': log_entry.metadata
        })
        
        # Log with appropriate level
        level_method = getattr(self.logger, level.value.lower())
        level_method(structured_message)
    
    def debug(self, message: str, **kwargs):
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(LogLevel.CRITICAL, message, **kwargs)


class LoggingManager:
    """Centralized logging manager"""
    
    _instance = None
    _loggers: Dict[str, StructuredLogger] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_logger(self, name: str, log_file: Optional[Path] = None) -> StructuredLogger:
        """Get or create a structured logger"""
        if name not in self._loggers:
            settings = get_settings()
            if log_file is None:
                log_file = settings.log_dir / f"{name}.log"
            self._loggers[name] = StructuredLogger(name, log_file)
        return self._loggers[name]


logging_manager = LoggingManager()

def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger by name"""
    return logging_manager.get_logger(name)


def request_logger(request_id: Optional[str] = None) -> Callable:
    """Decorator for request logging"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            req_id = request_id or generate_request_id()
            
            logger.info(
                f"Request started: {func.__name__}",
                request_id=req_id,
                metadata={'function': func.__name__}
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.info(
                    f"Request completed: {func.__name__}",
                    request_id=req_id,
                    metadata={'function': func.__name__}
                )
                return result
            except Exception as e:
                logger.error(
                    f"Request failed: {func.__name__} - {str(e)}",
                    request_id=req_id,
                    metadata={'function': func.__name__, 'error': str(e)}
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            req_id = request_id or generate_request_id()
            
            logger.info(
                f"Request started: {func.__name__}",
                request_id=req_id,
                metadata={'function': func.__name__}
            )
            
            try:
                result = func(*args, **kwargs)
                logger.info(
                    f"Request completed: {func.__name__}",
                    request_id=req_id,
                    metadata={'function': func.__name__}
                )
                return result
            except Exception as e:
                logger.error(
                    f"Request failed: {func.__name__} - {str(e)}",
                    request_id=req_id,
                    metadata={'function': func.__name__, 'error': str(e)}
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# ============================================================================
# METRICS UTILITIES
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Performance metrics container"""
    function_name: str
    execution_time_seconds: float
    memory_usage_mb: float
    cpu_percent: float
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Centralized metrics collection"""
    
    _instance = None
    _metrics: List[PerformanceMetrics] = []
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def record_metric(self, metric: PerformanceMetrics):
        """Record a performance metric"""
        self._metrics.append(metric)
        
        # Keep only last 1000 metrics
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]
    
    def get_metrics(self, function_name: Optional[str] = None) -> List[PerformanceMetrics]:
        """Get recorded metrics"""
        if function_name:
            return [m for m in self._metrics if m.function_name == function_name]
        return self._metrics
    
    def get_summary(self, function_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics summary"""
        metrics = self.get_metrics(function_name)
        
        if not metrics:
            return {}
        
        execution_times = [m.execution_time_seconds for m in metrics]
        memory_usage = [m.memory_usage_mb for m in metrics]
        
        return {
            'count': len(metrics),
            'avg_execution_time': sum(execution_times) / len(execution_times),
            'min_execution_time': min(execution_times),
            'max_execution_time': max(execution_times),
            'avg_memory_usage': sum(memory_usage) / len(memory_usage),
            'total_memory_usage': sum(memory_usage),
            'timestamp': datetime.now().isoformat()
        }


metrics_collector = MetricsCollector()


def track_execution_time(func: Callable) -> Callable:
    """Decorator to track execution time and memory usage"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        process = psutil.Process()
        start_time = time.time()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            end_memory = process.memory_info().rss / 1024 / 1024
            
            metric = PerformanceMetrics(
                function_name=func.__name__,
                execution_time_seconds=end_time - start_time,
                memory_usage_mb=end_memory - start_memory,
                cpu_percent=process.cpu_percent()
            )
            metrics_collector.record_metric(metric)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        process = psutil.Process()
        start_time = time.time()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            end_memory = process.memory_info().rss / 1024 / 1024
            
            metric = PerformanceMetrics(
                function_name=func.__name__,
                execution_time_seconds=end_time - start_time,
                memory_usage_mb=end_memory - start_memory,
                cpu_percent=process.cpu_percent()
            )
            metrics_collector.record_metric(metric)
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def measure_memory_usage() -> Dict[str, float]:
    """Measure current memory usage"""
    process = psutil.Process()
    return {
        'memory_mb': process.memory_info().rss / 1024 / 1024,
        'cpu_percent': process.cpu_percent(),
        'memory_percent': process.memory_percent()
    }


def performance_report() -> Dict[str, Any]:
    """Generate performance report"""
    return {
        'timestamp': datetime.now().isoformat(),
        'metrics_summary': metrics_collector.get_summary(),
        'current_memory': measure_memory_usage(),
        'environment': get_settings().environment.value
    }


# ============================================================================
# DATE UTILITIES
# ============================================================================

def current_timestamp() -> float:
    """Get current timestamp"""
    return time.time()


def current_iso_timestamp() -> str:
    """Get current ISO formatted timestamp"""
    return datetime.now().isoformat()


def format_date(dt: Optional[datetime] = None, format_str: str = "%Y-%m-%d") -> str:
    """
    Format date.
    
    Args:
        dt: Datetime object (default: now)
        format_str: Format string
        
    Returns:
        Formatted date string
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(format_str)


def generate_datetime_string() -> str:
    """Generate standardized datetime string"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ============================================================================
# SECURITY UTILITIES
# ============================================================================

class SecurityError(Exception):
    """Security-related error"""
    pass


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Input filename
        replacement: Replacement character for invalid chars
        
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace('/', replacement).replace('\\', replacement)
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Remove problematic characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
    for char in dangerous_chars:
        filename = filename.replace(char, replacement)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    
    return filename


def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input for safety.
    
    Args:
        text: Input text
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    
    # Remove script tags
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL)
    
    # Remove dangerous characters
    text = text.replace('javascript:', '')
    text = text.replace('onerror=', '')
    text = text.replace('onload=', '')
    
    return text.strip()


def safe_path_join(*parts: Union[str, Path]) -> Path:
    """
    Safely join path parts and prevent directory traversal.
    
    Args:
        *parts: Path parts to join
        
    Returns:
        Joined Path object
        
    Raises:
        SecurityError: If path traversal detected
    """
    if not parts:
        return Path()
    
    # Convert to Path and resolve
    path = Path(*parts)
    
    # Detect path traversal
    if '..' in path.parts:
        raise SecurityError("Directory traversal detected")
    
    return path


def detect_path_traversal(path: Union[str, Path]) -> bool:
    """
    Detect path traversal attempts.
    
    Args:
        path: Path to check
        
    Returns:
        True if path traversal detected
    """
    path_str = str(path)
    return '..' in path_str or '/../' in path_str or '\\..\\' in path_str


def basic_upload_security_check(file: Any, max_size: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Basic security check for uploaded files.
    
    Args:
        file: Uploaded file object
        max_size: Maximum file size (default from settings)
        
    Returns:
        Tuple of (is_safe, error_message)
    """
    # Check filename
    if not hasattr(file, 'filename'):
        return False, "Invalid file object"
    
    valid, error = validate_filename(file.filename)
    if not valid:
        return False, f"Invalid filename: {error}"
    
    # Check file size
    if hasattr(file, 'size'):
        max_size = max_size or get_settings().max_file_size_bytes
        if file.size > max_size:
            return False, f"File size exceeds limit: {file.size} > {max_size}"
    
    return True, None


# ============================================================================
# RESPONSE UTILITIES
# ============================================================================

class APIResponse(BaseModel):
    """Standardized API response"""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"key": "value"},
                "errors": None,
                "metadata": {"timestamp": "2024-01-01T00:00:00Z"}
            }
        }
    }


def success_response(data: Any = None, message: str = "Operation completed successfully", **kwargs) -> Dict[str, Any]:
    """
    Create a success API response.
    
    Args:
        data: Response data
        message: Success message
        **kwargs: Additional metadata
        
    Returns:
        Standardized success response
    """
    response = APIResponse(
        success=True,
        message=message,
        data=data,
        errors=None,
        metadata={
            "timestamp": current_iso_timestamp(),
            **kwargs
        }
    )
    return response.model_dump(exclude_none=True)


def error_response(message: str, errors: Optional[List[str]] = None, status_code: int = 500, **kwargs) -> Dict[str, Any]:
    """
    Create an error API response.
    
    Args:
        message: Error message
        errors: List of specific errors
        status_code: HTTP status code
        **kwargs: Additional metadata
        
    Returns:
        Standardized error response
    """
    response = APIResponse(
        success=False,
        message=message,
        data=None,
        errors=errors or [message],
        metadata={
            "timestamp": current_iso_timestamp(),
            "status_code": status_code,
            **kwargs
        }
    )
    return response.model_dump(exclude_none=True)


def validation_error_response(errors: List[str], **kwargs) -> Dict[str, Any]:
    """
    Create a validation error response.
    
    Args:
        errors: List of validation errors
        **kwargs: Additional metadata
        
    Returns:
        Standardized validation error response
    """
    return error_response(
        message="Validation failed",
        errors=errors,
        status_code=400,
        **kwargs
    )


def processing_error_response(process: str, error: Exception, **kwargs) -> Dict[str, Any]:
    """
    Create a processing error response.
    
    Args:
        process: Name of the process that failed
        error: Exception that occurred
        **kwargs: Additional metadata
        
    Returns:
        Standardized processing error response
    """
    return error_response(
        message=f"{process} processing failed",
        errors=[str(error)],
        status_code=500,
        process=process,
        **kwargs
    )


# ============================================================================
# ERROR HANDLING
# ============================================================================

class BaseError(Exception):
    """Base exception for all application errors"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}
        self.timestamp = datetime.now()


class ValidationError(BaseError):
    """Validation error"""
    pass


class FileProcessingError(BaseError):
    """File processing error"""
    pass


class PDFExtractionError(BaseError):
    """PDF extraction error"""
    pass


class ImageExtractionError(BaseError):
    """Image extraction error"""
    pass


class AIProcessingError(BaseError):
    """AI processing error"""
    pass


class DDRGenerationError(BaseError):
    """DDR generation error"""
    pass


class ReportGenerationError(BaseError):
    """Report generation error"""
    pass


class ConfigurationError(BaseError):
    """Configuration error"""
    pass


class SecurityError(BaseError):
    """Security error"""
    pass


def handle_error(error: Exception, logger: Optional[StructuredLogger] = None) -> Dict[str, Any]:
    """
    Centralized error handler.
    
    Args:
        error: Exception to handle
        logger: Logger instance
        
    Returns:
        Standardized error response
    """
    if logger is None:
        logger = get_logger("error_handler")
    
    # Log error
    logger.error(
        f"Error occurred: {str(error)}",
        metadata={
            "error_type": type(error).__name__,
            "error_details": getattr(error, 'details', {}),
            "traceback": str(error.__traceback__) if error.__traceback__ else None
        }
    )
    
    # Determine appropriate response
    if isinstance(error, ValidationError):
        return validation_error_response([str(error)])
    elif isinstance(error, SecurityError):
        return error_response("Security violation", status_code=403)
    elif isinstance(error, (FileProcessingError, PDFExtractionError, ImageExtractionError)):
        return processing_error_response("file_processing", error)
    elif isinstance(error, AIProcessingError):
        return processing_error_response("ai_processing", error)
    elif isinstance(error, DDRGenerationError):
        return processing_error_response("ddr_generation", error)
    elif isinstance(error, ReportGenerationError):
        return processing_error_response("report_generation", error)
    elif isinstance(error, ConfigurationError):
        return error_response("Configuration error", status_code=500)
    else:
        return error_response("Internal server error", status_code=500)


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_utils(env_file: Optional[Path] = None) -> None:
    """
    Initialize all utility modules.
    
    Args:
        env_file: Optional environment file path
    """
    # Initialize settings
    settings_manager.initialize(env_file)
    
    # Ensure directories
    ensure_project_directories()
    
    # Configure logging
    settings = get_settings()
    log_level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Log initialization
    logger = get_logger("utils")
    logger.info(
        "Utils initialized",
        metadata={
            "environment": settings.environment.value,
            "debug": settings.debug,
            "upload_dir": str(settings.upload_dir),
            "output_dir": str(settings.output_dir)
        }
    )


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Configuration
    "Settings",
    "SettingsManager",
    "get_settings",
    "initialize_utils",
    
    # Environment
    "Environment",
    
    # Validation
    "ValidationError",
    "FileValidationError",
    "SchemaValidationError",
    "validate_pdf_file",
    "validate_file_size",
    "validate_file_extension",
    "validate_filename",
    "validate_json_schema",
    "validate_required_fields",
    
    # File utilities
    "FileMetadata",
    "generate_unique_filename",
    "generate_report_id",
    "generate_request_id",
    "safe_file_save",
    "safe_file_delete",
    "file_checksum",
    "file_metadata",
    "create_directory",
    "ensure_project_directories",
    "cleanup_temp_files",
    "cleanup_old_reports",
    "cleanup_old_images",
    
    # Text utilities
    "clean_text",
    "normalize_whitespace",
    "remove_control_characters",
    "truncate_text",
    "safe_string",
    "format_paragraphs",
    
    # Logging
    "LogLevel",
    "LogEntry",
    "StructuredLogger",
    "LoggingManager",
    "get_logger",
    "request_logger",
    
    # Metrics
    "PerformanceMetrics",
    "MetricsCollector",
    "track_execution_time",
    "measure_memory_usage",
    "performance_report",
    
    # Date utilities
    "current_timestamp",
    "current_iso_timestamp",
    "format_date",
    "generate_datetime_string",
    
    # Security
    "SecurityError",
    "sanitize_filename",
    "sanitize_user_input",
    "safe_path_join",
    "detect_path_traversal",
    "basic_upload_security_check",
    
    # Response
    "APIResponse",
    "success_response",
    "error_response",
    "validation_error_response",
    "processing_error_response",
    
    # Error handling
    "BaseError",
    "FileProcessingError",
    "PDFExtractionError",
    "ImageExtractionError",
    "AIProcessingError",
    "DDRGenerationError",
    "ReportGenerationError",
    "ConfigurationError",
    "handle_error",
]


# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Utilities CLI")
    parser.add_argument("--env", type=str, help="Environment file path")
    parser.add_argument("--validate", type=str, help="Validate a file path")
    parser.add_argument("--checksum", type=str, help="Generate checksum for a file")
    parser.add_argument("--cleanup", action="store_true", help="Run cleanup")
    
    args = parser.parse_args()
    
    if args.env:
        initialize_utils(Path(args.env))
        print(f"Initialized with env file: {args.env}")
    
    if args.validate:
        path = Path(args.validate)
        is_valid, error = validate_pdf_file(path)
        print(f"File: {path}")
        print(f"Valid: {is_valid}")
        if error:
            print(f"Error: {error}")
    
    if args.checksum:
        path = Path(args.checksum)
        checksum = file_checksum(path)
        print(f"Checksum: {checksum}")
    
    if args.cleanup:
        import asyncio
        
        async def run_cleanup():
            cleaned = await cleanup_temp_files()
            cleaned_reports = await cleanup_old_reports()
            cleaned_images = await cleanup_old_images()
            print(f"Cleaned: {cleaned} temp, {cleaned_reports} reports, {cleaned_images} images")
        
        asyncio.run(run_cleanup())