"""P2 / CRITICAL-2: live body fill must never delete a paragraph blind.

Live COM is desktop-only, so these tests drive :func:`apply_body_targets` with a
fake COM object that records HAction calls. They prove that a failed ``set_pos``
(caret positioning) or a paragraph that changed since analysis SKIPS the target
instead of running ``Delete`` on whatever paragraph the caret happens to sit in.
"""

import zipfile
from pathlib import Path

from hangeul_core.body import detect_body_fields, resolve_body_targets
from hangeul_core.hwp.live_body import apply_body_targets

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
)


def _run(t: str) -> str:
    return f'<hp:run charPrIDRef="0"><hp:t>{t}</hp:t></hp:run>'


def _build(dst: Path) -> None:
    header = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>'
    )
    section0 = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec {_NS}>'
        '<hp:p id="1">' + _run("□ 제목 자리") + "</hp:p>"
        '<hp:p id="2">' + _run("본문 내용") + "</hp:p>"
        "</hs:sec>"
    ).encode()
    with zipfile.ZipFile(dst, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section0)


class _FakeHAction:
    def __init__(self, hwp):
        self.hwp = hwp

    def Run(self, action):
        self.hwp.actions.append(action)


class FakeHwp:
    """Minimal COM stand-in: list-0 paragraphs indexed by ``para``.

    ``marker_pos_ok=False`` makes the caret-past-marker ``set_pos`` fail (pos!=0).
    ``drift`` maps a para index to text returned on its SECOND read (the
    compare-before-write read), simulating a paragraph edited since analysis.
    """

    def __init__(self, paras, *, marker_pos_ok=True, drift=None):
        self.paras = paras
        self.marker_pos_ok = marker_pos_ok
        self.drift = drift or {}
        self.actions = []
        self.inserted = []
        self.cur = 0
        self._reads = {}
        self.HAction = _FakeHAction(self)

    def set_pos(self, lst, para, pos):
        if para >= len(self.paras):
            return False
        self.cur = para
        if pos != 0 and not self.marker_pos_ok:
            return False
        return True

    def get_selected_text(self):
        self._reads[self.cur] = self._reads.get(self.cur, 0) + 1
        if self._reads[self.cur] >= 2 and self.cur in self.drift:
            return self.drift[self.cur]
        return self.paras[self.cur]

    def insert_text(self, value):
        self.inserted.append(value)


def _targets(src):
    fields = detect_body_fields(src)
    marker_field = next(f for f in fields if f.insert_after and "□" in f.insert_after)
    return resolve_body_targets(src, {marker_field.field_id: "새 제목"}), marker_field


def test_set_pos_failure_skips_without_delete(tmp_path):
    src = tmp_path / "form.hwpx"
    _build(src)
    targets, mf = _targets(src)
    hwp = FakeHwp(["□ 제목 자리", "본문 내용"], marker_pos_ok=False)
    applied, skipped = [], []
    apply_body_targets(hwp, src, targets, applied, skipped)
    assert "Delete" not in hwp.actions, "must not delete when caret positioning failed"
    assert hwp.inserted == []
    assert applied == []
    assert any(s["key"] == mf.field_id and "caret past marker" in s["reason"] for s in skipped)


def test_compare_before_write_skips_on_mismatch(tmp_path):
    src = tmp_path / "form.hwpx"
    _build(src)
    targets, mf = _targets(src)
    # the target paragraph reads back as different text at write time
    hwp = FakeHwp(["□ 제목 자리", "본문 내용"], drift={0: "누군가 이미 바꾼 내용"})
    applied, skipped = [], []
    apply_body_targets(hwp, src, targets, applied, skipped)
    assert "Delete" not in hwp.actions, "must not delete a paragraph that changed"
    assert hwp.inserted == []
    assert any(s["key"] == mf.field_id and "changed since analysis" in s["reason"] for s in skipped)


def test_happy_path_deletes_then_inserts(tmp_path):
    src = tmp_path / "form.hwpx"
    _build(src)
    targets, mf = _targets(src)
    hwp = FakeHwp(["□ 제목 자리", "본문 내용"])
    applied, skipped = [], []
    apply_body_targets(hwp, src, targets, applied, skipped)
    assert "Delete" in hwp.actions
    assert hwp.inserted == ["새 제목"]
    assert any(a["field_id"] == mf.field_id for a in applied)
    assert skipped == []
