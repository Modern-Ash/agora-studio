"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .server import StartupError, create_server, server_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agora-studio", description="Run the local-first Agora Studio control plane"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--port", type=int, default=7357, help="loopback port (default: 7357)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        server = create_server(args.port)
    except StartupError as error:
        print(f"Agora Studio failed to start: {error}", file=sys.stderr)
        return 1

    print(f"Agora Studio is ready at {server_url(server)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
