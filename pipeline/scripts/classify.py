import os
import re
import shutil
import hashlib
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW
CATS = ["공법", "국제거래법", "국제법", "기록형", "민사법", "형사법"]
SUBFOLDERS = ["문제", "채점기준표"]

EXCLUDE_SUBJECT_RE = re.compile(r"조세법|노동법|경제법|지적재산권법|환경법")
ANSWER_KEYWORDS = ["채점기준표", "정답표", "정답가안", "최종정답", "정답"]

# folders/files to leave completely untouched (special-cased by user decision)
KEEP_AS_IS_MARKERS = [
    "1회~12회 선택형 최종정답",
]

# combined selective-subject files needing manual content-split later (handled separately)
SPECIAL_SPLIT_MARKER = "1-14회 선택과목"

DRY_RUN = False

def is_category_folder(p: Path) -> bool:
    try:
        rel = p.relative_to(BASE)
    except ValueError:
        return False
    return len(rel.parts) >= 1 and rel.parts[0] in CATS

def classify(filename: str, fullpath: str):
    if EXCLUDE_SUBJECT_RE.search(filename):
        return ("DELETE", None, None)
    if "기록" in filename:
        cat = "기록형"
    elif "국제거래법" in filename:
        cat = "국제거래법"
    elif "국제법" in filename:
        cat = "국제법"
    elif "공법" in filename:
        cat = "공법"
    elif "민사" in filename:
        cat = "민사법"
    elif "형사" in filename:
        cat = "형사법"
    elif "선택과목" in filename:
        return ("SPECIAL_SPLIT", None, None)
    elif "선택법" in fullpath or "선택과목" in fullpath:
        # leftover reference material for an excluded elective subject
        return ("DELETE", None, None)
    else:
        return ("UNCLASSIFIED", None, None)

    sub = "채점기준표" if any(k in filename for k in ANSWER_KEYWORDS) else "문제"
    return ("MOVE", cat, sub)

def file_hash(path: Path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def unique_dest(dest: Path, src: Path) -> Path | None:
    if not dest.exists():
        return dest
    # if identical content already at destination, treat as duplicate -> skip (return None)
    try:
        if dest.stat().st_size == src.stat().st_size and file_hash(dest) == file_hash(src):
            return None
    except OSError:
        pass
    # otherwise disambiguate using parent folder name of src
    parent_hint = src.parent.name
    stem, ext = dest.stem, dest.suffix
    candidate = dest.with_name(f"{stem} [{parent_hint}]{ext}")
    counter = 2
    while candidate.exists():
        candidate = dest.with_name(f"{stem} [{parent_hint}]({counter}){ext}")
        counter += 1
    return candidate

actions = {"MOVE": [], "DELETE": [], "UNCLASSIFIED": [], "SKIP_ASIS": [], "SPECIAL_SPLIT": [], "SKIP_DUP": []}

for root, dirs, files in os.walk(BASE):
    root_path = Path(root)

    if any(marker in str(root_path) for marker in KEEP_AS_IS_MARKERS):
        for fn in files:
            actions["SKIP_ASIS"].append(str(root_path / fn))
        continue

    if SPECIAL_SPLIT_MARKER in str(root_path):
        for fn in files:
            actions["SPECIAL_SPLIT"].append(str(root_path / fn))
        continue

    for fn in files:
        fpath = root_path / fn
        if fn == ".DS_Store":
            actions["DELETE"].append(str(fpath))
            continue
        if fn.lower().endswith(".zip"):
            # handled separately after verifying contents
            continue

        kind, cat, sub = classify(fn, str(fpath))

        if kind == "DELETE":
            actions["DELETE"].append(str(fpath))
        elif kind == "UNCLASSIFIED":
            actions["UNCLASSIFIED"].append(str(fpath))
        elif kind == "SPECIAL_SPLIT":
            actions["SPECIAL_SPLIT"].append(str(fpath))
        elif kind == "MOVE":
            dest_dir = BASE / cat / sub
            dest = dest_dir / fn
            final_dest = unique_dest(dest, fpath) if not DRY_RUN else dest
            if final_dest is None:
                actions["SKIP_DUP"].append(str(fpath))
            else:
                actions["MOVE"].append((str(fpath), str(final_dest)))

print("=== SUMMARY ===")
for k, v in actions.items():
    print(f"{k}: {len(v)}")

print("\n=== UNCLASSIFIED (need review) ===")
for f in actions["UNCLASSIFIED"]:
    print(f)

print("\n=== SAMPLE MOVES (first 20) ===")
for s, d in actions["MOVE"][:20]:
    print(f"{s}\n  -> {d}")

if not DRY_RUN:
    moved = 0
    skipped_same = 0
    for src, dest in actions["MOVE"]:
        src_path = Path(src)
        dest_path = Path(dest)
        if src_path.resolve() == dest_path.resolve():
            skipped_same += 1
            continue
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        real_dest = unique_dest(dest_path, src_path)
        if real_dest is None:
            os.remove(src)
            continue
        shutil.move(src, str(real_dest))
        moved += 1
    deleted = 0
    for f in actions["DELETE"]:
        if os.path.exists(f):
            os.remove(f)
            deleted += 1

    # prune now-empty directories (bottom-up), never touching the category folders
    removed_dirs = 0
    for dirpath, dirnames, filenames in os.walk(BASE, topdown=False):
        p = Path(dirpath)
        if p == BASE:
            continue
        try:
            rel_parts = p.relative_to(BASE).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] in CATS:
            continue
        if not any(p.iterdir()):
            p.rmdir()
            removed_dirs += 1

    print(f"\nDONE: moved={moved}, skipped_same={skipped_same}, deleted={deleted}, removed_empty_dirs={removed_dirs}")
