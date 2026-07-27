# -*- coding: utf-8 -*-
"""판례 사건번호와 법조문을 정규식으로 추출 (LLM 없이 결정론적 처리)."""
import json
import re
from pathlib import Path
from collections import Counter
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SRC = WORK / "공법_모의_사례.json"
OUT = WORK / "공법_모의_citations.json"

# 사건번호: 2019두12345, 92다15031, 2020헌마123, 2018헌바1 등
# 연도(2~4자리) + 사건부호(한글 1~2자) + 번호
CASE_RE = re.compile(r"\b(\d{2,4})\s*(헌마|헌바|헌가|헌라|헌나|헌사|헌아|두|다|누|도|므|추|카|허|후|재|초)\s*(\d+)\b")

# 법조문: "행정소송법 제20조", "헌법재판소법 제68조 제2항", "헌법 제27조 제4항"
STATUTE_RE = re.compile(
    r"([가-힣]{2,20}(?:법|법률|규칙|령|헌법))\s*(제\s*\d+조(?:\s*의\s*\d+)?"
    r"(?:\s*제\s*\d+항)?(?:\s*제\s*\d+호)?)"
)

data = json.load(open(SRC, encoding="utf-8"))

results = []
for rec in data:
    combined = (rec.get("problemText") or "") + "\n" + (rec.get("rubricText") or "")

    cases = []
    for y, code, num in CASE_RE.findall(combined):
        cases.append(f"{y}{code}{num}")
    case_counts = Counter(cases)

    statutes = []
    for law, article in STATUTE_RE.findall(combined):
        norm = re.sub(r"\s+", " ", f"{law} {article}").strip()
        statutes.append(norm)
    statute_counts = Counter(statutes)

    results.append({
        "id": rec["id"],
        "year": rec["year"],
        "round": rec["round"],
        "label": rec["label"],
        # 등장 횟수 순 정렬 (핵심 판례/조문이 앞으로)
        "caseCitations": [c for c, _ in case_counts.most_common()],
        "caseCitationCounts": dict(case_counts.most_common()),
        "statutes": [s for s, _ in statute_counts.most_common(30)],
        "statuteCounts": dict(statute_counts.most_common(30)),
    })

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"{len(results)}건 추출 완료 -> {OUT}\n")
for r in results[:5]:
    print(f"[{r['label']}]")
    print(f"  판례({len(r['caseCitations'])}): {r['caseCitations'][:8]}")
    print(f"  조문({len(r['statutes'])}): {r['statutes'][:5]}")
    print()

total_cases = sum(len(r["caseCitations"]) for r in results)
total_statutes = sum(len(r["statutes"]) for r in results)
no_case = [r["label"] for r in results if not r["caseCitations"]]
print(f"총 판례 인용 {total_cases}건, 조문 {total_statutes}건")
if no_case:
    print(f"판례 미검출 항목: {no_case}")
