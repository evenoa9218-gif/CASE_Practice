# -*- coding: utf-8 -*-
"""공법 사례형 '실제 변호사시험' 1~15회 데이터를 연도+회차 포함해 JSON으로 만든다."""
import json
from pathlib import Path
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

INDEX_PATH = WORK / "공법_사례_index.json"
OUT_PATH = WORK / "공법_변시_사례_1to15.json"

data = json.load(open(INDEX_PATH, encoding="utf-8"))
real = sorted([r for r in data if r["examType"] == "실제기출"], key=lambda r: r["hoi"])

records = []
for r in real:
    problem_text = None
    if r["problemFile"]:
        problem_text = Path(r["problemFile"]).read_text(encoding="utf-8", errors="replace")
    rubric_text = None
    if r["rubricFile"]:
        rubric_text = Path(r["rubricFile"]).read_text(encoding="utf-8", errors="replace")

    records.append({
        "id": r["id"],
        "subject": r["subject"],
        "examType": "실제기출",
        "hoi": r["hoi"],
        "year": r["year"],
        "label": r["label"],
        "problemText": problem_text,
        "rubricText": rubric_text,        # 현재 전부 null — 공식 채점기준표 미공개
        "hasRubric": rubric_text is not None,
    })

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"{len(records)}건 저장 완료 -> {OUT_PATH}")
for r in records:
    print(f"  {r['hoi']}회 ({r['year']}년) - 문제 {len(r['problemText'] or '')}자, 채점기준표 {'있음' if r['hasRubric'] else '없음'}")
