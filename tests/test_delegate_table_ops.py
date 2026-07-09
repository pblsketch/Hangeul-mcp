import pytest

pytest.importorskip("hwpx")

from hangeul_core.delegate import create_table_from_rows, merge_table_cells, set_cell_shading
from hangeul_core.validate import validate_hwpx
from hangeul_mcp import server


def test_merge_existing_table_cells(tmp_path):
    src = tmp_path / "src.hwpx"
    out = tmp_path / "merged.hwpx"
    create_table_from_rows([["a", "b"], ["c", "d"]], src)
    res = merge_table_cells(src, 0, "A1:B1", out)
    assert res["ok"] is True
    assert res["cell_range"] == "A1:B1"
    assert validate_hwpx(out)["valid"] is True


def test_set_cell_shading_existing_table(tmp_path):
    src = tmp_path / "src.hwpx"
    out = tmp_path / "shaded.hwpx"
    create_table_from_rows([["a", "b"], ["c", "d"]], src)
    res = set_cell_shading(src, 0, 0, 0, "#FFF2CC", out)
    assert res["ok"] is True
    assert res["fill_color"] == "#FFF2CC"
    assert validate_hwpx(out)["valid"] is True


def test_table_ops_invalid_inputs(tmp_path):
    src = tmp_path / "src.hwpx"
    out = tmp_path / "bad.hwpx"
    create_table_from_rows([["a", "b"]], src)
    assert merge_table_cells(src, 0, "A1", out)["ok"] is False
    assert set_cell_shading(src, 0, 0, 0, "FFF2CC", out)["ok"] is False
    assert server.merge_table_cells(str(src), 9, "A1:B1", str(out))["ok"] is False


def test_server_table_ops(tmp_path):
    src = tmp_path / "src.hwpx"
    merged = tmp_path / "merged.hwpx"
    shaded = tmp_path / "shaded.hwpx"
    create_table_from_rows([["a", "b"], ["c", "d"]], src)
    res = server.merge_table_cells(str(src), 0, "A1:B1", str(merged))
    assert res["available"] is True and res["ok"] is True
    res = server.set_cell_shading(str(merged), 0, 1, 0, "#FFF2CC", str(shaded))
    assert res["available"] is True and res["ok"] is True
    assert validate_hwpx(shaded)["valid"] is True
