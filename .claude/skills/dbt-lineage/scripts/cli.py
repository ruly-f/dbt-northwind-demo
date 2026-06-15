"""CLI dispatch for the dbt-lineage skill.

Subcommands:
  refresh                              Compile current branch + cache compare branch manifest
  model    <name>  [...flags]          Model lineage (upstream/downstream)
  column   <model>.<col> [...flags]    Column lineage (forward trace)
  diff             [...flags]          Model-level diff vs compare branch
  validate                             Sanity-check manifest depends_on vs sqlglot refs

Global flags:
  --branch <name>     Override compare branch (default: from config.yml)
  --dialect <name>    Override sqlglot dialect (default: detect from profiles.yml)
  --dbt-target <name> Override dbt target when detecting dialect (default: profile's `target`)
  --format mermaid|json|tree   (default depends on command)
  --json              Shortcut for --format json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import diff as diff_mod
from . import graph as graph_mod
from . import git_ops
from . import manifest as manifest_mod
from . import model_lineage as model_mod
from . import column_lineage as column_mod
from . import visualize as viz_mod

SKILL_REL = ".claude/skills/dbt-lineage"
CACHE_REL = "target/lineage_cache"


def _resolve_paths(project_root: Path) -> tuple[Path, Path]:
    return project_root / SKILL_REL, project_root / CACHE_REL


def _load_compare_manifest(
    project_root: Path,
    branch: str,
    cache_dir: Path,
) -> dict[str, Any]:
    cached = git_ops.compile_branch_manifest(project_root, branch, cache_dir)
    return manifest_mod.load_manifest(cached)


def _load_current_manifest(project_root: Path) -> dict[str, Any]:
    target = project_root / "target" / "manifest.json"
    if not target.exists():
        # Compile if missing
        manifest_mod.compile_current_branch(project_root)
    return manifest_mod.load_manifest(target)


def cmd_refresh(args: argparse.Namespace) -> int:
    project_root = manifest_mod.find_project_root()
    skill_dir, cache_dir = _resolve_paths(project_root)
    cfg = git_ops.LineageConfig.load_or_init(skill_dir, project_root)
    branch = args.branch or cfg.compare_branch

    dbt_bin, dbt_source = manifest_mod.resolve_dbt_binary(project_root)
    result: dict[str, Any] = {
        "compare_branch": branch,
        "compare_sha": git_ops.branch_sha(project_root, branch),
        "current_sha": git_ops.current_sha(project_root),
        "dbt_binary": dbt_bin,
        "dbt_binary_source": dbt_source,
    }
    current_manifest = project_root / "target" / "manifest.json"

    # Current branch: recompile only if forced OR manifest missing.
    if args.force or not current_manifest.exists():
        try:
            current_path = manifest_mod.compile_current_branch(project_root)
            result["current_manifest"] = str(current_path)
            result["current_compiled"] = True
        except RuntimeError as e:
            result["current_manifest"] = str(current_manifest) if current_manifest.exists() else None
            result["current_compiled"] = False
            result["current_compile_error"] = str(e).splitlines()[-1] if str(e) else "unknown"
    else:
        result["current_manifest"] = str(current_manifest)
        result["current_compiled"] = False
        result["note_current"] = "reused existing target/manifest.json (pass --force to recompile)"

    # Compare branch: skip if not requested via --force AND a cache is fresh enough.
    if args.force:
        for p in cache_dir.glob(f"{branch.replace('/', '_')}_*.json"):
            p.unlink()
    try:
        compare_path = git_ops.compile_branch_manifest(project_root, branch, cache_dir)
        result["compare_manifest"] = str(compare_path)
    except (RuntimeError, FileNotFoundError) as e:
        result["compare_manifest"] = None
        result["compare_compile_error"] = str(e).splitlines()[-1] if str(e) else "unknown"

    print(json.dumps(result, indent=2))
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    project_root = manifest_mod.find_project_root()
    skill_dir, cache_dir = _resolve_paths(project_root)
    cfg = git_ops.LineageConfig.load_or_init(skill_dir, project_root)

    manifest = _load_current_manifest(project_root)
    g = graph_mod.build_dag(manifest)

    node_id = graph_mod.resolve_node_id(g, args.name)
    if node_id is None:
        _err(f"Model '{args.name}' not found in current manifest.")
        return 2

    trace = model_mod.trace_model(g, node_id, direction=args.direction, depth=args.depth)

    if args.diff:
        branch = args.branch or cfg.compare_branch
        main_manifest = _load_compare_manifest(project_root, branch, cache_dir)
        main_g = graph_mod.build_dag(main_manifest)
        main_node = graph_mod.resolve_node_id(main_g, args.name)
        if main_node is not None:
            main_trace = model_mod.trace_model(
                main_g, main_node, direction=args.direction, depth=args.depth
            )
            trace["diff_vs_branch"] = branch
            trace["diff"] = _trace_diff(main_trace, trace)
        else:
            trace["diff_vs_branch"] = branch
            trace["diff"] = {"note": f"Model not present on {branch} — net new model"}

    _emit(trace, args, mermaid_fn=lambda: viz_mod.mermaid_model_trace(g, trace),
          ascii_fn=lambda: viz_mod.ascii_model_trace(trace))
    return 0


def cmd_column(args: argparse.Namespace) -> int:
    if "." not in args.locator:
        _err("Column locator must be `<model>.<column>` (e.g. `stg_erp__orders.order_pk`)")
        return 2
    model_name, col_name = args.locator.split(".", 1)

    project_root = manifest_mod.find_project_root()
    skill_dir, _ = _resolve_paths(project_root)
    git_ops.LineageConfig.load_or_init(skill_dir, project_root)

    ctx = manifest_mod.detect_dialect(
        project_root,
        target_override=args.dbt_target,
        dialect_override=args.dialect,
    )

    manifest = _load_current_manifest(project_root)
    g = graph_mod.build_dag(manifest)

    src_id = graph_mod.resolve_node_id(g, model_name)
    if src_id is None:
        _err(f"Source model '{model_name}' not found.")
        return 2

    target_id = None
    if args.to:
        target_id = graph_mod.resolve_node_id(g, args.to)
        if target_id is None:
            _err(f"Target model '{args.to}' not found.")
            return 2

    trace = column_mod.trace_column(
        g, manifest, src_id, col_name, ctx.dialect, target_node_id=target_id
    )
    trace["dialect"] = ctx.dialect

    _emit(trace, args, mermaid_fn=lambda: viz_mod.mermaid_column_trace(trace),
          ascii_fn=lambda: viz_mod.ascii_column_trace(trace))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    project_root = manifest_mod.find_project_root()
    skill_dir, cache_dir = _resolve_paths(project_root)
    cfg = git_ops.LineageConfig.load_or_init(skill_dir, project_root)
    branch = args.branch or cfg.compare_branch

    ctx = manifest_mod.detect_dialect(
        project_root,
        target_override=args.dbt_target,
        dialect_override=args.dialect,
    )

    current = _load_current_manifest(project_root)
    main = _load_compare_manifest(project_root, branch, cache_dir)

    result = diff_mod.diff_manifests(main, current, ctx.dialect)
    result["compare_branch"] = branch
    print(json.dumps(result, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Sanity-check: compare manifest's depends_on vs sqlglot-parsed table refs
    in compiled_code. Flags hardcoded tables (refs not via {{ ref() }})."""
    import sqlglot
    from sqlglot import exp

    project_root = manifest_mod.find_project_root()
    ctx = manifest_mod.detect_dialect(
        project_root,
        target_override=args.dbt_target,
        dialect_override=args.dialect,
    )
    manifest = _load_current_manifest(project_root)

    # Build a lookup: (schema, table) → unique_id for all nodes
    schema_lookup: dict[tuple[str, str], str] = {}
    for uid, node in {**manifest.get("nodes", {}), **manifest.get("sources", {})}.items():
        sch = (node.get("schema") or "").lower()
        ident = (node.get("alias") or node.get("identifier") or node.get("name") or "").lower()
        if sch and ident:
            schema_lookup[(sch, ident)] = uid

    parse_failures = []
    hardcoded_refs = []
    matched = 0

    for node in manifest_mod.iter_sql_models(manifest):
        compiled = node.get("compiled_code") or ""
        if not compiled.strip():
            continue
        try:
            tree = sqlglot.parse_one(compiled, read=ctx.dialect)
        except Exception as e:
            parse_failures.append({"unique_id": node["unique_id"], "error": str(e)})
            continue
        if tree is None:
            continue

        declared_deps = set(node.get("depends_on", {}).get("nodes") or [])
        for tbl in tree.find_all(exp.Table):
            sch = (tbl.db or "").lower()
            ident = (tbl.name or "").lower()
            resolved = schema_lookup.get((sch, ident))
            if resolved is None:
                continue  # unknown table (could be raw source not in manifest)
            if resolved in declared_deps:
                matched += 1
            else:
                hardcoded_refs.append({
                    "model": node["unique_id"],
                    "referenced_table": f"{tbl.db}.{tbl.name}",
                    "resolved_to": resolved,
                })

    print(json.dumps({
        "models_validated": sum(1 for _ in manifest_mod.iter_sql_models(manifest)),
        "matched_edges": matched,
        "hardcoded_refs": hardcoded_refs,
        "parse_failures": parse_failures,
    }, indent=2))
    return 0


def _trace_diff(main_trace: dict[str, Any], current_trace: dict[str, Any]) -> dict[str, Any]:
    def _ids(trace_list):
        return {n["unique_id"] for n in trace_list}

    return {
        "upstream_added": sorted(_ids(current_trace["upstream"]) - _ids(main_trace["upstream"])),
        "upstream_removed": sorted(_ids(main_trace["upstream"]) - _ids(current_trace["upstream"])),
        "downstream_added": sorted(_ids(current_trace["downstream"]) - _ids(main_trace["downstream"])),
        "downstream_removed": sorted(_ids(main_trace["downstream"]) - _ids(current_trace["downstream"])),
    }


def _emit(payload, args, mermaid_fn, ascii_fn):
    fmt = args.format
    if args.json:
        fmt = "json"
    if fmt == "json":
        print(json.dumps(payload, indent=2))
    elif fmt == "mermaid":
        print(mermaid_fn())
    elif fmt == "tree":
        print(ascii_fn())
    else:
        # Default: mermaid + a small JSON tail for the agent
        print(mermaid_fn())
        print("\n--- raw ---")
        print(json.dumps(payload, indent=2))


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dbt-lineage", description="dbt lineage skill")
    sub = p.add_subparsers(dest="command", required=True)

    # refresh
    pr = sub.add_parser("refresh", help="Compile current + cached compare manifest")
    pr.add_argument("--branch", default=None)
    pr.add_argument("--force", action="store_true")
    pr.set_defaults(func=cmd_refresh)

    # model
    pm = sub.add_parser("model", help="Model lineage (upstream/downstream)")
    pm.add_argument("name")
    pm.add_argument("--direction", choices=["up", "down", "both"], default="both")
    pm.add_argument("--depth", type=int, default=None)
    pm.add_argument("--diff", action="store_true", help="Overlay diff vs compare branch")
    pm.add_argument("--branch", default=None)
    pm.add_argument("--dialect", default=None)
    pm.add_argument("--dbt-target", dest="dbt_target", default=None)
    pm.add_argument("--format", choices=["mermaid", "json", "tree"], default=None)
    pm.add_argument("--json", action="store_true")
    pm.set_defaults(func=cmd_model)

    # column
    pc = sub.add_parser("column", help="Column lineage (forward trace)")
    pc.add_argument("locator", help="<model>.<column>")
    pc.add_argument("--to", default=None, help="Target downstream model")
    pc.add_argument("--diff", action="store_true")
    pc.add_argument("--branch", default=None)
    pc.add_argument("--dialect", default=None)
    pc.add_argument("--dbt-target", dest="dbt_target", default=None)
    pc.add_argument("--format", choices=["mermaid", "json", "tree"], default=None)
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(func=cmd_column)

    # diff
    pd = sub.add_parser("diff", help="Model-level diff vs compare branch")
    pd.add_argument("--branch", default=None)
    pd.add_argument("--dialect", default=None)
    pd.add_argument("--dbt-target", dest="dbt_target", default=None)
    pd.set_defaults(func=cmd_diff)

    # validate
    pv = sub.add_parser("validate", help="Check manifest depends_on vs sqlglot refs")
    pv.add_argument("--dialect", default=None)
    pv.add_argument("--dbt-target", dest="dbt_target", default=None)
    pv.set_defaults(func=cmd_validate)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
