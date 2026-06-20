"""
pdf_extractor.py
================
Enterprise-grade PDF document intelligence module.

Transforms raw PDF files into structured, LLM-ready content through a
layered pipeline:

    Validation -> Loading -> Metadata -> Text -> Cleaning -> Structure -> Statistics

Design goals
------------
- Never raises an undocumented exception: every failure mode maps to a
  typed exception in this module's hierarchy.
- Never holds more than one page's worth of raw content in memory at a time
  during extraction (streaming-friendly), while still supporting the
  simple "give me the whole text" use case.
- Fully unit-testable: every layer is a plain class/function operating on
  already-open `fitz.Document` objects or plain strings, with no implicit
  I/O. Only the outermost orchestration touches the filesystem.
- Backward compatible: `extract_text()`, `extract_metadata()`, and
  `get_page_count()` keep their original signatures and return types so
  `main.py` does not need to change its calling code. New, richer
  functionality is exposed via `extract_document()`.

Author: Refactored for production deployment.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import fitz  # PyMuPDF

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Logging
# ============================================================================
# Structured logger. The host application (main.py) configures handlers /
# formatters; this module just emits records with consistent `extra` fields
# so they can be shipped to JSON logs / observability backends without
# string-parsing.

logger = logging.getLogger("document_intelligence.pdf_extractor")


# ============================================================================
# Exception hierarchy
# ============================================================================
# Every failure mode in this module raises one of these. Callers (e.g.
# main.py) can catch `PDFExtractionError` for a blanket handler, or catch
# specific subclasses to return precise HTTP status codes.

class PDFExtractionError(Exception):
    """Base class for all errors raised by this module."""
    pass


class PDFNotFoundError(PDFExtractionError):
    """The given path does not exist on disk."""
    pass


class PDFEmptyFileError(PDFExtractionError):
    """The file exists but contains zero bytes."""
    pass


class PDFTooLargeError(PDFExtractionError):
    """The file exceeds the configured maximum size."""
    pass


class PDFCorruptedError(PDFExtractionError):
    """The file could not be parsed as a valid PDF (corrupted / malformed)."""
    pass


class PDFPasswordProtectedError(PDFExtractionError):
    """The PDF requires a password and cannot be opened without one."""
    pass


class PDFNoPagesError(PDFExtractionError):
    """The PDF opened successfully but contains zero pages."""
    pass


class PDFPageLimitExceededError(PDFExtractionError):
    """The PDF exceeds the configured maximum page count (anti-abuse)."""
    pass


class PDFNoExtractableTextError(PDFExtractionError):
    """
    The PDF opened and has pages, but no text could be extracted from any
    of them. This is the expected outcome for image-only / scanned PDFs
    that have not been OCR'd. Callers should treat this distinctly from a
    corrupted file -- it is a valid signal that OCR is needed, not a bug.
    """
    pass


# ============================================================================
# Configuration (dependency-injection point)
# ============================================================================

@dataclass(frozen=True)
class ExtractionConfig:
    """
    Tunable limits and behavior for extraction. Pass a custom instance to
    any entry point to override defaults -- this is the seam that makes
    the module configurable without env vars or globals, and makes tests
    able to use tiny limits instead of production ones.
    """

    max_file_size_bytes: int = 20 * 1024 * 1024       # 20 MB, matches main.py
    max_pages: int = 500                                # anti-abuse ceiling
    max_page_text_chars: int = 200_000                  # guards against malicious single-page text bombs
    min_chars_for_valid_extraction: int = 1             # threshold to consider a page "has text"
    heading_max_words: int = 12                          # heuristic: headings are short
    table_min_columns: int = 2                            # heuristic: table rows need >=2 cells
    table_min_rows: int = 2                                # heuristic: tables need >=2 rows
    preserve_page_markers: bool = True                      # keep "--- Page N ---" in full_text for traceability


DEFAULT_CONFIG = ExtractionConfig()


# ============================================================================
# Structured data contracts (Pydantic models)
# ============================================================================
# These are the shapes every downstream consumer (ai_processor.py,
# pdf_report_generator.py) can rely on. Using Pydantic means malformed data
# fails fast, at the boundary, with a clear validation error -- not three
# function calls later as an obscure KeyError.

class DocumentMetadata(BaseModel):
    """PDF document metadata, defensively defaulted -- PDFs routinely omit most of this."""

    page_count: int = 0
    title: Optional[str] = None
    author: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    is_encrypted: bool = False
    file_size_bytes: int = 0
    file_hash_sha256: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "page_count": 10,
                "title": "Inspection Report",
                "author": "John Doe",
                "creator": "Microsoft Word",
                "producer": "PDF Converter",
                "subject": "Property Inspection",
                "keywords": "inspection, property, structural",
                "creation_date": "2024-01-01 12:00:00",
                "modification_date": "2024-01-02 14:30:00",
                "is_encrypted": False,
                "file_size_bytes": 1024000,
                "file_hash_sha256": "abc123def456..."
            }
        }
    }


class ListItem(BaseModel):
    text: str
    marker: Optional[str] = None  # "-", "1.", "a)", etc., if detected


class TableBlock(BaseModel):
    """Best-effort table detection. Confidence reflects heuristic certainty, not ground truth."""

    rows: List[List[str]] = Field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    confidence: float = 0.0

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    model_config = {
        "json_schema_extra": {
            "example": {
                "rows": [["Header 1", "Header 2"], ["Data 1", "Data 2"]],
                "row_count": 2,
                "column_count": 2,
                "confidence": 0.85
            }
        }
    }


class ContentBlock(BaseModel):
    """
    A single classified unit of content on a page: a heading, paragraph,
    list, or table. This is the primary structure-preservation unit that
    feeds into both `sections` and the LLM-oriented `full_text`.
    """

    block_type: str  # "heading" | "paragraph" | "list" | "table"
    text: str
    page_number: int
    heading_level: Optional[int] = None      # 1 = top-level, 2 = sub, etc. (heuristic)
    list_items: List[ListItem] = Field(default_factory=list)
    table: Optional[TableBlock] = None


class PageContent(BaseModel):
    """Extracted content for a single page."""

    page_number: int
    raw_text: str = ""
    cleaned_text: str = ""
    char_count: int = 0
    blocks: List[ContentBlock] = Field(default_factory=list)
    has_text: bool = False
    extraction_error: Optional[str] = None  # set if this *specific page* failed; doesn't abort the doc


class Section(BaseModel):
    """
    A logical section of the document, anchored by a detected heading and
    spanning until the next heading of equal-or-higher level. This is what
    preserves "report hierarchy" for the LLM -- sections, not raw pages,
    are the semantically meaningful unit of an inspection/thermal report.
    """

    title: str
    level: int
    start_page: int
    end_page: int
    content_blocks: List[ContentBlock] = Field(default_factory=list)
    text: str = ""


class ExtractionStatistics(BaseModel):
    """Observability metrics for a single extraction run."""

    total_pages: int = 0
    pages_with_text: int = 0
    pages_without_text: int = 0
    pages_failed: int = 0
    total_chars_extracted: int = 0
    headings_detected: int = 0
    lists_detected: int = 0
    tables_detected: int = 0
    sections_detected: int = 0
    extraction_time_seconds: float = 0.0
    extraction_success_rate: float = 0.0  # pages_with_text / total_pages
    likely_scanned_document: bool = False  # heuristic flag: low text density vs page count


class DocumentQuality(BaseModel):
    """A rough, explainable quality/confidence score for the extraction as a whole."""

    score: float = 0.0  # 0.0 - 1.0
    reasons: List[str] = Field(default_factory=list)

    @field_validator('score')
    @classmethod
    def validate_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    model_config = {
        "json_schema_extra": {
            "example": {
                "score": 0.85,
                "reasons": [
                    "High text yield across all pages",
                    "Well-structured document with clear headings",
                    "No extraction errors detected"
                ]
            }
        }
    }


class ExtractedDocument(BaseModel):
    """
    The full structured output of the pipeline. This is the contract that
    should eventually flow into ai_processor.py instead of a flat string,
    once that module is ready to consume structure. `full_text` is still
    provided so existing callers keep working unchanged.
    """

    metadata: DocumentMetadata
    pages: List[PageContent] = Field(default_factory=list)
    sections: List[Section] = Field(default_factory=list)
    full_text: str = ""
    statistics: ExtractionStatistics = Field(default_factory=ExtractionStatistics)
    quality: DocumentQuality = Field(default_factory=DocumentQuality)

    @field_validator("full_text")
    @classmethod
    def validate_full_text(cls, v: str) -> str:
        return v or ""


# ============================================================================
# Layer 1: Validation
# ============================================================================

class PDFValidator:
    """
    Validates a PDF file *before* any parser ever touches it. This is the
    security boundary: extension/MIME/size checks happen here, so a hostile
    or malformed file is rejected with a clear, typed error before fitz
    spends any CPU cycles on it.
    """

    PDF_MAGIC_BYTES = b"%PDF-"

    def __init__(self, config: ExtractionConfig = DEFAULT_CONFIG):
        self.config = config

    def validate_path(self, pdf_path: str) -> Path:
        """
        Run all pre-flight checks on a file path. Returns the resolved
        Path on success; raises a typed PDFExtractionError subclass on
        any failure.
        """
        path = Path(pdf_path)

        if not path.exists():
            raise PDFNotFoundError(f"PDF file not found: {pdf_path}")

        if not path.is_file():
            raise PDFNotFoundError(f"Path is not a regular file: {pdf_path}")

        file_size = path.stat().st_size

        if file_size == 0:
            raise PDFEmptyFileError(f"PDF file is empty: {pdf_path}")

        if file_size > self.config.max_file_size_bytes:
            limit_mb = self.config.max_file_size_bytes // (1024 * 1024)
            raise PDFTooLargeError(
                f"File size ({file_size} bytes) exceeds {limit_mb}MB limit: {pdf_path}"
            )

        if path.suffix.lower() != ".pdf":
            raise PDFCorruptedError(f"File does not have a .pdf extension: {pdf_path}")

        self._validate_magic_bytes(path)

        return path

    def _validate_magic_bytes(self, path: Path) -> None:
        """
        MIME-style sniffing: a real PDF starts with `%PDF-` in its first
        few bytes. Extension checks alone are trivially spoofed (rename
        malware.exe to malware.pdf); this catches that class of attack
        without needing a heavyweight `python-magic` dependency.
        """
        try:
            with path.open("rb") as f:
                header = f.read(1024)
        except OSError as e:
            raise PDFCorruptedError(f"Unable to read file header: {e}") from e

        if self.PDF_MAGIC_BYTES not in header[:1024]:
            raise PDFCorruptedError(
                f"File does not appear to be a valid PDF (missing %PDF- header): {path}"
            )

    @staticmethod
    def compute_sha256(path: Path) -> str:
        """Streamed hash computation -- never loads the whole file into memory."""
        sha256 = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# ============================================================================
# Layer 2: Safe document loading (resource lifecycle)
# ============================================================================

@contextmanager
def open_pdf_document(path: Path, config: ExtractionConfig = DEFAULT_CONFIG) -> Iterator[fitz.Document]:
    """
    Context manager that owns the entire lifecycle of a fitz.Document:
    opening, translating library-specific exceptions into our typed
    hierarchy, enforcing the page-count ceiling, and guaranteeing the
    document is closed even if the caller raises mid-iteration.

    This is the single choke point all other layers go through to get a
    `fitz.Document` -- no other function in this module calls `fitz.open`
    directly, which is what makes resource leaks structurally impossible
    rather than just "unlikely if everyone remembers try/finally."
    """
    document: Optional[fitz.Document] = None
    try:
        try:
            document = fitz.open(str(path))
        except Exception as e:
            # PyMuPDF's exception types have changed across versions
            # (FileDataError, RuntimeError, mupdf.FzErrorBase...). We
            # don't trust any single type to be stable, so we catch
            # broadly here -- at the *open* boundary only -- and
            # translate everything into our own corrupted-file error.
            raise PDFCorruptedError(f"Unable to open PDF (corrupted or invalid): {e}") from e

        if document.is_encrypted and not document.is_repaired:
            # is_encrypted is True even for documents we *can* open with
            # an empty password; needs_pass tells us if it's truly locked.
            if document.needs_pass:
                raise PDFPasswordProtectedError(
                    f"PDF is password-protected and cannot be opened: {path}"
                )

        if document.page_count == 0:
            raise PDFNoPagesError(f"PDF has no pages: {path}")

        if document.page_count > config.max_pages:
            raise PDFPageLimitExceededError(
                f"PDF has {document.page_count} pages, exceeding the "
                f"{config.max_pages}-page limit for this operation: {path}"
            )

        yield document

    finally:
        if document is not None:
            try:
                document.close()
            except Exception:
                # Closing should never be allowed to mask the real error,
                # and a failure to close is not actionable by the caller.
                logger.warning("pdf.close_failed", extra={"path": str(path)})


# ============================================================================
# Layer 3: Metadata extraction
# ============================================================================

class MetadataExtractor:
    """Extracts and normalizes document-level metadata."""

    _PDF_DATE_RE = re.compile(r"^D?:?(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})")

    def extract(self, document: fitz.Document, *, file_size_bytes: int = 0,
                file_hash: Optional[str] = None) -> DocumentMetadata:
        try:
            raw = document.metadata or {}
        except Exception as e:
            # Metadata is never worth failing the whole extraction over.
            logger.warning("metadata.read_failed", extra={"error": str(e)})
            raw = {}

        return DocumentMetadata(
            page_count=document.page_count,
            title=self._clean_field(raw.get("title")),
            author=self._clean_field(raw.get("author")),
            creator=self._clean_field(raw.get("creator")),
            producer=self._clean_field(raw.get("producer")),
            subject=self._clean_field(raw.get("subject")),
            keywords=self._clean_field(raw.get("keywords")),
            creation_date=self._parse_pdf_date(raw.get("creationDate")),
            modification_date=self._parse_pdf_date(raw.get("modDate")),
            is_encrypted=bool(document.is_encrypted),
            file_size_bytes=file_size_bytes,
            file_hash_sha256=file_hash,
        )

    @staticmethod
    def _clean_field(value: Optional[str]) -> Optional[str]:
        if not value or not value.strip():
            return None
        return value.strip()

    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse PDF date format (D:YYYYMMDDHHmmSSOHH'mm') into ISO-ish
        'YYYY-MM-DD HH:MM:SS'. Unlike the original implementation, this
        validates the numeric ranges so a malformed date (e.g. month=13,
        common in buggy scanner firmware) is rejected explicitly rather
        than silently producing an invalid-but-plausible-looking string.
        Returns None on any failure -- a missing date is far less harmful
        downstream than a wrong one.
        """
        if not date_str:
            return None

        match = self._PDF_DATE_RE.match(date_str.strip())
        if not match:
            return None

        year, month, day, hour, minute, second = (int(g) for g in match.groups())

        if not (1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23
                and 0 <= minute <= 59 and 0 <= second <= 59 and 1900 <= year <= 2200):
            logger.debug("metadata.date_out_of_range", extra={"raw": date_str})
            return None

        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


# ============================================================================
# Layer 4: Text extraction (per-page, streaming-friendly)
# ============================================================================

class TextExtractor:
    """
    Extracts raw text page-by-page. Designed to be called in a loop by the
    orchestrator rather than all at once, so a 200-page document never
    requires holding more than one page object in memory simultaneously
    (PyMuPDF page objects hold native resources; we extract and discard
    immediately).
    """

    def __init__(self, config: ExtractionConfig = DEFAULT_CONFIG):
        self.config = config

    def extract_page(self, document: fitz.Document, page_number: int) -> PageContent:
        """
        Extract text for a single page (1-indexed for the caller, even
        though PyMuPDF is 0-indexed internally). Never raises: a failure
        on one page is recorded on the PageContent itself so one bad page
        in a 200-page report doesn't abort the whole extraction.
        """
        index = page_number - 1
        try:
            page = document[index]
            text = page.get_text() or ""

            if len(text) > self.config.max_page_text_chars:
                # Defensive cap: guards against pathological pages (e.g. a
                # deliberately crafted PDF with a single page containing
                # megabytes of repeated text -- a denial-of-service vector
                # for downstream LLM token limits and our own memory).
                logger.warning(
                    "page.text_truncated",
                    extra={"page": page_number, "original_chars": len(text)},
                )
                text = text[: self.config.max_page_text_chars]

            return PageContent(
                page_number=page_number,
                raw_text=text,
                char_count=len(text),
                has_text=bool(text.strip()),
            )

        except Exception as e:
            logger.error("page.extraction_failed", extra={"page": page_number, "error": str(e)})
            return PageContent(
                page_number=page_number,
                raw_text="",
                char_count=0,
                has_text=False,
                extraction_error=str(e),
            )

    def extract_all_pages(self, document: fitz.Document) -> Iterator[PageContent]:
        """Generator form -- the preferred entry point for large documents."""
        for page_number in range(1, document.page_count + 1):
            yield self.extract_page(document, page_number)


# ============================================================================
# Layer 5: Content cleaning (structure-preserving)
# ============================================================================

class ContentCleaner:
    """
    Normalizes whitespace and strips genuinely noisy artifacts (form-feed
    characters, repeated header/footer lines, stray control characters)
    WITHOUT collapsing the blank-line paragraph boundaries that the
    structure analyzer depends on. This is the key correction versus the
    original `_clean_text`: that implementation joined every non-empty
    line with a single '\\n', which destroys the very paragraph breaks
    needed to detect headings, lists, and tables.
    """

    _CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
    _MULTI_SPACE_RE = re.compile(r"[ \t]+")
    _MULTI_BLANK_LINES_RE = re.compile(r"\n{3,}")

    def clean(self, raw_text: str) -> str:
        if not raw_text:
            return ""

        text = self._CONTROL_CHARS_RE.sub("", raw_text)
        text = self._MULTI_SPACE_RE.sub(" ", text)

        # Normalize each line's edge whitespace, but PRESERVE blank lines
        # as paragraph separators rather than discarding them.
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines)

        # Collapse 3+ consecutive blank lines down to exactly one blank
        # line (a clean paragraph break), rather than zero.
        text = self._MULTI_BLANK_LINES_RE.sub("\n\n", text)

        return text.strip()


# ============================================================================
# Layer 6: Document intelligence / structure analysis
# ============================================================================

class StructureAnalyzer:
    """
    Best-effort structural analysis on cleaned page text: headings, lists,
    tables, and paragraphs, plus section grouping across page boundaries.

    Important honesty note (and this should be communicated to users of
    this module): without access to font-size/weight metadata -- which
    requires using `page.get_text("dict")` instead of `page.get_text()`
    -- heading detection from plain text is necessarily heuristic
    (short lines, title case, numbered prefixes, ALL CAPS, trailing
    colons). It will not be perfect on every report template. The
    heuristics below are deliberately conservative to minimize false
    positives, since a missed heading degrades gracefully (it just
    becomes a paragraph) while a false-positive heading fragments
    legitimate paragraphs.
    """

    _NUMBERED_HEADING_RE = re.compile(r"^(\d+(\.\d+)*)[\.\)]?\s+\S")
    _LIST_MARKER_RE = re.compile(r"^([-*\u2022\u25cf\u25aa])\s+\S")
    _NUMBERED_LIST_RE = re.compile(r"^(\d+[\.\)]|\([a-zA-Z0-9]+\)|[a-zA-Z][\.\)])\s+\S")
    _ALL_CAPS_RE = re.compile(r"^[A-Z0-9 \-:/&,\.]{3,}$")

    def __init__(self, config: ExtractionConfig = DEFAULT_CONFIG):
        self.config = config

    def analyze_page(self, page_text: str, page_number: int) -> List[ContentBlock]:
        """Split a page's cleaned text into classified content blocks."""
        if not page_text.strip():
            return []

        paragraphs = [p for p in page_text.split("\n\n") if p.strip()]
        blocks: List[ContentBlock] = []

        for para in paragraphs:
            block = self._classify_paragraph(para, page_number)
            if block:
                blocks.append(block)

        return blocks

    def _classify_paragraph(self, paragraph: str, page_number: int) -> Optional[ContentBlock]:
        lines = [l for l in paragraph.split("\n") if l.strip()]
        if not lines:
            return None

        # --- Table detection (best-effort) ---
        # Heuristic signal: multiple consecutive lines each containing
        # several whitespace-delimited "cells" separated by runs of
        # spaces (>=2) -- common in PDF-extracted tabular layouts where
        # real column delimiters are lost but visual spacing survives.
        table = self._try_detect_table(lines)
        if table:
            return ContentBlock(
                block_type="table",
                text=paragraph,
                page_number=page_number,
                table=table,
            )

        # --- List detection ---
        list_items = self._try_detect_list(lines)
        if list_items:
            return ContentBlock(
                block_type="list",
                text=paragraph,
                page_number=page_number,
                list_items=list_items,
            )

        # --- Heading detection (single short line, only) ---
        if len(lines) == 1 and self._looks_like_heading(lines[0]):
            level = 2 if self._NUMBERED_HEADING_RE.match(lines[0]) and "." in lines[0].split()[0] else 1
            return ContentBlock(
                block_type="heading",
                text=lines[0],
                page_number=page_number,
                heading_level=level,
            )

        # --- Default: paragraph ---
        return ContentBlock(block_type="paragraph", text=paragraph, page_number=page_number)

    def _looks_like_heading(self, line: str) -> bool:
        word_count = len(line.split())
        if word_count == 0 or word_count > self.config.heading_max_words:
            return False
        if line.endswith((".", ",", ";")):
            return False  # full sentences are not headings
        if self._NUMBERED_HEADING_RE.match(line):
            return True
        if self._ALL_CAPS_RE.match(line) and any(c.isalpha() for c in line):
            return True
        if line.endswith(":") and word_count <= self.config.heading_max_words:
            return True
        # Title Case heuristic: most words start with a capital letter
        words = [w for w in re.split(r"\s+", line) if w]
        if not words:
            return False
        capitalized = sum(1 for w in words if w[:1].isupper())
        if capitalized / len(words) >= 0.7:
            return True
        return False

    def _try_detect_list(self, lines: List[str]) -> List[ListItem]:
        items: List[ListItem] = []
        for line in lines:
            bullet_match = self._LIST_MARKER_RE.match(line)
            numbered_match = self._NUMBERED_LIST_RE.match(line)
            if bullet_match:
                marker = bullet_match.group(1)
                items.append(ListItem(text=line[bullet_match.end(1):].strip(), marker=marker))
            elif numbered_match:
                marker = numbered_match.group(1)
                items.append(ListItem(text=line[numbered_match.end(1):].strip(), marker=marker))
        # Require at least 2 matching lines to call it a list, to avoid
        # misclassifying a single sentence that happens to start with "1)".
        return items if len(items) >= 2 else []

    def _try_detect_table(self, lines: List[str]) -> Optional[TableBlock]:
        if len(lines) < self.config.table_min_rows:
            return None

        split_re = re.compile(r"\s{2,}|\t")
        rows: List[List[str]] = []
        for line in lines:
            cells = [c.strip() for c in split_re.split(line) if c.strip()]
            rows.append(cells)

        column_counts = [len(r) for r in rows]
        rows_with_enough_cols = sum(1 for c in column_counts if c >= self.config.table_min_columns)

        if rows_with_enough_cols < self.config.table_min_rows:
            return None

        # Confidence reflects consistency of column count across rows --
        # real tables tend to have a stable (or near-stable) column count.
        if not column_counts:
            return None
        most_common_count = max(set(column_counts), key=column_counts.count)
        consistency = sum(1 for c in column_counts if c == most_common_count) / len(column_counts)
        confidence = round(min(0.95, 0.4 + (consistency * 0.5)), 2)

        return TableBlock(
            rows=rows,
            row_count=len(rows),
            column_count=most_common_count,
            confidence=confidence,
        )

    def build_sections(self, pages: List[PageContent]) -> List[Section]:
        """
        Group content blocks across page boundaries into sections, anchored
        on detected headings. Content before the first heading is captured
        as an implicit "Document Start" section so nothing is silently
        dropped -- this matters because the opening summary/property
        details of an inspection report often appear before any heading.
        """
        sections: List[Section] = []
        current: Optional[Section] = None

        for page in pages:
            for block in page.blocks:
                if block.block_type == "heading":
                    if current:
                        current.end_page = page.page_number
                        current.text = "\n\n".join(b.text for b in current.content_blocks)
                        sections.append(current)
                    current = Section(
                        title=block.text,
                        level=block.heading_level or 1,
                        start_page=page.page_number,
                        end_page=page.page_number,
                        content_blocks=[block],
                    )
                else:
                    if current is None:
                        current = Section(
                            title="Document Start",
                            level=0,
                            start_page=page.page_number,
                            end_page=page.page_number,
                        )
                    current.content_blocks.append(block)
                    current.end_page = page.page_number

        if current:
            current.text = "\n\n".join(b.text for b in current.content_blocks)
            sections.append(current)

        return sections


# ============================================================================
# Layer 7: Statistics & quality scoring (observability)
# ============================================================================

class StatisticsCollector:
    """Derives processing metrics and a quality score from a completed extraction."""

    def __init__(self, config: ExtractionConfig = DEFAULT_CONFIG):
        self.config = config

    def compute(self, pages: List[PageContent], sections: List[Section],
                elapsed_seconds: float) -> ExtractionStatistics:
        total = len(pages)
        with_text = sum(1 for p in pages if p.has_text)
        failed = sum(1 for p in pages if p.extraction_error is not None)
        total_chars = sum(p.char_count for p in pages)
        headings = sum(1 for p in pages for b in p.blocks if b.block_type == "heading")
        lists_ = sum(1 for p in pages for b in p.blocks if b.block_type == "list")
        tables = sum(1 for p in pages for b in p.blocks if b.block_type == "table")

        success_rate = (with_text / total) if total else 0.0

        # Heuristic: if most pages have essentially no extractable text
        # despite the PDF having pages, it's very likely a scanned /
        # image-only document that needs OCR rather than text extraction.
        likely_scanned = total > 0 and success_rate < 0.2

        return ExtractionStatistics(
            total_pages=total,
            pages_with_text=with_text,
            pages_without_text=total - with_text,
            pages_failed=failed,
            total_chars_extracted=total_chars,
            headings_detected=headings,
            lists_detected=lists_,
            tables_detected=tables,
            sections_detected=len(sections),
            extraction_time_seconds=round(elapsed_seconds, 3),
            extraction_success_rate=round(success_rate, 3),
            likely_scanned_document=likely_scanned,
        )

    def score_quality(self, stats: ExtractionStatistics, metadata: DocumentMetadata) -> DocumentQuality:
        reasons: List[str] = []
        score = 1.0

        if stats.likely_scanned_document:
            score -= 0.5
            reasons.append("Low text yield relative to page count suggests a scanned/image-only document.")

        if stats.pages_failed > 0:
            penalty = min(0.3, 0.05 * stats.pages_failed)
            score -= penalty
            reasons.append(f"{stats.pages_failed} page(s) failed extraction.")

        if stats.total_pages > 0 and stats.extraction_success_rate < 0.5:
            score -= 0.2
            reasons.append("Fewer than half of pages yielded extractable text.")

        if stats.sections_detected == 0 and stats.total_pages > 1:
            score -= 0.1
            reasons.append("No section headings were detected across a multi-page document.")

        if not metadata.title and not metadata.author:
            reasons.append("Document metadata (title/author) is largely absent.")

        score = max(0.0, min(1.0, round(score, 2)))
        if not reasons:
            reasons.append("No quality issues detected.")

        return DocumentQuality(score=score, reasons=reasons)


# ============================================================================
# Layer 8: LLM-oriented text rendering
# ============================================================================

class LLMTextRenderer:
    """
    Renders the structured document back into a single text blob, but one
    that preserves semantic markup useful to an LLM: heading markers,
    section boundaries, list formatting, and table layout -- instead of
    flattening everything into undifferentiated prose. This directly
    serves the "AI-Oriented Processing" requirement: Gemini receives text
    that already signals "this is a heading," "this is a finding," "this
    is a table," via lightweight markdown-style conventions it already
    understands well from training data.
    """

    def __init__(self, config: ExtractionConfig = DEFAULT_CONFIG):
        self.config = config

    def render(self, pages: List[PageContent]) -> str:
        rendered_pages = []
        for page in pages:
            if not page.blocks:
                continue
            page_parts = [self._render_block(b) for b in page.blocks]
            page_body = "\n\n".join(page_parts)
            if self.config.preserve_page_markers:
                rendered_pages.append(f"[Page {page.page_number}]\n{page_body}")
            else:
                rendered_pages.append(page_body)
        return "\n\n".join(rendered_pages).strip()

    def _render_block(self, block: ContentBlock) -> str:
        if block.block_type == "heading":
            prefix = "#" * (block.heading_level or 1)
            return f"{prefix} {block.text}"
        if block.block_type == "list":
            return "\n".join(f"- {item.text}" for item in block.list_items)
        if block.block_type == "table":
            if not block.table:
                return block.text
            return "\n".join(" | ".join(row) for row in block.table.rows)
        return block.text


# ============================================================================
# Orchestration: the pipeline
# ============================================================================

class PDFExtractionPipeline:
    """
    Wires every layer together. This is the only class that knows the
    full sequence; every other class is independently testable in
    isolation (feed it a string, or a fitz.Document, and assert on the
    output -- no filesystem required).
    """

    def __init__(self, config: ExtractionConfig = DEFAULT_CONFIG):
        self.config = config
        self.validator = PDFValidator(config)
        self.metadata_extractor = MetadataExtractor()
        self.text_extractor = TextExtractor(config)
        self.cleaner = ContentCleaner()
        self.structure_analyzer = StructureAnalyzer(config)
        self.stats_collector = StatisticsCollector(config)
        self.llm_renderer = LLMTextRenderer(config)

    def run(self, pdf_path: str) -> ExtractedDocument:
        start_time = time.monotonic()
        path = self.validator.validate_path(pdf_path)
        file_size = path.stat().st_size

        logger.info("extraction.start", extra={"path": str(path), "file_size_bytes": file_size})

        with open_pdf_document(path, self.config) as document:
            file_hash = self.validator.compute_sha256(path)
            metadata = self.metadata_extractor.extract(
                document, file_size_bytes=file_size, file_hash=file_hash
            )

            pages: List[PageContent] = []
            for page_content in self.text_extractor.extract_all_pages(document):
                cleaned = self.cleaner.clean(page_content.raw_text)
                page_content.cleaned_text = cleaned
                page_content.blocks = self.structure_analyzer.analyze_page(
                    cleaned, page_content.page_number
                )
                pages.append(page_content)
                logger.debug(
                    "page.extracted",
                    extra={
                        "page": page_content.page_number,
                        "chars": page_content.char_count,
                        "has_text": page_content.has_text,
                    },
                )

        # Check if any pages have text
        if not any(p.has_text for p in pages):
            raise PDFNoExtractableTextError(
                f"No extractable text found in any of {len(pages)} page(s). "
                f"This document may be a scanned/image-only PDF requiring OCR: {pdf_path}"
            )

        sections = self.structure_analyzer.build_sections(pages)
        full_text = self._render_full_text(pages)

        elapsed = time.monotonic() - start_time
        stats = self.stats_collector.compute(pages, sections, elapsed)
        quality = self.stats_collector.score_quality(stats, metadata)

        logger.info(
            "extraction.finish",
            extra={
                "path": str(path),
                "pages": stats.total_pages,
                "success_rate": stats.extraction_success_rate,
                "elapsed_seconds": stats.extraction_time_seconds,
                "quality_score": quality.score,
            },
        )

        return ExtractedDocument(
            metadata=metadata,
            pages=pages,
            sections=sections,
            full_text=full_text,
            statistics=stats,
            quality=quality,
        )

    def _render_full_text(self, pages: List[PageContent]) -> str:
        return self.llm_renderer.render(pages)


# ============================================================================
# Public API
# ============================================================================
# These functions preserve the ORIGINAL module's public signatures and
# return types so existing callers (main.py, and anything importing this
# module today) continue to work without modification. They are thin
# wrappers over PDFExtractionPipeline.

def extract_text(pdf_path: str, config: ExtractionConfig = DEFAULT_CONFIG) -> str:
    """
    Extract clean, LLM-oriented text from all pages of a PDF.

    Backward-compatible with the original signature/return type (str).
    Internally this now runs the full structured pipeline and returns its
    rendered `full_text` -- so callers get richer (heading/list/table
    aware) text for free, with zero call-site changes required.

    Raises:
        PDFNotFoundError, PDFEmptyFileError, PDFTooLargeError,
        PDFCorruptedError, PDFPasswordProtectedError, PDFNoPagesError,
        PDFPageLimitExceededError, PDFNoExtractableTextError
    """
    pipeline = PDFExtractionPipeline(config)
    document = pipeline.run(pdf_path)
    return document.full_text


def extract_document(pdf_path: str, config: ExtractionConfig = DEFAULT_CONFIG) -> ExtractedDocument:
    """
    Run the full structured extraction pipeline and return the complete
    `ExtractedDocument` (metadata, pages, sections, full_text, statistics,
    quality). This is the new, richer entry point -- use this when you're
    ready to send structured content (not just a flat string) to
    ai_processor.py / Gemini.
    """
    pipeline = PDFExtractionPipeline(config)
    return pipeline.run(pdf_path)


def extract_metadata(pdf_path: str, config: ExtractionConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    """
    Extract metadata from a PDF file.

    Backward-compatible with the original signature/return type
    (Dict[str, Any]), now backed by validated DocumentMetadata internally.

    Raises:
        PDFNotFoundError, PDFEmptyFileError, PDFTooLargeError,
        PDFCorruptedError, PDFPasswordProtectedError, PDFNoPagesError,
        PDFPageLimitExceededError
    """
    validator = PDFValidator(config)
    path = validator.validate_path(pdf_path)
    file_size = path.stat().st_size

    with open_pdf_document(path, config) as document:
        file_hash = validator.compute_sha256(path)
        metadata = MetadataExtractor().extract(document, file_size_bytes=file_size, file_hash=file_hash)

    return metadata.model_dump()


def get_page_count(pdf_path: str, config: ExtractionConfig = DEFAULT_CONFIG) -> int:
    """
    Quick helper to get page count without full extraction.

    Backward-compatible with the original signature/return type (int).

    Raises:
        PDFNotFoundError, PDFEmptyFileError, PDFTooLargeError,
        PDFCorruptedError, PDFPasswordProtectedError, PDFNoPagesError,
        PDFPageLimitExceededError
    """
    validator = PDFValidator(config)
    path = validator.validate_path(pdf_path)
    with open_pdf_document(path, config) as document:
        return document.page_count


# ============================================================================
# Module exports
# ============================================================================
# These are the symbols that should be importable from this module.
# Everything else is internal implementation detail.

__all__ = [
    # Exceptions
    "PDFExtractionError",
    "PDFNotFoundError",
    "PDFEmptyFileError",
    "PDFTooLargeError",
    "PDFCorruptedError",
    "PDFPasswordProtectedError",
    "PDFNoPagesError",
    "PDFPageLimitExceededError",
    "PDFNoExtractableTextError",
    # Configuration
    "ExtractionConfig",
    "DEFAULT_CONFIG",
    # Data models
    "ExtractedDocument",
    "DocumentMetadata",
    "PageContent",
    "Section",
    "ContentBlock",
    "TableBlock",
    "ListItem",
    "ExtractionStatistics",
    "DocumentQuality",
    # Public API
    "extract_text",
    "extract_document",
    "extract_metadata",
    "get_page_count",
]


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="PDF Extraction Tool")
    parser.add_argument("pdf_path", type=str, help="Path to PDF file")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file")
    parser.add_argument("--text-only", action="store_true", help="Only extract text")
    parser.add_argument("--metadata-only", action="store_true", help="Only extract metadata")
    parser.add_argument("--pages", type=str, help="Page range (e.g., '1-5,10,15-20')")
    
    args = parser.parse_args()
    
    try:
        if args.metadata_only:
            metadata = extract_metadata(args.pdf_path)
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(metadata, f, indent=2)
            else:
                print(json.dumps(metadata, indent=2))
        elif args.text_only:
            text = extract_text(args.pdf_path)
            print(text[:500] + "..." if len(text) > 500 else text)
        else:
            doc = extract_document(args.pdf_path)
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(doc.model_dump(), f, indent=2, default=str)
            else:
                print(f"Document: {args.pdf_path}")
                print(f"Pages: {doc.metadata.page_count}")
                print(f"Sections: {len(doc.sections)}")
                print(f"Full text length: {len(doc.full_text)} characters")
                print(f"Quality Score: {doc.quality.score}")
                print(f"Quality Reasons: {doc.quality.reasons}")
                print(f"Statistics: {doc.statistics.model_dump()}")
    except PDFExtractionError as e:
        print(f"Error: {e}")
        exit(1)