"""Load dbt manifest.json and detect the sqlglot dialect from profiles.yml.

Single source of truth for everything we read off disk that isn't a git operation.
Other modules import `load_manifest`, `detect_dialect`, `iter_sql_models`.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yaml

ADAPTER_TO_DIALECT = {
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "postgres": "postgres",
    "redshift": "redshift",
    "databricks": "databricks",
    "spark": "spark",
    "duckdb": "duckdb",
    "athena": "athena",
    "trino": "trino",
    "sqlserver": "tsql",
    "mssql": "tsql",
    "fabric": "tsql",
    "clickhouse": "clickhouse",
}


@dataclass
class ProjectContext:
    project_root: Path
    profile_name: str
    target_name: str
    adapter_type: str
    dialect: str


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or cwd) until we find a dbt_project.yml."""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "dbt_project.yml").exists():
            return candidate
    raise FileNotFoundError(
        "No dbt_project.yml found in current directory or any parent. "
        "Run this command from inside a dbt project."
    )


def _profiles_dir() -> Path:
    override = os.environ.get("DBT_PROFILES_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".dbt"


def load_dbt_project(project_root: Path) -> dict[str, Any]:
    with (project_root / "dbt_project.yml").open() as f:
        return yaml.safe_load(f)


def detect_dialect(
    project_root: Path,
    target_override: str | None = None,
    dialect_override: str | None = None,
) -> ProjectContext:
    """Resolve profile → active target → adapter type → sqlglot dialect.

    `dialect_override` short-circuits the entire chain. `target_override`
    forces a specific target within the resolved profile (matches dbt's --target).
    """
    project = load_dbt_project(project_root)
    profile_name = project["profile"]

    profiles_path = _profiles_dir() / "profiles.yml"
    if not profiles_path.exists():
        raise FileNotFoundError(
            f"profiles.yml not found at {profiles_path}. "
            "Set DBT_PROFILES_DIR or create ~/.dbt/profiles.yml."
        )
    with profiles_path.open() as f:
        profiles = yaml.safe_load(f)

    if profile_name not in profiles:
        raise KeyError(
            f"Profile '{profile_name}' (referenced by dbt_project.yml) "
            f"not found in {profiles_path}."
        )

    profile = profiles[profile_name]
    target_name = (
        target_override
        or os.environ.get("DBT_TARGET")
        or profile.get("target")
        or "default"
    )

    outputs = profile.get("outputs", {})
    if target_name not in outputs:
        raise KeyError(
            f"Target '{target_name}' not found under profile '{profile_name}'. "
            f"Available: {sorted(outputs)}"
        )

    adapter_type = outputs[target_name]["type"]

    if dialect_override:
        dialect = dialect_override
    elif adapter_type in ADAPTER_TO_DIALECT:
        dialect = ADAPTER_TO_DIALECT[adapter_type]
    else:
        raise KeyError(
            f"Unknown adapter type '{adapter_type}'. "
            f"Pass --dialect explicitly or extend ADAPTER_TO_DIALECT."
        )

    return ProjectContext(
        project_root=project_root,
        profile_name=profile_name,
        target_name=target_name,
        adapter_type=adapter_type,
        dialect=dialect,
    )


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest not found at {manifest_path}. "
            "Run `dbt compile` (or the skill's `refresh` command) first."
        )
    with manifest_path.open() as f:
        manifest = json.load(f)
    if "nodes" not in manifest:
        raise ValueError(f"Malformed manifest at {manifest_path}: missing 'nodes' key.")
    return manifest


def iter_sql_models(manifest: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield manifest nodes that are SQL models (not seeds, tests, snapshots, py models)."""
    for unique_id, node in manifest["nodes"].items():
        if node.get("resource_type") != "model":
            continue
        if node.get("language", "sql") != "sql":
            continue
        yield node


def model_by_name(manifest: dict[str, Any], name: str) -> dict[str, Any] | None:
    """Look up a model by short name (without resource_type or package prefix)."""
    for node in iter_sql_models(manifest):
        if node["name"] == name:
            return node
    return None


def models_by_unique_ids(manifest: dict[str, Any], unique_ids: list[str]) -> list[dict[str, Any]]:
    return [manifest["nodes"][uid] for uid in unique_ids if uid in manifest["nodes"]]


def resolve_dbt_binary(project_root: Path) -> tuple[str, str]:
    """Pick which `dbt` to invoke.

    Preference order:
      1. `.venv/bin/dbt` in project root        (most common — Poetry/uv/pip venv)
      2. `venv/bin/dbt`                          (alternative name)
      3. `.virtualenv/bin/dbt`                   (uncommon)
      4. `dbt` on $PATH                          (system / pipx / homebrew install)

    Returns (binary_path, source_label) where source_label is one of:
    'project-venv', 'project-venv-alt', 'project-virtualenv', 'system-path'.

    If both a project venv AND a system install exist, the project venv wins
    so dbt version matches the project's pinned `requirements*.txt`.
    """
    candidates = [
        (project_root / ".venv" / "bin" / "dbt", "project-venv"),
        (project_root / "venv" / "bin" / "dbt", "project-venv-alt"),
        (project_root / ".virtualenv" / "bin" / "dbt", "project-virtualenv"),
    ]
    for path, label in candidates:
        if path.exists():
            return str(path), label
    return "dbt", "system-path"


def compile_current_branch(project_root: Path, target_path: Path | None = None) -> Path:
    """Run `dbt compile` in the project and return the manifest.json path.

    Excludes tests by default — broken/incompatible tests shouldn't block
    lineage analysis since we only need model/source/snapshot compiled_code.

    The dbt binary is resolved via `resolve_dbt_binary` (project venv first,
    then system PATH). If both a project venv install and a CLI install
    coexist, the project venv wins so the version matches the project pin.
    """
    dbt_bin, _label = resolve_dbt_binary(project_root)
    cmd = [
        dbt_bin,
        "compile",
        "--exclude", "resource_type:test",
    ]
    if target_path:
        cmd += ["--target-path", str(target_path)]

    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"dbt compile failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )

    manifest_path = (target_path or (project_root / "target")) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"dbt compile succeeded but manifest.json not at {manifest_path}"
        )
    return manifest_path
