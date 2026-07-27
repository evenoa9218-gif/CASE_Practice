# -*- coding: utf-8 -*-
"""형사법판 쟁점 레지스트리 구축 (build_issue_registry.py의 형사법 버전, CRI 접두사)."""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "형사법_사례_full_clean.json"
OUTDIR = SCRATCH / "registry"
OUTDIR.mkdir(exist_ok=True)

SUBJECT = "형사법"
PREFIX = "CRI"

data = json.load(open(SRC, encoding="utf-8"))

ALIAS = {
    "위법수집증거배제법칙": "위법수집증거배제법칙", "전문법칙적용": "전문법칙",
    "자백의보강법칙": "자백보강법칙", "자백보강법칙적용": "자백보강법칙",
    "불이익변경금지의원칙": "불이익변경금지원칙",
    "재량권일탈남용": "재량권의일탈·남용", "재량권일탈·남용": "재량권의일탈·남용",
    "공동정범성립여부": "공동정범", "간접정범성립여부": "간접정범",
}

def canon(kw: str) -> str:
    k = re.sub(r"\s+", "", kw.strip())
    k = k.replace("‧", "·").replace("・", "·")
    base = k.replace("·", "")
    return ALIAS.get(base, ALIAS.get(k, k))

surface = defaultdict(set)
count = Counter()
by_exam = defaultdict(set)
stat_link = defaultdict(Counter)
case_link = defaultdict(Counter)
field_link = defaultdict(Counter)

for rec in data:
    ks = {canon(k) for k in rec["issueKeywords"]}
    for orig in rec["issueKeywords"]:
        surface[canon(orig)].add(orig.strip())
    for k in ks:
        count[k] += 1
        by_exam[rec["id"]].add(k)
        field_link[k][rec["majorField"] or "미상"] += 1
        for s in rec["statutes"][:12]:
            stat_link[k][s] += 1
        for c in rec["caseCitations"][:12]:
            case_link[k][c] += 1

# 형사소송법(절차법) 쟁점 키워드 후보 — 이게 있으면 형사소송법으로 분류
PROC = [
    "전문법칙", "위법수집증거", "자백보강", "증언거부권", "긴급체포", "체포", "구속",
    "공소장변경", "불이익변경금지", "재전문", "증거능력", "압수", "수색", "영장",
    "상소", "항소", "상고", "재심", "공소시효", "기판력", "일사부재리", "탄핵증거",
    "진술거부권", "피의자신문조서", "참고인진술조서", "고소", "고발", "친고죄",
    "반의사불벌죄", "공판", "증인신문", "증거보전", "재정신청", "공소권남용",
    "기소독점주의", "기소편의주의", "약식명령", "즉결심판", "국선변호", "변호인",
    "접견교통권", "구속적부심", "보석", "기피", "관할", "공소사실의동일성",
    "이중기소", "확정판결", "면소", "공소기각", "일부상소", "간이공판절차",
    "국민참여재판", "배심원",
]
# 형법(실체법) 쟁점 키워드 후보
SUBST = [
    "공동정범", "간접정범", "교사범", "방조범", "중지미수", "장애미수", "불능미수",
    "예비", "음모", "정당방위", "긴급피난", "자구행위", "피해자의승낙", "정당행위",
    "책임조각", "위법성조각", "구성요건적착오", "금지착오", "원인에있어서자유로운행위",
    "죄수", "상상적경합", "실체적경합", "포괄일죄", "친족상도례", "합동범",
    "사기죄", "공갈죄", "절도죄", "강도죄", "장물", "횡령죄", "배임죄", "손괴죄",
    "살인죄", "상해죄", "폭행죄", "명예훼손죄", "모욕죄", "협박죄", "체포감금죄",
    "강요죄", "권리행사방해죄", "뇌물죄", "직권남용", "위계", "위력",
    "컴퓨터등사용사기죄", "준강도", "특수공무집행방해",
]

def guess_path(k: str) -> list:
    if any(t in k for t in PROC):
        return [SUBJECT, "형사소송법"]
    if any(t in k for t in SUBST):
        return [SUBJECT, "형법"]
    return [SUBJECT, "형사법일반"]

ordered = sorted(count.keys(), key=lambda k: (-count[k], k))

issues = []
for i, k in enumerate(ordered, start=1):
    issues.append({
        "id": f"{PREFIX}-{i:04d}",
        "label": k,
        "subject": SUBJECT,
        "path": guess_path(k),
        "aliases": sorted(surface[k] - {k}),
        "examCount": count[k],
        "statutes": [s for s, _ in stat_link[k].most_common(6)],
        "cases": [c for c, _ in case_link[k].most_common(8)],
    })

label2id = {it["label"]: it["id"] for it in issues}
exam_issues = {eid: sorted(label2id[k] for k in ks) for eid, ks in by_exam.items()}

json.dump({"subject": SUBJECT, "prefix": PREFIX, "count": len(issues), "issues": issues},
          open(OUTDIR / f"issues_{SUBJECT}.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump(exam_issues, open(OUTDIR / f"exam_issues_{SUBJECT}.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"쟁점 {len(issues)}개 등록 ({PREFIX}-0001 ~ {PREFIX}-{len(issues):04d})")
areas = Counter(it["path"][1] for it in issues)
print("계층 분포:", dict(areas))
print(f"\n=== 상위 15 쟁점 ===")
for it in issues[:15]:
    al = f" (별칭 {len(it['aliases'])})" if it["aliases"] else ""
    print(f"  {it['id']}  {it['label']:<22} {it['examCount']:2d}회  [{it['path'][1]}]{al}")
print(f"\n별칭 통합된 쟁점: {sum(1 for it in issues if it['aliases'])}개")
print(f"출력: {OUTDIR}")
