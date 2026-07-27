# -*- coding: utf-8 -*-
"""저장소 이름 변경(3000 → MCQ)으로 깨진 절대경로 수정.

주의: '/3000/' 형태의 경로만 바꾼다.
      제목 '3000제 OX 퀴즈', 판례번호 '2003도3000' 등은 절대 건드리지 않는다.
"""
import re
from pathlib import Path
from paths import MCQ_REPO   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

REPO = MCQ_REPO

TARGETS = ["index.html", "criminal.html", "public-law.html", "manifest.json", "sw.js"]

# 경로 패턴만 정밀 치환
PATH_PAT = re.compile(r"/3000/")

changed = []
for name in TARGETS:
    p = REPO / name
    if not p.exists():
        print(f"[없음] {name}")
        continue
    src = p.read_text(encoding="utf-8")
    n = len(PATH_PAT.findall(src))
    if n == 0:
        print(f"[변경없음] {name}")
        continue
    dst = PATH_PAT.sub("/MCQ/", src)

    # 안전 검증: 경로 외 '3000'은 그대로여야 함
    before_other = len(re.findall(r"3000", PATH_PAT.sub("", src)))
    after_other = len(re.findall(r"3000", re.compile(r"/MCQ/").sub("", dst)))
    assert before_other == after_other, f"{name}: 비경로 3000이 변경됨!"

    p.write_text(dst, encoding="utf-8")
    changed.append((name, n))
    print(f"[수정] {name}: {n}건")

# 서비스워커 캐시 버전 올리기 (기존 사용자에게 갱신 전파)
sw = REPO / "sw.js"
if sw.exists():
    s = sw.read_text(encoding="utf-8")
    m = re.search(r"const CACHE = 'ox-quiz-v(\d+)';", s)
    if m:
        old = int(m.group(1))
        s = s.replace(f"ox-quiz-v{old}", f"ox-quiz-v{old+1}")
        sw.write_text(s, encoding="utf-8")
        print(f"[캐시버전] ox-quiz-v{old} → v{old+1} (기존 사용자 갱신 유도)")

print(f"\n총 {len(changed)}개 파일, {sum(n for _, n in changed)}건 경로 수정")

# 최종 검증
print("\n=== 검증: 남은 /3000/ 참조 ===")
left = 0
for name in TARGETS:
    p = REPO / name
    if not p.exists():
        continue
    hits = PATH_PAT.findall(p.read_text(encoding="utf-8"))
    if hits:
        left += len(hits)
        print(f"  ⚠ {name}: {len(hits)}건 남음")
print("  없음 ✓" if left == 0 else f"  총 {left}건 남음")

print("\n=== 검증: 보존돼야 할 '3000' (판례번호·제목) ===")
for name in TARGETS:
    p = REPO / name
    if not p.exists():
        continue
    txt = p.read_text(encoding="utf-8")
    others = [m.start() for m in re.finditer(r"3000", txt)]
    if others:
        sample = txt[max(0, others[0]-40):others[0]+20].replace("\n", " ")
        print(f"  {name}: {len(others)}건 보존  …{sample}…")
