# -*- coding: utf-8 -*-
"""형사법 사례집(조균석) 파싱 — 깨끗한 판본을 쓴다.

기존 split_casebook_criminal.py는 `(26.04)[조균석] 형사법 사례형 해설.txt`를
읽는데, 그 OCR본은 당사자 표기가 59% 깨져 있다(甲乙丙 → 己江心因內).
사례 문제에서 누가 누구인지가 뒤섞이면 못 쓴다.

D:\\pdf에 있는 `(25.04)[조균석·강수진·이효진] 형사법 사례형 해설.pdf`는
텍스트 층이 깨끗하고(의심률 1%) 변시 1~14회를 덮는다. 기존 판본이 6~15회만
다뤘던 것보다 넓다 — 지금 모범답안이 없던 변시 1~5회가 들어온다.

15회는 이 책에 없으므로 기존 블록을 남겨 두고 합친다.
"""
import json
import re
from pathlib import Path

import fitz

from paths import CASEBOOK

PDF = Path(r"D:/pdf/사례/형사법/(25.04)[조균석·강수진·이효진] 형사법 사례형 해설.pdf")
OUT = CASEBOOK / "criminal_casebook_blocks.json"
BOOK = "형사법 사례형 해설"
AUTHOR = "조균석·강수진·이효진"

MARK = re.compile(r"사례\s*(\d+)\s*[.．]\s*[\[［]\s*(\d+)\s*[-—－]\s*변시\s*[\(（]\s*(\d+)\s*[\)）]"
                  r"\s*[-—－]\s*(\d+)\s*[\]］]")
MIN_CHARS = 800


def main():
    doc = fitz.open(PDF)
    body = "\n".join(doc[i].get_text() for i in range(20, doc.page_count - 20))

    # 쪽머리에 사례 표시가 되풀이되므로 사례 번호가 바뀌는 첫 지점만 경계로 삼는다
    marks = []
    for m in MARK.finditer(body):
        key = int(m.group(1))
        if not marks or marks[-1][1] != key:
            marks.append((m.start(), key, int(m.group(3)), int(m.group(4))))
    print(f"사례 구간 {len(marks)}개")

    blocks = []
    for i, (pos, case_no, hoi, qno) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        seg = re.sub(r"\n{3,}", "\n\n", body[pos:end].strip())
        if len(seg) < MIN_CHARS:
            continue
        blocks.append({
            "examId": f"형사법_변시_{hoi}회_사례", "hoi": str(hoi), "qno": str(qno),
            "caseNo": str(case_no), "book": BOOK, "author": AUTHOR, "area": "형사법",
            "answerText": seg, "chars": len(seg),
        })

    # 이 책에 없는 회차(15회)는 기존 블록을 살려 둔다
    if OUT.exists():
        old = json.load(open(OUT, encoding="utf-8"))
        have = {b["examId"] for b in blocks}
        kept = [b for b in old if b["examId"] not in have]
        if kept:
            print(f"기존 블록 유지 {len(kept)}개 ({sorted({b['examId'] for b in kept})})")
            blocks += kept

    OUT.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
    rounds = sorted({b["examId"] for b in blocks})
    print(f"블록 {len(blocks)}개 / {len(rounds)}회차")


if __name__ == "__main__":
    main()
