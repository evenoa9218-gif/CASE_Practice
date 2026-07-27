# -*- coding: utf-8 -*-
"""CASE_Practice 앱 데이터 생성 — 쟁점 ID(PUB-xxxx) 반영."""
import json
import re
from pathlib import Path
from paths import APP, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "공법_사례_full_clean.json"   # 정제본을 읽는다 (형사법·민사법과 동일 규약)
REG = SCRATCH / "registry" / "issues_공법.json"
DATA = APP / "data" / "공법"
EXAMS = DATA / "exams"
EXAMS.mkdir(parents=True, exist_ok=True)

reg = json.load(open(REG, encoding="utf-8"))
issues = reg["issues"]
label2id = {it["label"]: it["id"] for it in issues}
alias2id = {}
for it in issues:
    for a in it["aliases"]:
        alias2id[a] = it["id"]

ALIAS = {
    "포괄위임입법금지원칙": "포괄위임금지원칙", "포괄위임입법금지": "포괄위임금지원칙",
    "포괄위임금지": "포괄위임금지원칙",
    "비례원칙": "과잉금지원칙", "과잉금지": "과잉금지원칙",
    "명확성": "명확성원칙", "신뢰보호": "신뢰보호원칙",
    "소의이익": "협의의소익", "권리보호이익": "협의의소익",
    "처분성인정여부": "처분성", "대상적격": "처분성",
    "행정절차법상사전통지": "사전통지",
    "기본권침해의직접성": "직접성", "기본권침해의현재성": "현재성",
    "국가배상책임": "국가배상", "국가배상의위법성": "국가배상",
    "재량권일탈남용": "재량권의일탈·남용", "재량권일탈·남용": "재량권의일탈·남용",
}

def canon(kw):
    k = re.sub(r"\s+", "", kw.strip()).replace("‧", "·").replace("・", "·")
    base = k.replace("·", "")
    return ALIAS.get(base, ALIAS.get(k, k))

def to_id(kw):
    c = canon(kw)
    return label2id.get(c) or alias2id.get(kw.strip())

data = json.load(open(SRC, encoding="utf-8"))
id2issue = {it["id"]: it for it in issues}


def group_key(no):
    """문항 번호에서 '문' 단위 그룹을 뽑는다. 예: 설문1(1) → 설문1"""
    s = re.sub(r"\s", "", no or "")
    m = re.match(r"(설문|문제|질문|제|문)?\s*([0-9１-９]+)", s)
    if m:
        pre = m.group(1) or "문"
        if pre == "제":
            return f"제{m.group(2)}문"
        return pre + m.group(2)
    return s[:4] or "기타"


def build_groups(qs):
    """questionStructure를 문 단위 페이지로 묶는다."""
    groups, order = {}, []
    for q in qs:
        g = group_key(q.get("no"))
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(q)
    return [{
        "key": g,
        "label": g,
        "questions": groups[g],
        "points": sum(q.get("points") or 0 for q in groups[g]),
    } for g in order]


index = []
for r in data:
    iids, unmapped = [], []
    for k in r["issueKeywords"]:
        i = to_id(k)
        (iids.append(i) if i else unmapped.append(k))
    iids = sorted(set(iids))

    index.append({
        "id": r["id"], "label": r["label"], "examType": r["examType"],
        "year": r["year"], "round": r["round"], "hoi": r.get("hoi"),
        "majorField": r["majorField"], "subFields": r["subFields"],
        "issueIds": iids,
        "factSummary": r["factSummary"],
        "questions": r["questionStructure"],
        "groups": [{"key": g["key"], "label": g["label"],
                    "count": len(g["questions"]), "points": g["points"]}
                   for g in build_groups(r["questionStructure"])],
        "totalPoints": sum(q.get("points") or 0 for q in r["questionStructure"]),
        "hasRubric": r["hasRubric"], "hasCasebook": r["hasCasebook"],
        "unmappedKeywords": unmapped,
    })

    (EXAMS / f"{r['id']}.json").write_text(json.dumps({
        "id": r["id"], "label": r["label"],
        "problemText": r["problemText"],
        "rubricText": r["rubricText"],
        "casebookAnswers": r["casebookAnswers"],
        "caseCitations": r["caseCitations"],
        "statutes": r["statutes"][:20],
        "questions": r["questionStructure"],
        "groups": build_groups(r["questionStructure"]),
        "issueIds": iids,
    }, ensure_ascii=False), encoding="utf-8")

index.sort(key=lambda x: (0 if x["examType"] == "실제기출" else 1,
                          -(x["hoi"] or 0), -x["year"], -(x["round"] or 0)))

# 쟁점별 출제 시험 역인덱스 (허브·암기장이 "이 쟁점 사례" 조회할 때 사용)
by_issue = {}
for e in index:
    for i in e["issueIds"]:
        by_issue.setdefault(i, []).append(e["id"])

used = [it for it in issues if it["id"] in by_issue]

(DATA / "index.json").write_text(json.dumps({
    "meta": {
        "subject": "공법", "prefix": "PUB",
        "examCount": len(index),
        "issueCount": len(used),
        "generated": "2026-07-26",
    },
    "issues": [{
        "id": it["id"], "label": it["label"], "path": it["path"],
        "examCount": len(by_issue.get(it["id"], [])),
    } for it in sorted(used, key=lambda x: -len(by_issue.get(x["id"], [])))],
    "byIssue": by_issue,
    "exams": index,
}, ensure_ascii=False, indent=1), encoding="utf-8")

# 전체 쟁점 레지스트리도 함께 배포 (허브·암기장 공용)
(APP / "data").mkdir(exist_ok=True)
(APP / "data" / "issues_공법.json").write_text(
    json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")

idx_kb = (DATA / "index.json").stat().st_size / 1024
tot_mb = sum(f.stat().st_size for f in EXAMS.iterdir()) / 1024 / 1024
unmapped_total = sum(len(e["unmappedKeywords"]) for e in index)
print(f"index.json: {idx_kb:.0f}KB (시험 {len(index)}건, 쟁점 {len(used)}종)")
print(f"exams/: {len(list(EXAMS.iterdir()))}개, {tot_mb:.1f}MB")
print(f"쟁점 매핑 실패 키워드: {unmapped_total}건")
print(f"\n=== 최다 출제 쟁점 10 ===")
for it in sorted(used, key=lambda x: -len(by_issue[x["id"]]))[:10]:
    print(f"  {it['id']}  {it['label']:<20} {len(by_issue[it['id']]):2d}건  [{it['path'][1]}]")
