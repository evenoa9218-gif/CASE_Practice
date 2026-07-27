# -*- coding: utf-8 -*-
"""형사법(변시 6~15회) 사례집(조균석) 사례 블록 분할 + 시험 매핑."""
import json, re
from pathlib import Path
from paths import CASEBOOK, RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW / "사례집" / "형법"
OUT = CASEBOOK / "criminal_casebook_blocks.json"

FILE = BASE / "(26.04)[조균석] 형사법 사례형 해설.txt"
# 본문(목차 아님) 헤더만: "사례 5. [19 - 변시(8) - 1]" 형태(마침표+대괄호 필수 → 목차 항목과 구분)
MARK = re.compile(r"^사례\s*(\d+)\s*[.．]\s*[\[［]\s*(\d+)\s*[-—－]\s*변시\s*[\(（]\s*(\d+)\s*[\)）]\s*[-—－]\s*(\d+)\s*[\]］]", re.M)

text = FILE.read_text(encoding="utf-8", errors="replace")
hits = list(MARK.finditer(text))
print(f"총 매치: {len(hits)}개")

# 사례 N별로 첫 등장부터 다음 "사례 N+1." 헤더 전까지를 한 블록으로 묶는다(반복되는 페이지머리 포함)
blocks_by_case = {}
order = []
for i, m in enumerate(hits):
    case_no = int(m.group(1))
    if case_no not in blocks_by_case:
        blocks_by_case[case_no] = {"start": m.start(), "hoi": int(m.group(3)), "qno": int(m.group(4))}
        order.append(case_no)

out = []
for i, case_no in enumerate(order):
    info = blocks_by_case[case_no]
    start = info["start"]
    end = blocks_by_case[order[i+1]]["start"] if i+1 < len(order) else len(text)
    body = text[start:end].strip()
    out.append({
        "examId": f"형사법_변시_{info['hoi']}회_사례",
        "hoi": info["hoi"],
        "qno": info["qno"],
        "caseNo": case_no,
        "book": FILE.name,
        "author": "조균석",
        "answerText": body,
        "chars": len(body),
    })

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"블록 {len(out)}개 저장 → {OUT}")

covered_hoi = sorted(set(b["hoi"] for b in out))
print("커버 회차:", covered_hoi)
by_exam = {}
for b in out:
    by_exam.setdefault(b["examId"], []).append(b)
for eid in sorted(by_exam, key=lambda k: int(re.search(r"(\d+)회", k).group(1))):
    bl = by_exam[eid]
    print(f"  {eid}: 문항 {sorted(set(b['qno'] for b in bl))}, 총 {sum(b['chars'] for b in bl):,}자")
