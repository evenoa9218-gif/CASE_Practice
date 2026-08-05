# -*- coding: utf-8 -*-
"""송영곤 『민소사연』 파싱 — 민사소송법 사례 연습서.

앞의 책들과 달리 출처(변시/모의) 표기가 거의 없다. 주제별 연습서라서
회차에 붙일 수 없고 목록으로만 쓴다.

사례 경계는 쪽머리다 — `사례` 한 줄, 그 다음 줄이 제목이다.
"""
import json
import re

import fitz

from paths import CASEBOOK, RAW

PDF = RAW / "사례집" / "민사소송법" / "(26.01)[송영곤] 민소사연 (1).pdf"
OUT = CASEBOOK / "civil_procedure_cases.json"
BOOK, AUTHOR = "민소사연", "송영곤"
SKIP_HEAD, SKIP_TAIL = 20, 20
MIN_CHARS = 500

FOOT = re.compile(r"^[^\n]{0,40}[I|]\s*\d{1,4}\s*$", re.M)   # '소송의 개시 I 69'


def main():
    doc = fitz.open(PDF)
    pages = [doc[i].get_text() for i in range(SKIP_HEAD, doc.page_count - SKIP_TAIL)]

    starts = []
    for i, t in enumerate(pages):
        ls = [l.strip() for l in t.split("\n") if l.strip()]
        if ls and ls[0] == "사례" and len(ls) > 1:
            starts.append((i, re.sub(r"\s+", " ", ls[1])[:70]))
    print(f"사례 시작 쪽 {len(starts)}개")

    cases = []
    for k, (pi, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(pages)
        seg = FOOT.sub("", "\n".join(pages[pi:end])).strip()
        if len(seg) < MIN_CHARS:
            continue
        cases.append({
            "caseNo": str(k + 1), "title": title,
            "book": BOOK, "author": AUTHOR, "area": "민사소송법",
            "source": {"kind": "unlabeled", "examId": None, "label": "출처 미표기"},
            "text": re.sub(r"\n{3,}", "\n\n", seg), "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"사례 {len(cases)}개 → {OUT}")


if __name__ == "__main__":
    main()
