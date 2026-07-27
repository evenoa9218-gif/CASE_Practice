# -*- coding: utf-8 -*-
import re
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW / "사례집"

TARGETS = [
    BASE / "형법" / "(2026)[이인규] 형법 변사기.txt",
    BASE / "형법" / "(26.04)[조균석] 형사법 사례형 해설.txt",
    BASE / "형사소송법" / "(2027) 대비 작은변사기 형사소송법 OCR.txt",
    BASE / "형사소송법" / "(26.02)[이창현] 사례형사소송법.txt",
]

PATTERNS = {
    "사례번호_事例": re.compile(r"事例\s*(\d+)"),
    "사례번호_사례": re.compile(r"^\s*사\s*례\s*[\[\［(（]?\s*(\d+)\s*[\]\］)）]?", re.M),
    "문제번호_문제": re.compile(r"^\s*문\s*제\s*(\d+)", re.M),
}

for path in TARGETS:
    print("=" * 70)
    print(path.name)
    if not path.exists():
        print("  (없음)")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    print(f"  총 {len(text):,}자")
    for name, pat in PATTERNS.items():
        hits = pat.findall(text)
        print(f"  {name}: {len(hits)}회")
        if hits:
            uniq = sorted(set(map(str, hits)), key=lambda x: int(x) if x.isdigit() else 0)[:12]
            print(f"      값 예시: {uniq}")
    print("  --- CONTENTS 마커 확인 ---")
    idx = text.upper().find("CONTENTS")
    print("  CONTENTS idx:", idx, repr(text[max(0,idx-5):idx+30]) if idx>0 else "")
    print("  --- '변호사시험' 문맥 샘플 3개 ---")
    for m in list(re.finditer(r"변호사시험", text))[:3]:
        s = max(0, m.start() - 60)
        print("      ..." + text[s:m.end() + 40].replace("\n", " / "))
    print("  --- '모의시험' 문맥 샘플 3개 ---")
    for m in list(re.finditer(r"모의시험", text))[:3]:
        s = max(0, m.start() - 60)
        print("      ..." + text[s:m.end() + 40].replace("\n", " / "))
    print()
