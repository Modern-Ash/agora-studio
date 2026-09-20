"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .core import CoreReadGateway, ProjectStore, SelectionError
from .flavor import FlavorProjectorError, load_flavor_projector
from .server import StartupError, create_server, server_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agora-studio", description="Run the local-first Agora Studio control plane"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--port", type=int, default=7357, help="loopback port (default: 7357)")
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        metavar="PATH",
        help="local project directory to register (repeatable); the browser receives only an opaque id",
    )
    parser.add_argument(
        "--no-path-entry",
        action="store_true",
        help="do not let the browser open projects by typed path; only registered projects are available",
    )
    parser.add_argument(
        "--flavor-projector",
        action="append",
        default=[],
        metavar="MODULE:FACTORY",
        help="trusted local factory returning an Agora Core flavor projection provider",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        projectors = tuple(load_flavor_projector(spec) for spec in args.flavor_projector)
        store = ProjectStore(
            CoreReadGateway(flavor_projectors=projectors), allow_path_entry=not args.no_path_entry
        )
        registered = [store.register(path) for path in args.project]
        if len(registered) == 1:
            store.open(registered[0].selection_id)
        if args.no_path_entry and not registered:
            raise StartupError("--no-path-entry requires at least one --project")
        server = create_server(args.port, store)
    except (StartupError, SelectionError, FlavorProjectorError) as error:
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
