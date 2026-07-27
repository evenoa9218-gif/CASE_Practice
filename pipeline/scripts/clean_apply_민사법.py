# -*- coding: utf-8 -*-
"""민사법_사례_full.json에 정제 적용."""
import json, re
from pathlib import Path
import clean_text as C
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "민사법_사례_full.json"
OUT = SCRATCH / "final" / "민사법_사례_full_clean.json"

# 정연석 책의 반복 라벨/페이지머리 제거: 줄 시작의 "제N문(의M)" 라벨 중복,
# 단독 페이지번호 줄 등은 C.clean_pdf 의 PAGE_NUM_LINE 이 이미 처리.
REPEAT_LABEL = re.compile(r"^(제\s*\d+\s*문(?:\s*의\s*\d+)?)(?:\s*\1)+", re.M)

def clean_casebook_answer(t):
    t = REPEAT_LABEL.sub(r"\1", t)
    return C.clean_pdf(t)

data = json.load(open(SRC, encoding="utf-8"))
for r in data:
    r["problemText"] = C.clean_hwp(r["problemText"])
    if r.get("rubricText"):
        r["rubricText"] = C.clean_hwp(r["rubricText"])
    for cb in r.get("casebookAnswers", []):
        cb["answerText"] = clean_casebook_answer(cb["answerText"])

json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"정제 완료 → {OUT}")

leftover = sum(t.count("<표>") + t.count("<그림>") for r in data for t in [r["problemText"], r.get("rubricText") or ""])
print("잔존 <표>/<그림>:", leftover)
