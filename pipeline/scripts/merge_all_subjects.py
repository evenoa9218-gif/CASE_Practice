# -*- coding: utf-8 -*-
"""전 과목 태깅 결과 최종 병합 + 무결성 검증."""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
TAGDIR = SCRATCH / "tag_output_all"
SUBJ = SCRATCH / "subjects"
OUTDIR = SCRATCH / "final"
OUTDIR.mkdir(exist_ok=True)

SUBJECTS = ["민사법", "형사법", "국제법", "국제거래법"]

# 1) 태깅 결과 수집
tags = {}
dupes = []
for f in sorted(TAGDIR.glob("*.json")):
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", f.read_text(encoding="utf-8").strip())
    try:
        items = json.loads(raw)
    except Exception as e:
        print(f"[파싱실패] {f.name}: {e}")
        continue
    for it in items:
        i = it.get("id")
        if not i:
            continue
        if i in tags:
            dupes.append(i)
        tags[i] = it

print(f"태깅 결과 {len(tags)}건 수집 (중복덮어쓰기 {len(dupes)}건)")

# 2) 판례/조문 수집
cites = {}
for subj in SUBJECTS:
    p = SUBJ / f"{subj}_사례_citations.json"
    if p.exists():
        for c in json.load(open(p, encoding="utf-8")):
            cites[c["id"]] = c

# 3) 과목별 최종 병합
summary = []
missing_all = []
for subj in SUBJECTS:
    merged = []
    for kind, fname in (("모의", f"{subj}_모의_사례.json"), ("변시", f"{subj}_변시_사례.json")):
        p = SUBJ / fname
        if not p.exists():
            continue
        for rec in json.load(open(p, encoding="utf-8")):
            t = tags.get(rec["id"])
            if not t:
                missing_all.append(rec["id"])
            c = cites.get(rec["id"], {})
            merged.append({
                "id": rec["id"], "subject": subj, "examType": rec["examType"],
                "year": rec["year"], "round": rec["round"], "hoi": rec["hoi"],
                "label": rec["label"],
                # 원문 (축약 없이 전문 보존)
                "problemText": rec["problemText"],
                "rubricText": rec["rubricText"],
                "hasRubric": rec["hasRubric"],
                # 정규식 추출
                "caseCitations": c.get("caseCitations", []),
                "statutes": c.get("statutes", []),
                # LLM 태깅
                "majorField": (t or {}).get("majorField"),
                "subFields": (t or {}).get("subFields", []),
                "issueKeywords": (t or {}).get("issueKeywords", []),
                "factSummary": (t or {}).get("factSummary"),
                "questionStructure": (t or {}).get("questionStructure", []),
                "inferredCases": (t or {}).get("inferredCases", []),
            })
    merged.sort(key=lambda r: (r["examType"], r["year"], r["round"] or 0))
    json.dump(merged, open(OUTDIR / f"{subj}_사례_final.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    mock = [r for r in merged if r["examType"] == "모의고사"]
    real = [r for r in merged if r["examType"] == "실제기출"]
    tagged = sum(1 for r in merged if r["issueKeywords"])
    summary.append((subj, len(merged), len(mock), len(real), tagged,
                    sum(1 for r in merged if r["hasRubric"])))

print("\n=== 과목별 최종 데이터 ===")
print(f"{'과목':<10}{'총계':>6}{'모의':>6}{'변시':>6}{'태깅':>6}{'채점표':>7}")
for s in summary:
    print(f"{s[0]:<10}{s[1]:>6}{s[2]:>6}{s[3]:>6}{s[4]:>6}{s[5]:>7}")

if missing_all:
    print(f"\n태깅 누락 {len(missing_all)}건: {missing_all[:10]}")
else:
    print("\n태깅 누락: 없음 ✓")

# 4) 과목별 쟁점 상위
print("\n=== 과목별 최빈 쟁점 (상위 8) ===")
for subj in SUBJECTS:
    p = OUTDIR / f"{subj}_사례_final.json"
    data = json.load(open(p, encoding="utf-8"))
    kw = Counter(k for r in data for k in r["issueKeywords"])
    print(f"\n[{subj}] 고유쟁점 {len(kw)}종")
    for k, v in kw.most_common(8):
        print(f"   {v:2d}  {k}")
