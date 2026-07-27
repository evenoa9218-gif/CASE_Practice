# -*- coding: utf-8 -*-
import re
from pathlib import Path
from collections import defaultdict
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW

SUBJECTS = {
    "공법": ["선택형", "사례형", "기록형"],
    "민사법": ["선택형", "사례형", "기록형"],
    "형사법": ["선택형", "사례형", "기록형"],
    "국제법": ["사례형"],
    "국제거래법": ["사례형"],
}
DOCTYPES = ["문제", "채점기준표"]

MOCK_YEARS = list(range(2013, 2026))  # 2013~2025
MOCK_CHA = [1, 2, 3]
REAL_HOI = list(range(1, 16))  # 1~15

mock_re = re.compile(r"(\d{4})\D{0,4}제\s*(\d)\s*차")
real_hoi_re = re.compile(r"제?\s*(\d{1,2})\s*회")

def parse_file(fname: str):
    m = mock_re.search(fname)
    if m:
        return ("mock", int(m.group(1)), int(m.group(2)))
    m = real_hoi_re.search(fname)
    if m:
        return ("real", int(m.group(1)), None)
    return ("unknown", None, None)

results = {}
unparsed = []

for subject, types in SUBJECTS.items():
    for doctype in DOCTYPES:
        for typ in types:
            d = BASE / subject / doctype / typ
            found_mock = set()
            found_real = set()
            if d.exists():
                for f in d.iterdir():
                    if not f.is_file():
                        continue
                    kind, a, b = parse_file(f.name)
                    if kind == "mock":
                        found_mock.add((a, b))
                    elif kind == "real":
                        found_real.add(a)
                    else:
                        unparsed.append(str(f))

            missing_mock = [(y, c) for y in MOCK_YEARS for c in MOCK_CHA if (y, c) not in found_mock]
            missing_real = [h for h in REAL_HOI if h not in found_real]
            results[(subject, doctype, typ)] = (missing_mock, missing_real)

print("=== 파일명에서 회차 인식 실패 (수동 확인 필요) ===")
for u in unparsed:
    print(" ", u)

print("\n=== 과목/문서유형/시험유형별 누락 현황 ===")
for (subject, doctype, typ), (mm, mr) in results.items():
    if not mm and not mr:
        continue
    print(f"\n[{subject} / {doctype} / {typ}]")
    if mm:
        s = ", ".join(f"{y}-{c}차" for y, c in mm)
        print(f"  모의고사 누락({len(mm)}): {s}")
    if mr:
        s = ", ".join(f"{h}회" for h in mr)
        print(f"  변호사시험 누락({len(mr)}): {s}")
