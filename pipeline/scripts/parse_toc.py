# -*- coding: utf-8 -*-
import re, json
from pathlib import Path
from paths import CASEBOOK, RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BOOKS = {
    "헌법": {
        "path": str(RAW / "사례집" / "헌법" / "(2026) 강성민 헌법 사례형 연습 제9판 ocr+선명도.txt"),
        "case_re": re.compile(r"^\S{1,3}[례레]\s*(\d+)\s*[.．]\s*(.*)$"),
        "body_signal": None,
    },
    "행정법": {
        "path": str(RAW / "사례집" / "행정법" / "(26.04)[강성민] 행정법 사례형 연습 OCR.txt"),
        "case_re": re.compile(r"^(\d+)\s*[.．]\s*(.*)$"),
        "body_signal": re.compile(r"사례\s*\d"),
    },
}

PART_RE = re.compile(r"^[제재]\s*(\d+)\s*편\s*(.*)$")
PURE_NUM_RE = re.compile(r"^[0-9lI0-9]+$")
TRAIL_NUM_RE = re.compile(r"\s+[0-9]{1,4}$")

def strip_trailing_pagenum(line):
    line = line.rstrip()
    m = TRAIL_NUM_RE.search(line)
    if m:
        return line[:m.start()].rstrip()
    return line

def find_toc_bounds(lines):
    for i, l in enumerate(lines):
        if PART_RE.match(l.strip()):
            return i
    raise RuntimeError("no PART header found to anchor TOC start")

def parse_book(subject, cfg):
    path = cfg["path"]
    case_re = cfg["case_re"]
    body_signal = cfg["body_signal"]
    text = Path(path).read_text(encoding="utf-8")
    lines = text.split("\n")
    start = find_toc_bounds(lines)

    entries = []
    current_part = None
    last_case_no = 0
    i = start
    stopped_at = None
    pending_case = None
    label_buf = []

    def flush():
        nonlocal pending_case, label_buf
        if pending_case is not None:
            case_no, source = pending_case
            label = " ".join(label_buf).strip()
            label = re.sub(r"\s{2,}", " ", label)
            entries.append({
                "case_no": case_no,
                "part": current_part,
                "source": source.strip(),
                "issue_label": label,
            })
        pending_case = None
        label_buf = []

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line:
            continue
        if body_signal and body_signal.search(line):
            stopped_at = (i - 1, "body_signal")
            break
        if PURE_NUM_RE.match(line):
            continue
        line = strip_trailing_pagenum(line)
        if not line:
            continue

        pm = PART_RE.match(line)
        if pm:
            flush()
            current_part = f"제{pm.group(1)}편 {pm.group(2)}".strip()
            continue

        cm = case_re.match(line)
        if cm:
            case_no = int(cm.group(1))
            if case_no <= last_case_no or case_no > last_case_no + 5:
                stopped_at = (i - 1, case_no)
                break
            last_case_no = case_no
            flush()
            pending_case = (case_no, cm.group(2))
            continue

        if pending_case is not None:
            label_buf.append(line)

    flush()

    # strip trailing running-header noise that bleeds into the last label
    # before a part/EOF boundary, e.g. "... 2026 헌법 사례형 연습 제 9판"
    header_noise_re = re.compile(r"\s*\d{4}\s*(?:헌법|행정법)\s*사례형\s*연습.*$")
    for e in entries:
        e["issue_label"] = header_noise_re.sub("", e["issue_label"]).strip()

    return entries, stopped_at

if __name__ == "__main__":
    all_out = {}
    for subj, cfg in BOOKS.items():
        entries, stopped = parse_book(subj, cfg)
        all_out[subj] = entries
        print(f"=== {subj} === total entries: {len(entries)}  stopped_at(line_idx, next_case_no)={stopped}")
        for e in entries[:5]:
            print(" ", e)
        print("  ...")
        for e in entries[-3:]:
            print(" ", e)

    out_path = CASEBOOK / "toc_raw.json"
    out_path.write_text(json.dumps(all_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSaved to", out_path)
