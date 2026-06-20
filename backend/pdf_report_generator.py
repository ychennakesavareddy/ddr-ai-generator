"""
Enterprise PDF Report Generation Engine
Professional diagnostic report generation with premium enterprise design system

FIXES APPLIED IN THIS VERSION:
1. Logo loading is now robust: sends a real User-Agent (many hosts/CDNs 403 on
   bare urllib requests), validates bytes with PIL, normalizes to RGB PNG in a
   stable temp file, and logs loudly on failure instead of silently skipping.
2. Header/footer/page-border are now actually wired into doc.build() via
   onFirstPage / onLaterPages -- they existed before but were never called.
3. Header is skipped on the cover page (page 1) so it doesn't draw a navy bar
   over the cover title; footer still renders on page 1.
4. Executive summary KPI table width fixed to fit A4 content area
   (6.77" usable, not 9").
5. Cover page spacers reduced so content is vertically centered instead of
   pushed down/overflowing.
6. Profile info on cover wrapped in a bordered "card" table.
7. Observation cards wrapped in a single-cell background/border table so they
   read as cards instead of a flat text dump.
8. CondPageBreak no longer applied uniformly after every section; explicit
   PageBreak is used at true section boundaries instead.
"""

import os
import logging
import time
import urllib.request
import tempfile
from pathlib import Path as FilePath
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
import math

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, HRFlowable, Flowable, CondPageBreak
)
from reportlab.lib.colors import HexColor
from reportlab.graphics.shapes import Drawing, String, Path as GraphicsPath
from reportlab.pdfgen import canvas

from PIL import Image as PILImage

from pydantic import BaseModel, Field

# ============================================================================
# DOMAIN MODELS
# ============================================================================

class SeverityLevel(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Information"


class ReportSection(str, Enum):
    COVER = "cover"
    EXECUTIVE_SUMMARY = "executive_summary"
    HEALTH_SCORE = "health_score"
    AREA_OBSERVATIONS = "area_observations"
    ROOT_CAUSE = "root_cause"
    SEVERITY = "severity"
    RECOMMENDATIONS = "recommendations"


class BrandingTheme(BaseModel):
    primary_color: str = "#0F172A"
    secondary_color: str = "#2563EB"
    accent_color: str = "#F8FAFC"
    text_color: str = "#1A202C"
    success_color: str = "#10B981"
    warning_color: str = "#F59E0B"
    danger_color: str = "#EF4444"
    font_family: str = "Helvetica"
    logo_path: Optional[str] = "https://chennareddy.in/logo.png"
    company_name: str = "Chenna Kesava Reddy"
    report_title: str = "Detailed Diagnostic Report"

    def get_primary_color(self) -> HexColor:
        return HexColor(self.primary_color)

    def get_secondary_color(self) -> HexColor:
        return HexColor(self.secondary_color)

    def get_accent_color(self) -> HexColor:
        return HexColor(self.accent_color)

    def get_text_color(self) -> HexColor:
        return HexColor(self.text_color)

    def get_success_color(self) -> HexColor:
        return HexColor(self.success_color)

    def get_warning_color(self) -> HexColor:
        return HexColor(self.warning_color)

    def get_danger_color(self) -> HexColor:
        return HexColor(self.danger_color)


class PageConfiguration(BaseModel):
    page_size: str = "A4"
    margin_left: float = 0.75
    margin_right: float = 0.75
    margin_top: float = 1.5
    margin_bottom: float = 0.75
    show_page_numbers: bool = True
    show_footer: bool = True


class ReportConfiguration(BaseModel):
    branding: BrandingTheme = Field(default_factory=BrandingTheme)
    page_config: PageConfiguration = Field(default_factory=PageConfiguration)
    sections: List[ReportSection] = Field(default_factory=lambda: [
        ReportSection.COVER,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.HEALTH_SCORE,
        ReportSection.AREA_OBSERVATIONS,
        ReportSection.ROOT_CAUSE,
        ReportSection.SEVERITY,
        ReportSection.RECOMMENDATIONS,
    ])
    include_images: bool = True
    include_conflicts: bool = True
    include_health_score: bool = True
    max_observations_per_page: int = 2
    max_images_per_observation: int = 3
    debug_mode: bool = False

    model_config = {"arbitrary_types_allowed": True}


# ============================================================================
# LOGO LOADING (FIXED) -- robust download + validation + caching
# ============================================================================

class LogoLoader:
    """
    Centralized, robust logo loader.

    Why this exists: the original code called urllib.request.urlopen() with no
    headers and swallowed every exception, so a 403 from a host/CDN that
    blocks header-less requests (very common) resulted in a *silent* missing
    logo with no error anywhere. This version:
      - sends a real User-Agent and Accept header
      - verifies the response is actually image bytes (via PIL.verify())
      - re-opens and normalizes to RGB, saves as a clean PNG in a stable temp file
      - caches the result for the lifetime of the process so we only fetch once
      - logs the real exception instead of hiding it
    """

    _cache: Dict[str, Optional[str]] = {}

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def load(self, logo_path: Optional[str]) -> Optional[str]:
        if not logo_path:
            return None

        if logo_path in self._cache:
            return self._cache[logo_path]

        result = self._load_uncached(logo_path)
        self._cache[logo_path] = result
        return result

    def _load_uncached(self, logo_path: str) -> Optional[str]:
        raw_bytes = None

        if logo_path.startswith(("http://", "https://")):
            raw_bytes = self._download(logo_path)
        elif os.path.exists(logo_path):
            try:
                with open(logo_path, "rb") as f:
                    raw_bytes = f.read()
            except Exception as e:
                self.logger.error(f"Logo: failed to read local file '{logo_path}': {e}")
                return None
        else:
            self.logger.error(f"Logo: path is not a URL and does not exist on disk: '{logo_path}'")
            return None

        if not raw_bytes:
            return None

        return self._validate_and_normalize(raw_bytes, logo_path)

    def _download(self, url: str) -> Optional[bytes]:
        try:
            request = urllib.request.Request(
                url,
                headers={
                    # Many hosts / CDNs / WAFs reject requests with no UA -> 403.
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    self.logger.error(f"Logo: unexpected HTTP status {status} for {url}")
                    return None
                data = response.read()
                self.logger.info(f"Logo: downloaded {len(data)} bytes from {url}")
                return data
        except urllib.error.HTTPError as e:
            self.logger.error(f"Logo: HTTP error {e.code} fetching {url}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            self.logger.error(f"Logo: URL error fetching {url}: {e.reason}")
            return None
        except Exception as e:
            self.logger.error(f"Logo: unexpected error fetching {url}: {e!r}")
            return None

    def _validate_and_normalize(self, raw_bytes: bytes, source: str) -> Optional[str]:
        """Confirm the bytes are a real image, then write a clean RGB PNG to disk."""
        import io

        try:
            # First pass: verify() checks integrity but invalidates the file object,
            # so we need to re-open for actual use afterwards.
            verify_buf = io.BytesIO(raw_bytes)
            with PILImage.open(verify_buf) as probe:
                probe.verify()
        except Exception as e:
            self.logger.error(
                f"Logo: downloaded data from '{source}' is not a valid/decodable "
                f"image ({len(raw_bytes)} bytes received): {e!r}"
            )
            return None

        try:
            load_buf = io.BytesIO(raw_bytes)
            with PILImage.open(load_buf) as img:
                img.load()
                # Normalize mode: PNGs with palette/alpha can confuse some
                # ReportLab drawing paths. Flatten onto white if there's
                # transparency, otherwise just convert to RGB.
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    rgba = img.convert("RGBA")
                    background = PILImage.new("RGB", rgba.size, (255, 255, 255))
                    background.paste(rgba, mask=rgba.split()[-1])
                    final_img = background
                else:
                    final_img = img.convert("RGB")

                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                final_img.save(tmp.name, format="PNG")
                tmp.close()
                self.logger.info(
                    f"Logo: normalized and cached at {tmp.name} "
                    f"({final_img.width}x{final_img.height})"
                )
                return tmp.name
        except Exception as e:
            self.logger.error(f"Logo: failed to normalize/save image from '{source}': {e!r}")
            return None


# Module-level singleton so the logo is fetched once per process, not once
# per renderer instantiation.
_logo_loader = LogoLoader()


# ============================================================================
# DESIGN SYSTEM
# ============================================================================

class DesignSystem:
    def __init__(self, theme: BrandingTheme):
        self.theme = theme
        self._initialize_styles()
        self._initialize_colors()

    def _initialize_colors(self):
        self.colors = {
            'primary': self.theme.get_primary_color(),
            'secondary': self.theme.get_secondary_color(),
            'accent': self.theme.get_accent_color(),
            'text': self.theme.get_text_color(),
            'success': self.theme.get_success_color(),
            'warning': self.theme.get_warning_color(),
            'danger': self.theme.get_danger_color(),
            'white': HexColor('#FFFFFF'),
            'light_grey': HexColor('#F1F5F9'),
            'medium_grey': HexColor('#94A3B8'),
            'dark_grey': HexColor('#475569'),
        }

    def _initialize_styles(self):
        styles = getSampleStyleSheet()

        self.cover_title = ParagraphStyle(
            'CoverTitle', parent=styles['Title'], fontSize=36,
            textColor=self.theme.get_primary_color(), alignment=TA_CENTER,
            fontName='Helvetica-Bold', spaceAfter=10, leading=42
        )
        self.cover_subtitle = ParagraphStyle(
            'CoverSubtitle', parent=styles['Normal'], fontSize=16,
            textColor=self.theme.get_secondary_color(), alignment=TA_CENTER,
            spaceAfter=16, leading=22
        )
        self.cover_meta = ParagraphStyle(
            'CoverMeta', parent=styles['Normal'], fontSize=11,
            textColor=HexColor('#64748B'), alignment=TA_CENTER,
            spaceAfter=4, leading=15
        )
        self.cover_meta_bold = ParagraphStyle(
            'CoverMetaBold', parent=self.cover_meta,
            textColor=self.theme.get_primary_color(), fontName='Helvetica-Bold',
            fontSize=14
        )
        self.cover_small = ParagraphStyle(
            'CoverSmall', parent=styles['Normal'], fontSize=9,
            textColor=HexColor('#94A3B8'), alignment=TA_CENTER,
            spaceAfter=3, leading=12
        )
        self.section_title = ParagraphStyle(
            'SectionTitle', parent=styles['Heading1'], fontSize=24,
            textColor=self.theme.get_primary_color(), alignment=TA_LEFT,
            spaceAfter=12, fontName='Helvetica-Bold', leading=30
        )
        self.section_subtitle = ParagraphStyle(
            'SectionSubtitle', parent=styles['Heading2'], fontSize=15,
            textColor=self.theme.get_secondary_color(), alignment=TA_LEFT,
            spaceAfter=8, fontName='Helvetica-Bold', leading=20
        )
        self.body_text = ParagraphStyle(
            'BodyText', parent=styles['Normal'], fontSize=10.5,
            textColor=self.theme.get_text_color(), alignment=TA_JUSTIFY,
            spaceAfter=6, leading=16, fontName='Helvetica'
        )
        self.body_bold = ParagraphStyle('BodyBold', parent=self.body_text, fontName='Helvetica-Bold')
        self.body_small = ParagraphStyle(
            'BodySmall', parent=self.body_text, fontSize=8.5, leading=12,
            textColor=HexColor('#64748B')
        )
        self.evidence = ParagraphStyle(
            'Evidence', parent=styles['Italic'], fontSize=9,
            textColor=HexColor('#64748B'), alignment=TA_LEFT,
            leftIndent=16, spaceAfter=4, leading=13
        )
        self.severity_critical = ParagraphStyle('SeverityCritical', parent=self.body_bold,
                                                  textColor=self.theme.get_danger_color(), fontSize=10)
        self.severity_high = ParagraphStyle('SeverityHigh', parent=self.body_bold,
                                             textColor=HexColor('#F97316'), fontSize=10)
        self.severity_medium = ParagraphStyle('SeverityMedium', parent=self.body_bold,
                                               textColor=self.theme.get_warning_color(), fontSize=10)
        self.severity_low = ParagraphStyle('SeverityLow', parent=self.body_bold,
                                            textColor=self.theme.get_success_color(), fontSize=10)

    def get_style(self, style_name: str) -> Optional[ParagraphStyle]:
        return getattr(self, style_name, None)


# ============================================================================
# HEADER / FOOTER / BORDER -- now actually invoked from PDFEngine.generate()
# ============================================================================

class EnterpriseHeaderFooter:
    def __init__(self, design: DesignSystem, config: ReportConfiguration, logger: logging.Logger):
        self.design = design
        self.config = config
        self.logger = logger

    def render_page_border(self, canvas_obj, doc):
        canvas_obj.saveState()
        page_width, page_height = A4
        canvas_obj.setStrokeColor(HexColor("#CBD5E1"))
        canvas_obj.setLineWidth(1)
        margin = 20
        canvas_obj.rect(margin, margin, page_width - 2 * margin, page_height - 2 * margin)
        canvas_obj.restoreState()

    def render_header(self, canvas_obj, doc):
        canvas_obj.saveState()
        page_width, page_height = A4
        header_height = 50

        canvas_obj.setFillColor(self.design.colors['primary'])
        canvas_obj.rect(0, page_height - header_height, page_width, header_height, stroke=0, fill=1)

        logo_local_path = _logo_loader.load(self.design.theme.logo_path)
        if logo_local_path:
            try:
                with PILImage.open(logo_local_path) as img:
                    logo_height = 30
                    logo_width = logo_height * img.width / img.height
                    if logo_width > 90:
                        logo_width = 90
                        logo_height = logo_width * img.height / img.width
                    canvas_obj.drawImage(
                        logo_local_path,
                        30,
                        page_height - header_height + (header_height - logo_height) / 2,
                        width=logo_width,
                        height=logo_height,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
            except Exception as e:
                self.logger.error(f"Header: failed to draw logo image: {e!r}")

        canvas_obj.setFillColor(HexColor('#FFFFFF'))
        canvas_obj.setFont('Helvetica-Bold', 10)
        canvas_obj.drawCentredString(page_width / 2, page_height - header_height + 20, "DETAILED DIAGNOSTIC REPORT")

        report_id = getattr(doc, 'report_id', 'DDR-2025-001')
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.drawRightString(page_width - 30, page_height - header_height + 20, f"ID: {report_id}")

        canvas_obj.setStrokeColor(HexColor('#E2E8F0'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(20, page_height - header_height, page_width - 20, page_height - header_height)

        canvas_obj.restoreState()

    def render_footer(self, canvas_obj, doc):
        canvas_obj.saveState()
        page_width, page_height = A4
        footer_height = 40

        canvas_obj.setStrokeColor(HexColor('#E2E8F0'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(20, footer_height + 10, page_width - 20, footer_height + 10)

        canvas_obj.setFillColor(HexColor('#94A3B8'))
        canvas_obj.setFont('Helvetica', 7.5)
        canvas_obj.drawString(30, footer_height - 5, "CONFIDENTIAL BUSINESS DOCUMENT")
        canvas_obj.drawRightString(page_width - 30, footer_height - 5, "https://chennareddy.in")

        canvas_obj.restoreState()


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self.pages)
        for page_num, page_data in enumerate(self.pages, 1):
            self.__dict__.update(page_data)
            self.setFont('Helvetica', 8)
            self.setFillColor(HexColor('#94A3B8'))
            page_width, page_height = A4
            self.drawCentredString(page_width / 2, 20, f"Page {page_num} of {total_pages}")
            super().showPage()
        super().save()


# ============================================================================
# COMPONENT RENDERERS
# ============================================================================

class ComponentRenderer:
    def __init__(self, design_system: DesignSystem):
        self.design = design_system
        self.logger = logging.getLogger(__name__)

    def render(self, data: Any, **kwargs) -> List[Flowable]:
        return []


class CoverPageRenderer(ComponentRenderer):
    """Cover page with logo printed directly via reportlab Image, centered card layout."""

    def render(self, data: Dict[str, Any], **kwargs) -> List[Flowable]:
        content = []

        observations = data.get("area_observations", [])
        confidence = data.get("confidence_score", 0)
        if not confidence and observations:
            confidence = self._calculate_health_score(observations) / 100

        # Reduced top spacer (was 1.5" + 0.5" + 0.8"*2 = ~3.6" before content
        # even started -- that's what was pushing things down / off-page).
        content.append(Spacer(1, 0.5 * inch))

        # --- LOGO: loaded via centralized LogoLoader, drawn directly on the PDF ---
        logo_local_path = _logo_loader.load(self.design.theme.logo_path)
        if logo_local_path:
            try:
                with PILImage.open(logo_local_path) as img:
                    orig_width, orig_height = img.size
                    max_width = 2.0 * inch
                    max_height = 1.0 * inch
                    scale = min(max_width / orig_width, max_height / orig_height)
                    display_width = orig_width * scale
                    display_height = orig_height * scale

                logo_flowable = Image(logo_local_path, width=display_width, height=display_height)
                logo_flowable.hAlign = 'CENTER'
                content.append(logo_flowable)
                content.append(Spacer(1, 14))
                self.logger.info(f"Cover: logo printed successfully from {logo_local_path}")
            except Exception as e:
                self.logger.error(f"Cover: logo file exists but failed to render as Flowable: {e!r}")
                content.append(Spacer(1, 14))
        else:
            self.logger.error(
                "Cover: no logo available -- LogoLoader returned None. "
                "Check earlier 'Logo:' log lines for the root cause (download/validation failure)."
            )

        content.append(Paragraph("DETAILED DIAGNOSTIC REPORT", self.design.cover_title))
        content.append(Spacer(1, 4))
        content.append(Paragraph("Professional Building Assessment", self.design.cover_subtitle))
        content.append(Spacer(1, 0.35 * inch))

        content.append(HRFlowable(width="30%", thickness=1.5, color=self.design.theme.get_secondary_color(), hAlign='CENTER'))
        content.append(Spacer(1, 0.35 * inch))

        # --- Profile card: bordered single-row table wrapping name/contact info ---
        contact_lines = [
            Paragraph(f"<b>{self.design.theme.company_name}</b>", self.design.cover_meta_bold),
            Spacer(1, 4),
            Paragraph("Building Intelligence Specialist", self.design.cover_meta),
            Spacer(1, 8),
            Paragraph("Email: chenna.dev@chennareddy.in", self.design.cover_small),
            Paragraph("Phone: +91 77028 50533", self.design.cover_small),
            Paragraph("Website: https://chennareddy.in", self.design.cover_small),
        ]

        profile_card = Table([[contact_lines]], colWidths=[3.6 * inch])
        profile_card.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, HexColor("#D1D5DB")),
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F8FAFC")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 16),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LEFTPADDING', (0, 0), (-1, -1), 16),
            ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ]))
        profile_card.hAlign = 'CENTER'
        content.append(profile_card)

        content.append(Spacer(1, 0.45 * inch))

        meta_data = [
            ["Report ID", data.get('report_id', 'DDR-2025-001')],
            ["Generated Date", datetime.now().strftime('%B %d, %Y')],
            ["Property", data.get('property_id', 'Not Specified')],
            ["Confidence Score", f"{confidence:.0%}"]
        ]
        meta_table = Table(meta_data, colWidths=[2.0 * inch, 2.4 * inch])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#64748B')),
            ('TEXTCOLOR', (1, 0), (1, -1), self.design.theme.get_primary_color()),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ]))
        meta_table.hAlign = 'CENTER'
        content.append(meta_table)

        content.append(Spacer(1, 0.5 * inch))
        content.append(Paragraph("CONFIDENTIAL BUSINESS DOCUMENT", self.design.cover_small))
        content.append(Paragraph("Generated by Advanced Building Intelligence Platform", self.design.cover_small))

        return content

    def _calculate_health_score(self, observations: List[Dict[str, Any]]) -> int:
        score = 100
        penalties = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
        for obs in observations:
            score -= penalties.get(obs.get('severity', ''), 0)
        return max(0, min(100, score))


class ExecutiveSummaryRenderer(ComponentRenderer):
    def render(self, data: Dict[str, Any], **kwargs) -> List[Flowable]:
        content = []
        content.append(Paragraph("Executive Summary", self.design.section_title))
        content.append(Spacer(1, 8))
        content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#E2E8F0')))
        content.append(Spacer(1, 16))

        metrics = self._extract_metrics(data)

        kpi_data = [
            ["Total Findings", str(metrics['total_issues']), "Critical", str(metrics['critical'])],
            ["High", str(metrics['high']), "Medium", str(metrics['medium'])],
            ["Low", str(metrics['low']), "AI Confidence", f"{metrics['confidence']:.0%}"],
            ["Areas Impacted", str(metrics['areas_affected']), "Risk Level", metrics['risk_level']]
        ]

        # FIXED: A4 content width with 0.75" margins each side = 6.77".
        # 4 columns of 2.25" = 9.0" overflowed. Use doc.width-derived value.
        col_w = self._kpi_col_width(kwargs.get('doc_width'))
        kpi_table = Table(kpi_data, colWidths=[col_w] * 4)
        kpi_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#E2E8F0')),
        ]))

        if metrics['critical'] > 0:
            kpi_table.setStyle(TableStyle([
                ('TEXTCOLOR', (2, 0), (2, 0), self.design.theme.get_danger_color()),
                ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
            ]))

        risk_colors = {
            "Critical": self.design.theme.get_danger_color(),
            "High": HexColor('#F97316'),
            "Medium": self.design.theme.get_warning_color(),
            "Low": self.design.theme.get_success_color()
        }
        risk_color = risk_colors.get(metrics['risk_level'], self.design.theme.get_text_color())
        kpi_table.setStyle(TableStyle([
            ('TEXTCOLOR', (3, 3), (3, 3), risk_color),
            ('FONTNAME', (3, 3), (3, 3), 'Helvetica-Bold'),
        ]))

        content.append(kpi_table)
        content.append(Spacer(1, 16))

        content.append(Paragraph("Key Insights", self.design.section_subtitle))
        content.append(Spacer(1, 6))

        key_findings = metrics.get('key_findings', [])
        if key_findings:
            for finding in key_findings[:5]:
                severity = finding.get('severity', 'Info')
                style = self._get_severity_style(severity)
                content.append(Paragraph(f"• {finding.get('observation', '')}", style))
                content.append(Spacer(1, 3))
        else:
            content.append(Paragraph("No critical findings identified.", self.design.body_text))

        content.append(Spacer(1, 8))
        content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#E2E8F0')))
        return content

    def _kpi_col_width(self, doc_width):
        if doc_width:
            return doc_width / 4
        # Fallback: A4 (8.27in) minus 0.75in margins each side, /4 columns
        return ((8.27 - 1.5) * inch) / 4

    def _extract_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        observations = data.get("area_observations", [])
        conflicts = data.get("conflicts", [])

        critical = sum(1 for o in observations if o.get("severity") == "Critical")
        high = sum(1 for o in observations if o.get("severity") == "High")
        medium = sum(1 for o in observations if o.get("severity") == "Medium")
        low = sum(1 for o in observations if o.get("severity") == "Low")
        total = len(observations)

        if critical > 0:
            risk_level = "Critical"
        elif high > 0:
            risk_level = "High"
        elif medium > 0:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        sorted_obs = sorted(observations, key=lambda o: self._severity_weight(o.get("severity", "Info")), reverse=True)
        key_findings = sorted_obs[:5]

        confidence = data.get("confidence_score", 0)
        if not confidence and observations:
            confidence = self._calculate_health_score(observations) / 100

        return {
            "total_issues": total, "critical": critical, "high": high, "medium": medium, "low": low,
            "areas_affected": len(set(o.get("area", "") for o in observations)),
            "conflicts": len(conflicts), "key_findings": key_findings,
            "confidence": confidence, "risk_level": risk_level
        }

    def _severity_weight(self, severity: str) -> int:
        return {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Information": 0}.get(severity, 0)

    def _calculate_health_score(self, observations: List[Dict[str, Any]]) -> int:
        score = 100
        penalties = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
        for obs in observations:
            score -= penalties.get(obs.get("severity", ""), 0)
        return max(0, min(100, score))

    def _get_severity_style(self, severity: str) -> ParagraphStyle:
        styles = {
            "Critical": self.design.severity_critical, "High": self.design.severity_high,
            "Medium": self.design.severity_medium, "Low": self.design.severity_low
        }
        return styles.get(severity, self.design.body_text)


class HealthScoreRenderer(ComponentRenderer):
    def render(self, data: Dict[str, Any], **kwargs) -> List[Flowable]:
        content = []
        content.append(Paragraph("Property Health Dashboard", self.design.section_title))
        content.append(Spacer(1, 8))
        content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#E2E8F0')))
        content.append(Spacer(1, 16))

        observations = data.get("area_observations", [])
        score = self._calculate_health_score(observations)

        content.append(self._build_score_gauge(score))
        content.append(Spacer(1, 12))

        interpretation = self._get_score_interpretation(score)
        content.append(Paragraph(f"Health Score: <b>{score}/100</b> — {interpretation}", self.design.section_subtitle))
        content.append(Spacer(1, 10))

        content.append(Paragraph("Severity Breakdown", self.design.section_subtitle))
        content.append(Spacer(1, 6))
        content.append(self._build_breakdown_table(observations))
        return content

    def _calculate_health_score(self, observations: List[Dict[str, Any]]) -> int:
        if not observations:
            return 100
        score = 100
        penalties = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}
        for obs in observations:
            score -= penalties.get(obs.get("severity", ""), 0)
        return max(0, min(100, score))

    def _build_score_gauge(self, score: int) -> Drawing:
        drawing = Drawing(6 * inch, 2.2 * inch)
        gauge_radius = 0.75 * inch
        center_x = 3 * inch
        center_y = 1.1 * inch
        start_angle = 135
        end_angle = 405

        if score >= 90:
            gauge_color = self.design.theme.get_success_color()
        elif score >= 75:
            gauge_color = HexColor('#34D399')
        elif score >= 60:
            gauge_color = self.design.theme.get_warning_color()
        elif score >= 40:
            gauge_color = HexColor('#F97316')
        else:
            gauge_color = self.design.theme.get_danger_color()

        bg_path = GraphicsPath()
        for i, angle in enumerate(range(start_angle, end_angle + 1, 2)):
            rad = math.radians(angle)
            x = center_x + gauge_radius * math.cos(rad)
            y = center_y + gauge_radius * math.sin(rad)
            if i == 0:
                bg_path.moveTo(x, y)
            else:
                bg_path.lineTo(x, y)
        bg_path.strokeColor = HexColor('#E2E8F0')
        bg_path.strokeWidth = 14
        bg_path.fillColor = None
        drawing.add(bg_path)

        score_angle = start_angle + (score / 100) * 270
        score_path = GraphicsPath()
        for i, angle in enumerate(range(start_angle, int(score_angle) + 1, 2)):
            rad = math.radians(angle)
            x = center_x + gauge_radius * math.cos(rad)
            y = center_y + gauge_radius * math.sin(rad)
            if i == 0:
                score_path.moveTo(x, y)
            else:
                score_path.lineTo(x, y)
        score_path.strokeColor = gauge_color
        score_path.strokeWidth = 14
        score_path.fillColor = None
        drawing.add(score_path)

        score_text = String(center_x, center_y - 0.15 * inch, f"{score}/100")
        score_text.fontName = 'Helvetica-Bold'
        score_text.fontSize = 26
        score_text.textAnchor = 'middle'
        drawing.add(score_text)
        return drawing

    def _get_score_interpretation(self, score: int) -> str:
        if score >= 90:
            return "Excellent — Property is in outstanding condition"
        elif score >= 75:
            return "Good — Minor issues present but property is sound"
        elif score >= 60:
            return "Fair — Some issues require attention"
        elif score >= 40:
            return "Poor — Significant issues affecting property condition"
        return "Critical — Major issues requiring immediate intervention"

    def _build_breakdown_table(self, observations: List[Dict[str, Any]]) -> Table:
        severity_counts = {}
        for obs in observations:
            sev = obs.get("severity", "Information")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        data = [["Severity", "Count", "Impact", "Status"]]
        order = ["Critical", "High", "Medium", "Low", "Information"]
        for sev in order:
            count = severity_counts.get(sev, 0)
            impacts = {"Critical": "Severe", "High": "Significant", "Medium": "Moderate", "Low": "Minor", "Information": "Informational"}
            data.append([sev, str(count), impacts.get(sev, "Informational"), "OK" if count == 0 else "!"])

        table = Table(data, colWidths=[1.7 * inch, 1.7 * inch, 1.7 * inch, 1.7 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, 0), self.design.theme.get_primary_color()),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#E2E8F0')),
        ]))

        severity_colors = {
            "Critical": self.design.theme.get_danger_color(), "High": HexColor('#F97316'),
            "Medium": self.design.theme.get_warning_color(), "Low": self.design.theme.get_success_color(),
            "Information": HexColor('#94A3B8')
        }
        for i, sev in enumerate(order, 1):
            table.setStyle(TableStyle([
                ('TEXTCOLOR', (0, i), (0, i), severity_colors.get(sev, HexColor('#94A3B8'))),
                ('FONTNAME', (0, i), (0, i), 'Helvetica-Bold'),
            ]))
        return table


class ObservationRenderer(ComponentRenderer):
    def render(self, data: Dict[str, Any], **kwargs) -> List[Flowable]:
        content = []
        observations = data.get("area_observations", [])
        if not observations:
            content.append(Paragraph("No observations recorded.", self.design.body_text))
            return content

        content.append(Paragraph("Area Observations", self.design.section_title))
        content.append(Spacer(1, 8))
        content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#E2E8F0')))
        content.append(Spacer(1, 12))

        content.append(Paragraph(
            f"<b>{len(observations)}</b> observations identified across "
            f"<b>{len(set(o.get('area', '') for o in observations))}</b> areas",
            self.design.body_text
        ))
        content.append(Spacer(1, 12))

        for idx, obs in enumerate(observations):
            card = self._build_observation_card(obs, idx + 1)
            content.append(KeepTogether(card))
            content.append(Spacer(1, 10))

        return content

    def _build_observation_card(self, obs: Dict[str, Any], index: int) -> List[Flowable]:
        """Wraps the observation in a single-cell bordered/background table -> reads as a card."""
        area = obs.get("area", f"Area {index}")
        severity = obs.get("severity", "Information")
        severity_color = self._get_severity_color(severity)

        inner = []
        inner.append(Paragraph(f"<b>Observation {index}: {area}</b>", self.design.section_subtitle))
        inner.append(Spacer(1, 2))
        inner.append(Paragraph(f"<font color='{severity_color}'><b>{severity}</b></font>", self.design.body_bold))
        inner.append(Spacer(1, 6))

        observation = obs.get("observation", "No observation provided.")
        inner.append(Paragraph(f"<b>Finding:</b> {observation}", self.design.body_text))

        evidence = obs.get("evidence", [])
        if evidence:
            evidence_text = "; ".join(str(e) for e in evidence[:3]) if isinstance(evidence, list) else str(evidence)
            inner.append(Spacer(1, 4))
            inner.append(Paragraph("<b>Supporting Evidence:</b>", self.design.body_bold))
            inner.append(Paragraph(evidence_text, self.design.evidence))

        category = obs.get("category", "")
        if category:
            inner.append(Spacer(1, 4))
            inner.append(Paragraph(f"<b>Category:</b> {category}", self.design.body_small))

        confidence = obs.get("confidence", 0)
        if confidence:
            confidence_pct = confidence * 100 if confidence <= 1 else confidence
            inner.append(Paragraph(f"<b>Confidence:</b> {confidence_pct:.0f}%", self.design.body_small))

        images = obs.get("images", [])
        if images and isinstance(images, list):
            image_content = self._render_images(images)
            if image_content:
                inner.append(Spacer(1, 6))
                inner.append(Paragraph("<b>Visual Evidence:</b>", self.design.body_bold))
                inner.extend(image_content)

        card_table = Table([[inner]], colWidths=[6.77 * inch])
        card_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, HexColor('#CBD5E1')),
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#F8FAFC')),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return [card_table]

    def _render_images(self, image_paths: List[str]) -> List[Flowable]:
        content = []
        for idx, path in enumerate(image_paths[:3]):
            try:
                if path and os.path.exists(path):
                    with PILImage.open(path) as img:
                        width, height = img.size
                        aspect = height / width
                        display_width = min(2.5 * inch, 2 * inch / aspect)
                        display_height = display_width * aspect
                        if display_height > 2.5 * inch:
                            display_height = 2.5 * inch
                            display_width = display_height / aspect

                        img_obj = Image(path, width=display_width, height=display_height)
                        img_obj.hAlign = 'CENTER'
                        content.append(Spacer(1, 4))
                        content.append(img_obj)
                        content.append(Paragraph(f"<i>Figure {idx+1}: {os.path.basename(path)}</i>", self.design.body_small))
                        content.append(Spacer(1, 4))
            except Exception as e:
                self.logger.error(f"Observation image failed to render ({path}): {e!r}")
                content.append(Paragraph("<i>Image could not be loaded</i>", self.design.body_small))
        return content

    def _get_severity_color(self, severity: str) -> HexColor:
        colors_map = {
            "Critical": self.design.theme.get_danger_color(), "High": HexColor('#F97316'),
            "Medium": self.design.theme.get_warning_color(), "Low": self.design.theme.get_success_color(),
            "Information": HexColor('#94A3B8')
        }
        return colors_map.get(severity, HexColor('#94A3B8'))


class RootCauseRenderer(ComponentRenderer):
    def render(self, data: Dict[str, Any], **kwargs) -> List[Flowable]:
        content = []
        root_cause = data.get("root_cause", "")
        root_cause_analysis = data.get("root_cause_analysis", {})
        if not root_cause and not root_cause_analysis:
            return content

        content.append(Paragraph("Root Cause Analysis", self.design.section_title))
        content.append(Spacer(1, 8))
        content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#E2E8F0')))
        content.append(Spacer(1, 12))

        primary_cause = root_cause_analysis.get('primary_cause', root_cause)
        if primary_cause:
            content.append(Paragraph("<b>Primary Root Cause:</b>", self.design.section_subtitle))
            content.append(Paragraph(primary_cause, self.design.body_text))
            content.append(Spacer(1, 10))

        contributing_factors = root_cause_analysis.get('contributing_factors', [])
        if contributing_factors:
            content.append(Paragraph("<b>Contributing Factors:</b>", self.design.body_bold))
            for factor in contributing_factors[:5]:
                content.append(Paragraph(f"• {factor}", self.design.body_text))
            content.append(Spacer(1, 10))

        supporting_evidence = root_cause_analysis.get('supporting_evidence', [])
        if supporting_evidence:
            content.append(Paragraph("<b>Supporting Evidence:</b>", self.design.body_bold))
            for evidence in supporting_evidence[:3]:
                content.append(Paragraph(f"• {evidence}", self.design.evidence))
            content.append(Spacer(1, 10))

        confidence = root_cause_analysis.get('confidence', 0)
        if confidence:
            content.append(Paragraph(f"<b>Confidence Level:</b> {confidence:.0%}", self.design.body_text))
        return content


class SeverityRenderer(ComponentRenderer):
    def render(self, data: Dict[str, Any], **kwargs) -> List[Flowable]:
        content = []
        observations = data.get("area_observations", [])
        if not observations:
            return content

        content.append(Paragraph("Severity Assessment", self.design.section_title))
        content.append(Spacer(1, 8))
        content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#E2E8F0')))
        content.append(Spacer(1, 12))

        severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Information": 0}
        for obs in observations:
            sev = obs.get("severity", "Information")
            if sev in severity_counts:
                severity_counts[sev] += 1
        total = len(observations)

        cards_data = [
            ["Critical", severity_counts["Critical"], ""],
            ["High", severity_counts["High"], ""],
            ["Medium", severity_counts["Medium"], ""],
            ["Low", severity_counts["Low"], ""],
        ]
        card_table = Table(cards_data, colWidths=[2.27 * inch, 2.25 * inch, 2.25 * inch])
        card_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#E2E8F0')),
        ]))

        severity_colors = {
            "Critical": self.design.theme.get_danger_color(), "High": HexColor('#F97316'),
            "Medium": self.design.theme.get_warning_color(), "Low": self.design.theme.get_success_color()
        }
        for i, row in enumerate(cards_data):
            color = severity_colors.get(row[0], HexColor('#94A3B8'))
            card_table.setStyle(TableStyle([
                ('TEXTCOLOR', (0, i), (0, i), color),
                ('FONTNAME', (0, i), (0, i), 'Helvetica-Bold'),
            ]))
            if total > 0 and row[1] > 0:
                card_table.setStyle(TableStyle([
                    ('BACKGROUND', (2, i), (2, i), color),
                    ('TEXTCOLOR', (2, i), (2, i), HexColor('#FFFFFF')),
                ]))

        content.append(card_table)
        content.append(Spacer(1, 12))

        content.append(Paragraph("Severity Distribution", self.design.section_subtitle))
        content.append(Spacer(1, 6))

        chart_data = [["Severity", "Count", "Percentage"]]
        for sev in ["Critical", "High", "Medium", "Low"]:
            count = severity_counts.get(sev, 0)
            pct = (count / total * 100) if total > 0 else 0
            chart_data.append([sev, str(count), f"{pct:.1f}%"])

        chart_table = Table(chart_data, colWidths=[2.26 * inch, 2.26 * inch, 2.25 * inch])
        chart_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, 0), self.design.theme.get_primary_color()),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#E2E8F0')),
        ]))
        content.append(chart_table)
        return content


class RecommendationsRenderer(ComponentRenderer):
    def render(self, data: Dict[str, Any], **kwargs) -> List[Flowable]:
        content = []
        recommendations = data.get("recommendations", data.get("recommended_actions", []))
        if not recommendations:
            return content

        content.append(Paragraph("Recommended Actions", self.design.section_title))
        content.append(Spacer(1, 8))
        content.append(HRFlowable(width="100%", thickness=1, color=HexColor('#E2E8F0')))
        content.append(Spacer(1, 12))

        grouped = self._group_by_priority(recommendations)
        priority_order = ["Immediate", "Short-Term", "Long-Term", "Preventive"]
        priority_colors = {
            "Immediate": self.design.theme.get_danger_color(), "Short-Term": HexColor('#F97316'),
            "Long-Term": self.design.theme.get_warning_color(), "Preventive": self.design.theme.get_success_color()
        }

        for priority in priority_order:
            items = grouped.get(priority, [])
            if not items:
                continue
            color = priority_colors.get(priority, self.design.theme.get_text_color())
            content.append(Paragraph(
                f"{priority} Actions",
                ParagraphStyle('PriorityHeader', parent=self.design.section_subtitle, textColor=color)
            ))
            content.append(Spacer(1, 6))

            for idx, item in enumerate(items, 1):
                if isinstance(item, dict):
                    action_text = item.get('action', str(item))
                    impact = item.get('impact', '')
                    risk_reduction = item.get('risk_reduction', '')
                else:
                    action_text, impact, risk_reduction = str(item), '', ''

                item_text = f"{idx}. {action_text}"
                if impact:
                    item_text += f" <i>(Impact: {impact})</i>"
                if risk_reduction:
                    item_text += f" <i>(Risk Reduction: {risk_reduction})</i>"

                content.append(Paragraph(item_text, self.design.body_text))
                content.append(Spacer(1, 3))

            content.append(Spacer(1, 8))
        return content

    def _group_by_priority(self, recommendations: List) -> Dict[str, List]:
        grouped = {}
        for rec in recommendations:
            if isinstance(rec, dict):
                action = rec.get('action', str(rec))
                priority = rec.get('priority', 'Preventive')
            else:
                action = str(rec)
                low = action.lower()
                if any(k in low for k in ("immediate", "urgent", "emergency")):
                    priority = "Immediate"
                elif any(k in low for k in ("short", "soon", "next")):
                    priority = "Short-Term"
                elif any(k in low for k in ("long", "future", "plan")):
                    priority = "Long-Term"
                else:
                    priority = "Preventive"
            grouped.setdefault(priority, []).append(action)
        return grouped


# ============================================================================
# PDF ENGINE
# ============================================================================

class PDFEngine:
    """Main PDF generation engine with enterprise features."""

    # Section boundaries that should force a real page break (true new
    # chapters). Everything else just flows with a CondPageBreak guard so we
    # don't get the large-empty-space-at-bottom-of-page problem.
    HARD_BREAK_AFTER = {
        ReportSection.COVER,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.AREA_OBSERVATIONS,
    }

    def __init__(self, config: Optional[ReportConfiguration] = None):
        self.config = config or ReportConfiguration()
        self.design = DesignSystem(self.config.branding)
        self.logger = logging.getLogger(__name__)
        self.header_footer = EnterpriseHeaderFooter(self.design, self.config, self.logger)

        self.renderers = {
            ReportSection.COVER: CoverPageRenderer(self.design),
            ReportSection.EXECUTIVE_SUMMARY: ExecutiveSummaryRenderer(self.design),
            ReportSection.HEALTH_SCORE: HealthScoreRenderer(self.design),
            ReportSection.AREA_OBSERVATIONS: ObservationRenderer(self.design),
            ReportSection.ROOT_CAUSE: RootCauseRenderer(self.design),
            ReportSection.SEVERITY: SeverityRenderer(self.design),
            ReportSection.RECOMMENDATIONS: RecommendationsRenderer(self.design),
        }

    async def generate(self,
                        ddr_data: Dict[str, Any],
                        extracted_images: List[Dict[str, Any]],
                        output_path: FilePath,
                        **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        self.logger.info(f"Starting PDF generation: {output_path}")

        try:
            self._validate_data(ddr_data)

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=self.config.page_config.margin_left * inch,
                rightMargin=self.config.page_config.margin_right * inch,
                topMargin=self.config.page_config.margin_top * inch,
                bottomMargin=self.config.page_config.margin_bottom * inch
            )
            doc.report_id = ddr_data.get('report_id', 'DDR-2025-001')

            story = self._build_content(ddr_data, extracted_images, doc_width=doc.width)

            header_footer = self.header_footer

            def draw_page(canvas_obj, doc_):
                """
                THE KEY FIX: this function wires render_page_border /
                render_header / render_footer into actual page rendering.
                Previously these methods existed but were never passed to
                doc.build(), so nothing ever called them.

                Header is skipped on page 1 because CoverPageRenderer already
                builds a full custom cover layout -- drawing the navy header
                bar on top of it would visually clash with the cover title.
                """
                header_footer.render_page_border(canvas_obj, doc_)
                if doc_.page > 1:
                    header_footer.render_header(canvas_obj, doc_)
                header_footer.render_footer(canvas_obj, doc_)

            doc.build(
                story,
                onFirstPage=draw_page,
                onLaterPages=draw_page,
                canvasmaker=NumberedCanvas
            )

            generation_time = time.time() - start_time
            metrics = {
                "generation_time": generation_time,
                "pages": len(doc.canv.pages) if hasattr(doc, 'canv') and hasattr(doc.canv, 'pages') else 0,
                "observations": len(ddr_data.get("area_observations", [])),
                "images_rendered": len(extracted_images),
                "success": True
            }
            self.logger.info(f"PDF generated in {generation_time:.2f}s: {output_path}")
            return metrics

        except Exception as e:
            self.logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to generate PDF: {str(e)}")

    def _validate_data(self, data: Dict[str, Any]) -> None:
        if not data:
            raise ValueError("Input data is empty")
        if not isinstance(data, dict):
            raise ValueError(f"Invalid input format: expected dict, got {type(data)}")

    def _build_content(self,
                        ddr_data: Dict[str, Any],
                        extracted_images: List[Dict[str, Any]],
                        doc_width: float = None) -> List[Flowable]:
        story = []
        sections = self.config.sections

        for section_idx, section in enumerate(sections):
            try:
                section_content = self._render_section(section, ddr_data, extracted_images, doc_width)
                if not section_content:
                    continue
                story.extend(section_content)

                is_last = section_idx == len(sections) - 1
                if not is_last:
                    if section in self.HARD_BREAK_AFTER:
                        story.append(PageBreak())
                    else:
                        story.append(Spacer(1, 18))
                        story.append(CondPageBreak(120))
            except Exception as e:
                self.logger.error(f"Failed to render section {section}: {str(e)}", exc_info=True)
                if self.config.debug_mode:
                    story.append(Paragraph(f"Error rendering section: {section.value}", self.design.body_text))

        return story

    def _render_section(self,
                         section: ReportSection,
                         ddr_data: Dict[str, Any],
                         extracted_images: List[Dict[str, Any]],
                         doc_width: float = None) -> List[Flowable]:
        renderer = self.renderers.get(section)
        if not renderer:
            return []
        data = {**ddr_data, "extracted_images": extracted_images}
        return renderer.render(data, doc_width=doc_width)


# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

def generate_pdf(
    ddr_data: Dict[str, Any],
    extracted_images: List[Dict[str, Any]],
    output_dir: str = "generated_reports"
) -> str:
    output_path = FilePath(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = output_path / f"DDR_Report_{timestamp}.pdf"

    config = ReportConfiguration()
    engine = PDFEngine(config)

    import asyncio
    asyncio.run(engine.generate(ddr_data, extracted_images, pdf_filename))
    return str(pdf_filename)


__all__ = [
    "SeverityLevel", "ReportSection", "BrandingTheme", "PageConfiguration",
    "ReportConfiguration", "PDFEngine", "generate_pdf",
]


# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json
    import asyncio

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    parser = argparse.ArgumentParser(description="Enterprise PDF Report Generator")
    parser.add_argument("data_file", type=str, help="DDR data JSON file")
    parser.add_argument("--images", "-i", type=str, help="Images metadata JSON file")
    parser.add_argument("--output", "-o", type=str, default="generated_reports", help="Output directory")
    parser.add_argument("--branding", "-b", type=str, help="Branding configuration file")

    args = parser.parse_args()

    async def main():
        with open(args.data_file, 'r') as f:
            ddr_data = json.load(f)

        images = []
        if args.images:
            with open(args.images, 'r') as f:
                images = json.load(f)

        branding = None
        if args.branding:
            with open(args.branding, 'r') as f:
                branding = BrandingTheme(**json.load(f))

        config = ReportConfiguration()
        if branding:
            config.branding = branding

        engine = PDFEngine(config)
        output_path = FilePath(args.output)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_file = output_path / f"DDR_Report_{timestamp}.pdf"

        metrics = await engine.generate(ddr_data, images, pdf_file)
        print(f"PDF generated: {pdf_file}")
        print(f"Pages: {metrics['pages']}")
        print(f"Time: {metrics['generation_time']:.2f}s")
        print(f"Observations: {metrics['observations']}")

    asyncio.run(main())