# Architecture

## Layers

- `hangeul_core/` — pure-Python engine, no MCP dependency.
  - `owpml/` — HWPX container I/O (byte-preserving).
  - `analyze.py` — structural analysis (tables, cells, spans, paraPr, charPr).
  - `understand.py` — 2D label↔value mapping (merged-cell aware).
  - `inline.py` — inline-blank detection/insertion.
  - `fill.py` — format-preserving fill (set/append/inline).
  - `schema.py` — FieldSchema data model.
  - `hwp/` — (v2) HWP5 conversion + COM bridge.
- `hangeul_mcp/` — FastMCP stdio server exposing the engine as MCP tools.

## D1 substrate decision (US-002 spike)

**Decision: own byte-preserving engine is the core; `python-hwpx` is an optional
validation/security layer, not the fill substrate.**

Rationale:
- The differentiators — inline-blank (mid-sentence blanks) and merged-cell 2D
  fills — require run/paragraph-level XML control that high-level libraries do
  not expose. Ceding that control would cap quality.
- Byte-preservation is achieved by re-emitting every unmodified ZIP entry
  verbatim and only splicing changed XML at the byte level (never re-serializing
  the whole document). This avoids the class of bug where an XML re-serializer
  drops the `standalone="yes"` declaration or reorders attributes.
- `python-hwpx` remains valuable for **XSD schema validation** and **security
  hardening** (ZIP-bomb / XXE) as a verification pass. It is integrated as a
  soft/optional dependency (used when installed) so the core stays dependency-light
  and cross-platform.

`hangeul_core.owpml.HwpxPackage` implements the byte-preserving container:
preserves entry order, per-entry compression, and the STORED `mimetype` first
entry; only entries explicitly replaced change.

## Field addressing (D2)

`field_id` (e.g. `t2.r2.c3` = table/row/col) is the authoritative key; `label`
("성명") is a human-friendly alias resolved to a `field_id`. This is unambiguous
under merged cells, duplicate labels, and label-above-value layouts.
