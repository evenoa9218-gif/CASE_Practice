import shutil
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW

SUBJECTS = ["공법", "국제거래법", "국제법", "민사법", "형사법"]
DOCTYPES = ["문제", "채점기준표"]
TYPES = ["사례형", "기록형"]

FAILED_HWP = BASE / "국제거래법" / "채점기준표" / "사례형" / "2. 2013년도 제3차 변호사시험 모의시험 선택과목 사례형 채점기준표_국제거래법.hwp"

moved_txt = 0
moved_failed_hwp = 0

for subj in SUBJECTS:
    for dt in DOCTYPES:
        for t in TYPES:
            d = BASE / subj / dt / t
            if not d.exists():
                continue
            txt_files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".txt"]
            if not txt_files:
                continue
            txt_dir = d / "txt"
            txt_dir.mkdir(exist_ok=True)
            for f in txt_files:
                shutil.move(str(f), str(txt_dir / f.name))
                moved_txt += 1

if FAILED_HWP.exists():
    txt_dir = FAILED_HWP.parent / "txt"
    txt_dir.mkdir(exist_ok=True)
    shutil.move(str(FAILED_HWP), str(txt_dir / FAILED_HWP.name))
    moved_failed_hwp = 1

print(f"txt 이동: {moved_txt}, 실패 hwp 이동: {moved_failed_hwp}")
