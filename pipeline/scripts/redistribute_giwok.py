import os
import shutil
import hashlib
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW
GIROK = BASE / "기록형"
SUBFOLDERS = ["문제", "채점기준표"]

DRY_RUN = False

def classify_subject(filename: str):
    if "공법" in filename or "공기록" in filename:
        return "공법"
    if "민사" in filename or "민기록" in filename:
        return "민사법"
    if "형사" in filename or "형기록" in filename:
        return "형사법"
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

for sub in SUBFOLDERS:
    d = GIROK / sub
    if not d.exists():
        continue
    for f in d.iterdir():
        if not f.is_file():
            continue
        subject = classify_subject(f.name)
        if subject is None:
            unresolved.append(str(f))
            continue
        dest = BASE / subject / sub / "기록형" / f.name
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

    # prune now-empty dirs under 기록형, and 기록형 itself if empty
    for dirpath, dirnames, filenames in os.walk(GIROK, topdown=False):
        p = Path(dirpath)
        if not any(p.iterdir()):
            p.rmdir()
    if GIROK.exists() and not any(GIROK.iterdir()):
        GIROK.rmdir()
        print("기록형 폴더 제거 완료")
