# -*- coding: utf-8 -*-
"""사례집 PDF들의 텍스트층 유무를 빠르게 판별 (변환 전 사전조사)."""
import time
from pathlib import Path
from pypdf import PdfReader
from paths import RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

BASE = RAW / "사례집"

# 사용자 지정 우선순위
ORDER = ["헌법", "형법", "형사소송법", "행정법", "민사소송법", "민법", "상법", "기록형"]

MIN_CHARS = 100


def probe(pdf: Path):
    """앞/중간/뒤 각 2페이지씩 샘플링해 텍스트층 판별."""
    try:
        r = PdfReader(str(pdf))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    n = len(r.pages)
    spots = []
    for frac in (0.1, 0.45, 0.8):
        i = int(n * frac)
        spots.extend([i, min(i + 1, n - 1)])
    sample = ""
    t0 = time.time()
    for i in sorted(set(spots)):
        try:
            sample += r.pages[i].extract_text() or ""
        except Exception:
            pass
    dt = time.time() - t0
    per_page = dt / max(1, len(set(spots)))
    return {
        "pages": n,
        "chars": len(sample.strip()),
        "hasText": len(sample.strip()) >= MIN_CHARS,
        "secPerPage": per_page,
        "estMin": per_page * n / 60,
        "sample": sample.strip()[:200],
    }


results = {}
for subj in ORDER:
    d = BASE / subj
    if not d.exists():
        continue
    print(f"\n{'='*60}\n[{subj}]")
    results[subj] = []
    for pdf in sorted(d.glob("*.pdf")):
        size_mb = pdf.stat().st_size / 1024 / 1024
        info = probe(pdf)
        info["file"] = pdf.name
        info["sizeMB"] = size_mb
        results[subj].append(info)
        if "error" in info:
            print(f"  ✗ {pdf.name}: {info['error']}")
            continue
        mark = "✓ 텍스트" if info["hasText"] else "✗ 스캔본(OCR필요)"
        print(f"  {mark} | {pdf.name}")
        print(f"      {size_mb:.0f}MB, {info['pages']}p, 예상변환 {info['estMin']:.0f}분")
        if info["hasText"]:
            print(f"      샘플: {info['sample'][:100]}")

print(f"\n\n{'='*60}\n=== 과목별 요약 (우선순위 순) ===")
for subj in ORDER:
    if subj not in results:
        continue
    ok = [r for r in results[subj] if r.get("hasText")]
    ng = [r for r in results[subj] if not r.get("hasText") and "error" not in r]
    status = "착수가능" if ok else "OCR필요 — 보류"
    print(f"\n[{subj}] {status}")
    for r in ok:
        print(f"   ✓ {r['file']} ({r['pages']}p, 약 {r['estMin']:.0f}분)")
    for r in ng:
        print(f"   ✗ {r['file']} ({r['pages']}p) — 스캔본")
