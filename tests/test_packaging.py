from __future__ import annotations

import tomllib
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from agora_studio import __version__
from agora_studio.__main__ import build_parser


class PackagingContractTests(unittest.TestCase):
    root = Path(__file__).parents[1]

    def test_package_version_is_the_cli_version(self) -> None:
        output = StringIO()
        with self.assertRaises(SystemExit) as raised, redirect_stdout(output):
            build_parser().parse_args(["--version"])

        self.assertEqual(0, raised.exception.code)
        self.assertEqual(f"agora-studio {__version__}\n", output.getvalue())

    def test_packaging_reads_the_single_source_version(self) -> None:
        metadata = tomllib.loads((self.root / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(["version"], metadata["project"]["dynamic"])
        self.assertEqual(
            "agora_studio.__version__",
            metadata["tool"]["setuptools"]["dynamic"]["version"]["attr"],
        )

    def test_open_source_maintenance_files_and_packaged_assets_exist(self) -> None:
        for relative in (
            "LICENSE",
            "CONTRIBUTING.md",
            "AGENTS.md",
            ".github/workflows/ci.yml",
            "agora_studio/static/index.html",
            "agora_studio/static/agora-mark.png",
            "agora_studio/static/dashboard-model.js",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((self.root / relative).is_file())
        self.assertFalse((self.root / "q").exists())
        self.assertFalse((self.root / "q:q").exists())


if __name__ == "__main__":
    unittest.main()
