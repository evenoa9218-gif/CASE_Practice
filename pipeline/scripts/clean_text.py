# -*- coding: utf-8 -*-
"""법률 문서 텍스트 정제기.

출처별로 성격이 다르므로 두 갈래로 처리한다.
  - hwp 추출(문제·채점기준표): 플레이스홀더·공백 정리 위주. 원문 줄바꿈은 대체로 의미가 있음
  - PDF 추출(사례집):        하드랩 병합·머리글 제거가 핵심. 줄바꿈이 조판 산물이라 의미 없음

원칙: 확실한 것만 고친다. 애매하면 그대로 둔다(오교정이 미정제보다 나쁨).
"""
import re
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

# ── 공통 ────────────────────────────────────────────────
ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
FULLWIDTH_SP = re.compile(r"\u3000")

def normalize_ws(t: str) -> str:
    t = ZERO_WIDTH.sub("", t)
    t = FULLWIDTH_SP.sub(" ", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)        # 줄 끝 공백
    t = re.sub(r"[ \t]{2,}", " ", t)        # 연속 공백
    t = re.sub(r"\n{3,}", "\n\n", t)        # 빈 줄 3개+ → 2개
    return t.strip()


# ── hwp 계열 (문제 / 채점기준표) ─────────────────────────
PLACEHOLDER_LINE = re.compile(r"^[ \t]*<(?:표|그림)>[ \t]*$", re.M)
PLACEHOLDER_INLINE = re.compile(r"<(?:표|그림)>")

def clean_hwp(t: str) -> str:
    if not t:
        return t
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = ZERO_WIDTH.sub("", t)
    t = FULLWIDTH_SP.sub(" ", t)

    # 단독 줄 플레이스홀더는 줄째로 제거, 본문 중간이면 표식만 남김
    t = PLACEHOLDER_LINE.sub("", t)
    t = PLACEHOLDER_INLINE.sub("", t)

    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    # 주의: 단일 글자 조사(은/는/이/가…) 앞 공백은 건드리지 않는다.
    #  '있는 이 사건'의 '이'는 관형사라 붙이면 오히려 훼손된다.
    #  hwp 추출본은 띄어쓰기가 대체로 온전하므로 공백 정리만 한다.

    # 괄호 안팎 공백
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)

    return t.strip()


# ── PDF 계열 (사례집 모범답안) ───────────────────────────
# 반복 머리글/꼬리글 후보 (책 제목 등)
RUNNING_HEAD = re.compile(
    r"^\s*(?:\d{4}\s*)?(?:행정법|헌법)\s*사례형\s*연습.*$|"
    r"^\s*제?\s*\d+\s*판\s*[IlI|]?\s*$|"
    r"^\s*[IlI|]\s*$",
    re.M)

PAGE_NUM_LINE = re.compile(r"^\s*\d{1,4}\s*$", re.M)

# 줄이 이어지는지 판단: 종결 부호로 끝나지 않으면 다음 줄과 한 문장일 가능성
TERMINAL = re.compile(r"[.。?!:;、,·)】」』〉>\]]\s*$")
# 새 항목이 시작되는 줄 (병합하면 안 됨)
NEW_ITEM = re.compile(
    r"^\s*(?:"
    r"제\s*\d+\s*[조항호절편장]|"          # 제1조, 제2항
    r"[①-⑳㉑-㉟]|"                        # 원문자
    r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*[.．]|"           # 로마숫자
    r"[가-힣]\s*[.．)]\s|"                 # 가. 나.
    r"\d+\s*[.．)]\s|"                     # 1. 2)
    r"[-–—▶▸■□●○*]|"                      # 불릿
    r"<|\[|【|"                            # 표제
    r"사례\s*\d+|事例\s*\d+"
    r")")

# 고신뢰 OCR 교정 (법률 문서에서 사실상 100% 오인식)
OCR_FIX = [
    (re.compile(r"®"), "①"),
    (re.compile(r"[@⑳](?=\s*제\s*\d)"), "②"),   # ① 다음 항 번호
    (re.compile(r"(?<![가-힣])둥(?![가-힣])"), "등"),   # 독립 어절 '둥' → 등
    (re.compile(r"둥(?=은|을|의|이|과|,|\.|\s)"), "등"),
    (re.compile(r"바율"), "비율"),
    (re.compile(r"^l\.", re.M), "1."),          # 줄머리 소문자 L → 숫자 1
    (re.compile(r"(?<=\s)l\.(?=\s)"), "1."),
    (re.compile(r"(?<=\d)\s*분의\s*(?=\d)"), "분의 "),
]

# 분리된 복합 조사 복원 (다중 글자라 오교정 위험이 낮은 것만)
PARTICLE_FIX = [
    (re.compile(r"(?<=[가-힣]) 에\s*서(?=[\s,.)]|$)"), "에서"),
    (re.compile(r"(?<=[가-힣]) 으로\s*서(?=[\s,.)]|$)"), "으로서"),
    (re.compile(r"(?<=[가-힣]) 에\s*게(?=[\s,.)]|$)"), "에게"),
    (re.compile(r"(?<=[가-힣]) 까\s*지(?=[\s,.)]|$)"), "까지"),
    (re.compile(r"(?<=[가-힣]) 부\s*터(?=[\s,.)]|$)"), "부터"),
    (re.compile(r"(?<=[가-힣]) 하\s*여(?=[\s,.)]|$)"), "하여"),
]

# 사례 헤더 끝에 붙은 페이지번호: '… 설문 2 11 3' → '… 설문 2'
HEADER_PAGENUM = re.compile(
    r"^(\s*(?:사례|事例)\s*\d+\.?\s+.*?설문\s*\d+(?:\s*,\s*\d+)*)\s+[\d\s]{2,}$", re.M)

# 법조문 표기 정규화: '제 1 조' → '제1조'
ART_NUM = re.compile(r"제\s+(\d+)\s*(조|항|호|절|편|장|목)")
ART_NUM2 = re.compile(r"제\s*(\d+)\s+(조|항|호|절|편|장|목)")


def clean_pdf(t: str) -> str:
    if not t:
        return t
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = ZERO_WIDTH.sub("", t)
    t = FULLWIDTH_SP.sub(" ", t)

    # 1) 머리글·페이지번호 제거
    t = RUNNING_HEAD.sub("", t)
    t = PAGE_NUM_LINE.sub("", t)

    # 2) 줄 끝 공백 / 연속 공백
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)

    # 3) 하드랩 병합 — PDF 조판 줄바꿈을 문단으로 복원
    lines = t.split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            continue
        if out and out[-1] and not NEW_ITEM.match(s) and not TERMINAL.search(out[-1]):
            prev = out[-1]
            # 한글끼리 이어질 때 잘린 단어면 공백 없이, 아니면 공백 하나
            if re.search(r"[가-힣]$", prev) and re.match(r"^[가-힣]", s) and len(prev.split()[-1]) <= 2:
                out[-1] = prev + s          # 단어 중간 절단 복원
            else:
                out[-1] = prev + " " + s
        else:
            out.append(s)
    t = "\n".join(out)

    # 4) 조문 표기 정규화
    t = ART_NUM.sub(r"제\1\2", t)
    t = ART_NUM2.sub(r"제\1\2", t)

    # 5) 고신뢰 OCR 교정 + 분리 조사 복원
    for pat, rep in OCR_FIX:
        t = pat.sub(rep, t)
    for pat, rep in PARTICLE_FIX:
        t = pat.sub(rep, t)

    # 5-1) 사례 헤더 끝 페이지번호 제거
    t = HEADER_PAGENUM.sub(r"\1", t)

    # 6) 괄호·문장부호 주변 공백
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    t = re.sub(r"\s+([,.])", r"\1", t)

    # 7) 마무리
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


if __name__ == "__main__":
    import json
    from pathlib import Path
    SRC = WORK / "final" / "공법_사례_full.json"
    data = json.load(open(SRC, encoding="utf-8"))

    def show(title, before, after, n=700):
        print("\n" + "=" * 74)
        print(f"■ {title}")
        print("─" * 74 + "\n[변경 전]")
        print(before[:n])
        print("\n" + "─" * 74 + "\n[변경 후]")
        print(after[:n])

    r = data[0]
    show("문제 (hwp)", r["problemText"], clean_hwp(r["problemText"]))
    show("채점기준표 (hwp)", r["rubricText"], clean_hwp(r["rubricText"]))
    cb = next(b for x in data for b in x["casebookAnswers"])
    show("사례집 모범답안 (PDF)", cb["answerText"], clean_pdf(cb["answerText"]))
