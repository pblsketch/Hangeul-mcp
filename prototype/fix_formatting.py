# -*- coding: utf-8 -*-
import re, zipfile, sys

INSPECT = "_inspect"
SEC = INSPECT + "/Contents/section0.xml"
HDR = INSPECT + "/Contents/header.xml"
SRC = "강사카드_filled_demo.hwpx"
DST = "강사카드_filled_fixed.hwpx"

section = open(SEC, encoding="utf-8").read()
header  = open(HDR, encoding="utf-8").read()

# 내가 채운 4개 필드의 값 텍스트 고유 마커
markers = {
    "과정명":   "2026 미래교육 교원",
    "경력":     "프로젝트 기반 학습(PBL) 설계",
    "사용기자재": "노트북, 빔프로젝터",
    "기타사항":  "강의 시작 30분 전 도착",
}

char_ids = [int(x) for x in re.findall(r'<hh:charPr id="(\d+)"', header)]
next_char_id = max(char_ids) + 1
clone_map = {}
new_blocks = []

def get_charpr_block(cid):
    m = re.search(r'<hh:charPr id="' + str(cid) + r'"(?:(?!</hh:charPr>).)*</hh:charPr>', header, re.S)
    return m.group(0) if m else None

def spacing0_clone(cid):
    global next_char_id
    if cid in clone_map:
        return clone_map[cid]
    blk = get_charpr_block(cid)
    if blk is None:
        return cid
    newid = next_char_id; next_char_id += 1
    nb = re.sub(r'id="' + str(cid) + r'"', 'id="%d"' % newid, blk, count=1)
    def zero(m):
        inner = re.sub(r'(hangul|latin|hanja|japanese|other|symbol|user)="-?\d+"',
                       lambda mm: mm.group(1) + '="0"', m.group(1))
        return '<hh:spacing ' + inner + '/>'
    nb = re.sub(r'<hh:spacing ([^/]*)/>', zero, nb)
    clone_map[cid] = newid
    new_blocks.append(nb)
    return newid

pid_base = 4200000000
pid_ctr = [0]
def new_pid():
    pid_ctr[0] += 1
    return pid_base + pid_ctr[0]

def fix_field(name, marker):
    global section
    idx = section.find(marker)
    if idx < 0:
        print("SKIP", name, "(not found)"); return
    start = section.rfind("<hp:p ", 0, idx)
    end = section.find("</hp:p>", idx) + len("</hp:p>")
    block = section[start:end]
    nrun = block.count("<hp:run ")
    p_open = re.match(r"(<hp:p\b[^>]*>)", block).group(1)
    rm = re.search(r'<hp:run charPrIDRef="(\d+)"[^>]*>', block)
    run_open = rm.group(0); orig_cid = int(rm.group(1))
    texts = re.findall(r"<hp:t>(.*?)</hp:t>", block, re.S)
    full = "".join(texts)
    lines = full.split("\n")
    newcid = spacing0_clone(orig_cid)
    run_open_new = re.sub(r'charPrIDRef="\d+"', 'charPrIDRef="%d"' % newcid, run_open, count=1)
    paras = []
    for i, ln in enumerate(lines):
        po = p_open if i == 0 else re.sub(r'\bid="\d+"', 'id="%d"' % new_pid(), p_open, count=1)
        paras.append(po + run_open_new + "<hp:t>" + ln + "</hp:t></hp:run></hp:p>")
    section = section[:start] + "".join(paras) + section[end:]
    print("FIX %s: runs=%d lines=%d charPr %d->%d(spacing0)" % (name, nrun, len(lines), orig_cid, newcid))

for n, m in markers.items():
    fix_field(n, m)

if new_blocks:
    header = header.replace("</hh:charProperties>", "".join(new_blocks) + "</hh:charProperties>")
    def bump(m): return '<hh:charProperties itemCnt="%d">' % (int(m.group(1)) + len(new_blocks))
    header = re.sub(r'<hh:charProperties itemCnt="(\d+)">', bump, header, count=1)
    print("added %d spacing-0 charPr, itemCnt bumped" % len(new_blocks))

open(SEC, "w", encoding="utf-8").write(section)
open(HDR, "w", encoding="utf-8").write(header)

# --- repack: 원본 zip 순서/압축방식(mimetype STORED 포함) 보존하며 2개 파일만 교체 ---
zin = zipfile.ZipFile(SRC, "r")
mod = {"Contents/section0.xml": section.encode("utf-8"),
       "Contents/header.xml": header.encode("utf-8")}
zout = zipfile.ZipFile(DST, "w")
for item in zin.infolist():
    data = mod.get(item.filename, zin.read(item.filename))
    zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
    zi.compress_type = item.compress_type
    zi.external_attr = item.external_attr
    zi.internal_attr = item.internal_attr
    zi.create_system = item.create_system
    zout.writestr(zi, data)
zout.close(); zin.close()
print("repacked ->", DST)
