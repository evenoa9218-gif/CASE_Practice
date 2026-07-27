# -*- coding: utf-8 -*-
"""공법: 기존 문제/채점기준표 데이터에 사례집 모범답안을 결합."""
import json
from pathlib import Path
from collections import defaultdict
from paths import CASEBOOK, SOURCE, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
BLOCKS = CASEBOOK / "casebook_blocks_공법.json"
MOCK = SOURCE / "공법_사례_final.json"      # 모의 40건 (태깅 완료)
REAL = SOURCE / "공법_변시_final.json"      # 변시 15건 (태깅 완료)
OUTDIR = SCRATCH / "final"
OUTDIR.mkdir(exist_ok=True)
OUT = OUTDIR / "공법_사례_full.json"

blocks = json.load(open(BLOCKS, encoding="utf-8"))
by_exam = defaultdict(list)
for b in blocks:
    by_exam[b["examId"]].append(b)

# 블록 정렬: 저자 → 사례번호
for k in by_exam:
    by_exam[k].sort(key=lambda x: (x["author"], int(x["caseNo"])))

records = []

# 모의고사
for rec in json.load(open(MOCK, encoding="utf-8")):
    bl = by_exam.get(rec["id"], [])
    records.append({**rec,
        "casebookAnswers": [{
            "author": b["author"], "area": b["area"], "book": b["book"],
            "caseNo": b["caseNo"], "header": b["header"], "answerText": b["answerText"],
        } for b in bl],
        "hasCasebook": len(bl) > 0,
        "casebookChars": sum(b["chars"] for b in bl),
    })

# 실제 변시
for rec in json.load(open(REAL, encoding="utf-8")):
    bl = by_exam.get(rec["id"], [])
    records.append({
        "id": rec["id"], "subject": "공법", "examType": "실제기출",
        "year": rec["year"], "round": None, "hoi": rec["hoi"], "label": rec["label"],
        "problemText": rec["problemText"],
        "rubricText": None, "hasRubric": False,
        "caseCitations": [], "statutes": [],
        "majorField": rec.get("majorField"), "subFields": rec.get("subFields", []),
        "issueKeywords": rec.get("issueKeywords", []),
        "factSummary": rec.get("factSummary"),
        "questionStructure": rec.get("questionStructure", []),
        "inferredCases": rec.get("inferredCases", []),
        "casebookAnswers": [{
            "author": b["author"], "area": b["area"], "book": b["book"],
            "caseNo": b["caseNo"], "header": b["header"], "answerText": b["answerText"],
        } for b in bl],
        "hasCasebook": len(bl) > 0,
        "casebookChars": sum(b["chars"] for b in bl),
    })

records.sort(key=lambda r: (r["examType"], r["year"], r["round"] or 0))
json.dump(records, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

mock_r = [r for r in records if r["examType"] == "모의고사"]
real_r = [r for r in records if r["examType"] == "실제기출"]

print(f"공법 최종 {len(records)}건 → {OUT}\n")
print(f"{'구분':<8}{'건수':>5}{'채점기준표':>10}{'사례집답안':>10}{'채점근거有':>10}")
for name, rs in (("모의고사", mock_r), ("변시", real_r)):
    rub = sum(1 for r in rs if r["hasRubric"])
    cb = sum(1 for r in rs if r["hasCasebook"])
    both = sum(1 for r in rs if r["hasRubric"] or r["hasCasebook"])
    print(f"{name:<8}{len(rs):>5}{rub:>10}{cb:>10}{both:>10}")

print("\n=== 변시 회차별 (채점기준표 없어 사례집이 유일 근거) ===")
for r in sorted(real_r, key=lambda x: x["hoi"]):
    print(f"  제{r['hoi']:2d}회({r['year']}) 사례집 {len(r['casebookAnswers']):2d}블록 {r['casebookChars']:>7,}자")

no_basis = [r["id"] for r in records if not r["hasRubric"] and not r["hasCasebook"]]
print(f"\n채점근거 없는 항목: {len(no_basis)}건")
if no_basis:
    print("  ", no_basis)
