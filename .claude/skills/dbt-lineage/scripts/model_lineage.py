"""Model-level lineage answers.

`trace_model` returns a dict describing all upstream/downstream models for a node,
with hop distance, edge confidence, and the per-node attributes needed for output.
"""
from __future__ import annotations

from typing import Any

import networkx as nx

from . import graph as graph_mod


def trace_model(
    g: nx.DiGraph,
    node_id: str,
    direction: str = "both",
    depth: int | None = None,
) -> dict[str, Any]:
    """Return a structured trace for a model node.

    direction: "up" | "down" | "both"
    depth: hop limit (None = unlimited)
    """
    if node_id not in g:
        raise KeyError(f"Node '{node_id}' not in DAG")

    result: dict[str, Any] = {
        "node": _node_summary(g, node_id),
        "upstream": [],
        "downstream": [],
    }

    if direction in ("up", "both"):
        for ancestor in graph_mod.upstream(g, node_id, depth):
            path = graph_mod.shortest_path(g, ancestor, node_id)
            hops = (len(path) - 1) if path else None
            result["upstream"].append(
                {**_node_summary(g, ancestor), "hops_from_target": hops}
            )
        result["upstream"].sort(key=lambda n: (n["hops_from_target"] or 0, n["unique_id"]))

    if direction in ("down", "both"):
        for descendant in graph_mod.downstream(g, node_id, depth):
            path = graph_mod.shortest_path(g, node_id, descendant)
            hops = (len(path) - 1) if path else None
            result["downstream"].append(
                {**_node_summary(g, descendant), "hops_from_target": hops}
            )
        result["downstream"].sort(key=lambda n: (n["hops_from_target"] or 0, n["unique_id"]))

    return result


def _node_summary(g: nx.DiGraph, node_id: str) -> dict[str, Any]:
    attrs = g.nodes[node_id]
    return {
        "unique_id": node_id,
        "name": attrs.get("name"),
        "resource_type": attrs.get("resource_type"),
        "schema": attrs.get("schema"),
        "materialized": attrs.get("materialized"),
    }


def find_orphans(g: nx.DiGraph) -> dict[str, list[str]]:
    """Models with no downstream consumers (potential dead code) and
    sources with no downstream models (potentially unused source tables)."""
    orphan_models, orphan_sources = [], []
    for nid, attrs in g.nodes(data=True):
        rt = attrs.get("resource_type")
        if g.out_degree(nid) == 0:
            if rt == "model":
                orphan_models.append(nid)
            elif rt == "source":
                # Sources with zero out_degree never get consumed
                pass
        if rt == "source" and g.out_degree(nid) == 0:
            orphan_sources.append(nid)
    return {"orphan_models": sorted(orphan_models), "unused_sources": sorted(orphan_sources)}
