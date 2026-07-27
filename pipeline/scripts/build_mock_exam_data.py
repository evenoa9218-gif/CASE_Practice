# -*- coding: utf-8 -*-
"""공법 사례형 '모의고사' 데이터를 연도+차수 포함해 JSON으로 만든다."""
import json
from pathlib import Path
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

INDEX_PATH = WORK / "공법_사례_index.json"
OUT_PATH = WORK / "공법_모의_사례.json"

data = json.load(open(INDEX_PATH, encoding="utf-8"))
mock = sorted(
    [r for r in data if r["examType"] == "모의고사"],
    key=lambda r: (r["year"], r["round"]),
)

records = []
for r in mock:
    problem_text = None
    if r["problemFile"]:
        problem_text = Path(r["problemFile"]).read_text(encoding="utf-8", errors="replace")
    rubric_text = None
    if r["rubricFile"]:
        rubric_text = Path(r["rubricFile"]).read_text(encoding="utf-8", errors="replace")

    records.append({
        "id": r["id"],
        "subject": r["subject"],
        "examType": "모의고사",
        "year": r["year"],
        "round": r["round"],
        "label": r["label"],
        "problemText": problem_text,
        "rubricText": rubric_text,
        "hasRubric": rubric_text is not None,
    })

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"{len(records)}건 저장 완료 -> {OUT_PATH}")
has_rubric = sum(1 for r in records if r["hasRubric"])
print(f"채점기준표 있음: {has_rubric} / {len(records)}")
print()
for r in records:
    print(f"  {r['year']}년 {r['round']}차 - 문제 {len(r['problemText'] or '')}자, 채점기준표 {'있음('+str(len(r['rubricText']))+'자)' if r['hasRubric'] else '없음'}")
