# -*- coding: utf-8 -*-
r"""로사정(정연석 「로스쿨 사례의 정석」 26.02) 사례 텍스트 → 구조화.

입력은 `extract_rosajeong.py`가 만든 사례별 txt(=`ROSAJEONG_CASES` 폴더).
출력은 CASE_Practice exam 스키마에 그대로 넣을 수 있는 dict.

책의 한 사례는 이런 모양이다:

    채무불이행, 손해배상          ← 러닝헤더(제거)
    핵심사례 003
    최신판례 신작문제              ← 있을 때만
    〈기초적 사실관계〉
    …
    〈문제 1〉
    …(15점)
    ※ 이자·지연손해는 논외로 함
    최고답안 003
    〈문제 1〉
    (15점)
    1. 문제점
    …
    15 대법원 2002. 7. 12. 선고 2001다44338 판결   ← 각주

각주는 본문 흐름 사이사이 페이지 하단에 끼어 있어, 줄 단위로 걷어내
답안 끝에 「각주」로 모아 붙인다. 판례번호 각주와 해설 각주가 섞여 있는데
둘 다 채점에 쓸모가 있어 구분하지 않고 보존한다.
"""
import re

from reflow_rosajeong import reflow

# 〈문제 3〉 · 〈문제3〉 · 〈문제 1, 2〉 — 책이 두 표기를 섞어 쓴다
Q_RE = re.compile(r"^[〈<]\s*문제\s*([0-9]+(?:\s*,\s*[0-9]+)*)?\s*[〉>]", re.M)
# 〈기초적 사실관계〉 · 〈공통적 사실관계〉 · 〈추가적 사실관계 2〉
FACT_RE = re.compile(r"^[〈<]\s*(기초적|공통적|추가적)\s*사실관계\s*[0-9]*\s*[〉>]", re.M)
ANS_RE = re.compile(r"^최고답안\s*([0-9]{1,3}(?:-[0-9])?)\s*$", re.M)
HEAD_RE = re.compile(r"^핵심(?:사례|시려I)\s*([0-9]{1,3}(?:-[0-9])?)\s*$", re.M)
PAGE_RE = re.compile(r"^\[p\.\d+\]$", re.M)
PTS_RE = re.compile(r"\((\d{1,3})\s*점\)")
# 각주: 줄 첫머리 번호 + 공백 + 내용. 본문 목차("1. 문제점")와 달리 마침표가 없다.
FOOT_RE = re.compile(r"^(\d{1,3})\s+(?=[^\s.)])")
# 사례 머리의 출처 꼬리표 — "신작문제", "16년 변호사시험 유사", "최신판례 신작문제" 등
TAG_RE = re.compile(r"^(?=.*(?:신작문제|유사|변형|기출))[^\n]{2,40}$")


def _strip_pages(t):
    return PAGE_RE.sub("", t)


def _is_next(n, last):
    """`n`이 각주 연번으로 이어질 수 있는 값인가.

    번호는 PART가 바뀔 때 1로 되돌아가므로 `last + 1`만 인정하면 사슬이 끊긴다.
    한편 조건을 아예 없애면 본문의 숫자 시작 줄을 각주로 오인해 그 쪽 나머지를 통째로 잃는다.
    증가(또는 PART 경계에서의 리셋)까지만 허용하는 선에서 절충했다.
    """
    if last is None:
        return n <= 5
    return n > last or (n <= 3 and last > 50)


def split_footnotes(pages, first_no=None):
    """쪽별로 본문과 각주를 가른다. 각주는 (번호, 텍스트) 리스트.

    **각주는 언제나 그 쪽의 맨 아래에 모여 있다.** 그래서 한 쪽 안에서 각주가 시작되면
    그 쪽 나머지는 전부 각주다. 쪽 경계를 무시하고 줄 단위로만 판단하면, 각주 다음
    쪽의 본문이 각주에 딸려 들어가 답안이 통째로 잘린다(실제로 7개 사례가 그랬다).

    각주 번호는 책 전체를 관통해 1씩 증가한다. 이 단조성으로 본문에 우연히 나온
    숫자 시작 줄과 진짜 각주를 가른다.
    """
    body, foot, last = [], [], first_no
    body_wrap = []
    for entry in pages:
        page = entry[1]
        wr = entry[2] if len(entry) > 2 else ""
        lines = page.split("\n")
        wr = (wr + "0" * len(lines))[:len(lines)]
        hits = [(i, int(m.group(1)))
                for i, ln in enumerate(lines) if (m := FOOT_RE.match(ln))]
        start = _block_start(hits, last, len(lines))
        if start is None:
            body += lines
            body_wrap += list(wr)
            continue
        body += lines[:start]
        body_wrap += list(wr[:start])
        cur = None
        for ln in lines[start:]:
            m = FOOT_RE.match(ln)
            if m and (last is None or int(m.group(1)) > last or _is_next(int(m.group(1)), last)):
                cur = [m.group(1), ln[m.end():].strip()]
                foot.append(cur)
                last = int(m.group(1))
            elif cur is not None and ln.strip():
                cur[1] += " " + ln.strip()
    return body, body_wrap, foot, last


def _block_start(hits, last, nlines):
    """한 쪽의 각주 블록이 시작되는 줄 번호.

    각주 블록은 쪽의 꼬리에 붙고 번호가 1씩 오른다. 그래서 **맨 끝 각주에서 위로 거슬러
    올라가며 번호가 1씩 줄어드는 구간**이 곧 블록이다. 이렇게 잡으면 본문에 우연히
    숫자로 시작하는 줄이 있어도 (앞뒤 번호와 이어지지 않으므로) 블록에 끌려 들어가지 않는다.

    쪽에 각주가 하나뿐이면 이 검증이 힘을 못 쓴다. 그때는 직전 쪽까지의 연번과 이어지는지,
    그리고 **쪽의 아래쪽에 있는지**를 함께 본다. 본문 중간의 `2 대금채권을…` 같은 줄이
    PART 경계의 번호 리셋으로 오인돼 그 쪽 나머지(최고답안 표지 포함)를 통째로 삼킨 적이 있다.
    """
    if not hits:
        return None
    start_i, expect = hits[-1]
    for i, n in reversed(hits[:-1]):
        if n == expect - 1:
            start_i, expect = i, n
        elif n >= expect:
            continue          # 각주 본문 안에 인용된 숫자 — 건너뛴다
        else:
            break
    if start_i == hits[-1][0]:
        if not _is_next(hits[-1][1], last) or start_i < nlines * 0.5:
            return None       # 단독 후보인데 연번이 안 맞거나 쪽 위쪽이다 → 각주가 아니다
    return start_i


def parse_case(case, first_no=None, vocab=None):
    """`rosajeong_cases.json`의 사례 하나 → {problemText, answerText, footnotes, questions}

    `first_no`는 직전 사례까지 읽은 마지막 각주 번호다. 각주 연번이 책 전체를 관통하므로
    이걸 이어서 넘겨줘야 본문의 숫자 시작 줄을 각주로 오인하지 않는다.
    반환값의 `lastFootnote`를 다음 사례에 그대로 넘기면 된다.

    `vocab`을 주면 조판 줄바꿈을 문단으로 되돌린다(`reflow_rosajeong`).
    """
    no = case["no"]
    lines, wraps, foot, last = split_footnotes(case["pages"], first_no)

    cut = next((i for i, ln in enumerate(lines) if ANS_RE.match(ln)), None)
    if cut is None:
        raise ValueError(f"{no}: 최고답안 표지를 찾지 못했다")
    pl, pw = lines[:cut], wraps[:cut]
    al, aw = lines[cut + 1:], wraps[cut + 1:]

    # 문제부 머리 정리 — 러닝헤더·핵심사례 표지·출처 꼬리표를 걷어낸다
    hi = next((i for i, ln in enumerate(pl) if HEAD_RE.match(ln)), None)
    if hi is not None:
        pl, pw = pl[hi + 1:], pw[hi + 1:]
    head_lines, keep = [], []
    started = False
    for i, ln in enumerate(pl):
        if not started:
            if FACT_RE.match(ln) or Q_RE.match(ln):
                started = True
            elif ln.strip() and TAG_RE.match(ln.strip()):
                head_lines.append(ln.strip())
                continue
            elif not ln.strip():
                continue
        keep.append(i)
    pl, pw = [pl[i] for i in keep], [pw[i] for i in keep]
    tag = " · ".join(head_lines)

    if vocab is None:
        prob, ans = "\n".join(pl).strip(), "\n".join(al).strip()
    else:
        prob = reflow(pl, [w == "1" for w in pw], vocab).strip()
        ans = reflow(al, [w == "1" for w in aw], vocab).strip()

    # 설문 번호와 배점 — 답안부의 〈문제 N〉 (N점) 이 가장 정확하다.
    # 배점이 표지 '뒤'가 아니라 '앞'에 오는 사례가 있다. 지면에서 배점은 표지와 같은 줄
    # 오른쪽 끝에 붙는데, 추출 순서가 뒤집혀 "(10점)\n〈문제 3〉"이 되는 것이다.
    questions = []
    marks = list(Q_RE.finditer(ans))
    for i, mk in enumerate(marks):
        seg = ans[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(ans)]
        pm = PTS_RE.search(seg[:120]) or PTS_RE.search(ans[max(0, mk.start() - 80): mk.start()])
        questions.append({
            "no": (mk.group(1) or "1").replace(" ", ""),
            "points": int(pm.group(1)) if pm else 0,
            "ask": _ask_for(prob, mk.group(1)),
        })
    if not questions:                      # 〈문제〉 표지가 답안부에 없는 사례
        pm = PTS_RE.search(prob)
        questions = [{"no": "1", "points": int(pm.group(1)) if pm else 0,
                      "ask": _ask_for(prob, None)}]
    questions = _dedupe(questions, prob)
    return {"no": no, "tag": tag, "problemText": prob, "answerText": ans.strip(),
            "footnotes": foot, "questions": questions, "lastFootnote": last}


def _dedupe(questions, prob):
    """같은 설문번호가 두 번 잡히는 경우를 정리한다.

    답안 본문이 앞 설문을 되짚으며 `〈문제 2〉`를 다시 쓰는 일이 있어, 그때 배점 없는
    껍데기가 하나 더 생긴다. 배점이 있는 쪽을 남긴다. 문제부에 실제로 그 번호의 설문이
    두 번 있는 경우(본소/반소처럼 갈라진 사례)는 번호를 붙여 살려 둔다.
    """
    real = len(Q_RE.findall(prob)) or len(questions)
    best = {}
    for q in questions:
        cur = best.get(q["no"])
        if cur is None or (q["points"] or 0) > (cur["points"] or 0):
            best[q["no"]] = q
    out = [best[n] for n in dict.fromkeys(q["no"] for q in questions)]
    return out if len(out) <= real or real == 0 else questions


def _ask_for(prob, qno):
    """문제부에서 해당 설문의 물음 문장을 뽑는다(카드에 보일 한 줄)."""
    marks = list(Q_RE.finditer(prob))
    seg = None
    for i, mk in enumerate(marks):
        if (mk.group(1) or "").replace(" ", "") == (qno or "").replace(" ", "") or len(marks) == 1:
            seg = prob[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else len(prob)]
            break
    if seg is None:
        seg = prob
    seg = re.sub(r"^\s*[〈<][^\n]*[〉>]\s*", "", seg)
    seg = re.sub(r"※[^\n]*", "", seg)
    seg = PTS_RE.sub("", seg)
    seg = " ".join(x.strip() for x in seg.strip().split("\n") if x.strip())
    return seg[:200].strip()
