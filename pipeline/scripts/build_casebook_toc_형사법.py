# -*- coding: utf-8 -*-
"""형사법 사례집 목차 + 사례 본문을 앱 데이터로 만든다.

형사법은 회차 전문을 그대로 옮긴 책이 조균석(변시 6~15회)뿐이다. 나머지 45회차는
모범답안이 없다. 대신 주제순 사례집 두 권을 목록으로 붙여 쟁점 훈련에 쓴다.

  이창현 사례형사소송법   449사례  형사소송법
  이인규 형법 변사기      229사례  형법

출처(변시/모의)가 적힌 사례는 '기출 연계'로, 안 적힌 사례는 '출처 미표기'로
가른다. 안 적혔다고 창작이라 단정하지 않는다 — 확인할 방법이 없다.
기출 연계라 해도 저자가 변형·발췌한 것이라 시험 원문과 다를 수 있다.

  casebook_toc.json    목록(가벼움)
  casebook_cases.json  사례 본문. 목록에서 고를 때만 받는다
"""
import json
from collections import defaultdict

from paths import CASEBOOK

SOURCES = [
    ("이창현 형사소송법", "criminal_procedure_cases.json",
     "이창현 사례형사소송법 (26.02)"),
    ("이인규 형법", "criminal_inkyu_cases.json",
     "이인규 형법 변사기 (2026)"),
    ("작은변사기 형소", "jaksik_cases.json",
     "작은변사기 형사소송법 (2027, 재OCR)"),
]
OUT_DIR = CASEBOOK.parent.parent / "data" / "형사법"


def build(cases, prefix):
    for i, c in enumerate(cases):
        # 사례 번호는 장마다 되풀이되어 겹친다. 등장 순서로 고유 id를 붙인다.
        c["uid"] = f"{prefix}{i + 1:03d}"

    by_exam = defaultdict(list)
    unlabeled = []
    for c in cases:
        (by_exam[c["source"]["examId"]] if c["source"]["kind"] == "exam"
         else unlabeled).append(c)

    def row(c, src):
        return {"uid": c["uid"], "caseNo": c["caseNo"], "source": src,
                "label": c["title"], "examId": c["source"]["examId"],
                "groupKey": None, "kind": c["source"]["kind"]}

    exam_rows = []
    for eid in sorted(by_exam, key=lambda x: (("변시" not in x), x)):
        for c in sorted(by_exam[eid], key=lambda x: str(x["caseNo"])):
            exam_rows.append(row(c, c["source"]["label"]))

    parts = [{"title": f"기출 연계 ({len(exam_rows)}사례 · {len(by_exam)}회차)",
              "cases": exam_rows}]
    if unlabeled:
        parts.append({"title": f"출처 미표기 ({len(unlabeled)}사례)",
                      "cases": [row(c, "출처 미표기")
                                for c in sorted(unlabeled, key=lambda x: str(x["caseNo"]))]})
    return parts, len(exam_rows), len(unlabeled)


def main():
    toc, texts = {}, {}
    for i, (name, fname, title) in enumerate(SOURCES):
        cases = json.load(open(CASEBOOK / fname, encoding="utf-8"))
        parts, n_ex, n_un = build(cases, chr(ord("a") + i))
        toc[name] = {"meta": {"title": title, "year": 2026}, "parts": parts}
        for c in cases:
            texts[c["uid"]] = {"title": c["title"], "source": c["source"],
                               "area": c["area"], "book": c["book"],
                               "author": c["author"], "text": c["text"]}
        print(f"{name}: 기출 연계 {n_ex} / 출처 미표기 {n_un}")

    (OUT_DIR / "casebook_toc.json").write_text(
        json.dumps(toc, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "casebook_cases.json").write_text(
        json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    print(f"본문 {len(texts)}사례 → {OUT_DIR}")


if __name__ == "__main__":
    main()
