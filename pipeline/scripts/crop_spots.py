# -*- coding: utf-8 -*-
r"""지정한 정규식에 걸리는 자리만 지면에서 잘라 대조표를 만든다.

    python crop_spots.py "패턴1" "패턴2" ...

`make_verify_sheets.py`가 '의심 자리 전수'를 훑는 것과 달리, 이쪽은 이미 찾아낸
특정 오류 자리만 확인할 때 쓴다. 출력은 `pipeline/work/verify/spot_NN.png`.
"""
import json
import os
import re
import sys
from pathlib import Path

import fitz

from extract_rosajeong import normalize
from paths import CASEBOOK, WORK

PDF = Path(os.environ.get(
    "ROSAJEONG_PDF", r"D:\pdf\사례\민사법\(26.02)[정연석] 로사정.pdf"))
OUT = Path(WORK) / "verify"
DPI, ROWS, CTX = 150, 24, 210


def main(patterns):
    OUT.mkdir(parents=True, exist_ok=True)
    rx = re.compile("|".join(patterns))
    cases = json.load(open(CASEBOOK / "rosajeong_cases.json", encoding="utf-8"))
    doc = fitz.open(PDF)

    picks, seen = [], set()
    for no, c in sorted(cases.items()):
        for pno, _t, _w in c["pages"]:
            for w in doc[pno - 1].get_text("words"):
                if not rx.search(normalize(w[4])):
                    continue
                key = (pno, round(w[1], 1), w[4])
                if key in seen:
                    continue
                seen.add(key)
                picks.append((no, pno, w))

    for old in OUT.glob("spot_*.png"):
        old.unlink()
    zoom = DPI / 72
    for i in range(0, len(picks), ROWS):
        chunk = picks[i:i + ROWS]
        pix = []
        for _c, pno, w in chunk:
            pg = doc[pno - 1]
            pix.append(pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(
                max(0, w[0] - CTX), w[1] - 4,
                min(pg.rect.width, w[2] + CTX), w[3] + 4)))
        W = max(p.width for p in pix) + 66
        sheet = fitz.open()
        page = sheet.new_page(width=W, height=sum(p.height + 5 for p in pix))
        y = 0
        for (no, pno, _), p in zip(chunk, pix):
            page.insert_image(fitz.Rect(66, y, 66 + p.width, y + p.height), pixmap=p)
            page.insert_text((2, y + p.height / 2 + 4), f"{no}",
                             fontsize=8, color=(0.85, 0, 0))
            y += p.height + 5
        page.get_pixmap().save(OUT / f"spot_{i // ROWS + 1:02d}.png")
    print(f"{len(picks)}자리 → {(len(picks) + ROWS - 1) // ROWS}장")


if __name__ == "__main__":
    main(sys.argv[1:])
