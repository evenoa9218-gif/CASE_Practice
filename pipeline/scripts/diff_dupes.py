# -*- coding: utf-8 -*-
"""내용이 다른 중복 파일들의 실제 차이 확인."""
import difflib
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW

PAIRS = [
    ("민사법", "문제", "(수정)2014년도 제3차 변호사시험 모의시험 민사법 사례형 문제(배포용).txt",
                      "2. 2014년도 제3차 변호사시험 모의시험 민사법 사례형 문제(배포용).txt"),
    ("민사법", "문제", "2. 2013년도 제3차 변호사시험 모의시험 민사법 사례형 문제 [13-3].txt",
                      "2. 2013년도 제3차 변호사시험 모의시험 민사법 사례형 문제.txt"),
    ("민사법", "문제", "2. 2025년도 제2차 변호사시험 모의시험 민사법 사례형 문제 [3. 민사법].txt",
                      "2. 2025년도 제2차 변호사시험 모의시험 민사법 사례형 문제.txt"),
    ("국제거래법", "채점기준표", "2. 2014년도 제1차 변호사시험 모의시험 선택과목 사례형 채점기준표_국제거래법.txt",
                              "2. 채점기준표-2014년도 제1차 변호사시험 모의시험 선택과목_국제거래법.txt"),
]

for subj, dt, a, b in PAIRS:
    d = BASE / subj / dt / "사례형" / "txt"
    pa, pb = d / a, d / b
    print("=" * 70)
    print(f"[{subj}/{dt}]")
    print(f"  A: {a}")
    print(f"  B: {b}")
    if not (pa.exists() and pb.exists()):
        print("  파일 없음")
        continue
    ta = pa.read_text(encoding="utf-8", errors="replace").splitlines()
    tb = pb.read_text(encoding="utf-8", errors="replace").splitlines()
    diff = [l for l in difflib.unified_diff(ta, tb, "A", "B", lineterm="", n=0)]
    changed = [l for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    print(f"  전체 줄수: A={len(ta)}, B={len(tb)} / 차이 줄수: {len(changed)}")
    print("  --- 차이 (최대 20줄) ---")
    for l in changed[:20]:
        print(f"    {l[:150]}")
    print()
