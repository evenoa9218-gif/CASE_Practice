# -*- coding: utf-8 -*-
r"""조판 줄바꿈을 문단으로 되돌린다 — **확신이 설 때만**.

PDF의 줄바꿈은 조판 산물이라 그대로 두면 본문이 책 줄 너비로 딱딱하게 끊겨 보인다.
그런데 한국어는 줄을 아무 글자에서나 끊으므로, 이어붙일 때 띄어쓰기를 넣어야 할지
붙여야 할지가 추출 결과만으로는 판별되지 않는다.

  "…거주 자체"  +  "가 어렵게…"   → 붙여야 한다 (자체가)
  "…도급주어"   +  "C가 공사를…"  → 띄어야 한다

그래서 두 가지 근거를 함께 쓴다.

1. **줄 끝 x좌표** — 오른쪽 끝까지 찬 줄만 '조판 줄바꿈'이다. 짧게 끝난 줄은 문단의
   끝이므로 건드리지 않는다. 이걸 안 보면 문단 두 개가 통째로 붙는다.
2. **코퍼스 빈도** — 앞줄 마지막 토큰 `x`와 뒷줄 첫 토큰 `y`에 대해, 붙인 `xy`가
   본문 다른 곳에 낱말로 존재하면 붙이고, `x`·`y`가 각각 낱말로 존재하면 띄운다.
   사전은 **줄 중간에 온전히 들어 있는 토큰**으로만 만든다(줄 끝 토큰은 잘렸을 수 있다).

셋 다 아니면 **줄바꿈을 그대로 둔다.** 애매한 자리를 억지로 이어붙이면 없던 띄어쓰기
오류가 생기는데, 그건 안 이어붙인 것보다 나쁘다. 덜 이어붙는 대신 틀리지는 않는다.
"""
import collections
import re

# 이어붙이면 안 되는 줄머리 — 목차·설문 표지·조문 인용 등
NEW_ITEM = re.compile(
    r"^\s*(?:[〈<【\[]|※|[①-⑳㉠-㉣]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*[.．]|"
    r"[가-힣]\s*[.．)]\s|\d+\s*[.．)]\s|[-–—→▶▸■□●○*])")
# 종결부호로 끝난 줄은 문장이 끝난 것
TERMINAL = re.compile(r"[.。?!:;]\s*$")
WORD = re.compile(r"[가-힣A-Za-z0-9]")
TRIM = re.compile(r"^[‘’“”'\"(\[〈【]+|[‘’“”'\"),.\]〉】]+$")


def build_vocab(all_lines):
    """줄 중간에 온전히 들어 있는 토큰만으로 사전을 만든다."""
    v = collections.Counter()
    for lines in all_lines:
        for ln in lines:
            t = ln.split()
            for w in t[1:-1]:
                w = TRIM.sub("", w)
                if w:
                    v[w] += 1
    return v


# 홀로 설 수 없는 한 글자 조사·어미. 줄 첫머리에 이것만 떨어져 있으면 앞말이 잘린 것이다.
# `이`(이 사건)·`지`(사귄 지)·`다`·`한`·`할`처럼 낱말로도 쓰이는 글자는 뺐다.
STUCK = set("가를은는을의와과도며서로고만")


def _decide(x, y, vocab):
    """앞줄 끝 토큰 x, 뒷줄 첫 토큰 y → 'join'(붙임) / 'space'(띄움) / None(판단 보류)"""
    xs, ys = TRIM.sub("", x), TRIM.sub("", y)
    if not xs or not ys:
        return None
    if len(ys) == 1 and ys in STUCK:
        return "join"          # 줄 첫머리에 조사 한 글자만 → 앞말이 잘린 것
    merged = vocab.get(xs + ys, 0)
    apart = min(vocab.get(xs, 0), vocab.get(ys, 0))
    if merged and merged >= apart:
        return "join"
    if apart >= 2 and not merged:
        return "space"
    if len(xs) == 1 and merged == 0 and apart == 0:
        return "join"          # 한 글자만 남은 줄 끝도 낱말이 잘린 것
    return None


def reflow(lines, wraps, vocab):
    """lines/wraps 는 같은 길이. wraps[i]가 True면 i번째 줄이 오른쪽 끝까지 찬 줄."""
    out, out_wrap = [], []
    for ln, wr in zip(lines, wraps):
        s = ln.rstrip()
        if not out or not s or not out[-1]:
            out.append(s)
            out_wrap.append(wr)
            continue
        prev = out[-1]
        if not out_wrap[-1] or TERMINAL.search(prev) or NEW_ITEM.match(s) \
           or not WORD.search(prev[-1:]) or not WORD.search(s[:1]):
            out.append(s)
            out_wrap.append(wr)
            continue
        d = _decide(prev.split()[-1], s.split()[0], vocab)
        if d == "join":
            out[-1] = prev + s
        elif d == "space":
            out[-1] = prev + " " + s
        else:
            out.append(s)          # 보류 — 줄바꿈을 그대로 둔다
            out_wrap.append(wr)
            continue
        out_wrap[-1] = wr
    return "\n".join(out)
