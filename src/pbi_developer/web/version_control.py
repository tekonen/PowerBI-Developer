"""Git-backed version control for dashboard output.

Wraps git operations on the PBIR output directory. Each pipeline run or
refinement creates a commit. Users can undo/redo and push to a Bitbucket remote.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from pbi_developer.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VersionInfo:
    """Metadata for a single version (git commit)."""

    commit_hash: str
    short_hash: str
    message: str
    timestamp: str
    author: str = ""
    run_id: str = ""


class VersionManager:
    """Git-backed version control for generated PBIR output."""

    def __init__(self, repo_path: Path, remote_url: str | None = None):
        self.repo_path = repo_path
        self.repo_path.mkdir(parents=True, exist_ok=True)
        self._redo_stack: list[str] = []
        self._init_repo()
        if remote_url:
            self.set_remote(remote_url)

    def _init_repo(self) -> None:
        """Initialize git repo if not already initialized."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            self._git("init")
            self._git("config", "user.email", "pbi-developer@local")
            self._git("config", "user.name", "PBI Developer")
            self._git("config", "commit.gpgsign", "false")
            # Create initial commit on empty repo
            readme = self.repo_path / "README.md"
            if not readme.exists():
                readme.write_text("# Dashboard Versions\n\nManaged by AI Power BI Developer.\n")
            self._git("add", ".")
            self._git("commit", "-m", "Initial commit")
            logger.info(f"Initialized version control at {self.repo_path}")

    def _git(self, *args: str) -> str:
        """Run a git command in the repo directory."""
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 and "nothing to commit" not in result.stdout + result.stderr:
            logger.warning(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def commit_version(self, message: str, run_id: str = "") -> str | None:
        """Commit current state as a new version.

        Returns the commit hash, or None if nothing to commit.
        """
        self._git("add", ".")

        # Check if there are changes to commit
        status = self._git("status", "--porcelain")
        if not status:
            logger.info("No changes to commit")
            return None

        full_message = message
        if run_id:
            full_message = f"[{run_id}] {message}"

        self._git("commit", "-m", full_message)
        commit_hash = self._git("rev-parse", "HEAD")
        self._redo_stack.clear()
        logger.info(f"Committed version {commit_hash[:8]}: {message}")
        return commit_hash

    def list_versions(self, limit: int = 50) -> list[VersionInfo]:
        """List version history (most recent first)."""
        fmt = "%H|%h|%s|%ai|%an"
        log_output = self._git("log", f"--format={fmt}", f"-{limit}")
        if not log_output:
            return []

        versions = []
        for line in log_output.splitlines():
            parts = line.split("|", 4)
            if len(parts) >= 5:
                # Extract run_id from message if present
                message = parts[2]
                run_id = ""
                if message.startswith("[") and "]" in message:
                    run_id = message[1 : message.index("]")]
                    message = message[message.index("]") + 2 :]

                versions.append(
                    VersionInfo(
                        commit_hash=parts[0],
                        short_hash=parts[1],
                        message=message,
                        timestamp=parts[3],
                        author=parts[4],
                        run_id=run_id,
                    )
                )
        return versions

    def get_current_version(self) -> VersionInfo | None:
        """Get the current HEAD version."""
        versions = self.list_versions(limit=1)
        return versions[0] if versions else None

    def undo(self) -> VersionInfo | None:
        """Undo to the previous version (soft checkout)."""
        current = self._git("rev-parse", "HEAD")
        # Check if HEAD~1 exists
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD~1"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning("No previous version to undo to")
            return None

        parent = result.stdout.strip()
        self._redo_stack.append(current)
        self._git("checkout", parent, "--", ".")
        self._git("reset", "HEAD")
        return self.get_current_version()

    def redo(self) -> VersionInfo | None:
        """Redo to the next version (from undo stack)."""
        if not self._redo_stack:
            logger.warning("No version to redo to")
            return None

        target = self._redo_stack.pop()
        self._git("checkout", target, "--", ".")
        self._git("reset", "HEAD")
        return self.get_current_version()

    def checkout_version(self, commit_hash: str) -> VersionInfo | None:
        """Checkout a specific version's files."""
        self._git("checkout", commit_hash, "--", ".")
        self._redo_stack.clear()
        return self.get_current_version()

    def push_to_remote(self) -> tuple[bool, str]:
        """Push all commits to the configured remote."""
        remote = self._git("remote", "get-url", "origin")
        if not remote:
            return False, "No remote configured. Set a Bitbucket repository URL in Settings."

        result = subprocess.run(
            ["git", "push", "-u", "origin", "main"],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info(f"Pushed to {remote}")
            return True, f"Pushed to {remote}"
        return False, f"Push failed: {result.stderr.strip()}"

    def set_remote(self, url: str) -> None:
        """Set or update the Bitbucket remote URL."""
        existing = self._git("remote")
        if "origin" in existing:
            self._git("remote", "set-url", "origin", url)
        else:
            self._git("remote", "add", "origin", url)
        logger.info(f"Remote set to {url}")

    def get_remote(self) -> str | None:
        """Get the current remote URL."""
        url = self._git("remote", "get-url", "origin")
        return url if url else None

    def get_diff(self, from_hash: str, to_hash: str) -> str:
        """Get the diff between two versions."""
        return self._git("diff", from_hash, to_hash)

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0
