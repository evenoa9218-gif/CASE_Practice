# -*- coding: utf-8 -*-
"""배경영상(28MB) 제거 → CSS 그라디언트로 대체.

설계 지적사항: 수험생이 지하철에서 여는 앱에 1080p 28MB는 로딩·데이터·배터리 손해.
"""
import re
from pathlib import Path
from paths import MCQ_REPO   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

REPO = MCQ_REPO
FILES = ["index.html", "criminal.html", "public-law.html"]

# ── 1) <head> 프리로드 스크립트 제거 ─────────────────────
HEAD_PRELOAD = re.compile(
    r'<script>\s*\(function\(\)\{\s*var vids=\["bg_a\.mp4".*?\}\)\(\);\s*</script>\s*',
    re.S)

# ── 2) App() 내부 bgSrc useState 블록 제거 ───────────────
APP_BGSRC = re.compile(
    r'  const \[bgSrc\] = useState\(\(\) => \{\s*'
    r'    const vids=\["bg_a\.mp4".*?\n  \}\);\s*\n',
    re.S)

# ── 3) 컴포넌트 내 bgVideos/bgSrc 2줄 제거 ───────────────
COMP_BGSRC = re.compile(
    r'[ \t]*const bgVideos = \["bg_a\.mp4"[^\n]*\n'
    r'[ \t]*const \[bgSrc\] = React\.useState\(\(\) => bgVideos\[[^\n]*\n')

# ── 4) <video> 요소 → CSS 그라디언트 div ────────────────
VIDEO_EL = re.compile(
    r'<video ref=\{bgVideoRef\}[^>]*>\s*'
    r'<source src=\{bgSrc\} type="video/mp4" />\s*'
    r'</video>',
    re.S)
GRADIENT_DIV = (
    '<div className="bg-scene" style={{position:"absolute",inset:0,'
    'width:"100%",height:"100%"}}></div>'
)

# ── 5) bgVideoRef 선언 및 useEffect 정리 ────────────────
BGREF_DECL = re.compile(r'[ \t]*const bgVideoRef = useRef\(null\);\s*\n')

# 배경 그라디언트 CSS (기존 다크테마와 동일 계열)
BG_CSS = """
/* 배경: 영상 대신 CSS 그라디언트 (28MB 절감) */
.bg-scene{
  background:
    radial-gradient(1200px 800px at 18% 12%, rgba(52,96,168,.28), transparent 60%),
    radial-gradient(1000px 700px at 82% 78%, rgba(122,84,168,.20), transparent 62%),
    radial-gradient(900px 600px at 60% 20%, rgba(28,72,124,.22), transparent 58%),
    linear-gradient(160deg,#050a16 0%,#081428 45%,#040a18 100%);
  animation: bgdrift 32s ease-in-out infinite alternate;
}
@keyframes bgdrift{
  from{ background-position:0% 0%,100% 100%,50% 0%,0 0; }
  to  { background-position:12% 8%, 88% 92%, 42% 10%,0 0; }
}
@media (prefers-reduced-motion: reduce){ .bg-scene{ animation:none; } }
"""

total = {}
for name in FILES:
    p = REPO / name
    src = p.read_text(encoding="utf-8")
    orig = src
    counts = {}

    src, n = HEAD_PRELOAD.subn("", src);      counts["head프리로드"] = n
    src, n = APP_BGSRC.subn("", src);         counts["App_bgSrc"] = n
    src, n = COMP_BGSRC.subn("", src);        counts["컴포넌트_bgSrc"] = n
    src, n = VIDEO_EL.subn(GRADIENT_DIV, src);counts["video→div"] = n
    src, n = BGREF_DECL.subn("", src);        counts["bgVideoRef"] = n

    # bgVideoRef를 쓰던 useEffect 블록 정리 (참조가 사라졌으므로)
    src = re.sub(
        r'  useEffect\(\(\) => \{\s*\n'
        r'    const v = bgVideoRef\.current;.*?\n  \}, \[\]\);\s*\n',
        '', src, flags=re.S)

    # CSS 삽입: 첫 <style> 블록 안 또는 CSS 상수에 추가
    if ".bg-scene{" not in src:
        m = re.search(r'(const CSS = `)', src)
        if m:
            src = src[:m.end()] + BG_CSS + src[m.end():]
            counts["CSS삽입"] = 1
        else:
            m2 = re.search(r'(<style>)', src)
            if m2:
                src = src[:m2.end()] + BG_CSS + src[m2.end():]
                counts["CSS삽입"] = 1

    if src != orig:
        p.write_text(src, encoding="utf-8")
    total[name] = counts
    print(f"[{name}] " + ", ".join(f"{k}={v}" for k, v in counts.items()))

# ── 잔여 참조 검사 ───────────────────────────────────────
print("\n=== 잔여 mp4/bgSrc 참조 ===")
left = 0
for name in FILES:
    txt = (REPO / name).read_text(encoding="utf-8")
    hits = [(i+1, l.strip()[:90]) for i, l in enumerate(txt.split("\n"))
            if ("mp4" in l or "bgSrc" in l or "bgVideo" in l)]
    for ln, l in hits:
        left += 1
        print(f"  {name}:{ln}  {l}")
if left == 0:
    print("  없음 ✓")
