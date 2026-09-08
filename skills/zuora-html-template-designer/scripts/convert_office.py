#!/usr/bin/env python3
"""
Convert Word documents (.doc, .docx) to PDF via headless LibreOffice.

CLI Usage:
    python convert_office.py --input <doc_path> --output <output_dir> [--timeout 60]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_TIMEOUT = 60


class OfficeConversionError(Exception):
    """Office document conversion failed."""

    def __init__(
        self,
        message: str,
        error_code: str = "office_conversion_failed",
        retry_allowed: bool = True,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.retry_allowed = retry_allowed


def _find_soffice() -> str:
    for candidate in ("soffice", "libreoffice"):
        path = shutil.which(candidate)
        if path:
            return path
    raise OfficeConversionError(
        "LibreOffice (soffice) not found on PATH. "
        "Install LibreOffice for .doc/.docx support.",
        error_code="office_not_installed",
        retry_allowed=False,
    )


def convert_office_to_pdf(
    input_path: str | Path,
    output_dir: str | Path,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """
    Convert a Word document to PDF using headless LibreOffice.

    Returns:
        dict with success, pdf_path, and source extension
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    ext = input_path.suffix.lstrip(".").lower()
    if ext not in ("doc", "docx"):
        raise OfficeConversionError(
            f"Unsupported office format: .{ext or 'unknown'}",
            error_code="office_validation_failed",
            retry_allowed=False,
        )

    soffice = _find_soffice()
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(input_path),
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise OfficeConversionError(
            f"Office conversion timed out after {timeout}s",
            error_code="conversion_timeout",
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        raise OfficeConversionError(
            f"LibreOffice conversion failed: {stderr or exc}",
            error_code="office_conversion_failed",
        ) from exc

    pdf_path = output_dir / f"{input_path.stem}.pdf"
    if not pdf_path.is_file():
        raise OfficeConversionError(
            f"Expected PDF not found after conversion: {pdf_path}",
            error_code="office_conversion_failed",
        )

    return {
        "success": True,
        "pdf_path": str(pdf_path),
        "source": ext,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Word document to PDF for template generation"
    )
    parser.add_argument("--input", required=True, help="Input .doc or .docx file path")
    parser.add_argument("--output", required=True, help="Output directory path")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Conversion timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"Input file not found: {args.input}",
                    "error_code": "FILE_NOT_FOUND",
                }
            )
        )
        sys.exit(1)

    if not os.path.isdir(args.output):
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"Output directory not found: {args.output}",
                    "error_code": "DIR_NOT_FOUND",
                }
            )
        )
        sys.exit(1)

    try:
        result = convert_office_to_pdf(args.input, args.output, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except OfficeConversionError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "error_code": exc.error_code,
                    "retry_allowed": exc.retry_allowed,
                }
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
