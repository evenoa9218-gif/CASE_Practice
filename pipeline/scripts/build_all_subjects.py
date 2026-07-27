# -*- coding: utf-8 -*-
"""전 과목 사례형 데이터 구축 (모의고사 + 변시 분리, 원문 전문 보존).

산출:
  {과목}_모의_사례.json  — 모의고사 (연도+차수)
  {과목}_변시_사례.json  — 실제 변호사시험 (회차+연도)
  {과목}_사례_citations.json — 판례/조문 정규식 추출
"""
import json
import re
from pathlib import Path
from collections import Counter
from paths import RAW, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW
OUT = WORK / "subjects"
OUT.mkdir(exist_ok=True)

SUBJECTS = ["민사법", "형사법", "국제법", "국제거래법"]

mock_re = re.compile(r"(\d{4})\D{0,4}제\s*(\d)\s*차")
real_hoi_re = re.compile(r"제?\s*(\d{1,2})\s*회")

CASE_RE = re.compile(r"\b(\d{2,4})\s*(헌마|헌바|헌가|헌라|헌나|헌사|헌아|두|다|누|도|므|추|카|허|후|재|초)\s*(\d+)\b")
STATUTE_RE = re.compile(
    r"([가-힣]{2,20}(?:법|법률|규칙|령|헌법))\s*(제\s*\d+조(?:\s*의\s*\d+)?"
    r"(?:\s*제\s*\d+항)?(?:\s*제\s*\d+호)?)"
)


def parse_key(fname: str):
    m = mock_re.search(fname)
    if m:
        return ("모의고사", int(m.group(1)), int(m.group(2)))
    m = real_hoi_re.search(fname)
    if m:
        return ("실제기출", int(m.group(1)), None)
    return (None, None, None)


def collect(d: Path):
    out = {}
    unparsed = []
    if not d.exists():
        return out, unparsed
    for f in sorted(d.iterdir()):
        if f.suffix.lower() != ".txt":
            continue
        kind, a, b = parse_key(f.name)
        if kind is None:
            unparsed.append(f.name)
            continue
        out.setdefault((kind, a, b), []).append(f)
    return out, unparsed


summary = []

for subj in SUBJECTS:
    probs, up1 = collect(BASE / subj / "문제" / "사례형" / "txt")
    rubs, up2 = collect(BASE / subj / "채점기준표" / "사례형" / "txt")

    if up1 or up2:
        print(f"[{subj}] 회차 인식 실패: {up1 + up2}")

    dup_notes = []
    for key, fs in list(probs.items()) + list(rubs.items()):
        if len(fs) > 1:
            dup_notes.append((key, [f.name for f in fs]))

    keys = sorted(set(probs) | set(rubs), key=lambda k: (k[0], k[1], k[2] or 0))
    mock_recs, real_recs, cites = [], [], []

    for key in keys:
        kind, a, b = key
        pf = probs.get(key, [])
        rf = rubs.get(key, [])
        ptext = pf[0].read_text(encoding="utf-8", errors="replace") if pf else None
        rtext = rf[0].read_text(encoding="utf-8", errors="replace") if rf else None

        combined = (ptext or "") + "\n" + (rtext or "")
        cs = [f"{y}{c}{n}" for y, c, n in CASE_RE.findall(combined)]
        sts = [re.sub(r"\s+", " ", f"{law} {art}").strip()
               for law, art in STATUTE_RE.findall(combined)]

        if kind == "모의고사":
            rid = f"{subj}_모의_{a}_{b}차_사례"
            rec = {
                "id": rid, "subject": subj, "examType": "모의고사",
                "year": a, "round": b, "hoi": None,
                "label": f"{a}년 제{b}차 모의고사",
                "problemText": ptext, "rubricText": rtext,
                "hasProblem": ptext is not None, "hasRubric": rtext is not None,
            }
            mock_recs.append(rec)
        else:
            year = a + 2011   # 제1회 = 2012년
            rid = f"{subj}_변시_{a}회_사례"
            rec = {
                "id": rid, "subject": subj, "examType": "실제기출",
                "year": year, "round": None, "hoi": a,
                "label": f"제{a}회 변호사시험 ({year}년)",
                "problemText": ptext, "rubricText": rtext,
                "hasProblem": ptext is not None, "hasRubric": rtext is not None,
            }
            real_recs.append(rec)

        cites.append({
            "id": rid,
            "caseCitations": [c for c, _ in Counter(cs).most_common()],
            "statutes": [s for s, _ in Counter(sts).most_common(30)],
        })

    mock_recs.sort(key=lambda r: (r["year"], r["round"]))
    real_recs.sort(key=lambda r: r["hoi"])

    json.dump(mock_recs, open(OUT / f"{subj}_모의_사례.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(real_recs, open(OUT / f"{subj}_변시_사례.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(cites, open(OUT / f"{subj}_사례_citations.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    mock_rub = sum(1 for r in mock_recs if r["hasRubric"])
    real_rub = sum(1 for r in real_recs if r["hasRubric"])
    real_prob = sum(1 for r in real_recs if r["hasProblem"])
    summary.append({
        "subject": subj,
        "mock": len(mock_recs), "mock_with_rubric": mock_rub,
        "real": len(real_recs), "real_with_problem": real_prob, "real_with_rubric": real_rub,
        "dupes": dup_notes,
    })

print("\n=== 과목별 구축 결과 ===")
print(f"{'과목':<10} {'모의':>6} {'(채점표)':>8} {'변시':>6} {'(문제)':>7} {'(채점표)':>8}")
for s in summary:
    print(f"{s['subject']:<10} {s['mock']:>6} {s['mock_with_rubric']:>8} "
          f"{s['real']:>6} {s['real_with_problem']:>7} {s['real_with_rubric']:>8}")

print("\n=== 중복 매칭 (확인 필요) ===")
any_dup = False
for s in summary:
    for key, names in s["dupes"]:
        any_dup = True
        print(f"  [{s['subject']}] {key}: {names}")
if not any_dup:
    print("  없음")

print(f"\n저장 위치: {OUT}")
