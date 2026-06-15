"""Forward column lineage tracing through the dbt DAG.

Given (source_node_id, source_column), walk every downstream model in topological
order, classifying how the column is used in each model.

Handles simple alias renames (`source_col AS new_name`) by carrying the
downstream name forward for further tracing — so `id AS order_pk` in staging
doesn't truncate the trace; we just continue tracing `order_pk` downstream.

What it does NOT handle (limitations called out in SKILL.md):
  - Expression-level renames (`SUM(amount) AS total` — the new column is its own
    lineage chain; trace `total` separately if needed)
  - Same-name collisions across joined tables (`a.id` vs `b.id` — we conflate)
  - CASE / COALESCE chains that combine multiple sources into one output
"""
from __future__ import annotations

from typing import Any

import networkx as nx
import sqlglot
from sqlglot import exp

from . import graph as graph_mod
from .classifier import ColumnUsage, classify_column, list_output_columns


def compute_model_outputs(
    manifest: dict[str, Any],
    g: nx.DiGraph,
    dialect: str,
) -> dict[str, set[str]]:
    """Pre-compute the output column set of every model/source/seed/snapshot.

    Handles `SELECT *` correctly by walking CTEs and resolving stars against the
    actual FROM-clause source — not by naively unioning all upstream models
    (which would over-report when middle CTEs drop columns).
    """
    outputs: dict[str, set[str]] = {}

    for uid, src in manifest.get("sources", {}).items():
        outputs[uid] = {c.lower() for c in (src.get("columns") or {}).keys()}

    nodes = manifest.get("nodes", {})
    for uid, node in nodes.items():
        if node.get("resource_type") == "seed":
            outputs[uid] = {c.lower() for c in (node.get("columns") or {}).keys()}

    # Build a physical-table → columns lookup. Manifest models reference compiled
    # tables as `<db>.<schema>.<alias>`; we key on the short name (case-folded).
    table_to_cols: dict[str, set[str]] = {}

    model_subgraph = g.subgraph([
        n for n in g.nodes
        if g.nodes[n].get("resource_type") in ("model", "snapshot", "seed", "source")
    ])
    for uid in nx.topological_sort(model_subgraph):
        node = nodes.get(uid) or manifest.get("sources", {}).get(uid)
        if node is None:
            continue
        rt = node.get("resource_type")

        if rt in ("source", "seed"):
            short_name = (node.get("identifier") or node.get("alias") or node["name"]).lower()
            if uid in outputs:
                table_to_cols[short_name] = outputs[uid]
            continue

        if rt not in ("model", "snapshot"):
            continue

        code = node.get("compiled_code") or ""
        cols = _resolve_outermost_outputs(code, dialect, table_to_cols)
        outputs[uid] = cols

        # Register this model as a physical-table mapping for downstream models.
        short_name = (node.get("alias") or node["name"]).lower()
        table_to_cols[short_name] = cols

    return outputs


def _resolve_outermost_outputs(
    sql: str,
    dialect: str,
    table_to_cols: dict[str, set[str]],
) -> set[str]:
    """Return the output columns of `sql`'s outermost SELECT, walking CTEs."""
    if not sql or not sql.strip():
        return set()
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return set()
    if tree is None:
        return set()

    # First, resolve every CTE in declaration order.
    cte_outputs: dict[str, set[str]] = {}
    ctes = []
    if isinstance(tree, exp.Select):
        ctes = tree.ctes
    else:
        with_node = tree.find(exp.With)
        if with_node:
            ctes = list(with_node.expressions or [])
    for cte in ctes:
        cte_name = (cte.alias or "").lower()
        inner = cte.this
        cte_outputs[cte_name] = _resolve_select_outputs(
            inner, dialect, cte_outputs, table_to_cols
        )

    # Find the outermost SELECT (the one not nested in another SELECT).
    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if select is None:
        return set()
    while True:
        parent_select = select.parent.find_ancestor(exp.Select) if select.parent else None
        if parent_select is None:
            break
        select = parent_select

    return _resolve_select_outputs(select, dialect, cte_outputs, table_to_cols)


def _resolve_select_outputs(
    select: exp.Expression,
    dialect: str,
    cte_outputs: dict[str, set[str]],
    table_to_cols: dict[str, set[str]],
) -> set[str]:
    """Compute output columns of a single SELECT node (handles stars + joins)."""
    if not isinstance(select, exp.Select):
        return set()

    # Collect all FROM/JOIN sources for expanding bare `*`.
    sources: list[set[str]] = []
    from_clause = select.args.get("from_")
    if from_clause and from_clause.this is not None:
        sources.append(_resolve_table_columns(from_clause.this, dialect, cte_outputs, table_to_cols))
    for join in select.args.get("joins") or []:
        if join.this is not None:
            sources.append(_resolve_table_columns(join.this, dialect, cte_outputs, table_to_cols))

    all_source_cols: set[str] = set()
    for s in sources:
        all_source_cols |= s

    cols: set[str] = set()
    for proj in select.expressions or []:
        if isinstance(proj, exp.Star):
            cols |= all_source_cols
        elif isinstance(proj, exp.Alias):
            cols.add(proj.alias.lower())
        elif isinstance(proj, exp.Column):
            cols.add(proj.name.lower())
        else:
            # Bare expression — sqlglot will alias it with auto-name in real
            # query, but we can't infer that. Use sql() as a placeholder.
            cols.add(proj.sql(dialect=dialect).lower())

    return cols


def _resolve_table_columns(
    node: exp.Expression,
    dialect: str,
    cte_outputs: dict[str, set[str]],
    table_to_cols: dict[str, set[str]],
) -> set[str]:
    """Given a FROM / JOIN source expression, return its column set."""
    if isinstance(node, exp.Table):
        name = (node.name or "").lower()
        if name in cte_outputs:
            return cte_outputs[name]
        return table_to_cols.get(name, set())
    if isinstance(node, exp.Subquery):
        inner = node.this
        if isinstance(inner, exp.Select):
            return _resolve_select_outputs(inner, dialect, cte_outputs, table_to_cols)
    return set()


def trace_column(
    g: nx.DiGraph,
    manifest: dict[str, Any],
    source_node_id: str,
    source_column: str,
    dialect: str,
    target_node_id: str | None = None,
) -> dict[str, Any]:
    """Forward-trace `source_column` from `source_node_id` downstream.

    If `target_node_id` is given, only return hops along the shortest path
    from source → target. Otherwise trace to every downstream model.
    """
    if source_node_id not in g:
        raise KeyError(f"Source node '{source_node_id}' not in DAG")

    if target_node_id and target_node_id not in g:
        raise KeyError(f"Target node '{target_node_id}' not in DAG")

    if target_node_id:
        path = graph_mod.shortest_path(g, source_node_id, target_node_id)
        if not path:
            return {
                "source": {"node_id": source_node_id, "column": source_column},
                "target": {"node_id": target_node_id},
                "path": None,
                "hops": [],
                "error": "no path from source to target",
            }
        downstream_nodes = path[1:]
    else:
        # Topological order so we always process upstream models before downstream.
        full_subgraph = g.subgraph([source_node_id, *nx.descendants(g, source_node_id)])
        topo = list(nx.topological_sort(full_subgraph))
        downstream_nodes = [n for n in topo if n != source_node_id]

    # `aliases_by_node[uid]` = names this column is known by when consumed at uid
    aliases_by_node: dict[str, set[str]] = {source_node_id: {source_column}}

    # Pre-compute every model's resolved output columns (handles SELECT *).
    outputs_by_model = compute_model_outputs(manifest, g, dialect)

    hops = []
    nodes_dict = manifest.get("nodes", {})

    for node_id in downstream_nodes:
        node = nodes_dict.get(node_id)
        if node is None:
            continue
        if node.get("resource_type") not in ("model", "snapshot"):
            continue

        # What name(s) is this column known by when entering this node?
        incoming_names: set[str] = set()
        for parent in g.predecessors(node_id):
            incoming_names |= aliases_by_node.get(parent, set())
        if not incoming_names:
            continue  # column never reached this node

        # Python models: model-level edges are valid, but we can't analyze
        # column flow because their body is Python, not SQL.
        if node.get("language", "sql") != "sql":
            hops.append({
                "node": {
                    "unique_id": node_id,
                    "name": node["name"],
                    "resource_type": node["resource_type"],
                    "language": node.get("language"),
                },
                "incoming_names": sorted(incoming_names),
                "outgoing_names": [],
                "derived_names": [],
                "classification": "unknown_python",
                "labels": [],
                "appears_in_output": None,
                "note": "Python model — column-level flow not analyzed. Model-level edge is valid.",
            })
            # We don't propagate; downstream column lineage can't be inferred here.
            continue

        compiled = node.get("compiled_code") or node.get("raw_code") or ""
        model_outputs = outputs_by_model.get(node_id, set())
        model_outputs_lower = {c.lower() for c in model_outputs}

        # Classify each name we know it as; merge into a single usage.
        merged = ColumnUsage(column=",".join(sorted(incoming_names)))
        direct_aliases: set[str] = set()
        derived_aliases: set[str] = set()
        for name in incoming_names:
            u = classify_column(compiled, name, dialect)
            merged.labels |= u.labels
            if name.lower() in model_outputs_lower:
                direct_aliases.add(name)
            else:
                # Direct rename: `col AS new_name`
                direct_aliases |= _collect_output_aliases(compiled, name, dialect)
            # Derived: column wrapped inside an aliased expression
            # (`coalesce(col, x) AS c`, `sum(col) AS total`, ...)
            derived_aliases |= _collect_derived_aliases(compiled, name, dialect)

        # Drop derivatives that are already direct (no double-counting)
        derived_aliases -= direct_aliases

        # Resolved outputs are authoritative for `appears_in_output`.
        any_direct_in_output = any(a.lower() in model_outputs_lower for a in direct_aliases)
        any_incoming_in_output = any(n.lower() in model_outputs_lower for n in incoming_names)
        merged.appears_in_output = any_direct_in_output or any_incoming_in_output

        # Pure-passthrough chains (`SELECT * FROM upstream`) leave labels empty
        # but propagate the column — tag explicitly.
        if merged.appears_in_output and not merged.labels:
            merged.labels.add("select_passthrough")

        # If column doesn't propagate directly, drop direct-alias guesses
        # (they may have been collected speculatively).
        if not merged.appears_in_output:
            direct_aliases = set()

        # Filter derived aliases to those that actually exist in resolved outputs.
        derived_aliases = {a for a in derived_aliases if a.lower() in model_outputs_lower}

        # For tracing forward, treat derived names as also-propagated so the
        # next hop can pick them up.
        aliases_by_node[node_id] = direct_aliases | derived_aliases

        hops.append({
            "node": {
                "unique_id": node_id,
                "name": node["name"],
                "resource_type": node["resource_type"],
            },
            "incoming_names": sorted(incoming_names),
            "outgoing_names": sorted(direct_aliases),
            "derived_names": sorted(derived_aliases),
            "classification": merged.summary,
            "labels": sorted(merged.labels),
            "appears_in_output": merged.appears_in_output,
        })

        # If column doesn't propagate from here (direct OR derived), stop walking
        # this branch (we don't trace through descendants of a truncated node).
        if not merged.appears_in_output and not derived_aliases:
            for desc in list(nx.descendants(g, node_id)):
                aliases_by_node.setdefault(desc, set())

    return {
        "source": {"node_id": source_node_id, "column": source_column},
        "target": {"node_id": target_node_id} if target_node_id else None,
        "hops": hops,
    }


def _collect_derived_aliases(sql: str, source_col: str, dialect: str) -> set[str]:
    """Find aliases of expressions that CONTAIN `source_col` but transform it.

    Examples of what this catches (returns alias `c`):
      - `coalesce(source_col, x) AS c`
      - `sum(source_col) AS c`
      - `(source_col + 1) AS c`
      - `case when source_col is null then 0 else source_col end AS c`

    Does NOT catch direct renames like `source_col AS c` (that's
    `_collect_output_aliases`'s job). The distinction matters for tracing:
    derived columns combine multiple sources, so lineage fidelity degrades
    (we can't say a row's value of `c` came from `source_col` vs `x` in the
    coalesce case). The trace continues but flags the hop's `derived_names`.
    """
    if not sql or not sql.strip():
        return set()
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return set()
    if tree is None:
        return set()

    # Walk EVERY SELECT (outer + every CTE body). A column can be transformed
    # into a derived alias at any level — e.g. `sum(quantity) AS total_quantity`
    # inside a CTE that's then propagated upward. The caller filters the
    # returned set against the model's resolved outputs, so out-of-output
    # CTE-only aliases naturally drop out.
    out: set[str] = set()
    col_lower = source_col.lower()
    for select in tree.find_all(exp.Select):
        for proj in select.expressions or []:
            if not isinstance(proj, exp.Alias):
                continue
            inner = proj.this
            # Skip bare `col AS alias` — that's a direct rename, not derived.
            if isinstance(inner, exp.Column):
                continue
            # Inner is an expression — does it contain our source column?
            contains = any(
                isinstance(c, exp.Column) and c.name.lower() == col_lower
                for c in inner.find_all(exp.Column)
            )
            if contains:
                out.add(proj.alias)
    return out


def _collect_output_aliases(sql: str, source_col: str, dialect: str) -> set[str]:
    """Find names that `source_col` is exposed as in the outermost SELECT of `sql`.

    Detects `source_col`, `source_col AS new_name`, `t.source_col AS new_name`.
    Returns empty set if column is wrapped in a function or absent.
    """
    if not sql or not sql.strip():
        return set()
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return set()
    if tree is None:
        return set()

    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if select is None:
        return set()
    while True:
        parent_select = select.parent.find_ancestor(exp.Select) if select.parent else None
        if parent_select is None:
            break
        select = parent_select

    out: set[str] = set()
    col_lower = source_col.lower()
    for proj in select.expressions or []:
        if isinstance(proj, exp.Star):
            out.add(source_col)
            continue
        if isinstance(proj, exp.Alias):
            inner = proj.this
            if isinstance(inner, exp.Column) and inner.name.lower() == col_lower:
                out.add(proj.alias)
        elif isinstance(proj, exp.Column):
            if proj.name.lower() == col_lower:
                out.add(proj.name)
    return out
