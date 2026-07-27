# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import OrderedDict
from paths import APP, CASEBOOK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

MATCHED_PATH = str(CASEBOOK / "toc_matched.json")
OUT_PATH = str(APP / "data" / "공법" / "casebook_toc.json")

BOOK_META = {
    "헌법": {"title": "강성민 헌법 사례형 연습 제9판", "year": 2026},
    "행정법": {"title": "강성민 행정법 사례형 연습", "year": 2026},
}

def humanize_source(parsed, raw):
    et = parsed.get("examType")
    if et == "변시":
        return f"제{parsed['hoi']}회 변호사시험"
    if et == "모의":
        return f"{parsed['year']}년 제{parsed['round']}차 모의고사"
    return raw

def main():
    matched = json.loads(Path(MATCHED_PATH).read_text(encoding="utf-8"))
    out = {}
    stats = {}
    for subject, entries in matched.items():
        parts = OrderedDict()
        for e in entries:
            part = e["part"] or "미분류"
            parts.setdefault(part, [])
            parts[part].append({
                "caseNo": e["case_no"],
                "source": humanize_source(e["parsed"], e["source"]),
                "label": e["issue_label"],
                "examId": e["examId"],
                "groupKey": e["groupKey"],
            })
        out[subject] = {
            "meta": BOOK_META.get(subject, {}),
            "parts": [{"title": k, "cases": v} for k, v in parts.items()],
        }
        total = len(entries)
        matched_n = sum(1 for e in entries if e["examId"])
        group_n = sum(1 for e in entries if e["groupKey"])
        stats[subject] = {"total": total, "examMatched": matched_n, "groupMatched": group_n}

    Path(OUT_PATH).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved to", OUT_PATH)
    print(stats)

if __name__ == "__main__":
    main()
