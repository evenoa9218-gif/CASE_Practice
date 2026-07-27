# -*- coding: utf-8 -*-
"""공법 사례집에서 '회차 구분 마커'가 어떤 형태로 나타나는지 조사."""
import re
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW / "사례집"

TARGETS = [
    BASE / "헌법" / "(2026) 강성민 헌법 사례형 연습 제9판 ocr+선명도.txt",
    BASE / "헌법" / "(2027)[류정모] 헌법 사례형 ocr.txt",
    BASE / "행정법" / "(26.04)[강성민] 행정법 사례형 연습 OCR.txt",
]

# 후보 패턴들
PATTERNS = {
    "변시_제N회": re.compile(r"제\s*(\d{1,2})\s*회\s*변호사시험"),
    "변시_N회(공백변형)": re.compile(r"제\s*(\d{1,2})\s*회[^\n]{0,10}변호사"),
    "모의_YYYY년제N차": re.compile(r"(\d{4})\s*년?\s*도?\s*제\s*(\d)\s*차\s*(?:모의|변호사)"),
    "사례번호_事例": re.compile(r"事例\s*(\d+)"),
    "사례번호_사례": re.compile(r"사례\s*[\[\［(（]?\s*(\d+)\s*[\]\］)）]?"),
}

for path in TARGETS:
    print("=" * 70)
    print(path.name)
    if not path.exists():
        print("  (아직 변환 안 됨)")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    print(f"  총 {len(text):,}자")
    for name, pat in PATTERNS.items():
        hits = pat.findall(text)
        print(f"  {name}: {len(hits)}회")
        if hits:
            uniq = sorted(set(map(str, hits)))[:12]
            print(f"      값 예시: {uniq}")
    # 실제 마커 주변 문맥 샘플
    print("  --- '변호사시험' 등장 문맥 샘플 3개 ---")
    for m in list(re.finditer(r"변호사시험", text))[:3]:
        s = max(0, m.start() - 60)
        print("      ..." + text[s:m.end() + 40].replace("\n", " ⏎ "))
    print("  --- '모의시험' 등장 문맥 샘플 3개 ---")
    for m in list(re.finditer(r"모의시험", text))[:3]:
        s = max(0, m.start() - 60)
        print("      ..." + text[s:m.end() + 40].replace("\n", " ⏎ "))
    print()
