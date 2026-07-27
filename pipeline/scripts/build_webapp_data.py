# -*- coding: utf-8 -*-
"""웹앱용 데이터 생성: 가벼운 인덱스 + 회차별 상세 파일."""
import json
import re
from pathlib import Path
from collections import Counter
from paths import APP, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "공법_사례_full_clean.json"   # 정제본을 읽는다 (형사법·민사법과 동일 규약)
APP = APP
DATA = APP / "data"
EXAMS = DATA / "exams"
EXAMS.mkdir(parents=True, exist_ok=True)

data = json.load(open(SRC, encoding="utf-8"))

# ── 쟁점 키워드 정규화 (주제 선택용 그룹화) ───────────────
def norm(kw: str) -> str:
    k = re.sub(r"\s+", "", kw.strip())
    k = k.replace("·", "").replace("‧", "").replace("・", "")
    alias = {
        "포괄위임입법금지원칙": "포괄위임금지원칙", "포괄위임입법금지": "포괄위임금지원칙",
        "포괄위임금지": "포괄위임금지원칙",
        "비례원칙": "과잉금지원칙", "과잉금지": "과잉금지원칙",
        "명확성": "명확성원칙", "신뢰보호": "신뢰보호원칙",
        "소의이익": "협의의소익", "권리보호이익": "협의의소익",
        "처분성인정여부": "처분성", "대상적격": "처분성",
        "행정절차법상사전통지": "사전통지",
    }
    return alias.get(k, k)


# 빈도 상위 쟁점을 '주제'로 승격 (선택 UI용)
kw_count = Counter(norm(k) for r in data for k in r["issueKeywords"])
TOPICS = [k for k, v in kw_count.most_common() if v >= 3]

index = []
for r in data:
    nkws = sorted({norm(k) for k in r["issueKeywords"]})
    topics = [t for t in nkws if t in TOPICS]
    index.append({
        "id": r["id"],
        "label": r["label"],
        "examType": r["examType"],
        "year": r["year"],
        "round": r["round"],
        "hoi": r.get("hoi"),
        "majorField": r["majorField"],
        "subFields": r["subFields"],
        "keywords": nkws,
        "topics": topics,
        "factSummary": r["factSummary"],
        "questions": r["questionStructure"],
        "totalPoints": sum(q.get("points") or 0 for q in r["questionStructure"]),
        "hasRubric": r["hasRubric"],
        "hasCasebook": r["hasCasebook"],
        "problemChars": len(r["problemText"] or ""),
    })

    # 회차별 상세 (지연 로딩)
    detail = {
        "id": r["id"], "label": r["label"],
        "problemText": r["problemText"],
        "rubricText": r["rubricText"],
        "casebookAnswers": r["casebookAnswers"],
        "caseCitations": r["caseCitations"],
        "statutes": r["statutes"][:20],
        "questions": r["questionStructure"],
    }
    (EXAMS / f"{r['id']}.json").write_text(
        json.dumps(detail, ensure_ascii=False), encoding="utf-8")

index.sort(key=lambda x: (0 if x["examType"] == "실제기출" else 1,
                          -(x["hoi"] or 0), -x["year"], -(x["round"] or 0)))

meta = {
    "subject": "공법",
    "count": len(index),
    "topics": [{"key": t, "label": t, "count": kw_count[t]} for t in TOPICS],
    "generated": "2026-07-26",
}

(DATA / "index.json").write_text(
    json.dumps({"meta": meta, "exams": index}, ensure_ascii=False, indent=1),
    encoding="utf-8")

idx_mb = (DATA / "index.json").stat().st_size / 1024 / 1024
tot_mb = sum(f.stat().st_size for f in EXAMS.iterdir()) / 1024 / 1024
print(f"인덱스: {idx_mb:.2f}MB ({len(index)}건)")
print(f"상세파일: {len(list(EXAMS.iterdir()))}개, 합계 {tot_mb:.1f}MB")
print(f"주제(3회 이상 출제 쟁점): {len(TOPICS)}개")
print("  상위 15:", TOPICS[:15])
print(f"\n출력 위치: {APP}")
