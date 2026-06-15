"""Build a networkx DAG from manifest depends_on. Used by both model and column lineage.

Nodes:
  - Models: unique_id `model.<package>.<name>`
  - Sources: unique_id `source.<package>.<source>.<table>`
  - Seeds:   unique_id `seed.<package>.<name>`
  - Snapshots: unique_id `snapshot.<package>.<name>`

Edges point from upstream → downstream (data flow direction).
"""
from __future__ import annotations

from typing import Any

import networkx as nx

ALLOWED_RESOURCE_TYPES = {"model", "source", "seed", "snapshot"}


def build_dag(manifest: dict[str, Any]) -> nx.DiGraph:
    """Build the full model/source/seed/snapshot DAG from a manifest."""
    g = nx.DiGraph()

    # Add all parseable nodes first so isolated nodes still appear.
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") in ALLOWED_RESOURCE_TYPES:
            g.add_node(uid, **_node_attrs(node))

    for uid, node in manifest.get("sources", {}).items():
        g.add_node(uid, **_node_attrs(node))

    # Edges
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") not in {"model", "snapshot"}:
            continue
        for upstream in node.get("depends_on", {}).get("nodes", []) or []:
            if upstream in g:
                g.add_edge(upstream, uid)

    return g


def _node_attrs(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": node.get("name"),
        "resource_type": node.get("resource_type"),
        "schema": node.get("schema"),
        "database": node.get("database"),
        "materialized": (node.get("config") or {}).get("materialized"),
        "package": node.get("package_name"),
        "language": node.get("language", "sql"),
    }


def resolve_node_id(g: nx.DiGraph, name: str) -> str | None:
    """Resolve a short name like `fct_orders` or `erp.customer` to a unique_id.

    Match priority: exact unique_id → exact node name (models/seeds/snapshots) →
    source `<source>.<table>` → unique substring on name.
    """
    if name in g:
        return name

    # Exact name match across all non-source nodes
    matches_by_name = [
        nid for nid, attrs in g.nodes(data=True)
        if attrs.get("name") == name and attrs.get("resource_type") != "source"
    ]
    if len(matches_by_name) == 1:
        return matches_by_name[0]
    if len(matches_by_name) > 1:
        raise ValueError(
            f"Name '{name}' is ambiguous. Candidates: {sorted(matches_by_name)}"
        )

    # Source format: source_name.table_name
    if "." in name:
        src, tbl = name.split(".", 1)
        source_matches = [
            nid for nid in g.nodes
            if nid.startswith("source.") and nid.endswith(f".{src}.{tbl}")
        ]
        if len(source_matches) == 1:
            return source_matches[0]

    return None


def upstream(g: nx.DiGraph, node_id: str, depth: int | None = None) -> list[str]:
    """Return all ancestors of node_id up to `depth` hops (None = unlimited)."""
    if depth is None:
        return list(nx.ancestors(g, node_id))
    return _bounded_traversal(g.reverse(copy=False), node_id, depth)


def downstream(g: nx.DiGraph, node_id: str, depth: int | None = None) -> list[str]:
    if depth is None:
        return list(nx.descendants(g, node_id))
    return _bounded_traversal(g, node_id, depth)


def _bounded_traversal(g: nx.DiGraph, start: str, depth: int) -> list[str]:
    seen: set[str] = set()
    frontier = {start}
    for _ in range(depth):
        next_frontier: set[str] = set()
        for n in frontier:
            for succ in g.successors(n):
                if succ not in seen and succ != start:
                    seen.add(succ)
                    next_frontier.add(succ)
        frontier = next_frontier
        if not frontier:
            break
    return list(seen)


def shortest_path(g: nx.DiGraph, source: str, target: str) -> list[str] | None:
    try:
        return nx.shortest_path(g, source, target)
    except nx.NetworkXNoPath:
        return None
    except nx.NodeNotFound:
        return None


def terminal_descendants(g: nx.DiGraph, node_id: str) -> list[str]:
    """All descendants that have no further descendants (leaf models downstream)."""
    leaves = []
    for desc in nx.descendants(g, node_id):
        if g.out_degree(desc) == 0:
            leaves.append(desc)
    if not leaves and g.out_degree(node_id) == 0:
        return [node_id]
    return leaves
