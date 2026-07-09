"""mail_merge — bulk generation from one template + many records (OWN).

Unlike Phase C/D structural work (delegated to python-hwpx), mail-merge is squarely
our differentiator: each record is filled into the template with the *byte-preserving*
fill engine, so every output keeps the template's formatting exactly and only the
merged fields change. Records are client-provided (brain/hand separation); this just
iterates and fills.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from hangeul_core.fill import fill


def mail_merge(
    template_path: str | Path,
    records: List[Dict[str, str]],
    out_dir: str | Path,
    *,
    prefix: str = "merge",
    mask_pii: bool = False,
    checkbox_exclusive: bool = True,
) -> Dict:
    """Fill *template_path* once per record; write numbered outputs to *out_dir*.

    ``records`` is a list of ``{field_id_or_label: value}`` maps (same keys the
    fill engine accepts). Returns a per-record summary plus the total count.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[dict] = []
    for i, record in enumerate(records, start=1):
        out_path = out_dir / f"{prefix}_{i:03d}.hwpx"
        result = fill(
            template_path,
            record,
            out_path,
            mask_pii=mask_pii,
            checkbox_exclusive=checkbox_exclusive,
        )
        outputs.append(
            {
                "index": i,
                "out_path": str(out_path),
                "filled": len(result.filled),
                "skipped": len(result.skipped),
                "masked": len(result.masked),
            }
        )
    return {"count": len(outputs), "out_dir": str(out_dir), "outputs": outputs}
