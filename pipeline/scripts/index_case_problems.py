# -*- coding: utf-8 -*-
"""공법 사례형 문제-채점기준표 txt 쌍을 매칭해 중간 인덱스 JSON을 만든다."""
import re
import json
from pathlib import Path
from paths import RAW, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW
SUBJECT = "공법"
PROBLEM_DIR = BASE / SUBJECT / "문제" / "사례형" / "txt"
RUBRIC_DIR = BASE / SUBJECT / "채점기준표" / "사례형" / "txt"

OUT_PATH = WORK / "공법_사례_index.json"

mock_re = re.compile(r"(\d{4})\D{0,4}제\s*(\d)\s*차")
real_hoi_re = re.compile(r"제?\s*(\d{1,2})\s*회")


def parse_key(fname: str):
    is_mock = mock_re.search(fname)
    if is_mock:
        year, cha = is_mock.groups()
        return ("모의고사", int(year), int(cha))
    m = real_hoi_re.search(fname)
    if m:
        return ("실제기출", int(m.group(1)), None)
    return (None, None, None)


def load_texts(d: Path):
    entries = {}
    for f in sorted(d.iterdir()):
        if f.suffix.lower() != ".txt":
            continue
        exam_type, a, b = parse_key(f.name)
        if exam_type is None:
            print("파싱 실패:", f.name)
            continue
        key = (exam_type, a, b)
        entries.setdefault(key, []).append(f)
    return entries


problems = load_texts(PROBLEM_DIR)
rubrics = load_texts(RUBRIC_DIR)

all_keys = sorted(set(problems.keys()) | set(rubrics.keys()), key=lambda k: (k[0], k[1], k[2] or 0))

records = []
for key in all_keys:
    exam_type, year_or_hoi, cha = key
    prob_files = problems.get(key, [])
    rub_files = rubrics.get(key, [])
    if len(prob_files) > 1:
        print("경고: 문제 중복 매칭", key, [f.name for f in prob_files])
    if len(rub_files) > 1:
        print("경고: 채점기준표 중복 매칭", key, [f.name for f in rub_files])

    if exam_type == "모의고사":
        rid = f"{SUBJECT}_모의_{year_or_hoi}_{cha}차_사례"
        label = f"{year_or_hoi}년 제{cha}차 모의고사"
        year = year_or_hoi
    else:
        # 제1회 변호사시험 = 2012년 실시 (회차 + 2011)
        year = year_or_hoi + 2011
        rid = f"{SUBJECT}_변시_{year_or_hoi}회_사례"
        label = f"제{year_or_hoi}회 변호사시험 ({year}년)"

    records.append({
        "id": rid,
        "subject": SUBJECT,
        "examType": exam_type,        # "모의고사" | "실제기출" — 절대 혼용 금지
        "year": year,                  # 두 유형 모두 연도 채움 (정렬/필터용)
        "round": cha if exam_type == "모의고사" else None,   # 1/2/3차 (모의고사 전용)
        "hoi": year_or_hoi if exam_type == "실제기출" else None,  # 회차 (실제기출 전용)
        "label": label,
        "problemFile": str(prob_files[0]) if prob_files else None,
        "rubricFile": str(rub_files[0]) if rub_files else None,
    })

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

total = len(records)
with_both = sum(1 for r in records if r["problemFile"] and r["rubricFile"])
prob_only = sum(1 for r in records if r["problemFile"] and not r["rubricFile"])
rub_only = sum(1 for r in records if r["rubricFile"] and not r["problemFile"])
print(f"총 {total}건 (문제+채점기준표 모두={with_both}, 문제만={prob_only}, 채점기준표만={rub_only})")
