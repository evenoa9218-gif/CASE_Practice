# -*- coding: utf-8 -*-
"""LLM 개념 태깅용 경량 입력 파일 생성 (항목당 개별 파일로 분리)."""
import json
import re
from pathlib import Path
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SRC = WORK / "공법_모의_사례.json"
OUTDIR = WORK / "tag_input"
OUTDIR.mkdir(exist_ok=True)

RUBRIC_HEAD = 3500   # 채점기준표 앞부분만 (문항 구조 + 배점이 담긴 구간)

def clean(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"<(표|그림)>", "", t)          # 추출 placeholder 제거
    t = re.sub(r"\n{3,}", "\n\n", t)            # 과도한 빈 줄 축약
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()

data = json.load(open(SRC, encoding="utf-8"))

for rec in data:
    problem = clean(rec.get("problemText"))
    rubric = clean(rec.get("rubricText"))[:RUBRIC_HEAD]

    body = f"""# {rec['label']} — 공법 사례형
(id: {rec['id']}, 연도: {rec['year']}, 차수: {rec['round']}차)

## 문제 지문
{problem}

## 채점기준표 앞부분 (문항 구조·배점)
{rubric}
"""
    (OUTDIR / f"{rec['id']}.md").write_text(body, encoding="utf-8")

sizes = [(f.name, f.stat().st_size) for f in sorted(OUTDIR.iterdir())]
total = sum(s for _, s in sizes)
print(f"{len(sizes)}개 파일 생성, 총 {total:,}바이트 (평균 {total//len(sizes):,})")
print(f"최대: {max(sizes, key=lambda x: x[1])}")
print(f"최소: {min(sizes, key=lambda x: x[1])}")
