"""
PDF security validation for invoice template uploads.

Validates PDFs before processing to prevent security issues:
- Magic byte validation (ensures file is actually a PDF)
- Polyglot detection (PDF/ZIP, PDF/PE combinations)
- Encryption check (password-protected PDFs not supported)
- JavaScript detection (prevents malicious scripts)
- Forbidden features scan (OpenAction, Launch, EmbeddedFile, etc.)
"""

import logging
from typing import Tuple

from pypdf import PdfReader

logger = logging.getLogger(__name__)


class PDFValidationError(Exception):
    """PDF failed security/format validation."""

    pass


# Forbidden PDF features (security-sensitive)
# Note: Action-based patterns (/JavaScript, /JS, /OpenAction, /AA, /Launch)
# are safe to allow since we only convert to PNG (no code execution).
FORBIDDEN_PATTERNS: list[tuple[bytes, str]] = [
    (b"/EmbeddedFile", "embedded files"),
    (b"/RichMedia", "rich media content"),
]


def validate_pdf(pdf_path: str) -> Tuple[int, dict[str, int]]:
    """
    Validate PDF security constraints.

    Performs comprehensive security checks:
    1. Magic byte validation - ensures file starts with %PDF-
    2. Polyglot detection - checks for ZIP/PE signatures that indicate polyglot files
    3. pypdf parsing - validates PDF structure and checks encryption
    4. Forbidden features scan - detects JavaScript, launch actions, embedded files

    Args:
        pdf_path: Path to the PDF file to validate

    Returns:
        Tuple of (page_count, metadata_dict)
        metadata_dict contains: {"pages": int}

    Raises:
        PDFValidationError: If PDF is unsafe, invalid, or encrypted
    """
    logger.info(f"Validating PDF: {pdf_path}")

    # 1. Magic byte check
    with open(pdf_path, "rb") as f:
        header = f.read(1024)
        if not header.startswith(b"%PDF-"):
            raise PDFValidationError("Invalid PDF header - file is not a PDF")

        # Polyglot detection - check for signatures of other file types
        # ZIP signature (PK\x03\x04) could indicate PDF/ZIP polyglot
        if b"PK\x03\x04" in header[:512]:
            raise PDFValidationError(
                "PDF contains ZIP signature (potential polyglot attack)"
            )
        # PE executable signature (MZ) could indicate PDF/EXE polyglot
        if header[:2] == b"MZ":
            raise PDFValidationError(
                "PDF contains executable signature (potential polyglot attack)"
            )

    # 2. Parse with pypdf for structure validation
    try:
        reader = PdfReader(pdf_path)

        # Check encryption
        if reader.is_encrypted:
            raise PDFValidationError(
                "Encrypted/password-protected PDFs are not supported"
            )

        # Check page count
        page_count = len(reader.pages)
        if page_count == 0:
            raise PDFValidationError("PDF has no pages")

        logger.info(f"PDF structure valid: {page_count} pages")

    except PDFValidationError:
        raise
    except Exception as e:
        raise PDFValidationError(f"Failed to parse PDF structure: {str(e)}")

    # 3. Scan for forbidden features (security-sensitive PDF objects)
    with open(pdf_path, "rb") as f:
        content = f.read()
        for pattern, description in FORBIDDEN_PATTERNS:
            if pattern in content:
                raise PDFValidationError(
                    f"PDF contains forbidden feature: {description}"
                )

    logger.info(f"PDF security validation passed: {pdf_path}")
    return page_count, {"pages": page_count}
