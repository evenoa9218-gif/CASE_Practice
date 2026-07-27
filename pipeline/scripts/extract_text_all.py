import subprocess
from pathlib import Path
from paths import HWP5TXT, RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

HWP5TXT = HWP5TXT
BASE = RAW

SUBJECTS = ["공법", "국제거래법", "국제법", "민사법", "형사법"]
DOCTYPES = ["문제", "채점기준표"]
TYPES = ["사례형", "기록형"]

TARGET_DIRS = []
for subj in SUBJECTS:
    for dt in DOCTYPES:
        for t in TYPES:
            d = BASE / subj / dt / t
            if d.exists():
                TARGET_DIRS.append(d)

ok = 0
fail = 0
skipped = 0
failed_files = []

for d in TARGET_DIRS:
    for f in sorted(d.iterdir()):
        if f.suffix.lower() != ".hwp":
            continue
        out = f.with_suffix(".txt")
        if out.exists():
            skipped += 1
            continue
        try:
            result = subprocess.run(
                [HWP5TXT, str(f)],
                capture_output=True,
                timeout=60,
            )
            if result.returncode != 0 or not result.stdout.strip():
                fail += 1
                failed_files.append((str(f), result.stderr.decode("utf-8", "ignore")[:200]))
                continue
            out.write_bytes(result.stdout)
            ok += 1
        except Exception as e:
            fail += 1
            failed_files.append((str(f), str(e)))

print(f"\n완료: 성공={ok}, 실패={fail}, 이미존재={skipped}")
for fn, err in failed_files:
    print("FAIL:", fn, "-", err)
