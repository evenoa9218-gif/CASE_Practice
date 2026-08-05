# -*- coding: utf-8 -*-
"""이창현 『사례형사소송법』 파싱 — 기출 연계 사례와 창작 사례를 함께 뽑는다.

이 책은 조균석·정연석과 달리 회차순이 아니라 **주제순**이다. 본문 449개 사례 중
출처(변시 N회 / YYYY년 M차 모의)가 붙은 것은 175개(38%)뿐이고 나머지는 저자가
만든 창작 사례다.

창작 사례를 버리지 않는다. 기출만 도는 것보다 쟁점 훈련에 낫기 때문이다.
대신 `source.kind`로 기출 연계(exam)와 창작(original)을 갈라 둔다 —
앱에서 섞이면 사용자가 창작 사례를 기출 정답으로 오해한다.

주의: 기출 연계라 해도 저자가 변형·발췌한 것이라 시험 원문과 다를 수 있다.
그래서 회차에 붙일 때도 '모범답안'이 아니라 별도 이름으로 표시해야 한다.
"""
import json
import re

from pathlib import Path

import fitz

from paths import CASEBOOK, RAW

# 같은 책이지만 판본에 따라 텍스트 층 품질이 다르다. Desktop본은 당사자 표기가
# 38% 깨져 있고(甲乙丙 → 己江心), D 드라이브본은 1%다. 깨끗한 쪽을 쓴다.
PDF = Path(r"D:/pdf/사례/형사법/(26.02)[이창현] 사례형사소송법.pdf")
OUT = CASEBOOK / "criminal_procedure_cases.json"

BOOK = "사례형사소송법"
AUTHOR = "이창현"

# 앞 목차 30쪽, 뒤 판례색인 40쪽은 본문이 아니다
SKIP_HEAD, SKIP_TAIL = 30, 40

HEAD = re.compile(r"사례\s*(\d{1,3})\.\s*([^\n]{4,60})")
SRC = re.compile(
    r"\((\d{4})\s*년\s*제?\s*(\d{1,2})\s*회\s*변호사시험[^)]*\)"
    r"|\((\d{4})\s*년\s*제?\s*([1-3])\s*차\s*모의[^)]*\)"
)
# 각주·판례번호 줄이 본문에 섞여 들어오므로 너무 짧은 조각은 버린다
MIN_CHARS = 400


def main():
    doc = fitz.open(PDF)
    body = "\n".join(doc[i].get_text() for i in range(SKIP_HEAD, doc.page_count - SKIP_TAIL))

    heads = list(HEAD.finditer(body))
    print(f"본문 사례 헤더 {len(heads)}개")

    cases = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        seg = body[m.end():end].strip()
        if len(seg) < MIN_CHARS:
            continue

        # 출처 표기는 문제 지문 끝에 붙는다. 사례 앞부분에서만 찾는다 —
        # 뒤쪽 해설에 나오는 '2018년 제7회 변호사시험' 언급은 출처가 아니다.
        s = SRC.search(seg[:2500])
        if s and s.group(2):
            src = {"kind": "exam", "examId": f"형사법_변시_{int(s.group(2))}회_사례",
                   "label": f"제{int(s.group(2))}회 변호사시험"}
        elif s:
            src = {"kind": "exam", "examId": f"형사법_모의_{s.group(3)}_{s.group(4)}차_사례",
                   "label": f"{s.group(3)}년 제{s.group(4)}차 모의시험"}
        else:
            src = {"kind": "unlabeled", "examId": None, "label": "출처 미표기"}

        cases.append({
            "caseNo": int(m.group(1)),
            "title": re.sub(r"\s+", " ", m.group(2)).strip(),
            "book": BOOK, "author": AUTHOR, "area": "형사소송법",
            "source": src,
            "text": re.sub(r"\n{3,}", "\n\n", seg),
            "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    ex = [c for c in cases if c["source"]["kind"] == "exam"]
    org = [c for c in cases if c["source"]["kind"] == "original"]
    rounds = {c["source"]["examId"] for c in ex}
    print(f"사례 {len(cases)}개 → 기출 연계 {len(ex)} ({len(rounds)}회차) / 창작 {len(org)}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
