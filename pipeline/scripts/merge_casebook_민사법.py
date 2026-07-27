# -*- coding: utf-8 -*-
"""민사법: 태깅 완료 데이터에 사례집(정연석) 모범답안을 결합.

정연석 책은 25/55건(변시 8회차 + 모의고사 17회차)에서 사례 블록을 뽑을 수
있었다(2013~2018년 구간은 "요약"만 있어 제외, 일부 회차는 책 자체에 상세
해설이 없음). 모의고사는 이미 공식 채점기준표가 있어 사례집 결합이 필수는
아니지만, 있으면 참고자료로 함께 붙인다.
"""
import json
from pathlib import Path
from collections import defaultdict
from paths import CASEBOOK, SOURCE, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SOURCE / "민사법_사례_final.json"
BLOCKS = CASEBOOK / "civil_casebook_blocks.json"
OUTDIR = SCRATCH / "final"
OUTDIR.mkdir(exist_ok=True)
OUT = OUTDIR / "민사법_사례_full.json"

blocks = json.load(open(BLOCKS, encoding="utf-8"))
by_exam = defaultdict(list)
for b in blocks:
    by_exam[b["examId"]].append(b)
for k in by_exam:
    by_exam[k].sort(key=lambda x: (x["qno"], x["subno"] or 0))

data = json.load(open(SRC, encoding="utf-8"))
records = []
for rec in data:
    bl = by_exam.get(rec["id"], [])
    records.append({**rec,
        "casebookAnswers": [{
            "author": "정연석", "area": "민사법", "book": "로스쿨 민사 사례형 기출문제집[해설편]",
            "caseNo": i + 1, "header": b["label"],
            "answerText": b["answerText"],
        } for i, b in enumerate(bl)],
        "hasCasebook": len(bl) > 0,
        "casebookChars": sum(b["chars"] for b in bl),
    })

records.sort(key=lambda r: (r["examType"], r["year"], r["round"] or 0))
json.dump(records, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

real_r = [r for r in records if r["examType"] == "실제기출"]
mock_r = [r for r in records if r["examType"] == "모의고사"]
print(f"민사법 최종 {len(records)}건 → {OUT}\n")
print(f"{'구분':<8}{'건수':>5}{'채점기준표':>10}{'사례집답안':>10}{'채점근거有':>10}")
for name, rs in (("모의고사", mock_r), ("변시", real_r)):
    rub = sum(1 for r in rs if r["hasRubric"])
    cb = sum(1 for r in rs if r["hasCasebook"])
    both = sum(1 for r in rs if r["hasRubric"] or r["hasCasebook"])
    print(f"{name:<8}{len(rs):>5}{rub:>10}{cb:>10}{both:>10}")

print("\n=== 변시 회차별 ===")
for r in sorted(real_r, key=lambda x: x["hoi"]):
    print(f"  제{r['hoi']:2d}회({r['year']}) 사례집 {len(r['casebookAnswers'])}블록 {r['casebookChars']:>7,}자"
          f"{'  ← 근거 없음' if not r['hasRubric'] and not r['hasCasebook'] else ''}")

no_basis = [r["id"] for r in records if not r["hasRubric"] and not r["hasCasebook"]]
print(f"\n채점근거 없는 항목: {len(no_basis)}건: {no_basis}")
