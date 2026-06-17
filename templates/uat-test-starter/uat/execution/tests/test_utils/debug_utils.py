"""
Debug utilities for E2E tests.
Implements API request/response logging. Debug logs carry captured IDs that the AI reads
before UI execution via Playwright MCP.

UI visual captures are not handled here; UI runs record evidence via `browser_snapshot` in per-TR reports.
Output path: ``<execution-root>/debugging/{feature_id}_{test_name}_{timestamp}.log``.

``feature_id`` must match the testmatrix / discover_groups feature string (same as report
basenames), e.g. ``BillingOps_Billing_Document_Management``.
"""

import glob
import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from tests.test_utils.repo_paths import resolve_debugging_dir

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


def resolve_execution_debugging_dir(debug_dir: str = "debugging") -> str:
    """Resolve the debugging directory to an absolute path (same rules as DebugLogger)."""
    return resolve_debugging_dir(debug_dir)


def glob_debug_log_files(
    feature_id: str, tr_index: str, debug_dir: str = "debugging"
) -> List[str]:
    """Return paths matching ``{feature_id}_{tr_index}_*.log`` (e.g. TR1, TR2)."""
    d = resolve_debugging_dir(debug_dir)
    return glob.glob(os.path.join(d, f"{feature_id}_{tr_index}_*.log"))


class DebugLogger:
    """Core debugging utility for API test automation"""

    def __init__(
        self,
        test_name: str,
        *,
        feature_id: str,
        debug_dir: str = "debugging",
        api_client=None,
    ):
        """Initialize debug logger for a test case.

        Args:
            test_name: Name segment for this scenario (e.g. ``TR1_Generate_PDF_And_Download``)
            feature_id: Testmatrix feature id (stem of ``<design-root>/testmatrix/<Feature>_TRs.md``),
                e.g. ``BillingOps_Billing_Document_Management``
            debug_dir: Directory under the execution root (e.g. ``debugging``), optional ``execution/`` prefix, or absolute path
            api_client: API client instance for request tracking
        """
        if not feature_id or not str(feature_id).strip():
            raise ValueError("feature_id is required (testmatrix feature string)")

        self.test_name = test_name
        self.api_client = api_client
        self.test_exception = None
        self.log_entries = []
        self.feature_id = feature_id.strip()

        if os.path.isabs(debug_dir):
            self.debug_dir = debug_dir
        else:
            self.debug_dir = resolve_execution_debugging_dir(debug_dir)

        os.makedirs(self.debug_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debug_file = os.path.join(
            self.debug_dir, f"{self.feature_id}_{test_name}_{timestamp}.log"
        )

        self.cleanup_enabled = os.getenv("CLEANUP_DEBUG_FILES", "false").lower() == "true"
        self.keep_latest_only = os.getenv("KEEP_LATEST_DEBUG_LOG", "true").lower() == "true"

        self._write_header()

        if self.keep_latest_only:
            self._remove_older_logs(test_name)

        logger.info("Debug logger initialized for %s", test_name)
        logger.info("Debug file: %s", self.debug_file)
        logger.info("Cleanup enabled: %s", self.cleanup_enabled)

    def _write_header(self):
        with open(self.debug_file, "w", encoding="utf-8") as f:
            f.write(f"DEBUG LOG FOR TEST: {self.test_name}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Debug File: {self.debug_file}\n")
            f.write(f"Cleanup Enabled: {self.cleanup_enabled}\n")
            f.write(f"Environment Variable CLEANUP_DEBUG_FILES: {os.getenv('CLEANUP_DEBUG_FILES', 'false')}\n")
            f.write("=" * 80 + "\n\n")

    def _remove_older_logs(self, test_name: str):
        """Remove older log files for the same test, keeping only the current one.

        Matches on the stable part of the test name (stripping trailing timestamps
        like _20260422173526) so that successive runs of the same test clean up
        previous runs' logs.
        """
        stable_name = re.sub(r"_\d{14}$", "", test_name)
        prefix = f"{self.feature_id}_{stable_name}"

        current_basename = os.path.basename(self.debug_file)
        try:
            for filename in os.listdir(self.debug_dir):
                if filename.startswith(prefix) and filename.endswith(".log") and filename != current_basename:
                    old_path = os.path.join(self.debug_dir, filename)
                    os.remove(old_path)
                    logger.debug("Removed older debug log: %s", old_path)
        except OSError as e:
            logger.warning("Error cleaning up older debug logs: %s", e)

    def log_test_environment(self, account_number: str = None, config: Dict[str, Any] = None):
        with open(self.debug_file, "a", encoding="utf-8") as f:
            f.write("TEST ENVIRONMENT INFORMATION\n")
            f.write("=" * 50 + "\n")
            f.write(f"Test: {self.test_name}\n")
            if account_number:
                f.write(f"Account Number: {account_number}\n")
            f.write(f"Debug File: {self.debug_file}\n")
            f.write(f"Cleanup Enabled: {self.cleanup_enabled}\n")
            f.write("=" * 50 + "\n\n")

            if config:
                f.write("CONFIGURATION:\n")
                f.write(json.dumps(config, indent=2))
                f.write("\n\n")

    def log_request_response(
        self,
        step: str,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
        endpoint: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Log a complete API interaction in a single step"""
        timestamp = datetime.now().isoformat()

        if not url and method and endpoint and self.api_client:
            url = f"{method} {self.api_client.base_url}{endpoint}"
        elif not url and self.api_client and hasattr(self.api_client, "get_last_request_info"):
            url = self.api_client.get_last_request_info()

        log_entry = {
            "step": step,
            "timestamp": timestamp,
            "request_data": request_data,
            "response_data": response_data,
            "error": error,
            "url": url,
            "headers": headers,
        }
        self.log_entries.append(log_entry)

        with open(self.debug_file, "a", encoding="utf-8") as f:
            f.write(f"STEP: {step}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 60 + "\n\n")

            if url:
                f.write(f"REQUEST: {url}\n\n")

            if headers:
                f.write("REQUEST HEADERS:\n")
                f.write(json.dumps(headers, indent=2))
                f.write("\n\n")

            if request_data:
                f.write("REQUEST DATA:\n")
                f.write(json.dumps(request_data, indent=2))
                f.write("\n\n")

            if response_data:
                f.write("RESPONSE DATA:\n")
                f.write(json.dumps(response_data, indent=2))
                f.write("\n\n")

            if error:
                f.write("ERROR:\n")
                f.write(error)
                f.write("\n\n")

            f.write("=" * 60 + "\n\n")

    def log_info(self, message: str, *args):
        if args:
            try:
                text = message % args
            except TypeError:
                text = message
        else:
            text = message
        timestamp = datetime.now().isoformat()
        with open(self.debug_file, "a", encoding="utf-8") as f:
            f.write(f"INFO: {text}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 60 + "\n\n")

    def log_test_summary(self, test_passed=None, error_message: Optional[str] = None):
        if isinstance(test_passed, str):
            test_passed_bool = "completed successfully" in test_passed.lower()
            if (
                not test_passed_bool
                and error_message is None
                and any(
                    keyword in test_passed.lower()
                    for keyword in ["error", "failed", "exception", "fatal"]
                )
            ):
                error_message = test_passed
        else:
            test_passed_bool = test_passed if test_passed is not None else (self.test_exception is None)

        with open(self.debug_file, "a", encoding="utf-8") as f:
            f.write("TEST SUMMARY\n")
            f.write("=" * 50 + "\n")
            f.write(f"Test: {self.test_name}\n")
            f.write(f"Status: {'PASSED' if test_passed_bool else 'FAILED'}\n")
            f.write(f"Total Log Entries: {len(self.log_entries)}\n")
            f.write(f"Debug File: {self.debug_file}\n")
            f.write(f"Cleanup Enabled: {self.cleanup_enabled}\n")
            f.write("=" * 50 + "\n\n")

            if error_message:
                if not test_passed_bool:
                    f.write(f"ERROR MESSAGE: {error_message}\n\n")
                else:
                    f.write(f"MESSAGE: {error_message}\n\n")

            f.write("LOG ENTRIES SUMMARY:\n")
            for i, entry in enumerate(self.log_entries, 1):
                f.write(f"{i}. {entry['step']} ({entry['timestamp']})\n")
                if entry["request_data"]:
                    f.write("   - Request data logged\n")
                if entry["response_data"]:
                    f.write("   - Response data logged\n")
                if entry["error"]:
                    f.write("   - Error logged\n")
                f.write("\n")

    def set_test_exception(self, exception: Exception):
        self.test_exception = exception

    def cleanup_if_passed(self):
        test_passed = self.test_exception is None
        error_message = str(self.test_exception) if self.test_exception else None
        self.log_test_summary(test_passed, error_message)

        if test_passed and self.cleanup_enabled:
            try:
                if os.path.exists(self.debug_file):
                    os.remove(self.debug_file)
                    logger.info("Cleaned up debug file: %s", self.debug_file)
            except OSError as e:
                logger.warning("Failed to clean up debug file %s: %s", self.debug_file, e)
        elif not test_passed:
            logger.info("Preserving debug file for failed test: %s", self.debug_file)


def create_debug_logger(
    test_name: str,
    *,
    feature_id: str,
    debug_dir: str = "debugging",
    api_client=None,
) -> DebugLogger:
    return DebugLogger(test_name, feature_id=feature_id, debug_dir=debug_dir, api_client=api_client)


def log_global_environment_info():
    logger.info("=== GLOBAL ENVIRONMENT INFO ===")
    logger.info("Python version: %s", os.sys.version)
    logger.info("Working directory: %s", os.getcwd())
    logger.info("CLEANUP_DEBUG_FILES: %s", os.getenv("CLEANUP_DEBUG_FILES", "false"))
    logger.info("=" * 40)
