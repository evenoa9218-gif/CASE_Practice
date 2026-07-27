# -*- coding: utf-8 -*-
"""태깅 배치 결과 + 정규식 추출(판례/조문) + 원본 전문을 하나로 병합."""
import json
import re
from pathlib import Path
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
TAGDIR = SCRATCH / "tag_output"
SRC = SCRATCH / "공법_모의_사례.json"
CITES = SCRATCH / "공법_모의_citations.json"
OUT = SCRATCH / "공법_사례_final.json"

# 1) 배치 결과 병합
tags = {}
dupes = []
for f in sorted(TAGDIR.glob("batch_*.json")):
    raw = f.read_text(encoding="utf-8").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)   # 혹시 코드블록으로 감싼 경우 제거
    items = json.loads(raw)
    for it in items:
        if it["id"] in tags:
            dupes.append(it["id"])
        tags[it["id"]] = it
    print(f"{f.name}: {len(items)}건")

print(f"\n태깅 총 {len(tags)}건 (중복 {len(dupes)}건)")
if dupes:
    print("  중복:", dupes)

# 2) 원본 + 판례/조문 병합
src = json.load(open(SRC, encoding="utf-8"))
cites = {c["id"]: c for c in json.load(open(CITES, encoding="utf-8"))}

final = []
missing_tag = []
for rec in src:
    t = tags.get(rec["id"])
    if not t:
        missing_tag.append(rec["id"])
    c = cites.get(rec["id"], {})
    final.append({
        # 식별 정보
        "id": rec["id"],
        "subject": rec["subject"],
        "examType": rec["examType"],          # 모의고사 / 실제기출
        "year": rec["year"],
        "round": rec["round"],
        "label": rec["label"],
        # 원문 (절대 축약 금지 — 원본 txt와 바이트 일치 검증됨)
        "problemText": rec["problemText"],
        "rubricText": rec["rubricText"],
        "hasRubric": rec["hasRubric"],
        # 정규식 추출 (결정론적)
        "caseCitations": c.get("caseCitations", []),
        "statutes": c.get("statutes", []),
        # LLM 개념 태깅
        "majorField": (t or {}).get("majorField"),
        "subFields": (t or {}).get("subFields", []),
        "issueKeywords": (t or {}).get("issueKeywords", []),
        "factSummary": (t or {}).get("factSummary"),
        "questionStructure": (t or {}).get("questionStructure", []),
    })

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(final, f, ensure_ascii=False, indent=2)

print(f"\n최종 {len(final)}건 저장 -> {OUT}")
if missing_tag:
    print(f"태깅 누락: {missing_tag}")

# 3) 무결성 체크
no_field = [r["id"] for r in final if not r["majorField"]]
no_kw = [r["id"] for r in final if not r["issueKeywords"]]
no_qs = [r["id"] for r in final if not r["questionStructure"]]
no_text = [r["id"] for r in final if not r["problemText"] or not r["rubricText"]]
print(f"\n무결성: majorField 누락 {len(no_field)}, issueKeywords 누락 {len(no_kw)}, "
      f"questionStructure 누락 {len(no_qs)}, 원문 누락 {len(no_text)}")
for name, lst in (("majorField", no_field), ("issueKeywords", no_kw),
                  ("questionStructure", no_qs), ("원문", no_text)):
    if lst:
        print(f"  {name}: {lst}")
