import os
import re
import shutil
import hashlib
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW
SUBJECT_CATS = ["공법", "국제거래법", "국제법", "민사법", "형사법"]  # 기록형 제외
SUBFOLDERS = ["문제", "채점기준표"]
TYPES = ["선택형", "사례형"]

DRY_RUN = False

def classify_type(filename: str) -> str:
    if "선택형" in filename:
        return "선택형"
    if "사례형" in filename:
        return "사례형"
    if "선택과목" in filename:
        return "사례형"
    m = re.match(r"\s*(\d+)", filename)
    if m:
        n = m.group(1)
        if n == "1":
            return "선택형"
        if n == "2":
            return "사례형"
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
    candidate = dest.with_name(f"{stem} (dup){ext}")
    counter = 2
    while candidate.exists():
        candidate = dest.with_name(f"{stem} (dup{counter}){ext}")
        counter += 1
    return candidate

moves = []
unresolved = []

for cat in SUBJECT_CATS:
    for sub in SUBFOLDERS:
        d = BASE / cat / sub
        if not d.exists():
            continue
        for f in d.iterdir():
            if not f.is_file():
                continue
            t = classify_type(f.name)
            if t is None:
                unresolved.append(str(f))
                continue
            dest = d / t / f.name
            moves.append((f, dest))

print("총 이동 대상:", len(moves))
print("분류 불가:", len(unresolved))
for u in unresolved:
    print(" ", u)

if not DRY_RUN:
    moved = 0
    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        real_dest = unique_dest(dest, src)
        if real_dest is None:
            os.remove(src)
            continue
        shutil.move(str(src), str(real_dest))
        moved += 1
    print("이동 완료:", moved)
