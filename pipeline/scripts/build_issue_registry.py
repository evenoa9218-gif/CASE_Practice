# -*- coding: utf-8 -*-
"""쟁점(논점) ID 레지스트리 구축 — 4체계 연동의 척추.

설계 원칙(설계 대화 반영):
  - ID에 목차 위치를 넣지 않는다 → 불변 일련번호 (PUB-0001)
  - ID는 한 번 부여하면 재사용하지 않는다
  - 계층은 path 필드로 별도 관리
  - 조문·판례는 독립 엔티티로 다대다 연결
"""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "공법_사례_full_clean.json"   # 정제본을 읽는다 (형사법·민사법과 동일 규약)
OUTDIR = SCRATCH / "registry"
OUTDIR.mkdir(exist_ok=True)

SUBJECT = "공법"
PREFIX = "PUB"          # 공법. 향후 CIV(민사법), CRI(형사법), INT(국제법), ITL(국제거래법)

data = json.load(open(SRC, encoding="utf-8"))

# ── 표기 정규화 (같은 쟁점의 다른 표기를 하나로) ──────────
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

def canon(kw: str) -> str:
    k = re.sub(r"\s+", "", kw.strip())
    k = k.replace("‧", "·").replace("・", "·")
    base = k.replace("·", "")
    return ALIAS.get(base, ALIAS.get(k, k))

# ── 쟁점 수집 + 원표기 보존 ──────────────────────────────
surface = defaultdict(set)     # canonical -> {원표기들}
count = Counter()
by_exam = defaultdict(set)     # examId -> {canonical}
stat_link = defaultdict(Counter)   # canonical -> 조문 빈도
case_link = defaultdict(Counter)   # canonical -> 판례 빈도
field_link = defaultdict(Counter)  # canonical -> majorField

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

# ── 계층(path) 추정: subFields에서 상위 분류 유추 ─────────
def guess_path(k: str) -> list:
    """공법 → 헌법/행정법 → 쟁점. 세부 분류는 추후 수동 보정 가능."""
    fields = field_link[k]
    top = fields.most_common(1)[0][0] if fields else "미상"
    # majorField가 대부분 '헌법+행정법'이라 쟁점명으로 2차 판별
    ADMIN = ["처분", "행정", "취소소송", "항고소송", "원고적격", "제소기간", "재량",
             "대집행", "이행강제금", "부관", "하자", "소익", "집행정지", "국가배상",
             "손실보상", "정보공개", "인허가", "조례", "지방자치", "당사자소송",
             "기속력", "기판력", "사전통지", "청문", "신고", "공법상계약", "변상금"]
    CONST = ["기본권", "헌법소원", "위헌", "재판의전제성", "청구기간", "자기관련성",
             "직접성", "현재성", "보충성", "과잉금지", "평등", "명확성", "포괄위임",
             "권한쟁의", "탄핵", "정당", "국회", "대통령", "표현의자유", "재산권",
             "직업의자유", "신체의자유", "적법절차", "소급입법", "신뢰보호"]
    if any(t in k for t in ADMIN):
        area = "행정법"
    elif any(t in k for t in CONST):
        area = "헌법"
    else:
        area = "공법일반"
    return [SUBJECT, area]

# ── ID 부여: 빈도 내림차순 → 안정적 순서 위해 이름 2차 정렬 ──
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

# ── 시험별 issueIds 매핑 ─────────────────────────────────
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
