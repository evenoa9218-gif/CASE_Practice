import os
import re
import shutil
import hashlib
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW
CATS = ["공법", "국제거래법", "국제법", "민사법", "형사법"]

SOURCE_ROOTS = [
    BASE / "OneDrive_2026-07-24",
    BASE / "2023년 3차 모의시험 문제 및 답안",
    BASE / "2025 변모",
    BASE / "제15회변호사시험정답가안",
]
LOOSE_FILES = [
    BASE / "2023년도 제3차 변호사시험 모의시험 형사법 사례형 채점기준표.hwp",
]

EXCLUDE_ROOTS = [BASE / "변시기출(1-14)", BASE / "제15회변호사시험기출문제"]
for c in CATS:
    EXCLUDE_ROOTS.append(BASE / c)

EXCLUDE_SUBJECT_RE = re.compile(r"조세법|노동법|경제법|지적재산권법|환경법")
ANSWER_KEYWORDS = ["채점기준표", "정답표", "정답가안", "최종정답", "정답"]
OUTLIER_RE = re.compile(r"해설|\(시완\)|관련하여|게시용")

def classify_subject(filename: str, fullpath: str):
    if EXCLUDE_SUBJECT_RE.search(filename):
        return ("DELETE", None)
    if "기록" in filename:
        return ("SUBJECT_GIROK", None)  # 기록형 -> 실제 과목으로 재분배 필요
    if "국제거래법" in filename:
        return ("MOVE", "국제거래법")
    if "국제법" in filename:
        return ("MOVE", "국제법")
    if "공법" in filename or "공기록" in filename:
        return ("MOVE", "공법")
    if "민사" in filename or "민기록" in filename:
        return ("MOVE", "민사법")
    if "형사" in filename or "형기록" in filename:
        return ("MOVE", "형사법")
    if "선택과목" in filename:
        return ("SPECIAL_SPLIT", None)
    if "선택법" in fullpath or "선택과목" in fullpath:
        return ("DELETE", None)
    return ("UNCLASSIFIED", None)

def classify_type(filename: str):
    if "선택형" in filename:
        return "선택형"
    if "사례형" in filename:
        return "사례형"
    if "기록" in filename:
        return "기록형"
    if "선택과목" in filename:
        return "사례형"
    m = re.match(r"\s*(\d+)", filename)
    if m:
        n = m.group(1)
        if n == "1":
            return "선택형"
        if n == "2":
            return "사례형"
        if n == "3":
            return "기록형"
    return None

def file_hash(path: Path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def unique_dest(dest: Path, src: Path):
    if not dest.exists():
        return dest
    try:
        if dest.stat().st_size == src.stat().st_size and file_hash(dest) == file_hash(src):
            return None
    except OSError:
        pass
    stem, ext = dest.stem, dest.suffix
    parent_hint = src.parent.name
    candidate = dest.with_name(f"{stem} [{parent_hint}]{ext}")
    counter = 2
    while candidate.exists():
        candidate = dest.with_name(f"{stem} [{parent_hint}]({counter}){ext}")
        counter += 1
    return candidate

DRY_RUN = False

actions = {"MOVE": [], "DELETE": [], "UNCLASSIFIED": [], "OUTLIER": [], "SPECIAL_SPLIT": []}

def is_excluded(p: Path):
    for ex in EXCLUDE_ROOTS:
        if ex in p.parents or ex == p:
            return True
    return False

def gather_files():
    files = []
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dp = Path(dirpath)
            if is_excluded(dp):
                dirnames[:] = []
                continue
            for fn in filenames:
                files.append(dp / fn)
    files.extend([f for f in LOOSE_FILES if f.exists()])
    return files

for fpath in gather_files():
    fn = fpath.name
    if fn == ".DS_Store":
        actions["DELETE"].append(fpath)
        continue
    if fn.lower().endswith(".zip"):
        continue
    if OUTLIER_RE.search(fn):
        actions["OUTLIER"].append(fpath)
        continue

    kind, subject = classify_subject(fn, str(fpath))

    if kind == "DELETE":
        actions["DELETE"].append(fpath)
        continue
    if kind == "UNCLASSIFIED":
        actions["UNCLASSIFIED"].append(fpath)
        continue
    if kind == "SPECIAL_SPLIT":
        actions["SPECIAL_SPLIT"].append(fpath)
        continue

    if kind == "SUBJECT_GIROK":
        # 기록형 파일은 파일명에서 실제 과목(공법/민사법/형사법)을 재판별
        if "공법" in fn or "공기록" in fn:
            subject = "공법"
        elif "민사" in fn or "민기록" in fn:
            subject = "민사법"
        elif "형사" in fn or "형기록" in fn:
            subject = "형사법"
        else:
            actions["UNCLASSIFIED"].append(fpath)
            continue

    doctype = "채점기준표" if any(k in fn for k in ANSWER_KEYWORDS) else "문제"
    typ = classify_type(fn)
    if typ is None:
        actions["UNCLASSIFIED"].append(fpath)
        continue
    if subject in ("국제법", "국제거래법") and typ != "사례형":
        typ = "사례형"

    dest = BASE / subject / doctype / typ / fn
    actions["MOVE"].append((fpath, dest))

print("=== 요약 ===")
for k, v in actions.items():
    print(f"{k}: {len(v)}")

print("\n=== UNCLASSIFIED ===")
for f in actions["UNCLASSIFIED"]:
    print(" ", f)

print("\n=== OUTLIER (해설/개인답안 등, 수동 확인 필요) ===")
for f in actions["OUTLIER"]:
    print(" ", f)

print("\n=== SPECIAL_SPLIT (통합 선택과목, 건드리지 않음) ===")
for f in actions["SPECIAL_SPLIT"]:
    print(" ", f)

if not DRY_RUN:
    moved = 0
    dup_skipped = 0
    for src, dest in actions["MOVE"]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        real_dest = unique_dest(dest, src)
        if real_dest is None:
            os.remove(src)
            dup_skipped += 1
            continue
        shutil.move(str(src), str(real_dest))
        moved += 1
    deleted = 0
    for f in actions["DELETE"]:
        if f.exists():
            os.remove(f)
            deleted += 1
    print(f"\n이동={moved}, 중복삭제={dup_skipped}, 삭제={deleted}")
