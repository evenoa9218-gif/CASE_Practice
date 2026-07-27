# -*- coding: utf-8 -*-
"""사례집 PDF 텍스트 추출 가능성 테스트 (텍스트 PDF vs 스캔본 판별)."""
import time
from pathlib import Path
from pypdf import PdfReader
from paths import PDF_ROOT   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

TARGETS = [
    str(PDF_ROOT / "pdf" / "헌법" / "[강성민] Signature 공법기록2 해설편 (2026.04).pdf"),
    str(PDF_ROOT / "pdf" / "[조균석] 형사법 사례형 해설 (2026.04).pdf"),
    str(PDF_ROOT / "pdf" / "상법" / "OCR_인사이트 상법 사례형 해설편(2026).pdf"),
]

for p in TARGETS:
    path = Path(p)
    print("=" * 70)
    print(path.name)
    if not path.exists():
        print("  파일 없음")
        continue
    size_mb = path.stat().st_size / 1024 / 1024
    try:
        t0 = time.time()
        reader = PdfReader(str(path))
        n = len(reader.pages)
        # 앞 3페이지만 샘플 추출해 속도/품질 측정
        sample = ""
        for i in range(min(3, n)):
            sample += reader.pages[i].extract_text() or ""
        dt = time.time() - t0
        per_page = dt / max(1, min(3, n))
        print(f"  크기 {size_mb:.1f}MB, {n}페이지")
        print(f"  샘플3p 추출 {dt:.2f}초 (페이지당 {per_page:.2f}초) → 전체 예상 {per_page*n/60:.1f}분")
        print(f"  추출 문자수(3p): {len(sample)}")
        if len(sample.strip()) < 50:
            print("  ⚠ 텍스트 거의 없음 → 스캔본(이미지) 가능성, OCR 필요")
        else:
            print("  ✓ 텍스트 PDF — 추출 가능")
            print("  --- 샘플 ---")
            print("  " + sample[:400].replace("\n", "\n  "))
    except Exception as e:
        print(f"  실패: {type(e).__name__}: {e}")
    print()
