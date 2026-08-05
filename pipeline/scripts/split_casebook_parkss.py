# -*- coding: utf-8 -*-
"""박승수 『민민소 사례 CBT실전답안』 파싱 — 재OCR본을 쓴다.

원본 PDF에는 텍스트 층이 아예 없었다(이미지만). Windows 내장 OCR로 다시 읽어
`박승수_민민소_재OCR.txt`를 만들어 두었고, 이 파일이 입력이다.

쪽머리가 `2026년 제15회 변호사시험 [제1문 해설]`처럼 회차와 문을 함께 달고
반복된다. 그 값이 바뀌는 지점을 경계로 자른다.

변시 1~16회만 다루고 모의고사는 없다. 정연석 책이 이미 53/55 회차를 덮고
있으므로, 이 책은 '실전 답안 형식'을 보는 두 번째 자료로 쓴다.
"""
import json
import re

from paths import CASEBOOK, RAW

SRC = RAW / "사례집" / "민사소송법" / "박승수_민민소_재OCR.txt"
OUT = CASEBOOK / "parkss_cases.json"
BOOK, AUTHOR = "민민소 사례 CBT실전답안", "박승수"
MIN_CHARS = 500

HEAD = re.compile(r"(\d{4})\s*년\s*제\s*(\d{1,2})\s*회\s*변호사시험\s*\[\s*제\s*(\d)\s*문[^\]]{0,10}\]")
PAGE = re.compile(r"^<<<PAGE [^>]*>>>$", re.M)


def main():
    s = PAGE.sub("", SRC.read_text(encoding="utf-8"))

    # 쪽머리가 되풀이되므로, (회차, 문)이 바뀌는 첫 지점만 경계로 삼는다
    marks = []
    for m in HEAD.finditer(s):
        key = (int(m.group(2)), int(m.group(3)))
        if not marks or marks[-1][1] != key:
            marks.append((m.start(), key))
    print(f"구간 {len(marks)}개")

    cases = []
    for i, (pos, (hoi, qno)) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(s)
        seg = re.sub(r"\n{3,}", "\n\n", s[pos:end].strip())
        if len(seg) < MIN_CHARS:
            continue
        cases.append({
            "caseNo": f"{hoi}-{qno}",
            "title": f"제{hoi}회 제{qno}문",
            "book": BOOK, "author": AUTHOR, "area": "민법·민사소송법",
            "source": {"kind": "exam", "examId": f"민사법_변시_{hoi}회_사례",
                       "label": f"제{hoi}회 변호사시험 제{qno}문"},
            "text": seg, "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"사례 {len(cases)} → {len({c['source']['examId'] for c in cases})}회차")


if __name__ == "__main__":
    main()
