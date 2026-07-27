# -*- coding: utf-8 -*-
"""PDF → txt 자동 변환.

사용법:
    python pdf2txt.py <폴더 또는 파일> [...]

동작:
  - 텍스트층이 있는 PDF: 자동 추출 → 원본 옆에 같은 이름 .txt 생성
  - 스캔본(텍스트 없음): 건너뛰고 need_ocr.txt 목록에 기록
  - 이미 .txt가 있으면 건너뜀 (재실행 안전)
  - 페이지 단위로 진행상황 로그 → 중단돼도 어디까지 됐는지 확인 가능
"""
import sys
import time
from pathlib import Path
from pypdf import PdfReader
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
NEED_OCR_LOG = SCRATCH / "need_ocr.txt"

SAMPLE_PAGES = 3        # 텍스트층 판별용 샘플
MIN_CHARS = 50          # 이 미만이면 스캔본으로 간주


def has_text_layer(reader: PdfReader) -> bool:
    n = min(SAMPLE_PAGES, len(reader.pages))
    sample = ""
    for i in range(n):
        try:
            sample += reader.pages[i].extract_text() or ""
        except Exception:
            pass
    # 앞쪽이 표지라 비어있을 수 있어 중간 페이지도 확인
    if len(sample.strip()) < MIN_CHARS and len(reader.pages) > 10:
        mid = len(reader.pages) // 2
        for i in range(mid, min(mid + SAMPLE_PAGES, len(reader.pages))):
            try:
                sample += reader.pages[i].extract_text() or ""
            except Exception:
                pass
    return len(sample.strip()) >= MIN_CHARS


def convert(pdf: Path) -> str:
    out = pdf.with_suffix(".txt")
    if out.exists():
        return "skip_exists"
    try:
        reader = PdfReader(str(pdf))
    except Exception as e:
        print(f"  [열기실패] {pdf.name}: {type(e).__name__}")
        return "fail_open"

    if not has_text_layer(reader):
        print(f"  [스캔본] {pdf.name} ({len(reader.pages)}p) → OCR 필요")
        with open(NEED_OCR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{pdf}\n")
        return "need_ocr"

    n = len(reader.pages)
    t0 = time.time()
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
        if n > 100 and (i + 1) % 100 == 0:
            el = time.time() - t0
            print(f"    {pdf.name}: {i+1}/{n}p ({el:.0f}초, 남은시간 약 {el/(i+1)*(n-i-1)/60:.1f}분)",
                  flush=True)
    text = "\n".join(parts)
    out.write_text(text, encoding="utf-8")
    dt = time.time() - t0
    print(f"  [완료] {pdf.name}: {n}p, {len(text):,}자, {dt/60:.1f}분", flush=True)
    return "ok"


def main():
    targets = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.pdf")))
        elif p.suffix.lower() == ".pdf":
            targets.append(p)

    if not targets:
        print("대상 PDF 없음. 사용법: python pdf2txt.py <폴더|파일>")
        return

    print(f"대상 {len(targets)}개 PDF\n")
    stats = {}
    for pdf in targets:
        r = convert(pdf)
        stats[r] = stats.get(r, 0) + 1

    print("\n=== 요약 ===")
    labels = {"ok": "변환 완료", "skip_exists": "이미 존재",
              "need_ocr": "스캔본(OCR 필요)", "fail_open": "열기 실패"}
    for k, v in stats.items():
        print(f"  {labels.get(k, k)}: {v}")
    if stats.get("need_ocr"):
        print(f"\nOCR 필요 목록: {NEED_OCR_LOG}")


if __name__ == "__main__":
    main()
