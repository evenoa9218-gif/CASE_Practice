# -*- coding: utf-8 -*-
"""변시(실제기출) 15회분: 태깅 입력 생성 + 판례/조문 정규식 추출."""
import json
import re
from pathlib import Path
from collections import Counter
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
SRC = SCRATCH / "공법_변시_사례_1to15.json"
TAGDIR = SCRATCH / "tag_input_real"
TAGDIR.mkdir(exist_ok=True)
CITE_OUT = SCRATCH / "공법_변시_citations.json"

CASE_RE = re.compile(r"\b(\d{2,4})\s*(헌마|헌바|헌가|헌라|헌나|헌사|헌아|두|다|누|도|므|추|카|허|후|재|초)\s*(\d+)\b")
STATUTE_RE = re.compile(
    r"([가-힣]{2,20}(?:법|법률|규칙|령|헌법))\s*(제\s*\d+조(?:\s*의\s*\d+)?"
    r"(?:\s*제\s*\d+항)?(?:\s*제\s*\d+호)?)"
)

def clean(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"<(표|그림)>", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()

data = json.load(open(SRC, encoding="utf-8"))
cites = []

for rec in data:
    problem = rec.get("problemText") or ""

    # 태깅 입력 (변시는 채점기준표 없음 → 문제 전문만)
    body = f"""# {rec['label']} — 공법 사례형 (실제 변호사시험)
(id: {rec['id']}, 회차: 제{rec['hoi']}회, 시행연도: {rec['year']}년)
※ 이 시험은 공식 채점기준표가 공개되지 않아 문제 지문만 제공됩니다.

## 문제 지문
{clean(problem)}
"""
    (TAGDIR / f"{rec['id']}.md").write_text(body, encoding="utf-8")

    # 판례/조문 추출
    cs = [f"{y}{c}{n}" for y, c, n in CASE_RE.findall(problem)]
    sts = [re.sub(r"\s+", " ", f"{law} {art}").strip() for law, art in STATUTE_RE.findall(problem)]
    cites.append({
        "id": rec["id"], "hoi": rec["hoi"], "year": rec["year"], "label": rec["label"],
        "caseCitations": [c for c, _ in Counter(cs).most_common()],
        "statutes": [s for s, _ in Counter(sts).most_common(30)],
    })

with open(CITE_OUT, "w", encoding="utf-8") as f:
    json.dump(cites, f, ensure_ascii=False, indent=2)

sizes = [(f.name, f.stat().st_size) for f in sorted(TAGDIR.iterdir())]
print(f"태깅 입력 {len(sizes)}개 생성 (총 {sum(s for _,s in sizes):,}바이트)")
print(f"판례/조문 추출 -> {CITE_OUT}\n")
for c in cites:
    print(f"  제{c['hoi']:2d}회({c['year']}) 판례 {len(c['caseCitations'])}건, 조문 {len(c['statutes'])}건")
