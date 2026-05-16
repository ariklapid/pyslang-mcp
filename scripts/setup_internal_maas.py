#!/usr/bin/env python3
"""Create the Docker Compose .env file for internal MaaS bring-up."""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = REPO_ROOT / "deploy" / "internal" / ".env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create deploy/internal/.env for the self-hosted pyslang-mcp service."
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Absolute or relative path to the RTL checkout on this internal server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Host port to bind on 127.0.0.1. Default: 8000.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Path to write. Default: deploy/internal/.env.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing env file and generate a new token.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    env_file = args.env_file.expanduser().resolve()

    if not workspace.exists():
        raise SystemExit(f"Workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise SystemExit(f"Workspace is not a directory: {workspace}")
    if args.port < 1 or args.port > 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if env_file.exists() and not args.force:
        raise SystemExit(f"{env_file} already exists. Use --force to replace it.")

    token = secrets.token_urlsafe(32)
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        "\n".join(
            [
                f"PYSLANG_MCP_WORKSPACE={workspace.as_posix()}",
                f"PYSLANG_MCP_HTTP_PORT={args.port}",
                f"PYSLANG_MCP_HTTP_BEARER_TOKEN={token}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    rel_env = env_file.relative_to(REPO_ROOT) if env_file.is_relative_to(REPO_ROOT) else env_file
    print(f"Wrote {rel_env}")
    print()
    print("Start the internal service:")
    print("  cd deploy/internal")
    print("  docker compose up -d --build")
    print()
    print("Use this endpoint from a client that can reach the server:")
    print(f"  http://127.0.0.1:{args.port}/mcp")
    print()
    print("Bearer token:")
    print(f"  {token}")
    print()
    print("In tool calls, use this project_root inside the container:")
    print("  /workspace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
