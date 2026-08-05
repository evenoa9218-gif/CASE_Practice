# -*- coding: utf-8 -*-
"""공법 사례집 목차에 정선균 행정법을 덧붙인다.

공법에는 이미 강성민·류정모에서 뽑은 목차가 있고, 그 항목들은 회차의 특정
설문으로 바로 건너뛴다(examId + groupKey). 정선균은 문 단위라 groupKey가 없어
사례 본문을 띄우는 쪽으로 연결한다.

기존 항목은 건드리지 않는다 — 책 이름을 키로 덧붙이기만 한다.
"""
import json

from paths import CASEBOOK

SOURCES = [("정선균 행정법", "jsg_cases.json",
            "정선균 행정법 기출해설 바이블 (26.03, 재OCR)")]
OUT_DIR = CASEBOOK.parent.parent / "data" / "공법"


def main():
    toc_path = OUT_DIR / "casebook_toc.json"
    toc = json.load(open(toc_path, encoding="utf-8")) if toc_path.exists() else {}

    cases_path = OUT_DIR / "casebook_cases.json"
    texts = json.load(open(cases_path, encoding="utf-8")) if cases_path.exists() else {}

    for i, (name, fname, title) in enumerate(SOURCES):
        cases = json.load(open(CASEBOOK / fname, encoding="utf-8"))
        for k, c in enumerate(cases):
            c["uid"] = f"p{chr(ord('a') + i)}{k + 1:03d}"

        rows = [{"uid": c["uid"], "caseNo": c["caseNo"],
                 "source": c["source"]["label"], "label": c["title"],
                 "examId": c["source"]["examId"], "groupKey": None, "kind": "exam"}
                for c in cases]
        toc[name] = {"meta": {"title": title, "year": 2026},
                     "parts": [{"title": f"기출 해설 ({len(rows)}사례)", "cases": rows}]}
        for c in cases:
            texts[c["uid"]] = {"title": c["title"], "source": c["source"],
                               "area": c["area"], "book": c["book"],
                               "author": c["author"], "text": c["text"]}
        print(f"{name}: {len(rows)}사례")

    toc_path.write_text(json.dumps(toc, ensure_ascii=False, indent=1), encoding="utf-8")
    cases_path.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    print(f"목차 책 {len(toc)}종 / 본문 {len(texts)}사례 → {OUT_DIR}")


if __name__ == "__main__":
    main()
