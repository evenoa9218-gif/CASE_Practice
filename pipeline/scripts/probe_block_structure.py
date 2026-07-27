# -*- coding: utf-8 -*-
"""사례 블록의 실제 구조를 확인 (분할 로직 설계용)."""
import re
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW / "사례집"

def show(path: Path, marker_re, n=3, ctx=700, skip_head=0.15):
    print("=" * 70)
    print(path.name)
    text = path.read_text(encoding="utf-8", errors="replace")
    start = int(len(text) * skip_head)   # 목차 구간 건너뛰기
    hits = [m for m in marker_re.finditer(text) if m.start() > start]
    print(f"  본문 사례 마커 {len(hits)}개 (목차 이후)")
    for m in hits[:n]:
        print(f"\n  ── 마커 '{m.group()[:30]}' @ {m.start():,} ──")
        print("  " + text[m.start():m.start() + ctx].replace("\n", "\n  "))

show(BASE / "헌법" / "(2026) 강성민 헌법 사례형 연습 제9판 ocr+선명도.txt",
     re.compile(r"事例\s*\d+"), n=3)

show(BASE / "헌법" / "(2027)[류정모] 헌법 사례형 ocr.txt",
     re.compile(r"사례\s*[\[\［]\s*\d+\s*[\]\］]"), n=3)

show(BASE / "행정법" / "(26.04)[강성민] 행정법 사례형 연습 OCR.txt",
     re.compile(r"사\s*례\s*\d+"), n=3)
