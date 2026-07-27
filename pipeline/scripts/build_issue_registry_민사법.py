# -*- coding: utf-8 -*-
"""민사법판 쟁점 레지스트리 구축 (CIV 접두사)."""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "final" / "민사법_사례_full_clean.json"
OUTDIR = SCRATCH / "registry"
OUTDIR.mkdir(exist_ok=True)

SUBJECT = "민사법"
PREFIX = "CIV"

data = json.load(open(SRC, encoding="utf-8"))

ALIAS = {
    "기판력의주관적범위": "기판력의 주관적 범위", "기판력의객관적범위": "기판력의 객관적 범위",
    "채권자취소소송": "채권자취소권", "사해행위취소": "채권자취소권", "사해행위취소권": "채권자취소권",
    "채권자대위소송": "채권자대위권",
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

# 민사소송법(절차법) 쟁점 키워드
PROC = [
    "기판력", "재소금지", "독립당사자참가", "소송수계", "중복소송", "보조참가",
    "재판상자백", "처분권주의", "변론주의", "당사자적격", "당사자능력", "소송능력",
    "확인의이익", "확인의소익", "청구의객관적병합", "예비적병합", "선택적병합",
    "공동소송", "필수적공동소송", "통상공동소송", "소송참가", "소송고지",
    "상소", "항소", "상고", "재심", "판결경정", "청구이의", "제3자이의",
    "가압류", "가처분", "집행정지", "집행문", "소송상화해", "화해권고결정",
    "소취하", "청구의포기", "청구의인낙", "석명권", "변론종결후승계인",
    "증거력", "증명책임", "자유심증주의", "문서의진정성립", "서증",
    "소송고지의효력", "당사자표시정정", "피고경정", "임의적당사자변경",
    "일부청구", "명시적일부청구", "소송물", "상소이익", "불이익변경금지",
    "선정당사자", "임의적소송담당", "소송탈퇴", "인수승계", "참가승계",
]
# 상법 쟁점 키워드
COMM = [
    "표현대표이사", "영업양도", "주식매수청구권", "이사의책임", "상법",
    "회사분할", "합병", "주주총회", "이사회", "대표이사", "상업등기",
    "상행위", "상사시효", "상사유치권", "익명조합", "합자회사", "주식회사",
]

def guess_path(k: str) -> list:
    if any(t in k for t in PROC):
        return [SUBJECT, "민사소송법"]
    if any(t in k for t in COMM):
        return [SUBJECT, "상법"]
    return [SUBJECT, "민법"]

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
