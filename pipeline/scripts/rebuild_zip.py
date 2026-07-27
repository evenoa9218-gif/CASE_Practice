import zipfile
import os
from pathlib import Path
from paths import RAW, WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

TMPD = WORK / "zip_restore"
DEST = RAW / "제15회변호사시험정답가안.zip"

print("TMPD exists:", TMPD.exists(), list(TMPD.iterdir()))
print("DEST parent exists:", DEST.parent.exists())

with zipfile.ZipFile(DEST, "w", zipfile.ZIP_DEFLATED) as z:
    for f in TMPD.iterdir():
        z.write(f, f.name)

print("done, size:", DEST.stat().st_size)
