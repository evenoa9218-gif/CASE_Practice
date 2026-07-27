# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
from paths import APP, CASEBOOK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

TOC_PATH = str(CASEBOOK / "toc_raw.json")
INDEX_PATH = str(APP / "data" / "공법" / "index.json")
OUT_PATH = str(CASEBOOK / "toc_matched.json")

KOR_NUM = {"일":1,"이":2,"삼":3,"사":4,"오":5}

BAR_RE = re.compile(r"(?:제\s*)?(\d+)\s*회\s*변호사\s*시험")
MOCK_RE = re.compile(r"(\d{4})\s*년.*?제?\s*(\d)\s*차\s*모의\s*시험")
QNUM_RE = re.compile(r"(\d)\s*문(?:의\s*(\d))?")
SUBQ_RE = re.compile(r"설문\s*([\d,\s]+)")


GARBLED_1CHA = ["는卜", "제는卜", "は卜", "는｝", "は｝", "闵", "因", "제因", "제闵"]

def parse_source(src):
    src = src.replace("스", "제").replace("ス", "제")  # common OCR garble for 제
    for g in GARBLED_1CHA:
        src = src.replace(g, "1차")
    src = re.sub(r"제\s*[・･]\s*차", "제1차", src)
    src = re.sub(r"(\d)\s*자\s*모의시험", r"\1차 모의시험", src)  # 자/차 OCR confusion
    bar = BAR_RE.search(src)
    mock = MOCK_RE.search(src)
    result = {"raw": src}
    if bar:
        result["examType"] = "변시"
        result["hoi"] = int(bar.group(1))
    elif mock:
        result["examType"] = "모의"
        result["year"] = int(mock.group(1))
        result["round"] = int(mock.group(2))
    else:
        result["examType"] = None

    qm = QNUM_RE.search(src)
    if qm:
        result["qno"] = int(qm.group(1))
        result["qsub"] = int(qm.group(2)) if qm.group(2) else None
    sq = SUBQ_RE.search(src)
    if sq:
        nums = re.findall(r"\d+", sq.group(1))
        result["subq"] = [int(n) for n in nums]
    return result


def exam_id_for(parsed):
    if parsed["examType"] == "변시":
        return f"공법_변시_{parsed['hoi']}회_사례"
    if parsed["examType"] == "모의":
        return f"공법_모의_{parsed['year']}_{parsed['round']}차_사례"
    return None


GROUP_NUM_RE = re.compile(r"(\d+)")

def match_group(exam, parsed):
    group_keys = [g["key"] for g in exam.get("groups", [])]

    # some exam papers number their 2nd fact pattern as bare "설문N" instead of
    # nesting it under "문N" — prefer an exact "설문{n}" group when it exists,
    # since that's the more specific locator the casebook's "N문 설문M" implies.
    for n in parsed.get("subq", []):
        key = f"설문{n}"
        if key in group_keys:
            return key

    if "qno" not in parsed:
        return None
    qno = parsed["qno"]
    candidates = []
    for key in group_keys:
        m = GROUP_NUM_RE.search(key)
        if m and int(m.group(1)) == qno:
            candidates.append(key)
    if candidates:
        # prefer "문{qno}"/"문제{qno}" style keys over bare "설문{qno}" keys
        # when both happen to numerically collide
        preferred = [k for k in candidates if k.startswith("문")]
        return preferred[0] if preferred else candidates[0]
    return None


def main():
    toc = json.loads(Path(TOC_PATH).read_text(encoding="utf-8"))
    index = json.loads(Path(INDEX_PATH).read_text(encoding="utf-8"))
    exams_by_id = {e["id"]: e for e in index["exams"]}

    stats = {"total": 0, "exam_matched": 0, "group_matched": 0, "exam_unmatched": 0}
    out = {}
    for subject, entries in toc.items():
        out_entries = []
        for e in entries:
            stats["total"] += 1
            parsed = parse_source(e["source"])
            exam_id = exam_id_for(parsed)
            exam = exams_by_id.get(exam_id) if exam_id else None
            group_key = match_group(exam, parsed) if exam else None
            if exam:
                stats["exam_matched"] += 1
                if group_key:
                    stats["group_matched"] += 1
            else:
                stats["exam_unmatched"] += 1
            out_entries.append({
                **e,
                "parsed": parsed,
                "examId": exam_id if exam else None,
                "groupKey": group_key,
            })
        out[subject] = out_entries

    Path(OUT_PATH).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(stats)
    print("saved to", OUT_PATH)

    # print unmatched samples
    print("\n=== unmatched exam-id samples ===")
    n = 0
    for subject, entries in out.items():
        for e in entries:
            if not e["examId"]:
                print(f"[{subject}] case{e['case_no']}: {e['source']!r} -> parsed={e['parsed']}")
                n += 1
                if n >= 20:
                    break
        if n >= 20:
            break

if __name__ == "__main__":
    main()
