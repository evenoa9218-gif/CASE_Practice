# -*- coding: utf-8 -*-
"""인사이트 『상법 사례형 해설편』 파싱.

상법은 변호사시험 민사법의 한 축이라 민사법에 붙인다.

사례마다 머리에 출처가 먼저 온다 — `변시6 (2017)` 또는 `모고 (2022 • 3)`.
그 다음 줄이 사례 번호, 그 다음이 제목이다. 그래서 출처 줄을 경계로 자른다.
이창현·이인규와 달리 출처가 거의 다 붙어 있다.
"""
import json
import re

import fitz

from paths import CASEBOOK, RAW

PDF = RAW / "사례집" / "상법" / "(2026) OCR 인사이트 상법 사례형 해설편.pdf"
OUT = CASEBOOK / "commercial_cases.json"
BOOK, AUTHOR = "인사이트 상법 사례형 해설편", "인사이트"
SKIP_HEAD, SKIP_TAIL = 20, 20
MIN_CHARS = 400

# `변시6 (2017)` / `모고 (2022 • 3)` — OCR이 가운뎃점을 ■·•·- 로 흔든다
HEAD = re.compile(
    r"^\s*(?:변시\s*(\d{1,2})\s*\(\s*\d{4}\s*\)"
    r"|모고\s*\(\s*(\d{4})\s*[^\d\n]{0,4}\s*([1-3])\s*\))\s*$", re.M)
NOISE = re.compile(r"^\s*\d{1,4}\s*[|I]\s*인사이트상법[^\n]*$", re.M)


def main():
    doc = fitz.open(PDF)
    body = "\n".join(doc[i].get_text() for i in range(SKIP_HEAD, doc.page_count - SKIP_TAIL))
    body = NOISE.sub("", body)          # 쪽머리 잡음 제거

    heads = list(HEAD.finditer(body))
    print(f"사례 머리 {len(heads)}개")

    cases = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        seg = body[m.end():end].strip()
        if len(seg) < MIN_CHARS:
            continue

        if m.group(1):
            n = int(m.group(1))
            src = {"kind": "exam", "examId": f"민사법_변시_{n}회_사례",
                   "label": f"제{n}회 변호사시험"}
        else:
            y, r = m.group(2), m.group(3)
            src = {"kind": "exam", "examId": f"민사법_모의_{y}_{r}차_사례",
                   "label": f"{y}년 제{r}차 모의시험"}

        # 출처 다음 두 줄이 사례번호와 제목이다
        lines = [l.strip() for l in seg.split("\n") if l.strip()]
        no = lines[0] if lines and re.fullmatch(r"\d{1,3}", lines[0]) else ""
        title = lines[1] if no and len(lines) > 1 else (lines[0] if lines else "")

        cases.append({
            "caseNo": no or str(i + 1),
            "title": re.sub(r"\s+", " ", title)[:60],
            "book": BOOK, "author": AUTHOR, "area": "상법",
            "source": src, "text": re.sub(r"\n{3,}", "\n\n", seg), "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    rounds = {c["source"]["examId"] for c in cases}
    print(f"사례 {len(cases)} → 기출 연계 {len(cases)} ({len(rounds)}회차)")


if __name__ == "__main__":
    main()
