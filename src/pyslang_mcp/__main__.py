"""CLI entrypoint for pyslang-mcp."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from .server import create_server


def main(argv: Sequence[str] | None = None) -> int:
    """Run the MCP server."""

    parser = argparse.ArgumentParser(description="Run the pyslang-mcp server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help=(
            "MCP transport to use. `stdio` is the default. `streamable-http` is "
            "experimental and requires --experimental-enable-http."
        ),
    )
    parser.add_argument(
        "--experimental-enable-http",
        action="store_true",
        help=(
            "Allow the experimental local streamable-http transport. This mode is not "
            "a production hosted deployment and does not add workspace isolation."
        ),
    )
    parser.add_argument(
        "--http-host",
        default="127.0.0.1",
        help="Host interface for experimental streamable-http. Default: 127.0.0.1.",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8000,
        help="TCP port for experimental streamable-http. Default: 8000.",
    )
    parser.add_argument(
        "--http-public-url",
        default=None,
        help=(
            "Public URL used in HTTP auth metadata. Defaults to http://127.0.0.1:<port> "
            "when streamable-http binds to 0.0.0.0."
        ),
    )
    parser.add_argument(
        "--http-require-bearer-token",
        action="store_true",
        help=(
            "Require PYSLANG_MCP_HTTP_BEARER_TOKEN for experimental streamable-http. "
            "Use this for the internal Docker Compose deployment."
        ),
    )
    args = parser.parse_args(argv)
    if args.transport == "streamable-http" and not args.experimental_enable_http:
        parser.error(
            "`streamable-http` is experimental and requires --experimental-enable-http. "
            "Use the default `stdio` transport for normal local MCP clients."
        )
    http_bearer_token = os.environ.get("PYSLANG_MCP_HTTP_BEARER_TOKEN")
    if args.transport != "streamable-http":
        create_server().run(args.transport)
        return 0
    if args.http_require_bearer_token and not http_bearer_token:
        parser.error(
            "`--http-require-bearer-token` requires PYSLANG_MCP_HTTP_BEARER_TOKEN "
            "to be set in the environment."
        )
    create_server(
        host=args.http_host,
        port=args.http_port,
        http_bearer_token=http_bearer_token,
        http_public_url=args.http_public_url,
    ).run(args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
