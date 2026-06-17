"""
Single source of truth for UAT layout paths (``design/`` + ``execution/`` under UAT root).

UAT root defaults to ``<git-root>/uat/`` in mixed repos. Override with ``UAT_ROOT``,
``.zuora-uat.yaml`` (``root: uat`` or ``root: .``), or ``.zuora-uat-root`` marker.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from tests.test_utils.uat_root import find_git_root, find_uat_root


def find_repo_root(start: Path | None = None) -> Path:
    """Return the UAT workspace root (contains ``design/`` + ``execution/``)."""
    return find_uat_root(start=start or Path(__file__))


def execution_root(repo: Path | None = None) -> Path:
    """Root directory for pytest, config, scripts, debugging, reports, tests."""
    r = repo or find_repo_root()
    return r / "execution"


def design_root(repo: Path | None = None) -> Path:
    """Root directory for testmatrix, testplan, design-side ai_test_docs."""
    r = repo or find_repo_root()
    return r / "design"


def testmatrix_dir(repo: Path | None = None) -> Path:
    return design_root(repo) / "testmatrix"


def testplan_dir(repo: Path | None = None) -> Path:
    return design_root(repo) / "testplan"


def test_scenarios_dir(repo: Path | None = None) -> Path:
    """``execution/tests/test_scenarios/`` — per-feature pytest + UI doc folders."""
    return execution_root(repo) / "tests" / "test_scenarios"


_TR_INDEX_RE = re.compile(r"^[Tt][Rr]?(\d+)$")
_TR_FILENAME_RE = re.compile(r"^tr(\d+)_test_design\.md$")


def _normalize_tr_number(tr_index: str) -> int:
    """Accept ``TR1``, ``tr1``, or ``1`` and return the integer TR number."""
    s = (tr_index or "").strip()
    if not s:
        raise ValueError("tr_index must be non-empty")
    m = _TR_INDEX_RE.match(s)
    if m:
        return int(m.group(1))
    if s.isdigit():
        return int(s)
    raise ValueError(f"Unrecognized tr_index: {tr_index!r}; expected forms TR1, tr1, or 1")


def resolve_feature_testplan_dir(feature: str, repo: Path | None = None) -> Path:
    """Return the per-feature test-plan directory under ``design/testplan/``.

    Layout (post-refactor): ``design/testplan/<...feature...>_Test_Plan/``
    containing ``Test_Plan_Overview.md`` plus ``tr{n}_test_design.md`` files.

    Matching mirrors the legacy file glob ``*{feature}*_Test_Plan.md`` but
    against **directories**. Fails fast on 0 or >1 matches so callers never
    silently pick a stale candidate.
    """
    base = testplan_dir(repo)
    feat = (feature or "").strip()
    if not feat:
        raise ValueError("feature must be non-empty")
    candidates = sorted(p for p in base.glob(f"*{feat}*_Test_Plan") if p.is_dir())
    if not candidates:
        raise FileNotFoundError(
            f"No test-plan directory matching '*{feat}*_Test_Plan' under {base}"
        )
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        raise ValueError(
            f"Multiple test-plan directories matched '*{feat}*_Test_Plan': {names}"
        )
    return candidates[0]


def resolve_tr_test_design_path(
    feature: str, tr_index: str, repo: Path | None = None
) -> Path:
    """Return ``<feature_testplan_dir>/tr{n}_test_design.md`` for the given TR."""
    n = _normalize_tr_number(tr_index)
    return resolve_feature_testplan_dir(feature, repo) / f"tr{n}_test_design.md"


def testplan_overview_path(feature: str, repo: Path | None = None) -> Path:
    """Return ``<feature_testplan_dir>/Test_Plan_Overview.md`` for the feature."""
    return resolve_feature_testplan_dir(feature, repo) / "Test_Plan_Overview.md"


def list_tr_test_design_files(feature: str, repo: Path | None = None) -> list[Path]:
    """List ``tr{n}_test_design.md`` files under a feature folder, sorted by TR number."""
    folder = resolve_feature_testplan_dir(feature, repo)
    pairs: list[tuple[int, Path]] = []
    for p in folder.glob("tr*_test_design.md"):
        m = _TR_FILENAME_RE.match(p.name)
        if m:
            pairs.append((int(m.group(1)), p))
    pairs.sort(key=lambda t: t[0])
    return [p for _, p in pairs]


def resolve_feature_scenario_dir(feature: str, repo: Path | None = None) -> Path:
    """Resolve ``execution/tests/test_scenarios/test_<...>/`` for a feature stem or substring.

    Matching order (aligned with ``discover_groups.find_test_folder`` intent, but **strict**):

    1. Exact directory ``test_{feature.lower()}`` when present.
    2. Else unique **prefix** match: ``test_*`` folder core (without ``test_``) where
       ``norm.startswith(folder_core)`` or ``folder_core.startswith(norm)``.
    3. Else unique **substring** match: ``norm in folder_name.lower()``.

    Raises ``FileNotFoundError`` if nothing matches, ``ValueError`` if multiple
    directories tie at a tier (callers must disambiguate the **feature** string).
    """
    scenarios_dir = test_scenarios_dir(repo)
    if not scenarios_dir.is_dir():
        raise FileNotFoundError(f"No test_scenarios directory at {scenarios_dir}")
    feat = (feature or "").strip()
    if not feat:
        raise ValueError("feature must be non-empty")
    norm = feat.lower()

    exact = scenarios_dir / f"test_{norm}"
    if exact.is_dir():
        return exact

    prefix_matches: list[Path] = []
    for d in sorted(scenarios_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("test_"):
            continue
        folder_core = d.name[5:]
        if norm.startswith(folder_core) or folder_core.startswith(norm):
            prefix_matches.append(d)
    if len(prefix_matches) > 1:
        names = ", ".join(p.name for p in prefix_matches)
        raise ValueError(
            f"Multiple scenario directories matched feature {feat!r} (prefix tier): {names}"
        )
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    substr_matches = sorted(
        d
        for d in scenarios_dir.iterdir()
        if d.is_dir() and d.name.startswith("test_") and norm in d.name.lower()
    )
    if len(substr_matches) > 1:
        names = ", ".join(p.name for p in substr_matches)
        raise ValueError(
            f"Multiple scenario directories matched feature {feat!r} (substring tier): {names}"
        )
    if len(substr_matches) == 1:
        return substr_matches[0]

    raise FileNotFoundError(
        f"No test_scenarios folder found for feature {feat!r} under {scenarios_dir}"
    )


def resolve_ui_steps_doc_path(
    feature: str, tr_index: str, repo: Path | None = None
) -> Path:
    """Return ``<scenario_dir>/ui_steps_tr{n}.md`` for the given TR."""
    n = _normalize_tr_number(tr_index)
    path = resolve_feature_scenario_dir(feature, repo) / f"ui_steps_tr{n}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Missing UI test doc: {path}")
    return path


def resolve_api_test_script_path(
    feature: str, tr_index: str, repo: Path | None = None
) -> Path:
    """Return the single ``*_tr{n}_api.py`` under the feature scenario directory."""
    n = _normalize_tr_number(tr_index)
    scenario = resolve_feature_scenario_dir(feature, repo)
    matches = sorted(scenario.glob(f"*_tr{n}_api.py"))
    if not matches:
        raise FileNotFoundError(f"No *_tr{n}_api.py under {scenario}")
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise ValueError(
            f"Multiple API test scripts for TR{n} in {scenario}: {names}"
        )
    return matches[0]


def design_ai_test_docs_dir(repo: Path | None = None) -> Path:
    return design_root(repo) / "ai_test_docs"


def execution_ai_test_docs_dir(repo: Path | None = None) -> Path:
    return execution_root(repo) / "ai_test_docs"


def debugging_dir(repo: Path | None = None) -> Path:
    return execution_root(repo) / "debugging"


def reports_dir(repo: Path | None = None) -> Path:
    return execution_root(repo) / "reports"


def default_test_config_path(repo: Path | None = None) -> str:
    """Default tenant config path (absolute). Prefers ``test_config.local.yaml``."""
    config_dir = execution_root(repo) / "config"
    local = config_dir / "test_config.local.yaml"
    if local.is_file():
        return str(local)
    return str(config_dir / "test_config.yaml")


def default_debugging_relative() -> str:
    """Path segment relative to execution root (for docstrings / UI hints)."""
    return "debugging"


def resolve_debugging_dir(debug_dir: str | None = None, repo: Path | None = None) -> str:
    """Resolve debugging output directory to an absolute path."""
    if debug_dir and os.path.isabs(debug_dir):
        return debug_dir
    ex = execution_root(repo)
    if not debug_dir:
        return str(ex / "debugging")
    norm = debug_dir.replace("\\", "/").strip("/")
    if norm.startswith("execution/"):
        norm = norm[len("execution/") :]
    if not norm or norm == "debugging":
        return str(ex / "debugging")
    return str(ex / norm)
