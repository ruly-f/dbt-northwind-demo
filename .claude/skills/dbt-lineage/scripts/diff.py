"""Diff two manifests (typically `current branch` vs cached `main`).

Emits a structured diff: added/removed/modified models, new/dropped upstream edges,
and per-model output column deltas (uses classifier.list_output_columns).
"""
from __future__ import annotations

from typing import Any

from .classifier import list_output_columns


def diff_manifests(
    main_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
    dialect: str,
) -> dict[str, Any]:
    main_models = _model_index(main_manifest)
    curr_models = _model_index(current_manifest)

    main_ids = set(main_models)
    curr_ids = set(curr_models)

    added = sorted(curr_ids - main_ids)
    removed = sorted(main_ids - curr_ids)
    common = main_ids & curr_ids

    modified = []
    for uid in sorted(common):
        m_node = main_models[uid]
        c_node = curr_models[uid]

        m_deps = set(_deps(m_node))
        c_deps = set(_deps(c_node))
        added_deps = sorted(c_deps - m_deps)
        removed_deps = sorted(m_deps - c_deps)

        m_cols = set(list_output_columns(m_node.get("compiled_code") or "", dialect))
        c_cols = set(list_output_columns(c_node.get("compiled_code") or "", dialect))
        added_cols = sorted(c_cols - m_cols)
        removed_cols = sorted(m_cols - c_cols)

        code_changed = (m_node.get("compiled_code") or "") != (c_node.get("compiled_code") or "")

        if added_deps or removed_deps or added_cols or removed_cols or code_changed:
            modified.append({
                "unique_id": uid,
                "name": c_node["name"],
                "code_changed": code_changed,
                "added_deps": added_deps,
                "removed_deps": removed_deps,
                "added_columns": added_cols,
                "removed_columns": removed_cols,
            })

    return {
        "added_models": [{"unique_id": uid, "name": curr_models[uid]["name"]} for uid in added],
        "removed_models": [{"unique_id": uid, "name": main_models[uid]["name"]} for uid in removed],
        "modified_models": modified,
    }


def _model_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        uid: node
        for uid, node in manifest.get("nodes", {}).items()
        if node.get("resource_type") == "model"
    }


def _deps(node: dict[str, Any]) -> list[str]:
    return node.get("depends_on", {}).get("nodes") or []
