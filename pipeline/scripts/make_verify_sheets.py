# -*- coding: utf-8 -*-
r"""OCR 의심 구간을 지면과 대조하기 위한 '대조표' 이미지를 만든다.

    python make_verify_sheets.py            # 낱말 형태별 1건씩(기본)
    python make_verify_sheets.py --all      # 전 건

`rosajeong_verify.txt`가 짚은 자리마다 **그 낱말 둘레만** PDF에서 잘라내어 세로로 쌓는다.
쪽 전체를 렌더링하면 한 건 확인하는 데 한 장을 통째로 봐야 하지만, 줄만 자르면
한 장에 20건 넘게 담긴다. 지면 이미지 자체는 깨끗해서 이대로 읽으면 정확하다.

**같은 낱말 형태는 한 번만 본다.** `補修`가 41번 나온다고 41번 확인할 이유가 없다 —
한 번 보고 교정을 정하면 나머지는 같은 판단이 그대로 적용된다. 이 중복 제거로
확인할 자리가 1,200건에서 수백 건으로 줄어든다.

출력은 `pipeline/work/verify/sheet_NN.png` 와 자리별 정보를 적은 `slots.json`.
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import fitz

from extract_rosajeong import normalize
from paths import CASEBOOK, WORK

PDF = Path(os.environ.get(
    "ROSAJEONG_PDF", r"D:\pdf\사례\민사법\(26.02)[정연석] 로사정.pdf"))
OUT = Path(WORK) / "verify"

DPI = 150
ROWS = 26
PAD_Y = 4
CTX_X = 190          # 낱말 좌우로 남길 문맥(pt)
LABEL_W = 54

KNOWN = set("甲乙丙丁戊判例私見大法院全合條")
SUSPECT = [
    (re.compile(r"[\u4e00-\u9fff]"), "한자"),
    (re.compile(r"\(\s*[XＸ×xO0]{1,3}\s*\)|（\s*[XＸ×xO0]{1,3}\s*）"), "(X)"),
    (re.compile(r"\d\s*[이애]\s*\d"), "이애"),
    (re.compile(r"[☆◎■□♦€»]"), "기호"),
    (re.compile(r"(?<![A-Za-z])[A-Z][/?][A-Za-z가-힣]"), "Z/"),
    (re.compile(r"으(?=[는의가에])"), "으"),
    (re.compile(r"(?<![A-Za-z])Z[LlIi]?(?=[은는이가의에을로과와])"), "Z"),
]


def classify(raw):
    """교정 **후** 낱말로 판정한다.

    원문 낱말로 판정하면 `江`·`己`·`內`·`因`·`乂`처럼 이미 일괄교정으로 해결된 글자가
    전부 다시 걸려, 확인할 자리가 4,333건으로 부풀었다. 남은 문제만 봐야 한다.
    """
    word = normalize(raw)
    for rx, kind in SUSPECT:
        m = rx.search(word)
        if not m:
            continue
        if kind == "한자" and all(ch in KNOWN for ch in re.findall(r"[\u4e00-\u9fff]", word)):
            continue
        return kind
    return None


def scan(doc, page2case):
    slots = []
    for pno in sorted(page2case):
        page = doc[pno - 1]
        seen_line = set()
        for w in page.get_text("words"):
            kind = classify(w[4])
            if not kind:
                continue
            key = (round(w[1], 1), w[4])
            if key in seen_line:
                continue
            seen_line.add(key)
            slots.append({"id": len(slots) + 1, "case": page2case[pno], "page": pno,
                          "kind": kind, "word": normalize(w[4]), "raw": w[4],
                          "rect": [w[0], w[1], w[2], w[3]]})
    return slots


def main():
    show_all = "--all" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    cases = json.load(open(CASEBOOK / "rosajeong_cases.json", encoding="utf-8"))
    page2case = {}
    for no, c in cases.items():
        for p in range(c["pdfPages"][0], c["pdfPages"][1] + 1):
            page2case.setdefault(p, no)

    doc = fitz.open(PDF)
    slots = scan(doc, page2case)
    freq = Counter(s["word"] for s in slots)
    for s in slots:
        s["count"] = freq[s["word"]]

    if show_all:
        show = slots
    else:                       # 낱말 형태별 첫 자리만
        first, show = set(), []
        for s in slots:
            if s["word"] not in first:
                first.add(s["word"])
                show.append(s)

    for old in OUT.glob("sheet_*.png"):
        old.unlink()

    zoom = DPI / 72
    sheets = 0
    for i in range(0, len(show), ROWS):
        chunk = show[i:i + ROWS]
        pix = []
        for s in chunk:
            x0, y0, x1, y1 = s["rect"]
            pg = doc[s["page"] - 1]
            clip = fitz.Rect(max(0, x0 - CTX_X), y0 - PAD_Y,
                             min(pg.rect.width, x1 + CTX_X), y1 + PAD_Y)
            pix.append(pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip))
        W = max(p.width for p in pix) + LABEL_W
        H = sum(p.height + 5 for p in pix)
        sheet = fitz.open()
        page = sheet.new_page(width=W, height=H)
        y = 0
        for s, p in zip(chunk, pix):
            page.insert_image(fitz.Rect(LABEL_W, y, LABEL_W + p.width, y + p.height),
                              pixmap=p)
            page.insert_text((3, y + p.height / 2 + 4),
                             f"{s['id']}" + (f"×{s['count']}" if s["count"] > 1 else ""),
                             fontsize=9, color=(0.85, 0, 0))
            y += p.height + 5
        sheets += 1
        page.get_pixmap().save(OUT / f"sheet_{sheets:02d}.png")

    (OUT / "slots.json").write_text(
        json.dumps(slots, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"의심 자리 {len(slots)}건 · 낱말 형태 {len(freq)}종 "
          f"→ 대조표 {sheets}장 ({len(show)}행)")
    print("  종류별: " + " · ".join(f"{k} {v}" for k, v in
                                  Counter(s["kind"] for s in show).most_common()))


if __name__ == "__main__":
    main()
