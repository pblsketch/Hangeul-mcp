"""Data model for form analysis and field schema.

`field_id` (e.g. ``t2.r2.c3``) is the authoritative address; ``label`` is an
alias resolved to a field_id (see docs/DECISIONS.md D2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Cell:
    """A table cell with address, span, content and resolved style flags."""

    table: int
    row: int
    col: int
    col_span: int = 1
    row_span: int = 1
    text: str = ""
    is_empty: bool = False
    has_nested_table: bool = False
    para_bullet: bool = False
    char_spacing: Optional[int] = None
    para_pr: Optional[str] = None
    char_pr: Optional[str] = None

    @property
    def field_id(self) -> str:
        return f"t{self.table}.r{self.row}.c{self.col}"


@dataclass
class Table:
    index: int
    rows: int
    cols: int
    cells: List[Cell] = field(default_factory=list)


@dataclass
class AnalyzeResult:
    fmt: str
    tables: List[Table] = field(default_factory=list)

    def all_cells(self) -> List[Cell]:
        return [c for t in self.tables for c in t.cells]

    def cell(self, field_id: str) -> Optional[Cell]:
        for c in self.all_cells():
            if c.field_id == field_id:
                return c
        return None
