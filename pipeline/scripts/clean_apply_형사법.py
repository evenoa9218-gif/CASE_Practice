# -*- coding: utf-8 -*-
"""형사법_사례_full.json에 정제 적용 (hwp 문제/채점기준표, PDF 사례집답안)."""
import json, re
from pathlib import Path
import clean_text as C
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "형사법_사례_full.json"
OUT = SCRATCH / "final" / "형사법_사례_full_clean.json"

# 조균석 책 특유의 반복 페이지머리("사례 5. [19 - 변시(8)-1] 129") 제거
REPEAT_HEAD = re.compile(r"^사례\s*\d+\s*[.．]\s*[\[［].*?[\]］]\s*\d*\s*$", re.M)

def clean_casebook_answer(t):
    t = REPEAT_HEAD.sub("", t)
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

# 간단 검증: 표/그림 플레이스홀더 잔존 여부
leftover = sum(t.count("<표>") + t.count("<그림>") for r in data for t in [r["problemText"], r.get("rubricText") or ""])
print("잔존 <표>/<그림>:", leftover)
