# -*- coding: utf-8 -*-
"""민사법 사례집 목차 + 사례 본문을 앱 데이터로 만든다.

민사법은 정연석 책으로 53/55 회차에 모범답안이 붙어 있다. 여기에 더해
상법 사례집을 목록으로 붙인다 — 변호사시험 민사법은 민법·민소법·상법이
함께 나오는데, 정연석 책은 상법을 다루지 않는다.

앱에 없는 회차(2012년 등 데이터 범위 밖)는 회차 연결을 지우고 목록에만 남긴다.
"""
import json
from collections import defaultdict

from paths import CASEBOOK

SOURCES = [("인사이트 상법", "commercial_cases.json",
            "인사이트 상법 사례형 해설편 (2026)"),
           ("송영곤 민사소송법", "civil_procedure_cases.json",
            "송영곤 민소사연 (26.01)"),
           ("박승수 CBT실전답안", "parkss_cases.json",
            "박승수 민민소 사례 CBT실전답안 (26.02, 재OCR)")]
OUT_DIR = CASEBOOK.parent.parent / "data" / "민사법"


def main():
    idx = json.load(open(OUT_DIR / "index.json", encoding="utf-8"))
    exams = idx if isinstance(idx, list) else idx.get("exams", idx)
    if isinstance(exams, dict):
        exams = list(exams.values())
    known = {e["id"] for e in exams}
    toc, texts = {}, {}

    for i, (name, fname, title) in enumerate(SOURCES):
        cases = json.load(open(CASEBOOK / fname, encoding="utf-8"))
        for k, c in enumerate(cases):
            c["uid"] = f"m{chr(ord('a') + i)}{k + 1:03d}"

        # 출처가 아예 없는 것과, 출처는 있지만 앱 데이터 범위 밖인 것을 구분한다.
        # 둘을 뭉뚱그리면 "범위 밖"이라는 잘못된 설명이 붙는다.
        by_exam, outside, nosrc = defaultdict(list), [], []
        for c in cases:
            eid = c["source"]["examId"]
            if eid is None:
                nosrc.append(c)
            elif eid in known:
                by_exam[eid].append(c)
            else:
                outside.append(c)

        def row(c, linked):
            return {"uid": c["uid"], "caseNo": c["caseNo"],
                    "source": c["source"]["label"], "label": c["title"],
                    "examId": c["source"]["examId"] if linked else None,
                    "groupKey": None, "kind": "exam" if linked else "unlabeled"}

        rows = []
        for eid in sorted(by_exam, key=lambda x: (("변시" not in x), x)):
            rows += [row(c, True) for c in sorted(by_exam[eid], key=lambda x: str(x["caseNo"]))]

        parts = []
        if rows:
            parts.append({"title": f"기출 연계 ({len(rows)}사례 · {len(by_exam)}회차)",
                          "cases": rows})
        if outside:
            parts.append({"title": f"앱 범위 밖 회차 ({len(outside)}사례)",
                          "cases": [row(c, False) for c in outside]})
        if nosrc:
            parts.append({"title": f"출처 미표기 ({len(nosrc)}사례)",
                          "cases": [row(c, False) for c in nosrc]})

        toc[name] = {"meta": {"title": title, "year": 2026}, "parts": parts}
        for c in cases:
            texts[c["uid"]] = {"title": c["title"], "source": c["source"],
                               "area": c["area"], "book": c["book"],
                               "author": c["author"], "text": c["text"]}
        print(f"{name}: 기출 연계 {len(rows)} / 범위 밖 {len(outside)} / 출처 미표기 {len(nosrc)}")

    (OUT_DIR / "casebook_toc.json").write_text(
        json.dumps(toc, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "casebook_cases.json").write_text(
        json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    print(f"본문 {len(texts)}사례 → {OUT_DIR}")


if __name__ == "__main__":
    main()
