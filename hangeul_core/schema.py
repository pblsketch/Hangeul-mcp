"""Data model for form analysis and field schema.

`field_id` (e.g. ``t2.r2.c3``) is the authoritative address; ``label`` is an
alias resolved to a field_id (see docs/DECISIONS.md D2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# Field kinds (see docs/PLAN.md section 5)
KIND_EMPTY_CELL = "empty_cell"
KIND_INLINE_BLANK = "inline_blank"
KIND_BULLET_ITEM = "bullet_item"
KIND_CHECKBOX = "checkbox"
KIND_NARRATIVE = "narrative"
KIND_PLACEHOLDER = "placeholder"  # {token} template variable (section-wide)
KIND_MARKPEN = "markpen"          # 형광펜-highlighted example value
KIND_FORMFIELD = "form_field"     # 누름틀 named field control
KIND_BODY_PARA = "body_para"      # body paragraph outside any table (marker-led or plain)


def normalize_label(text: str) -> str:
    """Collapse whitespace for a readable label (e.g. '학    력' -> '학 력')."""
    return re.sub(r"\s+", " ", text).strip()


def label_key(text: str) -> str:
    """Space-insensitive key for matching labels (e.g. '학    력' -> '학력')."""
    return re.sub(r"\s+", "", text)


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
    para_id: Optional[str] = None  # id of the cell's first paragraph (unique anchor)
    section: Optional[str] = None  # containing section xml entry (e.g. Contents/section0.xml)
    table_in_section: int = 0      # 1-based table index within its own section
    width: Optional[int] = None    # cellSz width in HWPUNIT (for form-fit)
    height: Optional[int] = None   # cellSz height in HWPUNIT

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


@dataclass
class Field:
    """A fillable field: where a value goes (`field_id`) and how (`kind`)."""

    field_id: str
    label: str
    kind: str = KIND_EMPTY_CELL
    label_id: Optional[str] = None
    value: Optional[str] = None
    para_bullet: bool = False
    char_spacing: Optional[int] = None
    # inline_blank specifics
    template: Optional[str] = None
    insert_after: Optional[str] = None
    # checkbox specifics: [{"label": str, "checked": bool}, ...]
    options: Optional[List[dict]] = None
    # approx max Korean characters that fit the value cell at its font (client sizing hint)
    capacity_hint: Optional[int] = None


@dataclass
class FormSchema:
    fmt: str
    fields: List[Field] = field(default_factory=list)
    source_sha256: str = ""

    def by_id(self, field_id: str) -> Optional[Field]:
        for f in self.fields:
            if f.field_id == field_id:
                return f
        return None

    def by_label(self, label: str) -> Optional[Field]:
        key = label_key(label)
        for f in self.fields:
            if label_key(f.label) == key:
                return f
        return None
