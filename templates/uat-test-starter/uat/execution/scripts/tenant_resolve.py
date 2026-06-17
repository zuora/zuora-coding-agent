#!/usr/bin/env python3
"""Layered tenant resolution for zuora-uat verify/run (mcp default)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "tests"))

from test_utils.uat_root import find_git_root, find_uat_root  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None


def derive_ui_base_url(api_base_url: str) -> str:
    url = api_base_url.rstrip("/")
    url = re.sub(r"^https?://rest[-.]?", "https://", url)
    url = re.sub(r"^https?://", "", url)
    host = url.split("/")[0]
    if host.startswith("rest-"):
        host = host[5:]
    elif host.startswith("rest."):
        host = host[5:]
    return f"https://{host}/apps"


def load_yaml(path: Path) -> dict | None:
    if not path.is_file() or yaml is None:
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def mcp_env_config() -> dict | None:
    base = os.environ.get("ZUORA_BASE_URL", "").strip()
    client_id = os.environ.get("ZUORA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ZUORA_CLIENT_SECRET", "").strip()
    bearer = os.environ.get("ZUORA_BEARER_TOKEN", "").strip()
    if bearer and base:
        return {
            "environment": "mcp",
            "api_base_url": base,
            "ui_base_url": derive_ui_base_url(base),
            "authentication": {"type": "bearer", "token": bearer},
            "has_ui_auth": False,
        }
    if base and client_id and client_secret:
        return {
            "environment": "mcp",
            "api_base_url": base,
            "ui_base_url": derive_ui_base_url(base),
            "authentication": {
                "type": "oauth",
                "client_id": client_id,
                "client_secret": client_secret,
                "token_endpoint": "/oauth/token",
                "grant_type": "client_credentials",
            },
            "has_ui_auth": False,
        }
    return None


def resolve(uat_root: Path, environment: str, tenant_suffix: str | None) -> dict:
    local_path = uat_root / "execution" / "config" / "test_config.local.yaml"
    committed_path = uat_root / "execution" / "config" / "test_config.yaml"

    if environment == "mcp":
        mcp = mcp_env_config()
        if mcp:
            return mcp

    for cfg_path in (local_path, committed_path):
        cfg = load_yaml(cfg_path)
        if not cfg:
            continue
        envs = cfg.get("test_environments", {})
        key = environment
        if key in ("staging", "preprod") and key not in envs:
            mcp = mcp_env_config()
            if mcp:
                return {**mcp, "warning": f"environment '{key}' not in config; using mcp"}
            raise SystemExit(f"environment '{key}' not in test_config; use environment=mcp or add the key")
        if key == "mcp":
            mcp = mcp_env_config()
            if mcp:
                return mcp
            default = cfg.get("default_environment", "staging")
            key = default
        if tenant_suffix and key in envs:
            suffixed = f"{key}_{tenant_suffix}"
            if suffixed in envs:
                key = suffixed
        if key not in envs:
            raise SystemExit(f"environment '{environment}' not found in {cfg_path}")
        env = envs[key]
        has_ui = bool(env.get("ui_authentication") or cfg.get("ui_authentication"))
        return {
            "environment": key,
            "api_base_url": env.get("api_base_url", env.get("rest_url", "")),
            "ui_base_url": env.get("ui_base_url", ""),
            "authentication": env.get("authentication", {}),
            "has_ui_auth": has_ui,
            "test_data": env.get("test_data", cfg.get("test_data", {})),
            "config_path": str(cfg_path),
        }

    mcp = mcp_env_config()
    if mcp:
        return mcp
    raise SystemExit(
        "No tenant config found. Set ZUORA_BASE_URL + ZUORA_CLIENT_ID/SECRET (zuora-mcp) "
        "or add uat/execution/config/test_config.yaml"
    )


def scaffold_local(uat_root: Path) -> Path | None:
    mcp = mcp_env_config()
    if not mcp:
        return None
    target = uat_root / "execution" / "config" / "test_config.local.yaml"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "default_environment": "mcp",
        "test_environments": {
            "mcp": {
                "api_base_url": mcp["api_base_url"],
                "ui_base_url": mcp["ui_base_url"],
                "authentication": mcp["authentication"],
            }
        },
    }
    target.write_text(
        "# Auto-scaffolded from zuora-mcp env on first tenant touch.\n"
        + "# Add ui_authentication here for UI tests.\n"
        + yaml.safe_dump(content, sort_keys=False),
        encoding="utf-8",
    )
    return target


def main():
    parser = argparse.ArgumentParser(description="Resolve tenant for UAT verify/run")
    parser.add_argument("--git-root", default=None, help="Git project root")
    parser.add_argument("--repo-root", default=None, help="Deprecated: use --git-root")
    parser.add_argument("--uat-root", default=None, help="UAT workspace root override")
    parser.add_argument("--environment", default="mcp")
    parser.add_argument("--tenant-suffix", default=None)
    parser.add_argument("--scaffold-local", action="store_true")
    args = parser.parse_args()

    git_arg = args.git_root or args.repo_root
    git = Path(git_arg).resolve() if git_arg else find_git_root()
    uat = Path(args.uat_root).resolve() if args.uat_root else find_uat_root(git)

    if args.scaffold_local:
        scaffold_local(uat)
    result = resolve(uat, args.environment, args.tenant_suffix)
    result["uat_root"] = str(uat)
    print(json.dumps(result, indent=2))
    if result.get("environment"):
        print(f"export TEST_ENVIRONMENT={result['environment']}", file=sys.stderr)


if __name__ == "__main__":
    main()
