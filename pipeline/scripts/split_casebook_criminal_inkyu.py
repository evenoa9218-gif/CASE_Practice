# -*- coding: utf-8 -*-
"""이인규 『형법 변사기』 파싱.

이창현과 구조가 다르다. 장(章)은 `사례 19. 형벌론`처럼 주제로 나뉘고, 그 안의
개별 사례는 `사례 2-5` 다음 줄에 출처가 온다 — `2023년 제12회 변호사시험（제2문）`.
그래서 장 헤더가 아니라 **하위 사례 번호**를 기준으로 자른다.

이창현과 달리 창작 사례가 거의 없다. 대신 형법 쪽을 덮으므로, 형사소송법만
있던 이창현과 합치면 형사법 사례 폭이 넓어진다.
"""
import json
import re

import fitz

from paths import CASEBOOK, RAW

PDF = RAW / "사례집" / "형법" / "(2026)[이인규] 형법 변사기.pdf"
OUT = CASEBOOK / "criminal_inkyu_cases.json"
BOOK, AUTHOR = "형법 변사기", "이인규"
SKIP_HEAD, SKIP_TAIL = 20, 20
MIN_CHARS = 400

CHAP = re.compile(r"사례\s*(\d{1,3})\.\s*([^\n]{2,40})")
SUB = re.compile(r"사례\s*(\d{1,3})\s*[-—]\s*(\d{1,2})\s*\n?\s*([^\n]{0,60})")
BY = re.compile(r"(\d{4})\s*년\s*제?\s*(\d{1,2})\s*회\s*변호사시험")
MO = re.compile(r"(\d{4})\s*년\s*제?\s*([1-3])\s*차\s*모의")


def main():
    doc = fitz.open(PDF)
    body = "\n".join(doc[i].get_text() for i in range(SKIP_HEAD, doc.page_count - SKIP_TAIL))

    # 장 제목을 위치별로 기억해 두었다가, 각 하위 사례에 가장 가까운 앞 장을 붙인다
    chaps = [(m.start(), re.sub(r"\s+", " ", m.group(2)).strip()) for m in CHAP.finditer(body)]

    subs = list(SUB.finditer(body))
    print(f"하위 사례 {len(subs)}개 / 장 {len(chaps)}개")

    cases = []
    for i, m in enumerate(subs):
        end = subs[i + 1].start() if i + 1 < len(subs) else len(body)
        seg = body[m.end():end].strip()
        if len(seg) < MIN_CHARS:
            continue
        head = m.group(3) + "\n" + seg[:200]
        b, o = BY.search(head), MO.search(head)
        if b:
            src = {"kind": "exam", "examId": f"형사법_변시_{int(b.group(2))}회_사례",
                   "label": f"제{int(b.group(2))}회 변호사시험"}
        elif o:
            src = {"kind": "exam", "examId": f"형사법_모의_{o.group(1)}_{o.group(2)}차_사례",
                   "label": f"{o.group(1)}년 제{o.group(2)}차 모의시험"}
        else:
            src = {"kind": "unlabeled", "examId": None, "label": "출처 미표기"}

        chap = next((t for p, t in reversed(chaps) if p < m.start()), "")
        cases.append({
            "caseNo": f"{m.group(1)}-{m.group(2)}", "title": chap or f"사례 {m.group(1)}",
            "book": BOOK, "author": AUTHOR, "area": "형법",
            "source": src, "text": re.sub(r"\n{3,}", "\n\n", seg), "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    ex = [c for c in cases if c["source"]["kind"] == "exam"]
    print(f"사례 {len(cases)} → 기출 연계 {len(ex)} ({len({c['source']['examId'] for c in ex})}회차) "
          f"/ 창작 {len(cases)-len(ex)}")


if __name__ == "__main__":
    main()
