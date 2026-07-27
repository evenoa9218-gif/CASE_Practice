import zipfile
from pathlib import Path
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW
EXCLUDE = BASE / "변시기출(1-14)"

for zpath in BASE.rglob("*.zip"):
    if EXCLUDE in zpath.parents:
        continue
    if zpath.is_dir():
        print("SKIP (실은 폴더):", zpath)
        continue
    dest_dir = zpath.parent / zpath.stem
    dest_dir.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(zpath) as z:
            names = z.namelist()
            for name in names:
                # zip 내부 파일명이 cp437로 잘못 디코딩된 경우 교정 시도
                try:
                    fixed_name = name.encode("cp437").decode("cp949")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    fixed_name = name
                target = dest_dir / fixed_name
                if name.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as src, open(target, "wb") as out:
                    out.write(src.read())
        print("추출 완료:", zpath, "->", dest_dir, f"({len(names)}개)")
    except Exception as e:
        print("실패:", zpath, "-", e)
