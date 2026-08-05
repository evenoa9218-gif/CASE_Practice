# -*- coding: utf-8 -*-
"""형사법 사례집 목차 + 사례 본문을 앱 데이터로 만든다.

이창현 『사례형사소송법』은 주제순이라 회차에 통째로 붙지 않는다. 449개 사례 중
175개만 출처(변시/모의)가 있고 274개는 저자 창작이다.

창작을 버리지 않는다 — 기출만 도는 것보다 쟁점 훈련에 낫다. 대신 목차를
'기출 연계'와 '창작 사례' 두 묶음으로 갈라 둔다. 섞이면 창작을 기출 정답으로
오해한다.

  casebook_toc.json    목록(가벼움). 기출 연계는 해당 회차로 건너뛸 수 있다.
  casebook_cases.json  사례 본문(무거움). 목록에서 고를 때만 받는다.
"""
import json
from collections import defaultdict

from paths import CASEBOOK

SRC = CASEBOOK / "criminal_procedure_cases.json"
OUT_DIR = CASEBOOK.parent.parent / "data" / "형사법"
BOOK = "이창현 형사소송법"


def main():
    cases = json.load(open(SRC, encoding="utf-8"))
    # 사례 번호는 편마다 다시 1로 돌아가서 겹친다. 본문을 번호로만 담으면
    # 449개 중 104개가 덮어써진다. 등장 순서로 고유 id를 붙인다.
    for i, c in enumerate(cases):
        c["uid"] = f'c{i+1:03d}'

    # 기출 연계는 회차별로, 창작은 번호순으로 늘어놓는다
    by_exam = defaultdict(list)
    original = []
    for c in cases:
        (by_exam[c["source"]["examId"]] if c["source"]["kind"] == "exam" else original).append(c)

    parts = []
    exam_cases = []
    for eid in sorted(by_exam, key=lambda x: (("변시" not in x), x)):
        for c in sorted(by_exam[eid], key=lambda x: x["caseNo"]):
            exam_cases.append({
                "uid": c["uid"], "caseNo": c["caseNo"], "source": c["source"]["label"],
                "label": c["title"], "examId": eid, "groupKey": None,
                "kind": "exam",
            })
    parts.append({"title": f"기출 연계 ({len(exam_cases)}사례 · {len(by_exam)}회차)",
                  "cases": exam_cases})
    parts.append({"title": f"창작 사례 ({len(original)}사례)",
                  "cases": [{"uid": c["uid"], "caseNo": c["caseNo"], "source": "저자 창작",
                             "label": c["title"], "examId": None, "groupKey": None,
                             "kind": "original"}
                            for c in sorted(original, key=lambda x: x["caseNo"])]})

    toc_path = OUT_DIR / "casebook_toc.json"
    prev = json.load(open(toc_path, encoding="utf-8")) if toc_path.exists() else {}
    prev[BOOK] = {"meta": {"title": "이창현 사례형사소송법 (26.02)", "year": 2026},
                  "parts": parts}
    toc_path.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")

    texts = {c["uid"]: {"title": c["title"], "source": c["source"],
                                "area": c["area"], "book": c["book"],
                                "author": c["author"], "text": c["text"]}
             for c in cases}
    (OUT_DIR / "casebook_cases.json").write_text(
        json.dumps(texts, ensure_ascii=False), encoding="utf-8")

    print(f"목차 {len(exam_cases)}(기출) + {len(original)}(창작) → {toc_path}")
    print(f"본문 {len(texts)}사례 → {OUT_DIR / 'casebook_cases.json'}")


if __name__ == "__main__":
    main()
