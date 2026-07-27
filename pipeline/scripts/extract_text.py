import subprocess
import sys
from pathlib import Path
from paths import HWP5TXT, RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

HWP5TXT = HWP5TXT

TARGET_DIRS = [
    RAW / "공법" / "문제" / "사례형",
    RAW / "공법" / "채점기준표" / "사례형",
]

ok = 0
fail = 0
skipped = 0

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
                print("FAIL:", f.name, result.stderr.decode("utf-8", "ignore")[:200])
                continue
            out.write_bytes(result.stdout)
            ok += 1
        except Exception as e:
            fail += 1
            print("ERROR:", f.name, e)

print(f"\n완료: 성공={ok}, 실패={fail}, 이미존재={skipped}")
