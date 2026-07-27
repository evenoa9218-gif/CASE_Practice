# -*- coding: utf-8 -*-
"""전 과목 태깅 입력 파일 일괄 생성 (모의고사 + 변시)."""
import json
import re
from pathlib import Path

SCRATCH = WORK
SUBJ_DIR = SCRATCH / "subjects"
OUTDIR = SCRATCH / "tag_input_all"
OUTDIR.mkdir(exist_ok=True)

RUBRIC_HEAD = 3500

SUBJECTS = ["민사법", "형사법", "국제법", "국제거래법"]


def clean(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"<(표|그림)>", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


manifest = []

for subj in SUBJECTS:
    for kind, fname in (("모의", f"{subj}_모의_사례.json"), ("변시", f"{subj}_변시_사례.json")):
        p = SUBJ_DIR / fname
        if not p.exists():
            continue
        data = json.load(open(p, encoding="utf-8"))
        for rec in data:
            problem = clean(rec.get("problemText"))
            rubric = clean(rec.get("rubricText"))
            if not problem and not rubric:
                continue

            head = f"# {rec['label']} — {subj} 사례형"
            meta = f"(id: {rec['id']}"
            if rec["examType"] == "모의고사":
                meta += f", 연도: {rec['year']}, 차수: {rec['round']}차)"
            else:
                meta += f", 회차: 제{rec['hoi']}회, 시행연도: {rec['year']}년)"

            body = f"{head}\n{meta}\n\n## 문제 지문\n{problem or '(없음)'}\n"
            if rubric:
                body += f"\n## 채점기준표 앞부분 (문항 구조·배점)\n{rubric[:RUBRIC_HEAD]}\n"
            else:
                body += "\n## 채점기준표\n(공개되지 않아 없음 — 문제 지문만으로 태깅)\n"

            (OUTDIR / f"{rec['id']}.md").write_text(body, encoding="utf-8")
            manifest.append({
                "id": rec["id"], "subject": subj, "kind": kind,
                "examType": rec["examType"], "year": rec["year"],
                "round": rec["round"], "hoi": rec["hoi"],
                "hasRubric": bool(rubric),
                "bytes": len(body.encode("utf-8")),
            })

json.dump(manifest, open(SCRATCH / "tag_manifest.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(f"태깅 입력 {len(manifest)}개 생성 -> {OUTDIR}\n")
from collections import Counter
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)
c = Counter((m["subject"], m["kind"]) for m in manifest)
for (s, k), v in sorted(c.items()):
    print(f"  {s} {k}: {v}건")
total_mb = sum(m["bytes"] for m in manifest) / 1024 / 1024
print(f"\n총 {total_mb:.1f}MB, 평균 {sum(m['bytes'] for m in manifest)//len(manifest):,}바이트")
no_rubric = [m["id"] for m in manifest if not m["hasRubric"]]
print(f"채점기준표 없는 항목: {len(no_rubric)}건")
