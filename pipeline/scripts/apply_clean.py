# -*- coding: utf-8 -*-
"""정제기를 전체 공법 데이터에 적용 + 안전성 검증."""
import json
import re
from pathlib import Path
import clean_text as C
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "공법_사례_full.json"
OUT = SCRATCH / "final" / "공법_사례_full_clean.json"

data = json.load(open(SRC, encoding="utf-8"))

# ── 안전성 검증: 한글 음절이 손실되지 않았는지 ──────────
def hangul_only(t):
    return re.sub(r"[^가-힣]", "", t or "")

stats = {"problem": [0,0], "rubric": [0,0], "casebook": [0,0]}
warn = []

for rec in data:
    for key, fn, slot in (("problemText", C.clean_hwp, "problem"),
                          ("rubricText", C.clean_hwp, "rubric")):
        src = rec.get(key)
        if not src:
            continue
        dst = fn(src)
        h0, h1 = hangul_only(src), hangul_only(dst)
        stats[slot][0] += len(src); stats[slot][1] += len(dst)
        if h0 != h1:
            lost = len(h0) - len(h1)
            warn.append((rec["id"], key, lost))
        rec[key] = dst

    for b in rec.get("casebookAnswers", []):
        src = b["answerText"]
        dst = C.clean_pdf(src)
        h0, h1 = hangul_only(src), hangul_only(dst)
        stats["casebook"][0] += len(src); stats["casebook"][1] += len(dst)
        # PDF는 머리글 제거로 한글이 줄어드는 게 정상 → 큰 손실만 경고
        if len(h0) - len(h1) > len(h0) * 0.03:
            warn.append((rec["id"], f"casebook#{b['caseNo']}", len(h0)-len(h1)))
        b["answerText"] = dst
    rec["casebookChars"] = sum(len(b["answerText"]) for b in rec.get("casebookAnswers", []))

json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("=== 정제 결과 (문자 수 변화) ===")
for k, (a, b) in stats.items():
    if a:
        print(f"  {k:<10} {a:>9,} → {b:>9,}  ({(b-a)/a*100:+.1f}%)")

print(f"\n한글 손실 경고: {len(warn)}건")
for w in warn[:10]:
    print("  ", w)

# ── 잔여 아티팩트 재검사 ─────────────────────────────────
PAT = {
    "<표>/<그림>": r"<(?:표|그림)>",
    "빈 줄 3연속+": r"\n{3,}",
    "줄 끝 공백": r"[ \t]+\n",
    "연속 공백": r"[^\n][ ]{2,}",
    "페이지번호 단독줄": r"^\s*\d{1,4}\s*$",
    "깨진 문자": r"[\ufffd□■]",
    "제 N 조 (분리)": r"제\s+\d+\s*조",
}
def texts(field):
    if field == "casebook":
        return [b["answerText"] for r in data for b in r["casebookAnswers"]]
    return [r[field] or "" for r in data]

print("\n=== 정제 후 잔여 아티팩트 ===")
for field, label in (("problemText","문제"),("rubricText","채점기준표"),("casebook","사례집")):
    ts = [t for t in texts(field) if t]
    line = []
    for name, p in PAT.items():
        c = sum(len(re.findall(p, t, re.M)) for t in ts)
        if c: line.append(f"{name} {c}")
    print(f"  [{label}] " + (", ".join(line) if line else "없음 ✓"))

print(f"\n저장: {OUT}")
