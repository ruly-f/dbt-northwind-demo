"""Render lineage results as Mermaid (renders inline in Claude Code chat) or ASCII tree."""
from __future__ import annotations

from typing import Any

import networkx as nx

# Label colors / shapes by classification in Mermaid
_NODE_STYLES = {
    "model": ("[", "]"),
    "source": ("([", "])"),
    "seed": ("[[", "]]"),
    "snapshot": ("{{", "}}"),
}


def mermaid_model_trace(g: nx.DiGraph, trace: dict[str, Any]) -> str:
    """Render a model trace as a Mermaid flowchart (TD)."""
    lines = ["flowchart LR"]
    target = trace["node"]
    target_id = target["unique_id"]

    nodes = {target_id, *(n["unique_id"] for n in trace["upstream"]),
                          *(n["unique_id"] for n in trace["downstream"])}

    for nid in sorted(nodes):
        label, shape_l, shape_r = _mermaid_node(g, nid)
        marker = " :::target" if nid == target_id else ""
        lines.append(f"  {_sanitize(nid)}{shape_l}\"{label}\"{shape_r}{marker}")

    # Edges only between included nodes
    for u, v in g.edges():
        if u in nodes and v in nodes:
            lines.append(f"  {_sanitize(u)} --> {_sanitize(v)}")

    lines.append("  classDef target fill:#ffe082,stroke:#f57f17,stroke-width:2px;")
    return "\n".join(lines)


def mermaid_column_trace(trace: dict[str, Any]) -> str:
    """Render a column trace (linear, source → hops) as a Mermaid flowchart."""
    lines = ["flowchart LR"]
    src = trace["source"]
    src_id = f"src::{src['node_id']}"
    lines.append(f"  {_sanitize(src_id)}([\"{src['node_id'].split('.')[-1]}\\n.{src['column']}\"])")

    prev = src_id
    for i, hop in enumerate(trace["hops"]):
        node_label = hop["node"]["name"]
        outgoing = ",".join(hop["outgoing_names"]) or "—"
        class_label = hop["classification"].upper()
        labels = ",".join(hop["labels"]) or "—"
        node_uid = f"hop{i}::{hop['node']['unique_id']}"
        body = f"{node_label}\\n[{class_label}] {labels}\\nout: {outgoing}"
        lines.append(f"  {_sanitize(node_uid)}[\"{body}\"]")
        lines.append(f"  {_sanitize(prev)} --> {_sanitize(node_uid)}")
        if hop["classification"] == "truncated":
            lines.append(f"  {_sanitize(node_uid)}:::truncated")
        elif hop["classification"] == "meaningful":
            lines.append(f"  {_sanitize(node_uid)}:::meaningful")
        else:
            lines.append(f"  {_sanitize(node_uid)}:::passthrough")
        prev = node_uid

    lines.append("  classDef passthrough fill:#c8e6c9,stroke:#2e7d32;")
    lines.append("  classDef meaningful  fill:#bbdefb,stroke:#1565c0;")
    lines.append("  classDef truncated   fill:#ffcdd2,stroke:#c62828;")
    return "\n".join(lines)


def ascii_model_trace(trace: dict[str, Any]) -> str:
    lines = []
    target_name = trace["node"]["name"]
    lines.append(f"=== {target_name} ({trace['node']['unique_id']}) ===")

    if trace["upstream"]:
        lines.append("\nUpstream (data feeds in from):")
        for n in trace["upstream"]:
            lines.append(f"  +{n['hops_from_target']:>2}  {n['resource_type']:<8} {n['name']}")

    if trace["downstream"]:
        lines.append("\nDownstream (data flows out to):")
        for n in trace["downstream"]:
            lines.append(f"  -{n['hops_from_target']:>2}  {n['resource_type']:<8} {n['name']}")

    return "\n".join(lines)


def ascii_column_trace(trace: dict[str, Any]) -> str:
    lines = []
    src = trace["source"]
    lines.append(f"=== {src['node_id'].split('.')[-1]}.{src['column']} ===")
    if not trace["hops"]:
        lines.append("(no downstream models consume this column)")
        return "\n".join(lines)
    for hop in trace["hops"]:
        n = hop["node"]
        cls = hop["classification"].upper()
        labels = ",".join(hop["labels"]) or "—"
        out = ",".join(hop["outgoing_names"]) or "—"
        der = ",".join(hop.get("derived_names", [])) or "—"
        suffix = ""
        if hop.get("classification") == "unknown_python":
            suffix = "  [python model — column flow not analyzed]"
        lines.append(
            f"  → {n['name']:<35} [{cls:<14}] labels={labels:<35} out={out:<20} derived={der}{suffix}"
        )
    return "\n".join(lines)


def _mermaid_node(g: nx.DiGraph, node_id: str) -> tuple[str, str, str]:
    attrs = g.nodes.get(node_id, {})
    rt = attrs.get("resource_type", "model")
    name = attrs.get("name", node_id.split(".")[-1])
    shape_l, shape_r = _NODE_STYLES.get(rt, ("[", "]"))
    label = f"{name}\\n({rt})"
    return label, shape_l, shape_r


def _sanitize(uid: str) -> str:
    return uid.replace(".", "_").replace("-", "_").replace(":", "_")
