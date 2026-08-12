# -*- coding: utf-8 -*-
r"""박승수 「민법 기본사례」(2025) 지문 정제 — 2차.

`parkss_ocr_fixes.py`(당사자 기호)·`parkss_body_fixes.py`(낱말 오인식)에 이어,
**화면에 드러나는 세 가지 흠**을 고친다. 2026-08-13.

1. **금액 숫자 파손** — OCR 이 `000` 을 `(XX)` 로 읽었다. 10개 사례에서 났다.
   전부 지면 이미지를 잘라 확대해 1:1 대조했다(아래 표). 추론으로 넣은 것은 없다.
   ⚠ 사례 149 는 `1(X)0만` 인데 **`100만`이 아니라 `1000만`**이다(책에 쉼표가 없다).
   문맥으로 짐작했으면 틀렸을 자리다.

2. **문장 중간 줄바꿈** — PDF 줄바꿈이 그대로 남아 `…충당하기로 합의\n하였다.` 처럼
   문장이 끊긴다. 286개 중 222개에 있다. 앞줄이 종결부호로 끝나지 않고 뒷줄이
   설문 번호·머리표가 아닐 때만 잇는다.

3. **설문이 답안 앞머리로 밀림** — 지문이 `(1)` 에서 잘리고 `(2)(3)` 이 답안 첫머리로
   넘어간 사례가 있다. ⚠ **답안 앞의 `(1)` 이 전부 설문인 것은 아니다** — 사례 1·16
   처럼 답안 목차 번호인 경우가 훨씬 많다. 그래서 «지문의 마지막 설문 번호 + 1» 로
   이어질 때만 되돌린다.

| 사례 | OCR | 지면(책쪽/PDF쪽) | 확정 |
|---|---|---|---|
| 40 | `의류 1,(XX)벌` | 131 / 157 | `의류 1,000벌` |
| 50 | `1,(XX)만 원` | 156 / 182 | `1,000만 원` |
| 78 | `40,000,(XX)원` · `20,(XX),000원` | 232 / 258 | `40,000,000원` · `20,000,000원` |
| 96 | `1,(XX)만 원` | 266 / 292 | `1,000만 원` |
| 113 | `3,(XX)만 원` | 304 / 331 | `3,000만 원` |
| 149 | `1(X)0만 원` | 399 / 425 | **`1000만 원`** |
| 157 | `7,(XX)만 원` | 427 / 453 | `7,000만 원` |
| 162 | `7,(XX)만원` | 440 / 466 | `7,000만원` |
| 248 | `5,(XX)만 원` | 707 / 733 | `5,000만 원` |
| 259 | `50,000,(XW` | 737 / 765 | `50,000,000원(` |
"""
import re

# ── 1. 금액 ──────────────────────────────────────────────
# 숫자 사이에 낀 (XX)·(XW 만 바꾼다. 괄호 안 X 가 글자로 쓰인 곳(X토지·X주택)은
# 앞뒤가 숫자가 아니라 걸리지 않는다.
NUM_XX = re.compile(r"(?<=[\d,])\(\s*X\s*X\s*\)")          # 1,(XX) → 1,000
NUM_XW = re.compile(r"(?<=[\d,])\(\s*X\s*W(?=\S)")          # 50,000,(XW → …000원(
NUM_1X0 = re.compile(r"(?<![\d,])1\(\s*X\s*\)0(?=\s*만)")   # 1(X)0만 → 1000만


DASH_ONE = re.compile(r"(?<=\s)一(?=\s)")   # `함 一 를 작성하였다` → 줄표


def fix_numbers(s):
    s = DASH_ONE.sub("—", s)
    s = NUM_XX.sub("000", s)
    s = NUM_XW.sub("000원(", s)
    s = NUM_1X0.sub("1000", s)
    return s


# ── 2. 문장 중간 줄바꿈 ─────────────────────────────────
# 뒷줄이 이것으로 시작하면 새 줄이다 — 이으면 안 된다.
LINE_START = re.compile(
    r"^\s*(?:[(（]\s*\d+\s*[)）]"          # (1) （2）
    r"|[⑴-⒇①-⑩㉠-㉭]"                    # ⑴ ① ㉠
    r"|\d+\s*[.)]"                        # 1. 2)
    r"|[〈<【\[※□■◇▶*]"                  # 〈사실관계〉 ※ [문제]
    # 목차 「가. 나. 다.」 — 뒤에 내용이 붙어 있을 때만 목차다.
    # `…증명되었\n다.` 의 `다.` 를 목차로 오인하면 문장을 못 잇는다.
    # 마침표 뒤에 «공백»이 있어야 목차다. `인정된\n다.1)` 의 `다.1)` 은 이어지는 문장이다.
    r"|[가나다라마]\s*\.\s+\S{0,20}$"
    r"|[IVXivx]+\s*\.\s*\S)"              # I. II.
)
# 앞줄이 이것으로 끝나면 문장이 끝난 것이다.
# ⚠ 맨 `다`를 종결로 보면 안 된다 — `지표면보다\n약 1m` 처럼 조사 `보다`가 걸린다.
LINE_END = re.compile(r"[.。!?！？\"'」』〉\)）]\s*$")


def join_wrapped(text):
    """PDF 줄바꿈으로 끊긴 문장을 잇는다. 설문·머리표 줄은 건드리지 않는다."""
    if not text:
        return text
    lines = text.split("\n")
    out = []
    for ln in lines:
        if (out and out[-1].strip() and ln.strip()
                and not LINE_END.search(out[-1])
                and not LINE_START.match(ln)):
            # 한글·숫자로 이어질 때만 — 표나 기호 줄은 그대로 둔다
            if re.match(r"^[가-힣0-9A-Za-z(（]", ln.strip()):
                sep = "" if re.search(r"[가-힣]$", out[-1]) and re.match(r"^[가-힣]", ln.strip()) else " "
                out[-1] = out[-1].rstrip() + sep + ln.strip()
                continue
        out.append(ln)
    return "\n".join(out)


# ── 3. 답안 앞머리로 밀린 설문 되돌리기 ────────────────
QNUM = re.compile(r"^\s*(?:[(（]\s*(\d+)\s*[)）]|([⑴-⑽]))")
CIRCLE = {"⑴": 1, "⑵": 2, "⑶": 3, "⑷": 4, "⑸": 5,
          "⑹": 6, "⑺": 7, "⑻": 8, "⑼": 9, "⑽": 10}


def _qnum(line):
    m = QNUM.match(line)
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else CIRCLE.get(m.group(2))


# 설문의 끝. OCR 이 물음표를 `〒*` 따위로 깨뜨리므로 끝에서 조금 물러나 찾는다.
Q_TERM = re.compile(r"(?:하시오|하십시오|하라|답하라|논하|서술|설명|검토|판단|평가|적시|밝히"
                    r"|하는가|있는가|되는가|인가|드는가|것인가|\?|？|는지)")
# 설문 끝의 각주 번호·배점 표시. 물음 문장을 뽑기 전에 떼어낸다.
# ⚠ `※`·`*` 로 시작하는 꼬리를 통째로 자르면 안 된다 — 설문 문장 자체가 `* 甲에 대하여…`
# 로 시작하는 사례가 있어 물음이 통째로 날아갔다(사례 92).
TAIL_JUNK = re.compile(r"(?:\s*[(（]\s*\d+\s*점\s*[)）]|\s*\d\))+\s*$")
MAX_Q_LINES = 12
# 답안이 시작되는 표지. 여기서 끊지 않으면 답안 본문이 딸려온다(사례 15).
ANS_HEAD = re.compile(r"^\s*(?:\[설문|【설문|논점의?\s*정리|[IVXⅠ-Ⅹ]{1,4}\s*[.．]"
                      r"|[가나다라마]\s*[.．]|①|②|③|판례는|사안의\s*경우)")


def _has_question(block):
    return bool(Q_TERM.search(block))


def last_question_no(problem):
    """지문에 실제로 쓰인 마지막 설문 번호."""
    last = None
    for ln in (problem or "").split("\n"):
        n = _qnum(ln)
        if n is not None and (last is None or n == last + 1 or n > last):
            last = n
    return last


def pull_back_questions(problem, answer):
    """답안 첫머리가 «지문의 마지막 설문 + 1» 로 이어지면 그만큼 지문으로 옮긴다.

    답안 목차 번호와 구별하는 유일한 근거가 «번호의 연속»이다. 사례 1 처럼
    지문에 설문 번호가 아예 없으면 아무것도 옮기지 않는다."""
    last = last_question_no(problem)
    if last is None:
        return problem, answer, 0
    lines = (answer or "").split("\n")
    moved, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        n = _qnum(lines[i])
        if n != last + 1:
            break
        # 설문은 «묻는 말»로 끝난다. 그 종결이 나올 때까지만 덩어리로 잡는다.
        # 이걸 안 걸면 뒤따르는 답안 본문까지 통째로 딸려온다(사례 15에서 실제로 났다).
        blk, j = [lines[i]], i + 1
        while j < len(lines) and len(blk) < MAX_Q_LINES:
            if not lines[j].strip():
                j += 1
                continue
            if _qnum(lines[j]) is not None or ANS_HEAD.match(lines[j]):
                break
            blk.append(lines[j])
            j += 1
        if not _has_question("\n".join(blk)):
            break                       # 묻는 말이 없으면 설문이 아니다 — 옮기지 않는다
        moved.append("\n".join(blk))
        last = n
        i = j
    if not moved:
        return problem, answer, 0
    problem = (problem or "").rstrip() + "\n" + "\n".join(moved)
    answer = "\n".join(lines[i:]).lstrip("\n")
    return problem, answer, len(moved)


# ── 4. 설문 쪼개기 (build 단계에서 ask 를 채우는 데 쓴다) ──
def split_questions(problem):
    """지문을 «사실관계» + «설문 목록» 으로 가른다.

    반환 (fact, [(번호, 설문문장), …]). 설문 번호가 없으면 ([], 통짜)로 둔다 —
    없는 설문을 지어내지 않는다."""
    lines = (problem or "").split("\n")
    idx = [i for i, ln in enumerate(lines) if _qnum(ln) is not None]
    if not idx:
        return problem, []
    # 번호가 1부터 이어져야 설문으로 인정한다 (답안 목차 번호 오인 방지)
    nums = [_qnum(lines[i]) for i in idx]
    if nums[0] != 1:
        return problem, []
    fact = "\n".join(lines[:idx[0]]).rstrip()
    qs = []
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        body = "\n".join(lines[i:end]).strip()
        body = QNUM.sub("", body, count=1).strip()
        qs.append((nums[k], body))
    return fact, qs


def tail_question(problem):
    """설문 번호가 없는 사례에서 «묻는 문장» 하나를 뽑는다.

    이 책은 286개 중 다수가 `…논하시오.` 한 문장으로 끝난다. 그 문장이 곧 설문이다.
    못 찾으면 빈 문자열 — **없는 설문을 지어내지 않는다.**"""
    t = TAIL_JUNK.sub("", (problem or "").strip())
    if not t:
        return ""
    # `〈문제〉` 머리표 뒤가 곧 설문이다 — 있으면 거기서부터 본다
    m = re.search(r"[〈<(（]\s*문\s*[제저][〉>)）,、]?\s*", t)
    if m:
        t = t[m.end():]
    sents = [s.strip() for s in re.split(r"(?<=[.。?!？！])\s+", t.replace("\n", " ")) if s.strip()]
    for s in reversed(sents):
        if Q_TERM.search(s):
            return TAIL_JUNK.sub("", s).strip()
    # 묻는 말을 못 찾았어도 `〈문제〉` 뒤를 잘라 왔다면 그게 설문이다.
    # 지문이 문장 도중에 잘린 사례(34번 `…소를 제기한 경우,`)라도 번호만 띄우는 것보다 낫다.
    if m and t.strip():
        return TAIL_JUNK.sub("", t.replace("\n", " ")).strip()
    return ""


def apply(problem, answer):
    """지문·답안에 위 1~3을 한 번에 적용한다. 여러 번 돌려도 결과가 같다."""
    problem = join_wrapped(fix_numbers(problem or ""))
    answer = fix_numbers(answer or "")
    problem, answer, n = pull_back_questions(problem, answer)
    if n:
        problem = join_wrapped(problem)
    return problem, answer, n
