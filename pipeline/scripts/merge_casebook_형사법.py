# -*- coding: utf-8 -*-
"""형사법: 태깅 완료 데이터에 사례집(조균석) 모범답안을 결합.

공법과 달리 형사법은 사례집 커버리지가 좁다(조균석 책이 변시 6~15회만
책자로 수록, 1~4~5회는 QR코드 온라인 제공이라 텍스트 추출 대상에서 빠짐).
모의고사 40건은 이미 공식 채점기준표(rubricText)가 있어 사례집이 굳이
필요 없고, 변시 15건 중 10건만 사례집 모범답안으로 채워진다.
"""
import json
from pathlib import Path
from collections import defaultdict
from paths import CASEBOOK, SOURCE, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SOURCE / "형사법_사례_final.json"
BLOCKS = CASEBOOK / "criminal_casebook_blocks.json"
OUTDIR = SCRATCH / "final"
OUTDIR.mkdir(exist_ok=True)
OUT = OUTDIR / "형사법_사례_full.json"

blocks = json.load(open(BLOCKS, encoding="utf-8"))
by_exam = defaultdict(list)
for b in blocks:
    by_exam[b["examId"]].append(b)
for k in by_exam:
    by_exam[k].sort(key=lambda x: x["qno"])

data = json.load(open(SRC, encoding="utf-8"))
records = []
for rec in data:
    bl = by_exam.get(rec["id"], [])
    records.append({**rec,
        "casebookAnswers": [{
            "author": b["author"], "area": "형사법", "book": b["book"],
            "caseNo": b["caseNo"], "header": f"문제{b['qno']}",
            "answerText": b["answerText"],
        } for b in bl],
        "hasCasebook": len(bl) > 0,
        "casebookChars": sum(b["chars"] for b in bl),
    })

records.sort(key=lambda r: (r["examType"], r["year"], r["round"] or 0))
json.dump(records, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

real_r = [r for r in records if r["examType"] == "실제기출"]
mock_r = [r for r in records if r["examType"] == "모의고사"]
print(f"형사법 최종 {len(records)}건 → {OUT}\n")
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
