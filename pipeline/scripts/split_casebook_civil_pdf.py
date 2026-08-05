# -*- coding: utf-8 -*-
"""민사법 사례집(정연석) 파싱 — PDF 쪽 꼬리말에서 회차를 읽는다.

기존 split_casebook_civil.py는 OCR된 txt에서 '2025년 06모' 같은 **단독 줄**을
회차 헤더로 삼았다. 그런데 OCR이 연도와 월을 자주 뭉갠다 — '2이9년', '08E',
'10S', '모' 대신 'E/S/몬'. 그래서 55회차 중 25개만 잡히고 30개를 놓쳤다.

여기서는 PDF에서 쪽마다 꼬리말을 읽어 회차를 정한다. 꼬리말은 판형이 일정해
OCR이 흔들려도 느슨한 정규식으로 잡힌다. 한두 쪽이 튀는 것은 앞뒤 쪽의
회차로 메운다(구간은 이어져 있다).

모의고사 월 → 차수: 법전협 모의는 매년 6·8·10월 3회이므로 06→1차, 08→2차,
10→3차. 기존 스크립트와 같은 규약이다.
"""
import json
import re
from collections import Counter

import fitz

from paths import CASEBOOK, RAW

PDF = RAW / "사례집" / "민법" / "2026_06_정연석_로스쿨_민사_사례형_기출문제집_해설편.pdf"
OUT = CASEBOOK / "civil_casebook_blocks.json"

BOOK = "로스쿨 민사 사례형 기출문제집[해설편]"
AUTHOR = "정연석"

# OCR이 '모'를 E/S/몬/므로, '0'을 '이'로 자주 바꾼다. 느슨하게 받는다.
MOCK = re.compile(r"(20[0-9]{2}|2이[0-9]|20[0-9])\s*년\s*([01]?\d)\s*[모ES몬므]")
BAR = re.compile(r"제?\s*(\d{1,2})\s*[회히]\s*변시")
CASE_ANY = re.compile(r"제\s*(\d+)\s*문(?:\s*의\s*(\d+))?")
MONTH_TO_ROUND = {6: 1, 8: 2, 10: 3}


def fix_year(y):
    y = y.replace("이", "0")
    return int(y) if len(y) == 4 else None


def page_round(text):
    """쪽 꼬리말 4줄에서 회차를 읽는다."""
    tail = "\n".join([l.strip() for l in text.split("\n") if l.strip()][-4:])
    m = MOCK.search(tail)
    if m:
        y, mm = fix_year(m.group(1)), int(m.group(2))
        if y and mm in MONTH_TO_ROUND:
            return ("모의고사", y, MONTH_TO_ROUND[mm])
    m = BAR.search(tail)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 20:
            return ("변시", n, None)
    return None


def smooth(rounds):
    """표시가 없는 쪽을 앞뒤로 메운다. 구간은 끊기지 않는다는 전제다."""
    out = list(rounds)
    for i, v in enumerate(out):
        if v is not None:
            continue
        prev = next((out[j] for j in range(i - 1, -1, -1) if out[j]), None)
        nxt = next((out[j] for j in range(i + 1, len(out)) if out[j]), None)
        out[i] = prev if prev == nxt else None   # 경계가 애매하면 비워 둔다
    return out


def exam_id(kind, a, b):
    return f"민사법_변시_{a}회_사례" if kind == "변시" else f"민사법_모의_{a}_{b}차_사례"


def main():
    doc = fitz.open(PDF)
    # 이 책의 원래 텍스트 층은 당사자 표기가 47% 깨져 있다(甲乙丙 → 己江心因內).
    # 누가 누구인지 뒤섞이면 사례로 못 쓰므로, Windows 내장 OCR로 다시 읽은
    # 본문(의심률 0%)을 쪽 단위로 갈아 끼운다. 회차 판정에 쓰는 꼬리말은 그대로다.
    reocr = PDF.parent / "정연석_해설편_재OCR.txt"
    if reocr.exists():
        parts = re.split(r"^<<<PAGE p(\d+)>>>$", reocr.read_text(encoding="utf-8"), flags=re.M)
        page_text = {}
        for i in range(1, len(parts) - 1, 2):
            page_text[int(parts[i])] = parts[i + 1]
        texts = [page_text.get(i, doc[i].get_text()) for i in range(doc.page_count)]
        print(f"재OCR 본문 사용 {len(page_text)}쪽")
    else:
        texts = [doc[i].get_text() for i in range(doc.page_count)]
    raw = [page_round(t) for t in texts]
    rounds = smooth(raw)

    # 같은 회차가 이어지는 구간으로 묶는다
    spans, cur, start = [], None, 0
    for i, v in enumerate(rounds + [None]):
        if v != cur:
            if cur is not None and i - start >= 2:      # 한 쪽짜리는 목차 잔재로 본다
                spans.append((cur, start, i - 1))
            cur, start = v, i
    print(f"회차 구간 {len(spans)}개")

    blocks = []
    for (kind, a, b), s, e in spans:
        eid = exam_id(kind, a, b)
        body = "\n".join(texts[s:e + 1])
        # 재OCR 본문은 줄바꿈이 원본과 달라 라벨이 줄머리에 오지 않는다.
        # 그래서 줄 단위가 아니라 본문 전체에서 라벨 위치를 찾아 자른다.
        flat = " ".join(l.strip() for l in body.split("\n") if l.strip())
        marks = [(m.start(), m.group(0), m.group(1), m.group(2) or "1")
                 for m in CASE_ANY.finditer(flat)]
        # 같은 라벨이 쪽머리로 되풀이되므로 바뀌는 첫 지점만 남긴다
        keep = []
        for mk in marks:
            if not keep or (keep[-1][2], keep[-1][3]) != (mk[2], mk[3]):
                keep.append(mk)
        for i, (pos, lab, qno, subno) in enumerate(keep):
            end = keep[i + 1][0] if i + 1 < len(keep) else len(flat)
            txt = flat[pos:end].strip()
            if len(txt) < 300:                      # 목차·요약 조각은 버린다
                continue
            blocks.append({
                "examId": eid, "label": lab.strip(),
                "qno": qno, "subno": subno,
                "book": BOOK, "author": AUTHOR, "area": "민사법",
                "answerText": txt, "chars": len(txt),
            })

    OUT.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
    c = Counter(b["examId"] for b in blocks)
    print(f"블록 {len(blocks)}개 / 회차 {len(c)}개 → {OUT}")


if __name__ == "__main__":
    main()
