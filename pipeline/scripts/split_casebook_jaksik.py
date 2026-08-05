# -*- coding: utf-8 -*-
"""작은변사기 형사소송법 파싱 — 재OCR본을 쓴다.

원본 PDF의 텍스트 층은 판독이 불가능했다(`례곧빠대(）j2색느몸`). D 드라이브
판본도 당사자 표기가 34% 깨져 있어 못 쓴다. Windows 내장 OCR로 다시 읽은
`작은변사기_형소_재OCR.txt`가 입력이며, 의심률 0%다.

`[사례 16] 변호인의 피의자신문 참여권과 ...` 형태가 사례 단위다.
출처(변시/모의) 표기는 없다 — 주제별 요약 사례집이라 목록으로만 쓴다.
"""
import json
import re

from paths import CASEBOOK, RAW

SRC = RAW / "사례집" / "형사소송법" / "작은변사기_형소_재OCR.txt"
OUT = CASEBOOK / "jaksik_cases.json"
BOOK, AUTHOR = "작은변사기 형사소송법", "작은변사기"
MIN_CHARS = 300

HEAD = re.compile(r"\[\s*사례\s*(\d{1,3})\s*\]\s*([^\n\[]{2,60})")
PAGE = re.compile(r"^<<<PAGE [^>]*>>>$", re.M)


def main():
    s = PAGE.sub("", SRC.read_text(encoding="utf-8"))
    heads = list(HEAD.finditer(s))
    print(f"사례 헤더 {len(heads)}개")

    # 쪽머리에 같은 사례 표시가 되풀이된다. 번호가 바뀌는 첫 지점만 경계로 삼는다.
    # 앞서 '이미 본 번호는 건너뛴다'로 짰더니, 뒤에서 번호가 되돌아올 때 구간이
    # 문서 끝까지 늘어나 130개 중 21개만 남았다.
    marks = []
    for m in heads:
        no = int(m.group(1))
        if not marks or marks[-1][1] != no:
            marks.append((m, no))

    cases = []
    for i, (m, no) in enumerate(marks):
        nxt = marks[i + 1][0].start() if i + 1 < len(marks) else len(s)
        seg = re.sub(r"\n{3,}", "\n\n", s[m.start():nxt].strip())
        if len(seg) < MIN_CHARS:
            continue
        cases.append({
            "caseNo": str(no),
            "title": re.sub(r"\s+", " ", m.group(2)).strip()[:60],
            "book": BOOK, "author": AUTHOR, "area": "형사소송법",
            "source": {"kind": "unlabeled", "examId": None, "label": "출처 미표기"},
            "text": seg, "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"사례 {len(cases)}개 → {OUT}")


if __name__ == "__main__":
    main()
