"""Bounded, read-only Git history for one registered repository file."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Sequence


GitRunner = Callable[..., subprocess.CompletedProcess[str]]
_SHA = re.compile(r"^[0-9a-f]{40}$")


class GitReadError(Exception):
    """A safe Git availability or validation failure."""


@dataclass(frozen=True)
class GitOutput:
    stdout: str
    truncated: bool


class GitHistoryReader:
    """Run a fixed read-only Git subset for one canonical repository path."""

    def __init__(
        self,
        executable: str = "git",
        runner: GitRunner = subprocess.run,
        timeout_seconds: float = 5.0,
        max_output_bytes: int = 262_144,
        max_revisions: int = 80,
    ) -> None:
        self._executable = executable
        self._runner = runner
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._max_revisions = max_revisions

    @staticmethod
    def resolve_repo_file(repository: Path, uri: str) -> tuple[Path, str]:
        """Resolve one regular ``repo://`` file without allowing escapes."""
        if not isinstance(uri, str) or not uri.startswith("repo://"):
            raise GitReadError("the registered specification is not a repository URI")
        relative = uri.removeprefix("repo://")
        if not relative or relative.startswith("/") or "\\" in relative:
            raise GitReadError("the registered specification path is invalid")
        path = Path(relative)
        if any(part in ("", ".", "..") for part in path.parts):
            raise GitReadError("the registered specification path contains traversal components")
        try:
            root = repository.resolve(strict=True)
            unresolved = root / path
            cursor = root
            for part in path.parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise GitReadError("the registered specification path uses a symbolic link")
            target = unresolved.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise GitReadError("the registered specification file is unavailable") from error
        try:
            target.relative_to(root)
        except ValueError as error:
            raise GitReadError("the registered specification escapes the repository") from error
        if target.is_symlink() or not target.is_file():
            raise GitReadError("the registered specification is not a regular repository file")
        return target, target.relative_to(root).as_posix()

    def _environment(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LC_ALL": "C",
            "LANG": "C",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
        }

    def _run(self, repository: Path, arguments: Sequence[str], expected_codes: tuple[int, ...] = (0,)) -> GitOutput:
        command = [self._executable, "-C", str(repository), *arguments]
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
                shell=False,
                env=self._environment(),
            )
        except FileNotFoundError as error:
            raise GitReadError("Git is not available") from error
        except subprocess.TimeoutExpired as error:
            raise GitReadError("the bounded Git read timed out") from error
        except OSError as error:
            raise GitReadError("the bounded Git read could not start") from error
        if completed.returncode not in expected_codes:
            raise GitReadError(f"Git could not read the registered specification (exit code {completed.returncode})")
        encoded = completed.stdout.encode("utf-8", errors="replace")
        truncated = len(encoded) > self._max_output_bytes
        if truncated:
            encoded = encoded[: self._max_output_bytes]
        return GitOutput(encoded.decode("utf-8", errors="replace"), truncated)

    def history(self, repository: Path, relative_path: str) -> dict[str, object]:
        """Return bounded commit nodes plus a distinct working-tree revision."""
        log = self._run(repository, [
            "log", "--follow", f"--max-count={self._max_revisions}",
            "--format=%H%x1f%aI%x1f%an%x1f%s", "--", relative_path,
        ])
        revisions: list[dict[str, object]] = []
        for line in log.stdout.splitlines():
            fields = line.split("\x1f", 3)
            if len(fields) != 4 or not _SHA.fullmatch(fields[0]):
                continue
            sha, timestamp, author, subject = fields
            revisions.append({
                "id": sha,
                "kind": "commit",
                "sha": sha,
                "short_sha": sha[:10],
                "timestamp": timestamp,
                "author": author,
                "subject": subject,
                "uncommitted": False,
                "approved": None,
            })

        status = self._run(repository, ["status", "--porcelain=v1", "--", relative_path])
        working = bool(status.stdout.strip())
        if working:
            revisions.insert(0, {
                "id": "working-tree",
                "kind": "working-tree",
                "sha": None,
                "short_sha": "WORKTREE",
                "timestamp": None,
                "author": None,
                "subject": "Modified, uncommitted specification",
                "uncommitted": True,
                "approved": False,
            })
        return {
            "available": True,
            "path": relative_path,
            "revisions": revisions,
            "has_history": bool(revisions and any(not item["uncommitted"] for item in revisions)),
            "working_tree": working,
            "truncated": log.truncated or status.truncated or len(revisions) >= self._max_revisions,
        }

    def detail(self, repository: Path, relative_path: str, revision: str) -> dict[str, object]:
        """Return a capped plain-text diff only for a known commit or working tree."""
        if revision == "working-tree":
            status = self._run(repository, ["status", "--porcelain=v1", "--", relative_path])
            if status.stdout.startswith("??"):
                output = self._run(
                    repository,
                    ["diff", "--no-index", "--no-ext-diff", "--unified=3", "--", "/dev/null", relative_path],
                    expected_codes=(0, 1),
                )
            else:
                output = self._run(repository, ["diff", "--no-ext-diff", "--unified=3", "--", relative_path])
        elif _SHA.fullmatch(revision):
            output = self._run(repository, ["show", "--format=", "--no-ext-diff", "--unified=3", revision, "--", relative_path])
        else:
            raise GitReadError("the requested revision identifier is invalid")
        lines = output.stdout.splitlines()
        line_limit = 600
        clipped = lines[:line_limit]
        headings = []
        for line in clipped:
            candidate = line[1:] if line[:1] in ("+", "-") else ""
            if candidate.lstrip().startswith("#"):
                headings.append(candidate.strip()[:200])
        return {
            "revision": revision,
            "text": "\n".join(clipped),
            "line_count": len(lines),
            "changed_headings": list(dict.fromkeys(headings))[:40],
            "truncated": output.truncated or len(lines) > line_limit,
        }
