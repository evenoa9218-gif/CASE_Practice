# -*- coding: utf-8 -*-
"""정선균 『행정법 기출해설 바이블』 파싱 — 재OCR본을 쓴다.

원본 PDF에는 텍스트 층이 아예 없었다(이미지만). D 드라이브 판본도 마찬가지라
Windows 내장 OCR로 다시 읽었고, 의심률 0%다.

본문은 `2026년 제15회 변호사시험 제1문의 3`처럼 회차와 문을 함께 단 헤더로
나뉜다. 5급공채·입법고시 등 다른 시험 구간도 있는데, 우리 앱은 변호사시험만
다루므로 변시 헤더만 잡는다.
"""
import json
import re

from paths import CASEBOOK, RAW

SRC = RAW / "사례집" / "행정법" / "정선균_행정법_재OCR.txt"
OUT = CASEBOOK / "jsg_cases.json"
BOOK, AUTHOR = "행정법 기출해설 바이블", "정선균"
MIN_CHARS = 600

HEAD = re.compile(r"(\d{4})\s*년\s*제\s*(\d{1,2})\s*회\s*변호사시험\s*제\s*(\d)\s*문(?:\s*의\s*(\d))?")
PAGE = re.compile(r"^<<<PAGE [^>]*>>>$", re.M)


def main():
    s = PAGE.sub("", SRC.read_text(encoding="utf-8"))

    # 앞쪽 목차에도 `2015년 제4회 변호사시험 제2문의 1` 같은 줄이 그대로 나온다.
    # 본문 표지(`제2편 변호사시험`)가 나온 뒤부터만 본다 - 안 그러면 첫 사례가
    # 쪽번호만 늘어선 목차 조각을 담는다.
    # 표지 문구는 목차에도 나오므로 마지막 등장을 본문 시작으로 삼는다.
    ms = list(re.finditer(r"제\s*2\s*편\s*변호사시험", s))
    if ms:
        s = s[ms[-1].end():]

    marks = []
    for m in HEAD.finditer(s):
        key = (int(m.group(2)), int(m.group(3)), m.group(4))
        if not marks or marks[-1][1] != key:
            marks.append((m.start(), key))
    print(f"구간 {len(marks)}개")

    cases = []
    for i, (pos, (hoi, qno, sub)) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(s)
        seg = re.sub(r"\n{3,}", "\n\n", s[pos:end].strip())
        if len(seg) < MIN_CHARS:
            continue
        label = f"제{hoi}회 변호사시험 제{qno}문" + (f"의 {sub}" if sub else "")
        cases.append({
            "caseNo": f"{hoi}-{qno}" + (f"-{sub}" if sub else ""),
            "title": label,
            "book": BOOK, "author": AUTHOR, "area": "행정법",
            "source": {"kind": "exam", "examId": f"공법_변시_{hoi}회_사례", "label": label},
            "text": seg, "chars": len(seg),
        })

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"사례 {len(cases)} → {len({c['source']['examId'] for c in cases})}회차")


if __name__ == "__main__":
    main()
