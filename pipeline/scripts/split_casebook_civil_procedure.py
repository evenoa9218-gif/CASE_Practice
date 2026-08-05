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
    # 경계는 원본 PDF에서, 본문은 재OCR에서 가져온다.
    # 원본은 쪽머리가 `사례` + 제목이라 사례 시작 쪽을 정확히 알려주지만 당사자
    # 표기가 35% 깨져 있다. 재OCR본은 표기가 깨끗한 대신 쪽 전체가 한 줄로
    # 합쳐져 나와 쪽머리 판정이 안 된다. 각자 잘하는 것을 쓴다.
    doc = fitz.open(PDF)
    orig = [doc[i].get_text() for i in range(SKIP_HEAD, doc.page_count - SKIP_TAIL)]

    reocr = PDF.parent / "송영곤_민소사연_재OCR.txt"
    body_of = orig
    if reocr.exists():
        parts = re.split(r"^<<<PAGE p(\d+)>>>$", reocr.read_text(encoding="utf-8"), flags=re.M)
        page = {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}
        body_of = [page.get(i, "") for i in range(SKIP_HEAD, SKIP_HEAD + len(orig))]
        print(f"재OCR 본문 사용 {len(page)}쪽")

    starts = []
    for i, t in enumerate(orig):
        ls = [l.strip() for l in t.split("\n") if l.strip()]
        if ls and ls[0] == "사례" and len(ls) > 1:
            starts.append((i, re.sub(r"\s+", " ", ls[1])[:70]))
    print(f"사례 시작 쪽 {len(starts)}개")

    # 재OCR본에는 원본 OCR이 놓쳤던 출처 표기가 살아 있다.
    # OCR이 "변시"를 "변사"로도 읽고, 회차 숫자를 놓쳐 "제: 회"가 되기도 한다.
    SRC = re.compile(r"[(（]\s*\d{4}\s*년\s*제?\s*(\d{1,2})\s*회\s*변\s*[시사]")

    cases = []
    for k, (pi, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(orig)
        seg = FOOT.sub("", "\n".join(body_of[pi:end])).strip()
        if len(seg) < MIN_CHARS:
            continue
        m = SRC.search(seg[:600])
        if m:
            hoi = int(m.group(1))
            src = {"kind": "exam", "examId": f"민사법_변시_{hoi}회_사례",
                   "label": f"제{hoi}회 변호사시험"}
        else:
            src = {"kind": "unlabeled", "examId": None, "label": "출처 미표기"}
        cases.append({
            "caseNo": str(k + 1), "title": title,
            "book": BOOK, "author": AUTHOR, "area": "민사소송법",
            "source": src,
            "text": re.sub(r"\n{3,}", "\n\n", seg), "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"사례 {len(cases)}개 → {OUT}")


if __name__ == "__main__":
    main()
