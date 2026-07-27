# -*- coding: utf-8 -*-
"""공법 사례집을 사례 블록 단위로 분할하고, 각 블록을 출처 시험에 매핑."""
import json
import re
from pathlib import Path
from collections import defaultdict
from paths import RAW, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW / "사례집"
SCRATCH = WORK
OUT = SCRATCH / "casebook_blocks_공법.json"

BOOKS = [
    {
        "file": BASE / "헌법" / "(2026) 강성민 헌법 사례형 연습 제9판 ocr+선명도.txt",
        "author": "강성민", "area": "헌법",
        "marker": re.compile(r"^\s*事例\s*(\d+)\s*(.{0,70})$", re.M),
    },
    {
        "file": BASE / "헌법" / "(2027)[류정모] 헌법 사례형 ocr.txt",
        "author": "류정모", "area": "헌법",
        "marker": re.compile(r"^\s*사례\s*[\[\［]\s*(\d+)\s*[\]\］]\s*(.{0,70})$", re.M),
    },
    {
        "file": BASE / "행정법" / "(26.04)[강성민] 행정법 사례형 연습 OCR.txt",
        "author": "강성민", "area": "행정법",
        "marker": re.compile(r"^\s*사\s*례\s*(\d+)\s*(.{0,70})$", re.M),
    },
]

# 헤더에서 출처 시험 추출 (OCR 오류 내성)
RE_REAL = re.compile(r"(\d{1,2})회변호사시험")
# 차수: '제N차' / OCR로 제·차가 깨진 경우 연도 뒤 한 자리 숫자도 허용
RE_MOCK = re.compile(r"(20\d{2})년?도?제?(\d)차")
RE_MOCK_LOOSE = re.compile(r"(20\d{2})년?도?[^\d]{0,6}(\d)[^\d]{0,3}(?:차|모의)")


def normalize(header: str) -> str:
    """OCR 잡음 제거: 공백 삭제 + 흔한 오인식 문자 정리."""
    h = re.sub(r"\s+", "", header)
    # 'ス II', 'スセ' 등은 '제'의 오인식 → 제거해도 숫자 추출에 지장 없음
    h = h.replace("スII", "제").replace("スII", "제").replace("スセ", "제").replace("ス", "제")
    h = h.replace("天F", "차").replace("曾다", "차").replace("R다", "차")
    h = h.replace(":", "").replace("，", "").replace("•", "")
    return h


def parse_exam(header: str):
    """헤더 문자열 → (examType, a, b). 모의고사 우선 판정."""
    h = normalize(header)
    is_mock = "모의" in h
    r = RE_REAL.search(h)
    if r and not is_mock:
        return ("실제기출", int(r.group(1)), None)
    m = RE_MOCK.search(h) or RE_MOCK_LOOSE.search(h)
    if m:
        year, cha = int(m.group(1)), int(m.group(2))
        if 2010 <= year <= 2026 and 1 <= cha <= 3:
            return ("모의고사", year, cha)
    if r:
        return ("실제기출", int(r.group(1)), None)
    return (None, None, None)


def exam_id(kind, a, b):
    if kind == "모의고사":
        return f"공법_모의_{a}_{b}차_사례"
    if kind == "실제기출":
        return f"공법_변시_{a}회_사례"
    return None


all_blocks = []
for bk in BOOKS:
    p = bk["file"]
    if not p.exists():
        print(f"[없음] {p.name}")
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    hits = list(bk["marker"].finditer(text))
    # 목차 구간(앞 12%) 제외
    cutoff = int(len(text) * 0.12)
    hits = [h for h in hits if h.start() > cutoff]

    ok = 0
    unparsed = []
    for i, m in enumerate(hits):
        start = m.start()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[start:end].strip()
        header = m.group(2).strip()
        kind, a, b = parse_exam(header)
        eid = exam_id(kind, a, b)
        if eid is None:
            unparsed.append(header[:50])
            continue
        ok += 1
        all_blocks.append({
            "examId": eid,
            "examType": kind,
            "year": a if kind == "모의고사" else (a + 2011),
            "round": b,
            "hoi": a if kind == "실제기출" else None,
            "book": p.name,
            "author": bk["author"],
            "area": bk["area"],
            "caseNo": m.group(1),
            "header": header,
            "answerText": body,
            "chars": len(body),
        })
    print(f"[{bk['area']}/{bk['author']}] 블록 {len(hits)}개 중 매핑 {ok}개, 미매핑 {len(unparsed)}개")
    if unparsed:
        print(f"    미매핑 예시: {unparsed[:5]}")

json.dump(all_blocks, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"\n총 {len(all_blocks)}개 블록 → {OUT}")

# 시험별 집계
g = defaultdict(list)
for b in all_blocks:
    g[b["examId"]].append(b)

real = sorted([k for k in g if "변시" in k], key=lambda k: int(re.search(r"(\d+)회", k).group(1)))
mock = sorted([k for k in g if "모의" in k])

print(f"\n=== 실제 변호사시험 ({len(real)}개 회차) ===")
for k in real:
    tot = sum(x["chars"] for x in g[k])
    print(f"  {k}: 블록 {len(g[k])}개, {tot:,}자")

print(f"\n=== 모의고사 ({len(mock)}개 회차) ===")
for k in mock[:10]:
    tot = sum(x["chars"] for x in g[k])
    print(f"  {k}: 블록 {len(g[k])}개, {tot:,}자")
print(f"  ... 외 {max(0, len(mock)-10)}개")
