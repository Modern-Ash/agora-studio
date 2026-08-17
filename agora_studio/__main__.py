"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys

from .server import StartupError, create_server, server_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local, read-only Agora Studio server")
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
