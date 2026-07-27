# -*- coding: utf-8 -*-
"""데이터 텍스트 품질 진단 — 어떤 추출 흔적이 얼마나 있는지."""
import json
import re
from pathlib import Path
from collections import Counter
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SRC = WORK / "final" / "공법_사례_full.json"
data = json.load(open(SRC, encoding="utf-8"))

def collect(field):
    if field == "casebook":
        return [b["answerText"] for r in data for b in r["casebookAnswers"]]
    return [r[field] or "" for r in data]

PATTERNS = {
    "<표> 플레이스홀더":      r"<표>",
    "<그림> 플레이스홀더":    r"<그림>",
    "빈 줄 3연속 이상":       r"\n{3,}",
    "줄 끝 공백":             r"[ \t]+\n",
    "연속 공백 2개+":         r"[^\n][ ]{2,}",
    "전각 공백":              r"\u3000",
    "제로폭 문자":            r"[\u200b\u200c\u200d\ufeff]",
    "단어 사이 깨진 공백(한글)": r"[가-힣] [가-힣](?=[가-힣])",
    "숫자 사이 공백":         r"\d\s+\d",
    "괄호 앞뒤 공백":         r"[ ]+[)）]|[(（][ ]+",
    "조사 앞 공백":           r"[가-힣] (은|는|이|가|을|를|의|에|와|과|로|으로)\b",
    "페이지번호 추정(단독 숫자줄)": r"^\s*\d{1,4}\s*$",
    "점선/구분선":            r"[.·]{6,}|[-—=]{6,}",
    "깨진 문자(사각형 등)":   r"[\ufffd□■]",
}

print("=" * 72)
for field, label in (("problemText","문제"), ("rubricText","채점기준표"), ("casebook","사례집 모범답안")):
    texts = [t for t in collect(field) if t]
    total = sum(len(t) for t in texts)
    print(f"\n[{label}]  {len(texts)}건, 총 {total:,}자")
    for name, pat in PATTERNS.items():
        c = sum(len(re.findall(pat, t, re.M)) for t in texts)
        if c:
            per = c / len(texts)
            print(f"   {name:<26} {c:>7,}건  (건당 {per:.1f})")

# 실제 샘플로 눈으로 확인
print("\n" + "=" * 72)
print("=== 문제 원문 샘플 (첫 900자) ===")
print(repr(data[0]["problemText"][:900]))
print("\n=== 사례집 모범답안 샘플 (첫 900자) ===")
cb = next(b for r in data for b in r["casebookAnswers"])
print(repr(cb["answerText"][:900]))
