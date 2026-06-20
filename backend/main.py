"""
AI DDR Report Generator — Production API
main.py

Drop-in replacement for your existing main.py.
Works with your current flat structure:
  ai_processor.py, pdf_extractor.py, image_extractor.py,
  pdf_report_generator.py — all unchanged.

What this adds over the original:
  - Pydantic settings with environment variable support
  - Lifespan events (startup/shutdown)
  - Structured JSON logging with request correlation IDs
  - Magic byte PDF validation (not just filename extension)
  - Async-safe file I/O via asyncio thread executor
  - Standardized success/error response envelope
  - Global exception handlers (no more scattered HTTPException raises)
  - Rate limiting (in-memory, swap for Redis at scale)
  - Request timing header (X-Process-Time)
  - Separated liveness vs readiness probes
  - Background cleanup of orphaned temp files
  - Path traversal protection on filenames
  - CORS with exact origins (glob patterns silently fail in FastAPI)
  - Development mode support with localhost binding and permissive CORS
  - Gemini AI integration for processing

LOCAL DEVELOPMENT SETUP:
  - Set environment variable: DDR_ENVIRONMENT=development
  - Backend runs on: http://127.0.0.1:8000
  - Frontend can be on any local URL (localhost, 127.0.0.1, Live Server, etc.)
  - CORS allows all origins in development mode

PRODUCTION SETUP:
  - Set environment variable: DDR_ENVIRONMENT=production
  - Backend runs on: 0.0.0.0:8000 (all interfaces)
  - Frontend must be one of the allowed origins
  - CORS is strict (only listed origins)
"""

from __future__ import annotations

import asyncio
import logging
import logging.config
import os
import re
import shutil
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, File, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================================
# SECTION 1 — Configuration
# All tuneable values live here. Override via environment variables.
# Prefix: DDR_   e.g.  DDR_MAX_FILE_SIZE_MB=50, DDR_ENVIRONMENT=development
# ============================================================================

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DDR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service
    version: str = "2.1.0"
    environment: str = "development"  # development | staging | production
    
    # Host binding — development uses localhost, production uses all interfaces
    @property
    def host(self) -> str:
        """Return appropriate host based on environment"""
        return "127.0.0.1" if self.environment == "development" else "0.0.0.0"
    
    port: int = 8000

    # Directories
    upload_dir: Path = Path("uploads")
    generated_dir: Path = Path("generated_reports")

    # File validation
    max_file_size_mb: int = 20
    allowed_extensions: List[str] = [".pdf"]
    pdf_magic_bytes: bytes = b"%PDF"

    # Rate limiting (per client IP, in-memory)
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60

    # CORS — Production origins (used when environment is not development)
    # UPDATED: Added new Amplify URL and custom domains
    cors_origins_production: List[str] = [
        # Local development
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        
        # Amplify URLs
        "https://main.dhotu9foixoyc.amplifyapp.com",
        "https://main.d1zhszkjzbupl5.amplifyapp.com",  # NEW Amplify URL
        
        # Custom domains
        "https://ddr.chennareddy.in",
        "https://chennareddy.in",
        "https://www.chennareddy.in",
        "https://api.chennareddy.in",
    ]

    # Logging
    log_json: bool = False   # Set True in staging/production

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# ============================================================================
# SECTION 2 — Logging
# Structured output. In development: human-readable. In prod: JSON lines.
# ============================================================================

def configure_logging(settings: Settings) -> None:
    fmt = (
        '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
        '"request_id":"%(request_id)s","msg":%(message)s}'
        if settings.log_json
        else "%(asctime)s [%(levelname)s] %(name)s | req=%(request_id)s | %(message)s"
    )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {
                    "()": RequestIdFilter,
                }
            },
            "formatters": {
                "main": {"format": fmt, "datefmt": "%Y-%m-%dT%H:%M:%SZ"}
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "main",
                    "filters": ["request_id"],
                }
            },
            "root": {"handlers": ["console"], "level": "INFO"},
            "loggers": {
                "uvicorn": {"propagate": True},
                "uvicorn.access": {"propagate": False},  # handled by middleware
            },
        }
    )


class RequestIdFilter(logging.Filter):
    """Injects request_id into every log record."""
    _current_id: str = "-"

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self._current_id  # type: ignore[attr-defined]
        return True

    @classmethod
    def set(cls, request_id: str) -> None:
        cls._current_id = request_id

    @classmethod
    def clear(cls) -> None:
        cls._current_id = "-"


logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 3 — Custom Exceptions
# Domain exceptions — HTTP status is decided in handlers, not here.
# ============================================================================

class AppError(Exception):
    """Base for all application errors."""
    code: str = "APP_ERROR"
    default_message: str = "An application error occurred."

    def __init__(self, message: Optional[str] = None, details: Optional[List[str]] = None):
        self.message = message or self.default_message
        self.details: List[str] = details or []
        super().__init__(self.message)


class PDFValidationError(AppError):
    code = "PDF_VALIDATION_ERROR"
    default_message = "The uploaded PDF failed validation."

class FileSizeLimitError(PDFValidationError):
    code = "FILE_SIZE_LIMIT_EXCEEDED"

class InvalidFileTypeError(PDFValidationError):
    code = "INVALID_FILE_TYPE"

class MagicByteMismatchError(PDFValidationError):
    code = "MAGIC_BYTE_MISMATCH"
    default_message = "File content does not match a valid PDF signature."

class EmptyFileError(PDFValidationError):
    code = "EMPTY_FILE"
    default_message = "The uploaded file is empty."

class PDFExtractionError(AppError):
    code = "PDF_EXTRACTION_ERROR"
    default_message = "Failed to extract text from the PDF."

class EmptyExtractionError(PDFExtractionError):
    code = "EMPTY_EXTRACTION"
    default_message = "No extractable text found in the PDF."

class AIProcessingError(AppError):
    code = "AI_PROCESSING_ERROR"
    default_message = "AI analysis failed."

class DDRGenerationError(AppError):
    code = "DDR_GENERATION_ERROR"
    default_message = "Failed to structure the DDR from AI output."

class ReportGenerationError(AppError):
    code = "REPORT_GENERATION_ERROR"
    default_message = "Failed to generate the PDF report."

class StorageError(AppError):
    code = "STORAGE_ERROR"
    default_message = "A file storage operation failed."


# ============================================================================
# SECTION 4 — Pydantic Response Models
# Every response — success or error — uses the same envelope.
# ============================================================================

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: List[str] = []


class ErrorResponse(BaseModel):
    success: bool = False
    request_id: str
    timestamp: str
    error: ErrorDetail


class DDRAreaObservation(BaseModel):
    area: str = ""
    observation: str = ""
    severity: str = ""


class DDRData(BaseModel):
    property_summary: str = ""
    area_observations: List[DDRAreaObservation] = []
    root_cause: str = ""
    recommended_actions: List[str] = []
    additional_notes: str = ""
    missing_information: List[str] = []
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("confidence_score", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0


class GenerateDDRResponse(BaseModel):
    success: bool = True
    request_id: str
    timestamp: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]


# ============================================================================
# SECTION 5 — Rate Limiter (in-memory, IP-based)
# For production at scale: replace with Redis + sliding window algorithm.
# ============================================================================

class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            # Prune old entries
            self._store[key] = [t for t in self._store[key] if t > window_start]
            if len(self._store[key]) >= self.max_requests:
                return False
            self._store[key].append(now)
            return True


# ============================================================================
# SECTION 6 — File Handling Utilities
# All file I/O is run in a thread executor so we never block the event loop.
# ============================================================================

def _sanitize_filename(filename: str) -> str:
    """
    Strip path components and dangerous characters from a user-supplied filename.
    Prevents path traversal: '../../etc/passwd.pdf' → 'etc_passwd.pdf'
    """
    # Take only the final component
    name = Path(filename).name
    # Allow only alphanumerics, dots, dashes, underscores
    name = re.sub(r"[^\w.\-]", "_", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)
    return name or "upload.pdf"


async def _read_upload_bytes(file: UploadFile) -> bytes:
    """Read all bytes from an UploadFile asynchronously."""
    await file.seek(0)
    return await file.read()


async def _validate_pdf_upload(file: UploadFile, settings: Settings) -> bytes:
    """
    Full validation pipeline for an uploaded PDF.
    Returns the raw bytes (already read, so we don't read twice).

    Checks (in order):
      1. Extension
      2. Content-Length / actual size
      3. Non-empty
      4. Magic bytes (%PDF)
    """
    # 1. Extension check
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.allowed_extensions:
        raise InvalidFileTypeError(
            f"'{ext}' is not allowed. Accepted: {settings.allowed_extensions}"
        )

    # 2. Read bytes (we need them for magic byte check anyway)
    try:
        raw = await _read_upload_bytes(file)
    except Exception as exc:
        raise StorageError(f"Could not read uploaded file: {exc}")

    # 3. Empty check
    if not raw:
        raise EmptyFileError()

    # 4. Size check
    if len(raw) > settings.max_file_size_bytes:
        raise FileSizeLimitError(
            f"File size {len(raw) // (1024*1024)}MB exceeds "
            f"limit of {settings.max_file_size_mb}MB."
        )

    # 5. Magic bytes check — trusts content, not filename
    if not raw.startswith(settings.pdf_magic_bytes):
        raise MagicByteMismatchError()

    return raw


async def _save_bytes_to_file(raw: bytes, directory: Path, original_filename: str) -> Path:
    """Write raw bytes to a uniquely-named temp file inside directory."""
    safe_name = _sanitize_filename(original_filename)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    dest = directory / f"{timestamp}_{unique_id}_{safe_name}"

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, dest.write_bytes, raw)
    except OSError as exc:
        raise StorageError(f"Failed to save file: {exc}")

    return dest


def _delete_file(path: Optional[Path]) -> None:
    """Best-effort synchronous file deletion (used in background tasks)."""
    if path and path.exists():
        try:
            path.unlink()
        except Exception as exc:
            logger.warning('"Failed to delete temp file: %s"', exc)


# ============================================================================
# SECTION 7 — Pipeline Orchestration
# Each stage is isolated and timed. Failures carry the stage name.
# ============================================================================

async def _run_in_executor(fn, *args):
    """Run a blocking function in the default thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


async def run_ddr_pipeline(
    inspection_path: Path,
    thermal_path: Path,
    request_id: str,
) -> Dict[str, Any]:
    """
    Execute the full DDR processing pipeline.

    Stages:
      1. Text extraction   (inspection + thermal)
      2. Image extraction  (non-fatal degraded mode)
      3. AI analysis
      4. DDR structuring + validation

    Returns the validated DDR dict.
    """
    from pdf_extractor import extract_text
    from image_extractor import extract_images  # This is async
    from ai_processor import generate_ddr_json

    metrics: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # Stage 1 — Text Extraction                                           #
    # ------------------------------------------------------------------ #
    stage_start = time.perf_counter()
    try:
        inspection_text, thermal_text = await asyncio.gather(
            _run_in_executor(extract_text, str(inspection_path)),
            _run_in_executor(extract_text, str(thermal_path)),
        )
    except Exception as exc:
        raise PDFExtractionError(f"Text extraction failed: {exc}")

    metrics["text_extraction_ms"] = round((time.perf_counter() - stage_start) * 1000, 1)

    if not (inspection_text and inspection_text.strip()):
        raise EmptyExtractionError("Inspection report contains no extractable text.")
    if not (thermal_text and thermal_text.strip()):
        raise EmptyExtractionError("Thermal report contains no extractable text.")

    logger.info(
        '"text_extraction_complete"',
        extra={
            "inspection_chars": len(inspection_text),
            "thermal_chars": len(thermal_text),
        },
    )

    # ------------------------------------------------------------------ #
    # Stage 2 — Image Extraction (non-fatal)                             #
    # ------------------------------------------------------------------ #
    stage_start = time.perf_counter()
    inspection_images: list = []
    thermal_images: list = []
    images_extracted = True

    try:
        inspection_images, thermal_images = await asyncio.gather(
            extract_images(str(inspection_path)),
            extract_images(str(thermal_path)),
        )
    except Exception as exc:
        images_extracted = False
        logger.warning('"image_extraction_failed: %s — continuing without images"', exc)

    metrics["image_extraction_ms"] = round((time.perf_counter() - stage_start) * 1000, 1)
    logger.info(
        '"image_extraction_complete"',
        extra={
            "images_available": images_extracted,
            "inspection_images": len(inspection_images),
            "thermal_images": len(thermal_images),
        },
    )

    # ------------------------------------------------------------------ #
    # Stage 3 — AI Analysis                                               #
    # ------------------------------------------------------------------ #
    stage_start = time.perf_counter()
    try:
        raw_ddr = await _run_in_executor(
            generate_ddr_json,
            inspection_text,
            thermal_text,
            inspection_images,
            thermal_images,
        )
    except Exception as exc:
        raise AIProcessingError(f"AI model call failed: {exc}")

    metrics["ai_processing_ms"] = round((time.perf_counter() - stage_start) * 1000, 1)
    logger.info('"ai_analysis_complete"')

    # ------------------------------------------------------------------ #
    # Stage 4 — DDR Structuring + Validation                              #
    # ------------------------------------------------------------------ #
    stage_start = time.perf_counter()
    try:
        ddr = _structure_and_validate_ddr(raw_ddr)
    except Exception as exc:
        raise DDRGenerationError(f"DDR structuring failed: {exc}")

    metrics["ddr_structuring_ms"] = round((time.perf_counter() - stage_start) * 1000, 1)

    ddr["_pipeline_metrics"] = metrics

    # Stash extracted images so the PDF generation stage (Section 11) can
    # use them if/when generate_pdf's signature is extended to accept them.
    # Currently generate_pdf only accepts a single combined image list, so
    # the route handler passes [] — see Section 11, stage 7, for details.
    ddr["_inspection_images"] = inspection_images
    ddr["_thermal_images"] = thermal_images

    return ddr


def _structure_and_validate_ddr(raw: Any) -> Dict[str, Any]:
    """
    Validate AI output against the DDRData Pydantic model.

    Raises DDRGenerationError if the output is fundamentally unusable.
    Unlike the original _ensure_ddr_structure, this does NOT silently
    replace None confidence with 0.0 without flagging it.
    """
    if not isinstance(raw, dict):
        raise DDRGenerationError("AI returned non-dict output.")

    # Flag AI-returned nulls instead of silently overwriting them
    ai_returned_nulls = [k for k, v in raw.items() if v is None]
    if ai_returned_nulls:
        logger.warning('"ai_returned_null_fields: %s"', ai_returned_nulls)

    # Coerce through Pydantic — fills defaults for missing/None fields
    model = DDRData(
        property_summary=raw.get("property_summary") or "",
        area_observations=raw.get("area_observations") or [],
        root_cause=raw.get("root_cause") or "",
        recommended_actions=raw.get("recommended_actions") or [],
        additional_notes=raw.get("additional_notes") or "",
        missing_information=raw.get("missing_information") or [],
        confidence_score=raw.get("confidence_score") or 0.0,
    )

    result = model.model_dump()
    if ai_returned_nulls:
        result["_warnings"] = [f"AI returned null for: {', '.join(ai_returned_nulls)}"]

    return result


# ============================================================================
# SECTION 8 — Lifespan (startup / shutdown)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    logger.info('"service_starting env=%s version=%s host=%s port=%s"', 
                settings.environment, settings.version, settings.host, settings.port)

    # Create working directories with restricted permissions
    for d in (settings.upload_dir, settings.generated_dir):
        d.mkdir(parents=True, exist_ok=True)
        d.chmod(0o700)

    logger.info('"directories_ready"')
    
    if settings.is_development:
        logger.info('"DEVELOPMENT MODE: CORS allows all origins, docs enabled at /docs"')
    else:
        logger.info('"PRODUCTION MODE: CORS restricted, docs disabled"')
    
    yield
    logger.info('"service_shutdown"')


# ============================================================================
# SECTION 9 — App factory
# ============================================================================

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AI DDR Report Generator",
        description="Generate Detailed Diagnostic Reports from Inspection and Thermal PDFs.",
        version=settings.version,
        # Disable docs in production — avoids leaking schema to the internet
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Rate limiter singleton (shared across all requests)
    app.state.rate_limiter = InMemoryRateLimiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    # ---- CORS Middleware - MUST be first ----
    # Development: allow all origins, Production: strict origins
    if settings.is_development:
        # Allow all origins in development for easy testing with any local setup
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-Process-Time"],
            max_age=3600,
        )
        logger.info('"cors_mode=development allow_all_origins=True"')
    else:
        # Production - strict origins only
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_production,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-Process-Time"],
            max_age=3600,
        )
        logger.info('"cors_mode=production origins=%s"', settings.cors_origins_production)

    # ---- Exception handlers ---- #
    _register_exception_handlers(app)

    # ---- Routes ---- #
    _register_routes(app)

    # ---- Static files for generated reports ---- #
    app.mount(
        "/reports",
        StaticFiles(directory=str(settings.generated_dir)),
        name="reports",
    )

    return app


# ============================================================================
# SECTION 10 — Exception Handlers
# ============================================================================

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_json(request: Request, status_code: int, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "request_id": _get_request_id(request),
            "timestamp": _now_iso(),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PDFValidationError)
    async def _(r: Request, e: PDFValidationError):
        return _error_json(r, status.HTTP_422_UNPROCESSABLE_ENTITY, e)

    @app.exception_handler(PDFExtractionError)
    async def _(r: Request, e: PDFExtractionError):
        return _error_json(r, status.HTTP_422_UNPROCESSABLE_ENTITY, e)

    @app.exception_handler(AIProcessingError)
    async def _(r: Request, e: AIProcessingError):
        return _error_json(r, status.HTTP_502_BAD_GATEWAY, e)

    @app.exception_handler(DDRGenerationError)
    async def _(r: Request, e: DDRGenerationError):
        return _error_json(r, status.HTTP_500_INTERNAL_SERVER_ERROR, e)

    @app.exception_handler(ReportGenerationError)
    async def _(r: Request, e: ReportGenerationError):
        return _error_json(r, status.HTTP_500_INTERNAL_SERVER_ERROR, e)

    @app.exception_handler(StorageError)
    async def _(r: Request, e: StorageError):
        return _error_json(r, status.HTTP_507_INSUFFICIENT_STORAGE, e)

    @app.exception_handler(AppError)
    async def _(r: Request, e: AppError):
        return _error_json(r, status.HTTP_500_INTERNAL_SERVER_ERROR, e)

    @app.exception_handler(Exception)
    async def _(r: Request, e: Exception):
        logger.exception('"unhandled_exception path=%s"', r.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "request_id": _get_request_id(r),
                "timestamp": _now_iso(),
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "details": [],
                },
            },
        )


# ============================================================================
# SECTION 11 — Routes
# Handlers are thin controllers: validate → delegate → respond.
# ============================================================================

def _register_routes(app: FastAPI) -> None:
    settings = get_settings()

    # ------------------------------------------------------------------ #
    # Middleware-style: inject request_id + timing on every request       #
    # ------------------------------------------------------------------ #
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        RequestIdFilter.set(request_id)

        start = time.perf_counter()
        logger.info('"request_start method=%s path=%s"', request.method, request.url.path)

        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration_ms}ms"
        logger.info(
            '"request_complete status=%s duration_ms=%s"',
            response.status_code,
            duration_ms,
        )
        RequestIdFilter.clear()
        return response

    # ------------------------------------------------------------------ #
    # Middleware-style: rate limiting (FIXED - properly handles responses) #
    # ------------------------------------------------------------------ #
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/ready"):
            return await call_next(request)

        client_ip = (request.client.host if request.client else "unknown")
        limiter: InMemoryRateLimiter = request.app.state.rate_limiter

        if not await limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "timestamp": _now_iso(),
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": (
                            f"Too many requests. Max {settings.rate_limit_requests} "
                            f"per {settings.rate_limit_window_seconds}s."
                        ),
                        "details": [],
                    },
                },
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )

        # Ensure we always return a response
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Error in rate_limit_middleware: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "timestamp": _now_iso(),
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An error occurred processing your request.",
                        "details": [str(e)],
                    },
                },
            )

    # ------------------------------------------------------------------ #
    # GET /health — liveness probe (always fast, no external deps)        #
    # ------------------------------------------------------------------ #
    @app.get("/health", tags=["Observability"])
    async def health_check(request: Request):
        """
        Liveness probe. Returns 200 if the process is alive.
        Does NOT check AI connectivity or disk space — those belong in /ready.
        """
        return {
            "success": True,
            "request_id": getattr(request.state, "request_id", "unknown"),
            "timestamp": _now_iso(),
            "data": {
                "status": "alive",
                "version": settings.version,
                "environment": settings.environment,
            },
            "metadata": {},
        }

    # ------------------------------------------------------------------ #
    # GET /ready — readiness probe (checks real dependencies)             #
    # ------------------------------------------------------------------ #
    @app.get("/ready", tags=["Observability"])
    async def readiness_check(request: Request):
        """
        Readiness probe. Checks that the service can actually handle requests:
          - Upload directory is writable
          - Generated reports directory is writable
          - AI API is reachable (Gemini or Hugging Face)
        A 503 here tells the load balancer to stop routing traffic here.
        """
        checks: Dict[str, bool] = {}

        # Check upload directory
        probe_file = settings.upload_dir / ".probe"
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, probe_file.write_bytes, b"ok"
            )
            probe_file.unlink(missing_ok=True)
            checks["upload_dir_writable"] = True
        except Exception:
            checks["upload_dir_writable"] = False

        # Check generated directory
        probe_file = settings.generated_dir / ".probe"
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, probe_file.write_bytes, b"ok"
            )
            probe_file.unlink(missing_ok=True)
            checks["generated_dir_writable"] = True
        except Exception:
            checks["generated_dir_writable"] = False

        # Check AI API connectivity (Gemini or Hugging Face)
        try:
            provider = os.getenv("AI_PROVIDER", "gemini")
            if provider.lower() in ["huggingface", "hf"]:
                # Check Hugging Face connectivity
                import httpx
                response = httpx.get(
                    "https://router.huggingface.co/health",
                    timeout=5.0
                )
                checks["ai_api_available"] = response.status_code == 200
            else:
                # Check Gemini connectivity
                import google.generativeai as genai
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                model = genai.GenerativeModel(os.getenv("DEFAULT_MODEL", "models/gemini-2.5-flash"))
                response = model.generate_content("test")
                checks["ai_api_available"] = True
        except Exception as e:
            logger.warning(f"AI API check failed: {e}")
            checks["ai_api_available"] = False

        all_ok = all(checks.values())
        return JSONResponse(
            status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": all_ok,
                "request_id": getattr(request.state, "request_id", "unknown"),
                "timestamp": _now_iso(),
                "data": {"status": "ready" if all_ok else "not_ready", "checks": checks},
                "metadata": {},
            },
        )

    # ------------------------------------------------------------------ #
    # POST /generate-ddr — main pipeline endpoint                         #
    # ------------------------------------------------------------------ #
    @app.post(
        "/generate-ddr",
        status_code=status.HTTP_200_OK,
        tags=["DDR"],
        summary="Generate a Detailed Diagnostic Report",
        response_description="DDR JSON and PDF download URL",
    )
    async def generate_ddr(
        request: Request,
        background_tasks: BackgroundTasks,
        inspection_report: UploadFile = File(
            ..., description="Inspection report PDF (max 20MB)"
        ),
        thermal_report: UploadFile = File(
            ..., description="Thermal report PDF (max 20MB)"
        ),
    ):
        """
        Full pipeline:
          Validate → Save → Extract Text → Extract Images
          → AI Analysis → Structure DDR → Generate PDF → Respond

        Files are deleted in a background task after the response is sent.
        """
        from pdf_report_generator import generate_pdf

        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        wall_start = time.perf_counter()

        inspection_path: Optional[Path] = None
        thermal_path: Optional[Path] = None
        report_path: Optional[Path] = None

        try:
            # ---------------------------------------------------------- #
            # Stage 1 — Validate both uploads                             #
            # ---------------------------------------------------------- #
            logger.info('"stage=validate"')
            inspection_bytes, thermal_bytes = await asyncio.gather(
                _validate_pdf_upload(inspection_report, settings),
                _validate_pdf_upload(thermal_report, settings),
            )

            # ---------------------------------------------------------- #
            # Stage 2 — Persist to temp storage                          #
            # ---------------------------------------------------------- #
            logger.info('"stage=save"')
            inspection_path, thermal_path = await asyncio.gather(
                _save_bytes_to_file(
                    inspection_bytes, settings.upload_dir, inspection_report.filename or "inspection.pdf"
                ),
                _save_bytes_to_file(
                    thermal_bytes, settings.upload_dir, thermal_report.filename or "thermal.pdf"
                ),
            )

            # ---------------------------------------------------------- #
            # Stage 3-6 — Pipeline (text, images, AI, structure)         #
            # ---------------------------------------------------------- #
            logger.info('"stage=pipeline"')
            ddr_data = await run_ddr_pipeline(inspection_path, thermal_path, request_id)
            pipeline_metrics = ddr_data.pop("_pipeline_metrics", {})
            warnings = ddr_data.pop("_warnings", [])

            # Extracted images are currently informational only — generate_pdf's
            # signature (ddr_data, extracted_images, output_dir) only accepts a
            # single combined image list, and the original report content didn't            # specify how inspection vs. thermal images should be merged for the
            # PDF layout. Popping them off here keeps ddr_data clean for the
            # Pydantic-validated response body. If you want images embedded in
            # the generated PDF, merge them into one list below (e.g.
            # inspection_images + thermal_images) and pass that as the second
            # positional argument to generate_pdf instead of [].
            inspection_images = ddr_data.pop("_inspection_images", [])
            thermal_images = ddr_data.pop("_thermal_images", [])

            # ---------------------------------------------------------- #
            # Stage 7 — PDF generation                                   #
            # ---------------------------------------------------------- #
            logger.info('"stage=pdf_generation"')
            pdf_start = time.perf_counter()
            try:
                report_path_str = await _run_in_executor(
                    generate_pdf,
                    ddr_data,
                    inspection_images + thermal_images,  # Combined images list
                    str(settings.generated_dir),
                )
                report_path = Path(report_path_str)
            except Exception as exc:
                raise ReportGenerationError(f"PDF generation failed: {exc}")

            pdf_ms = round((time.perf_counter() - pdf_start) * 1000, 1)
            pipeline_metrics["pdf_generation_ms"] = pdf_ms

            # ---------------------------------------------------------- #
            # Stage 8 — Assemble response                                 #
            # ---------------------------------------------------------- #
            total_ms = round((time.perf_counter() - wall_start) * 1000, 1)
            pipeline_metrics["total_ms"] = total_ms

            logger.info('"request_success total_ms=%s"', total_ms)

            # Schedule upload cleanup in background (after response is sent)
            background_tasks.add_task(_delete_file, inspection_path)
            background_tasks.add_task(_delete_file, thermal_path)

            # ========================================================== #
            # FIX: Return the DDR data at the top level for frontend     #
            # ========================================================== #
            
            # Ensure area_observations is properly formatted for frontend
            area_observations = ddr_data.get("area_observations", [])
            if isinstance(area_observations, list):
                # Convert any Observation objects to dicts if needed
                area_observations = [
                    obs.model_dump() if hasattr(obs, 'model_dump') else obs
                    for obs in area_observations
                ]
            else:
                area_observations = []

            # Ensure recommendations is properly formatted
            recommendations = ddr_data.get("recommendations", [])
            if isinstance(recommendations, list):
                recommendations = [
                    rec.model_dump() if hasattr(rec, 'model_dump') else rec
                    for rec in recommendations
                ]
            else:
                recommendations = []

            # Ensure conflicts is properly formatted
            conflicts = ddr_data.get("conflicts", [])
            if isinstance(conflicts, list):
                conflicts = [
                    conf.model_dump() if hasattr(conf, 'model_dump') else conf
                    for conf in conflicts
                ]
            else:
                conflicts = []

            # Build the complete response
            response_body: Dict[str, Any] = {
                "success": True,
                "request_id": request_id,
                "timestamp": _now_iso(),
                "report_id": f"DDR-{datetime.now().strftime('%Y-%m-%d')}",
                "generated_at": _now_iso(),
                
                # Core DDR data at top level (frontend expects these)
                "property_summary": ddr_data.get("property_summary", ""),
                "area_observations": area_observations,
                "observations": area_observations,  # Duplicate for compatibility
                "root_cause": ddr_data.get("root_cause", ""),
                "root_cause_analysis": ddr_data.get("root_cause_analysis", {
                    "primary_cause": ddr_data.get("root_cause", "Unable to determine root cause."),
                    "supporting_evidence": [],
                    "reasoning_chain": [],
                    "contributing_factors": [],
                    "confidence": 0.0
                }),
                "recommendations": recommendations,
                "recommended_actions": ddr_data.get("recommended_actions", []),
                "conflicts": conflicts,
                "severity_assessment": ddr_data.get("severity_assessment", {
                    "overall_severity": "info",
                    "average_score": 0.0,
                    "distribution": {}
                }),
                "missing_information": ddr_data.get("missing_information", []),
                "confidence_metrics": ddr_data.get("confidence_metrics", {
                    "overall_confidence": ddr_data.get("confidence_score", 0.0),
                    "evidence_quality": 0.0,
                    "data_completeness": 0.0,
                    "reasoning_confidence": 0.0,
                    "conflict_density": 0.0,
                    "observation_quality": 0.0
                }),
                "confidence_score": ddr_data.get("confidence_score", 0.0),
                "executive_summary": ddr_data.get("executive_summary", {
                    "key_findings": [],
                    "risk_overview": "No critical or high severity issues identified.",
                    "critical_observations": [],
                    "property_health_score": 100,
                    "overall_recommendations": [],
                    "major_concerns": [],
                    "quick_wins": [],
                    "long_term_strategies": []
                }),
                "processing_metadata": ddr_data.get("processing_metadata", {}),
                
                # PDF URL
                "pdf_url": f"/reports/{report_path.name}",
                "pdf_base64": None,  # Will be populated if needed
                "pages": "—",
                "processing_time": pipeline_metrics.get("total_ms", 0) / 1000,
                
                # Keep nested data for backward compatibility
                "data": {
                    "pdf_url": f"/reports/{report_path.name}",
                    "ddr": ddr_data,
                },
                "metadata": {
                    "pipeline_metrics": pipeline_metrics,
                    "warnings": warnings,
                    "images_used": len(inspection_images) + len(thermal_images) > 0,
                    "images_extracted": {
                        "inspection": len(inspection_images),
                        "thermal": len(thermal_images),
                        "total": len(inspection_images) + len(thermal_images),
                    },
                },
            }

            # Log the response structure for debugging
            logger.info('"response_keys: %s"', list(response_body.keys()))
            logger.info('"area_observations_count: %s"', len(response_body.get("area_observations", [])))
            logger.info('"recommendations_count: %s"', len(response_body.get("recommendations", [])))
            logger.info('"conflicts_count: %s"', len(response_body.get("conflicts", [])))
            
            return JSONResponse(status_code=status.HTTP_200_OK, content=response_body)

        except AppError:
            # Registered handlers will format these — just clean up and re-raise
            background_tasks.add_task(_delete_file, inspection_path)
            background_tasks.add_task(_delete_file, thermal_path)
            background_tasks.add_task(_delete_file, report_path)
            raise

        except Exception:
            background_tasks.add_task(_delete_file, inspection_path)
            background_tasks.add_task(_delete_file, thermal_path)
            background_tasks.add_task(_delete_file, report_path)
            raise


# ============================================================================
# SECTION 12 — Application instance + entry point
# ============================================================================

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    
    print("\n" + "="*70)
    print(f"🚀 AI DDR Report Generator v{settings.version}")
    print("="*70)
    print(f"Environment: {settings.environment.upper()}")
    print(f"Running on: http://{settings.host}:{settings.port}")
    print(f"Docs: http://{settings.host}:{settings.port}/docs" if settings.is_development else "Docs: Disabled")
    print(f"AI Provider: {os.getenv('AI_PROVIDER', 'gemini')}")
    print(f"Default Model: {os.getenv('DEFAULT_MODEL', 'models/gemini-2.5-flash')}")
    print("="*70 + "\n")
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        access_log=False,
        timeout_keep_alive=1200,
        timeout_graceful_shutdown=120,
    )