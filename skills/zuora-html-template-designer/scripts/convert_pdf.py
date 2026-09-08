#!/usr/bin/env python3
"""
PDF to PNG conversion with security validation.

For PDFs with more than 3 pages, only first, second-to-last, and last pages
are converted and stacked into a single combined PNG.

CLI Usage:
    python convert_pdf.py --input <pdf_path> --output <output_dir> [--dpi 300] [--timeout 30]

Module Usage:
    from convert_pdf import convert_pdf_to_image, process_pdf
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from security import PDFValidationError, validate_pdf

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
SEPARATOR_HEIGHT = 40


class PDFConversionError(Exception):
    """PDF conversion failed."""

    def __init__(self, message: str, error_code: str = "pdf_conversion_failed", retry_allowed: bool = True):
        super().__init__(message)
        self.error_code = error_code
        self.retry_allowed = retry_allowed


def safe_unlink(path: Optional[str]) -> None:
    """Safely delete a file, ignoring errors if it doesn't exist."""
    if path:
        try:
            os.unlink(path)
        except (FileNotFoundError, OSError):
            pass


def select_pages(total_pages: int) -> list[int]:
    """Return 1-indexed page numbers to convert."""
    if total_pages <= 3:
        return list(range(1, total_pages + 1))
    return [1, total_pages - 1, total_pages]


def get_pdf_page_count(pdf_path: str | Path) -> int:
    """Get page count via pypdf (raises on invalid PDF)."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    if page_count == 0:
        raise PDFConversionError("PDF has no pages", error_code="pdf_validation_failed", retry_allowed=False)
    return page_count


def _strip_and_save(img: Image.Image, path: Path) -> None:
    """Save PNG with metadata stripped."""
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    clean.save(path, "PNG", optimize=True)


def convert_pdf_to_png(
    pdf_path: str | Path,
    output_dir: str | Path,
    dpi: int = 300,
    total_pages: Optional[int] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Convert selected PDF pages to a single combined PNG.

    Returns dict with success, png_path, pages_used, pages.
    Raises PDFConversionError on failure.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if total_pages is None:
        total_pages = get_pdf_page_count(pdf_path)

    pages_to_convert = select_pages(total_pages)
    temp_images: list[tuple[int, Path]] = []

    for page_num in pages_to_convert:
        output_file = output_dir / f"page_{page_num}.png"
        output_stem = str(output_file.with_suffix(""))

        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r",
                    str(dpi),
                    "-f",
                    str(page_num),
                    "-l",
                    str(page_num),
                    "-singlefile",
                    str(pdf_path),
                    output_stem,
                ],
                check=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise PDFConversionError(
                f"Timed out converting page {page_num}",
                error_code="conversion_timeout",
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace") if exc.stderr else str(exc)
            raise PDFConversionError(
                f"Error converting page {page_num}: {stderr.strip()}",
            ) from exc

        if not output_file.exists():
            raise PDFConversionError(f"pdftoppm did not produce output for page {page_num}")

        temp_images.append((page_num, output_file))

    final_output = output_dir / f"{pdf_path.name}.png"

    if len(temp_images) == 1:
        _strip_and_save(Image.open(temp_images[0][1]), final_output)
        temp_images[0][1].unlink(missing_ok=True)
        return {
            "success": True,
            "png_path": str(final_output),
            "pages_used": [temp_images[0][0]],
            "pages": total_pages,
        }

    images: list[tuple[int, Image.Image]] = []
    for page_num, img_path in temp_images:
        images.append((page_num, Image.open(img_path)))

    total_height = sum(img.height for _, img in images) + SEPARATOR_HEIGHT * (len(images) - 1)
    max_width = max(img.width for _, img in images)
    combined = Image.new("RGB", (max_width, total_height), "white")
    draw = ImageDraw.Draw(combined)

    y_offset = 0
    for i, (page_num, img) in enumerate(images):
        combined.paste(img, (0, y_offset))
        y_offset += img.height

        if i < len(images) - 1:
            draw.rectangle(
                [(0, y_offset), (max_width, y_offset + SEPARATOR_HEIGHT)],
                fill="#ffcccc",
            )
            draw.line(
                [(0, y_offset + 2), (max_width, y_offset + 2)],
                fill="red",
                width=2,
            )

            text = f"── PAGE {page_num} of {total_pages} ──"
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
                )
            except OSError:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (max_width - text_width) // 2
            draw.text((text_x, y_offset + 12), text, fill="#cc0000", font=font)
            y_offset += SEPARATOR_HEIGHT

    _strip_and_save(combined, final_output)

    for _, img_path in temp_images:
        img_path.unlink(missing_ok=True)

    return {
        "success": True,
        "png_path": str(final_output),
        "pages_used": [page_num for page_num, _ in images],
        "pages": total_pages,
    }


def _convert_pdf_sync(pdf_path: str, dpi: int = 300, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Synchronous conversion; PNG written beside the PDF file."""
    output_dir = os.path.dirname(pdf_path) or "."
    result = convert_pdf_to_png(pdf_path, output_dir, dpi=dpi, timeout=timeout)
    return result["png_path"]


async def convert_pdf_to_image(pdf_path: str, dpi: int = 300, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Convert PDF to combined PNG asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _convert_pdf_sync, pdf_path, dpi, timeout)


async def process_pdf(pdf_path: str) -> tuple[Optional[str], Optional[dict]]:
    """
    Validate PDF and convert to PNG for visual analysis.

    Returns:
        Success: (image_path, None)
        Failure: (None, error_dict)
    """
    image_path = None
    start_time = time.time()

    try:
        page_count, _metadata = validate_pdf(pdf_path)
        logger.info(f"PDF validated: {page_count} pages")

        output_dir = os.path.dirname(pdf_path) or "."
        result = convert_pdf_to_png(
            pdf_path,
            output_dir,
            total_pages=page_count,
        )
        image_path = result["png_path"]

        duration = time.time() - start_time
        logger.info(f"PDF processed in {duration:.2f}s: {image_path}")

        safe_unlink(pdf_path)
        return image_path, None

    except PDFValidationError as exc:
        logger.error(f"PDF validation failed: {exc}")
        safe_unlink(pdf_path)
        safe_unlink(image_path)
        return None, {
            "error": f"Invalid PDF: {exc}",
            "error_code": "pdf_validation_failed",
            "retry_allowed": False,
        }
    except PDFConversionError as exc:
        logger.error(f"PDF conversion failed: {exc}")
        safe_unlink(pdf_path)
        safe_unlink(image_path)
        return None, {
            "error": str(exc),
            "error_code": exc.error_code,
            "retry_allowed": exc.retry_allowed,
        }
    except Exception as exc:
        duration = time.time() - start_time
        logger.error(f"PDF conversion failed after {duration:.2f}s: {exc}")
        safe_unlink(pdf_path)
        safe_unlink(image_path)
        return None, {
            "error": f"Could not convert PDF: {exc}",
            "error_code": "pdf_conversion_failed",
            "retry_allowed": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PDF to PNG for visual analysis")
    parser.add_argument("--input", required=True, help="Input PDF file path")
    parser.add_argument("--output", required=True, help="Output directory path")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for conversion (default: 300)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-page conversion timeout in seconds (default: {DEFAULT_TIMEOUT})",
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
        page_count, _metadata = validate_pdf(args.input)
        result = convert_pdf_to_png(
            args.input,
            args.output,
            dpi=args.dpi,
            total_pages=page_count,
            timeout=args.timeout,
        )
        print(json.dumps(result, indent=2))
        sys.exit(0)

    except PDFValidationError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "error_code": "pdf_validation_failed",
                    "retry_allowed": False,
                }
            )
        )
        sys.exit(4)

    except PDFConversionError as exc:
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
        sys.exit(2)

    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "error_code": "pdf_conversion_failed",
                    "retry_allowed": True,
                }
            )
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
