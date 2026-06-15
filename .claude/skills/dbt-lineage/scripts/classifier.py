"""Classify how a column is used inside a single model.

Inputs: compiled SQL + a column name + dialect.
Output: a structured classification (passthrough / meaningful + sublabels / truncated).

Sublabels for meaningful transformation:
  - join_key        : in a JOIN ... ON predicate
  - filter          : in WHERE / HAVING / QUALIFY
  - groupby         : in GROUP BY
  - order_by        : in ORDER BY
  - window          : in an OVER() partition/order clause
  - select_transform: in SELECT projection but wrapped in a function / expression
                      (SUM, CASE, COALESCE, arithmetic, CAST, ...)

A column can carry multiple sublabels at once. `select_transform` and `select_passthrough`
are mutually exclusive (a SELECT-list reference is one or the other), but a column may
appear as both `select_passthrough` (propagated as-is) AND `filter` (also used in WHERE)
in the same model — both labels are emitted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp


@dataclass
class ColumnUsage:
    column: str
    labels: set[str] = field(default_factory=set)
    appears_in_output: bool = False  # propagated to downstream models

    @property
    def is_passthrough(self) -> bool:
        return self.appears_in_output and self.labels == {"select_passthrough"}

    @property
    def is_meaningful(self) -> bool:
        return bool(self.labels - {"select_passthrough"})

    @property
    def is_truncated(self) -> bool:
        # Column reaches the model (we wouldn't be classifying otherwise) but
        # is not in the SELECT output — it dies here.
        return not self.appears_in_output and len(self.labels) > 0

    @property
    def summary(self) -> str:
        if not self.labels:
            return "absent"
        if self.is_passthrough:
            return "passthrough"
        if self.is_truncated:
            return "truncated"
        return "meaningful"

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "classification": self.summary,
            "labels": sorted(self.labels),
            "appears_in_output": self.appears_in_output,
        }


_CLAUSE_LABELS = {
    exp.Where: "filter",
    exp.Having: "filter",
    exp.Qualify: "filter",
    exp.Group: "groupby",
    exp.Order: "order_by",
    exp.Window: "window",
}

# Expressions that, when an ancestor of a Column in the SELECT projection,
# mark it as `select_transform` rather than passthrough.
_TRANSFORM_WRAPPERS = (
    exp.Func,
    exp.Case,
    exp.Binary,      # arithmetic, comparison, logical
    exp.Unary,       # NOT, negation
    exp.Cast,
    exp.Concat,
    exp.Paren,       # parens alone don't transform but often wrap expressions
    exp.Coalesce,
    exp.If,
)


def classify_column(sql: str, column: str, dialect: str) -> ColumnUsage:
    """Walk the AST of `sql` and tag every occurrence of `column` with a clause label."""
    usage = ColumnUsage(column=column)
    if not sql or not sql.strip():
        return usage

    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return usage

    if tree is None:
        return usage

    col_lower = column.lower()

    # Pre-scan: any Column with this name anywhere in the tree?
    any_column_ref = any(
        c.name.lower() == col_lower for c in tree.find_all(exp.Column)
    )

    # Determine SELECT-output propagation from the outermost SELECT.
    usage.appears_in_output = _column_in_output(tree, col_lower, any_column_ref)

    # Walk every Column node and tag with clause labels.
    for col_node in tree.find_all(exp.Column):
        if col_node.name.lower() != col_lower:
            continue
        _tag_column(col_node, usage.labels)

    # SELECT * with no explicit column reference anywhere → still a passthrough
    # IF the column genuinely propagates. We already qualified that via
    # `any_column_ref` in `_column_in_output`; if appears_in_output is True
    # but labels is empty, treat as bare passthrough.
    if usage.appears_in_output and not usage.labels:
        usage.labels.add("select_passthrough")

    return usage


def _column_in_output(tree: exp.Expression, col_lower: str, any_column_ref: bool) -> bool:
    """Does the outermost SELECT expose this column to downstream consumers?

    `any_column_ref` is a pre-scan flag: True if the AST contains ANY Column
    node with this name. Used to qualify `SELECT *` — a star alone doesn't
    confirm propagation if the column never appears anywhere.
    """
    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if select is None:
        return False

    # Find the OUTERMOST select (not one nested inside a CTE / subquery).
    while True:
        parent_select = select.parent.find_ancestor(exp.Select) if select.parent else None
        if parent_select is None:
            break
        select = parent_select

    for proj in select.expressions or []:
        if isinstance(proj, exp.Star):
            # SELECT * — column propagates IFF it appears somewhere in the AST.
            # (Otherwise the star is over a CTE / subquery that doesn't include it.)
            if any_column_ref:
                return True
            continue
        target = proj.unalias() if isinstance(proj, exp.Alias) else proj
        if isinstance(target, exp.Column) and target.name.lower() == col_lower:
            return True
        if isinstance(proj, exp.Alias) and proj.alias.lower() == col_lower:
            return True
    return False


def _tag_column(col_node: exp.Column, labels: set[str]) -> None:
    """Walk ancestors of a Column node and add clause labels."""
    in_select_projection = False
    wrapped_by_transform = False

    node: exp.Expression | None = col_node.parent
    while node is not None:
        # Clause labels (WHERE, GROUP BY, etc.)
        for clause_type, label in _CLAUSE_LABELS.items():
            if isinstance(node, clause_type):
                labels.add(label)

        # JOIN ON predicate
        if isinstance(node, exp.Join):
            # Column is inside an ON expression if any ancestor IS the join's `on`.
            on_expr = node.args.get("on")
            if on_expr is not None and _is_descendant_of(col_node, on_expr):
                labels.add("join_key")

        # Track wrappers as we walk up — anything between col and SELECT projection
        # that's a function, case, arithmetic, etc. → it's a transform
        if isinstance(node, _TRANSFORM_WRAPPERS):
            wrapped_by_transform = True

        # Did we reach the SELECT projection?
        if isinstance(node, exp.Select):
            # Check if col is in the projection list (vs. WHERE, etc., which are args)
            for proj in node.expressions or []:
                if _is_descendant_of(col_node, proj):
                    in_select_projection = True
                    break
            break  # stop at the enclosing select

        node = node.parent

    if in_select_projection:
        if wrapped_by_transform:
            labels.add("select_transform")
        else:
            labels.add("select_passthrough")


def _is_descendant_of(child: exp.Expression, ancestor: exp.Expression) -> bool:
    """True if `child` is reachable from `ancestor` by walking down the AST."""
    node = child
    while node is not None:
        if node is ancestor:
            return True
        node = node.parent
    return False


def list_output_columns(sql: str, dialect: str) -> list[str]:
    """Return the column names exposed in the outermost SELECT's projection."""
    if not sql or not sql.strip():
        return []
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return []
    if tree is None:
        return []

    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if select is None:
        return []
    # Outermost select
    while True:
        parent_select = select.parent.find_ancestor(exp.Select) if select.parent else None
        if parent_select is None:
            break
        select = parent_select

    cols: list[str] = []
    for proj in select.expressions or []:
        if isinstance(proj, exp.Star):
            cols.append("*")
        elif isinstance(proj, exp.Alias):
            cols.append(proj.alias)
        elif isinstance(proj, exp.Column):
            cols.append(proj.name)
        else:
            # Unaliased expression — emit a SQL string for visibility.
            cols.append(proj.sql(dialect=dialect))
    return cols
