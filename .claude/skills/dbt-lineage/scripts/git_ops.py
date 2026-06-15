"""Git operations: detect the compare branch, materialize it via worktree,
compile dbt inside the worktree, snapshot the manifest into our cache, and
always clean up the worktree (try/finally — equivalent of a bash trap on EXIT).
"""
from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_FILENAME = "config.yml"


@dataclass
class LineageConfig:
    compare_branch: str

    @classmethod
    def load_or_init(cls, skill_dir: Path, project_root: Path) -> "LineageConfig":
        config_path = skill_dir / CONFIG_FILENAME
        if config_path.exists():
            with config_path.open() as f:
                data = yaml.safe_load(f) or {}
            if data.get("compare_branch"):
                return cls(compare_branch=data["compare_branch"])

        detected = detect_default_branch(project_root)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w") as f:
            yaml.safe_dump({"compare_branch": detected}, f)
        return cls(compare_branch=detected)


def _git(project_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed:\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def detect_default_branch(project_root: Path) -> str:
    """Resolve origin/HEAD → 'main' / 'master' / 'develop' / etc.

    Falls back: 'main' if it exists locally, then 'master', then HEAD's name.
    """
    head = _git(project_root, "symbolic-ref", "refs/remotes/origin/HEAD", check=False)
    if head:
        return head.split("/")[-1]

    for candidate in ("main", "master", "develop"):
        if _git(project_root, "rev-parse", "--verify", candidate, check=False):
            return candidate

    return _git(project_root, "rev-parse", "--abbrev-ref", "HEAD")


def branch_sha(project_root: Path, branch: str) -> str:
    """Resolve `origin/<branch>` if it exists, else local `<branch>`."""
    sha = _git(project_root, "rev-parse", f"origin/{branch}", check=False)
    if sha:
        return sha
    return _git(project_root, "rev-parse", branch)


def current_sha(project_root: Path) -> str:
    return _git(project_root, "rev-parse", "HEAD")


@contextlib.contextmanager
def temp_worktree(project_root: Path, branch: str):
    """Yield a temporary worktree checked out to `branch`. Always cleaned up.

    Equivalent of a bash `trap 'git worktree remove ...' EXIT`.
    """
    worktree_dir = Path(tempfile.mkdtemp(prefix=f"dbt-lineage-{branch.replace('/', '_')}-"))
    # mkdtemp creates the dir; git worktree add needs it to not exist.
    worktree_dir.rmdir()

    ref = f"origin/{branch}"
    if not _git(project_root, "rev-parse", "--verify", ref, check=False):
        ref = branch

    try:
        _git(project_root, "worktree", "add", "--detach", str(worktree_dir), ref)
        yield worktree_dir
    finally:
        # Always try to remove, even if the body raised.
        _git(project_root, "worktree", "remove", "--force", str(worktree_dir), check=False)
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)


def compile_branch_manifest(project_root: Path, branch: str, cache_dir: Path) -> Path:
    """Materialize `branch` via worktree, run dbt compile, snapshot the manifest.

    Cache key: `<branch>_<sha>.json`. If that file exists, reuse it (no recompile).
    Returns the cached manifest path.
    """
    from .manifest import compile_current_branch  # local import to avoid cycle

    cache_dir.mkdir(parents=True, exist_ok=True)
    sha = branch_sha(project_root, branch)
    cached = cache_dir / f"{branch.replace('/', '_')}_{sha}.json"
    if cached.exists():
        return cached

    with temp_worktree(project_root, branch) as worktree:
        # The worktree shares .git with project_root but needs its own dbt_packages
        # and target. Symlinking dbt_packages avoids re-running `dbt deps`.
        src_packages = project_root / "dbt_packages"
        if src_packages.exists():
            dst_packages = worktree / "dbt_packages"
            if not dst_packages.exists():
                dst_packages.symlink_to(src_packages.resolve())

        worktree_target = worktree / "target_lineage"
        manifest_path = compile_current_branch(worktree, target_path=worktree_target)
        shutil.copy2(manifest_path, cached)

    return cached
