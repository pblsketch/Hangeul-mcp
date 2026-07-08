# -*- coding: utf-8 -*-
import re, zipfile
import xml.etree.ElementTree as ET

SEC = "_tpl/Contents/section0.xml"
SRC = "(양식)강사카드.hwpx"
DST = "강사카드_양식_채움.hwpx"

raw = open(SEC, encoding="utf-8").read()
# 네임스페이스 접두사 보존을 위해 등록
for pfx, uri in re.findall(r'xmlns:(\w+)="([^"]+)"', raw):
    ET.register_namespace(pfx, uri)
P = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"

tree = ET.parse(SEC)
root = tree.getroot()
def L(t): return t.split("}")[-1]

# 표2 = 문서 내 2번째 tbl
tbls = [e for e in root.iter() if L(e.tag) == "tbl"]
form = tbls[1]

# 채울 값: (rowAddr, colAddr): (mode, value)
#  mode 'set'    = 빈 셀에 값 입력
#  mode 'append' = '∘' 뒤에 이어붙이기
targets = {
    (2,0): ("set", "○○고등학교"),
    (2,2): ("set", "교사"),
    (2,3): ("set", "홍길동"),
    (2,4): ("set", "900101-1234567"),
    (2,7): ("set", "010-0000-0000"),
    (3,7): ("set", "hong@example.com"),
    (6,1): ("append", "2026 교원 프로젝트수업 역량강화 연수"),
    (7,1): ("append", "프로젝트 기반 학습(PBL) 설계와 과정중심평가"),
    (9,1): ("append", "○○대학교 대학원"),
    (10,1): ("append", "○○고등학교 국어교사"),
    (11,1): ("append", "프로젝트 기반 학습·과정중심평가 강의 다수"),
    (12,1): ("append", "『샘플 도서 A』 공동 번역 등"),
    (13,1): ("append", "○○고등학교 교사"),
    (14,1): ("append", "『샘플 도서 B』(2023, 공저)"),
}

def find_cell(row, col):
    for tr in form:
        if L(tr.tag) != "tr": continue
        for tc in tr:
            if L(tc.tag) != "tc": continue
            a = tc.find(P + "cellAddr")
            if a is not None and a.get("rowAddr") == str(row) and a.get("colAddr") == str(col):
                return tc
    return None

def first_t(cell):
    for e in cell.iter():
        if L(e.tag) == "t":
            return e
    return None

def first_run(cell):
    for e in cell.iter():
        if L(e.tag) == "run":
            return e
    return None

done = []
for (row, col), (mode, val) in sorted(targets.items()):
    cell = find_cell(row, col)
    if cell is None:
        done.append(f"MISS R{row}C{col}"); continue
    if mode == "set":
        t = first_t(cell)
        if t is None:
            run = first_run(cell)
            t = ET.SubElement(run, P + "t")
        t.text = val
        done.append(f"SET  R{row}C{col} = {val}")
    else:  # append after ∘
        # ∘ 를 담은 t 찾기
        target_t = None
        for e in cell.iter():
            if L(e.tag) == "t" and e.text and "∘" in e.text:
                target_t = e; break
        if target_t is None:
            target_t = first_t(cell)
        base = (target_t.text or "").rstrip()
        target_t.text = base + " " + val
        done.append(f"APP  R{row}C{col} = {base.strip()} {val}")

for d in done: print(d)

# 저장 (XML 선언 유지)
tree.write(SEC, encoding="UTF-8", xml_declaration=True)

# repack: 원본 순서/압축(STORED mimetype 포함) 보존, section0만 교체
newsec = open(SEC, "rb").read()
zin = zipfile.ZipFile(SRC, "r"); zout = zipfile.ZipFile(DST, "w")
for it in zin.infolist():
    data = newsec if it.filename == "Contents/section0.xml" else zin.read(it.filename)
    zi = zipfile.ZipInfo(it.filename, date_time=it.date_time)
    zi.compress_type = it.compress_type; zi.external_attr = it.external_attr
    zi.internal_attr = it.internal_attr; zi.create_system = it.create_system
    zout.writestr(zi, data)
zout.close(); zin.close()
print("repacked ->", DST)
