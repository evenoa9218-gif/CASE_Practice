# -*- coding: utf-8 -*-
r"""박승수 「민법 기본사례」(2025) PDF → pipeline/casebook/parkss_basic_cases.json

    set CASE_PDF_ROOT=D:\pdf
    python parse_parkss_toc.py     # 먼저 목차(사례 경계의 뼈대)
    python extract_parkss.py

**왜 2025판인가.** 같은 책의 2026판(`(2026)[박승수] 민법 기본사례-ocr.pdf`)이 더 최신이지만
텍스트층이 훨씬 심하게 깨져 있다(`가담퍼F였으면`·`λ범에게`·`매매계으폐`). 쪽당 한글·라틴
혼입이 2026판 35.5건 대 2025판 22.9건이고, `사실관계` 표지가 2026판에는 53개밖에 안 남아
사례 경계조차 못 잡는다. 다시 OCR할 수단이 없어 **본문이 읽히는 2025판**을 쓴다.

**쪽 구성** — 한 쪽은 세 갈래다. 좌표로 가른다.
  · 본문      x0 < 393
  · 여백 메모  x0 >= 393  (오른쪽 여백의 강조·암기 포인트. 본문에 섞이면 문장이 끊긴다)
  · 답안 개요  사례 첫 쪽의 지문과 본답안 사이. 3단으로 짜여 있어 추출 순서가 뒤엉킨다.
              **버리지 않는다** — 같은 x대(200~393)가 이어지는 쪽 137곳에도 나와서,
              좌표만으로 걷어내면 본문이 날아간다. 따로 표시만 해 둔다.
"""
import collections
import json
import re

import fitz

from parse_parkss_toc import OFFSET, PDF, fill_pages, parse
from paths import CASEBOOK
from reflow_rosajeong import build_vocab, reflow   # 책과 무관한 일반 재조립기다
import parkss_body_fixes
import parkss_ocr_fixes

MARGIN_X = 393        # 이보다 오른쪽에서 시작하는 줄 = 여백 메모
BODY_WIDE = 430       # 본답안 첫 줄은 쪽 폭을 다 쓴다(개요도 줄은 짧다)
LAST_PAGE = None      # 판례색인 앞까지. None이면 자동 탐지


WRAP_SLACK = 6      # 오른쪽 끝에서 이만큼 안쪽까지는 '끝까지 찬 줄'로 본다


def page_lines(page):
    """줄 단위로 (x0, x1, y, size, text, wrap). 블록 순서가 아니라 y 순으로 되돌린다.

    `wrap`은 그 줄이 **오른쪽 끝까지 찼는가** — 조판 줄바꿈인지 문단 끝인지를 가른다.
    여백은 **블록마다** 재야 한다. 지문은 음영 박스라 폭이 다르고, 답안은 오른쪽에
    여백 메모가 있어 본문이 더 좁다. 쪽 전체 최댓값으로 재면 답안이 재조립되지 않는다.
    """
    blocks = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        rows = []
        for l in b["lines"]:
            sp = l["spans"]
            t = "".join(s["text"] for s in sp).rstrip()
            if not t.strip():
                continue
            rows.append({
                "x0": min(s["bbox"][0] for s in sp),
                "x1": max(s["bbox"][2] for s in sp),
                "y": l["bbox"][1],
                "size": max(s["size"] for s in sp),
                "text": t,
            })
        if rows:
            blocks.append(rows)

    # 여백은 블록마다 재면 안 된다 — 한 줄짜리 블록은 제 자신이 곧 최댓값이라
    # 무조건 '끝까지 찬 줄'이 돼서 제목이 본문에 붙어버린다. 그렇다고 쪽 하나로 재면
    # 폭이 다른 단(지문 박스는 넓고, 여백 메모 옆 답안은 좁다)이 재조립되지 않는다.
    # 그래서 **줄 끝 x좌표가 여럿 모이는 자리**를 단의 오른쪽 끝으로 본다.
    # 제목은 길이가 제각각이라 그런 무리를 이루지 않아 자연히 걸러진다.
    body_x1 = [r["x1"] for rows in blocks for r in rows if r["x0"] < MARGIN_X]
    widest = max(body_x1, default=0)
    # 오른쪽 3분의 1 안쪽에서만 찾는다. 짧은 제목끼리도 우연히 같은 자리에서 끝나는데,
    # 그걸 단의 끝으로 삼으면 제목이 본문에 붙는다.
    # 딱 떨어지는 값이 아니라 **오차 안에 몇 개가 모이는가**로 센다 — 글자 끝이
    # 466.0·467.1처럼 흩어져 있어 값이 같기를 바라면 무리가 잡히지 않는다.
    cand = sorted({round(x) for x in body_x1 if x >= widest * 0.66})
    right_edges = [x for x in cand
                   if sum(1 for v in body_x1 if abs(v - x) <= WRAP_SLACK) >= 3]
    out = []
    for rows in blocks:
        for r in rows:
            r["wrap"] = any(abs(r["x1"] - e) <= WRAP_SLACK for e in right_edges)
        out += rows
    return sorted(out, key=lambda l: (round(l["y"] / 4), l["x0"]))


def strip_footer(lines):
    """쪽 하단의 쪽번호 한 줄을 뗀다.

    제목 띠 줄은 여기서 버리면 안 된다 — 그 줄이 곧 **사례가 시작하는 표시**라
    `looks_like_start()`가 그것을 보고 판단한다. 본문을 조립할 때 걸러낸다.
    """
    return [l for l in lines
            if not (l["y"] > 680 and re.fullmatch(r"\d{1,3}", l["text"].strip()))]


def clean(lines):
    """본문으로 쓸 줄만 남긴다 — 제목 띠와 그 무늬가 읽힌 줄을 뺀다."""
    return [l for l in lines if not parkss_body_fixes.is_banner_noise(l["text"])]


def trim_head(lines):
    """지문 앞머리에 남은 제목 띠 부스러기(`*—`, `"r ―1`)를 걷어낸다.

    지문은 반드시 글월이나 `〈사실관계〉` 표지로 시작하므로, 한글이 다섯 자도
    안 되는 줄이 앞에 붙어 있으면 본문이 아니다. 뒤쪽은 건드리지 않는다.
    """
    i = 0
    while i < len(lines) and len(re.findall(r"[가-힣]", lines[i]["text"])) < 5:
        i += 1
    return lines[i:] if i < len(lines) else lines


def split_columns(lines):
    """본문 / 여백 메모로 가른다."""
    body = [l for l in lines if l["x0"] < MARGIN_X]
    note = [l for l in lines if l["x0"] >= MARGIN_X]
    return body, note


# 설문이 끝나는 말. 이 줄까지가 지문이다 — 짧아서 폭으로는 못 잡는다.
# `여부`·`가부`는 넣지 않는다 — 답안 소제목이 온통 `…인지 여부`라 지문이 답안까지 삼킨다.
# 맺음말 뒤에는 배점(`(15점)`)과 기출 표시(`2005*0013`)가 따라붙는다 — 같이 흘려보낸다.
ASK_END = re.compile(r"(하시오|하라|하는가|인가|있는가|없는가|되는가|타당한가|"
                     r"어떠한가|무엇인가)\s*[.?)\]』」]*\s*"
                     r"(?:[(（]\s*\d+\s*점\s*[)）]\s*[.]?\s*)?[\d*·\s]*$")
# 답안의 대제목(로마숫자). OCR이 I·II·III·IV를 n·H·m·fl·h로 흘린다.
# 지문에는 로마숫자 제목이 없어, 여기서 지문 탐색을 끊으면 된다.
ANSWER_HEAD = re.compile(r"^\s*[IVXⅠⅡⅢⅣⅤnNHhmfl]{1,4}\s*[.．·]\s*\S")


def find_answer_start(body):
    """(지문 끝, 본답안 시작) 줄 번호. 그 사이가 답안 개요다.

    지문은 쪽 폭을 다 쓰는 긴 줄이 이어지다 `…논하시오`류의 **짧은 줄**로 끝난다.
    폭으로만 자르면 정작 설문이 잘려 나가므로, 맺음말을 먼저 찾고 폭은 예비로만 쓴다.
    개요는 짧은 줄뿐이라, 그 뒤 **다시 폭을 다 쓰는 줄**이 본답안의 시작이다.
    """
    half = max(3, int(len(body) * 0.65))
    end, head = 0, None
    for i, l in enumerate(body[:half]):
        if ANSWER_HEAD.match(l["text"]):     # 답안이 시작됐다 — 지문은 여기까지
            head = i
            break
        if ASK_END.search(l["text"]):
            end = i
    if not end and head:                 # 맺음말이 깨졌다 — 답안 대제목 직전까지
        end = head - 1
    if not end:                          # 둘 다 없다 — 마지막 수단으로 폭
        for i, l in enumerate(body):
            if l["x1"] >= BODY_WIDE:
                end = i
            elif end and i - end > 4:
                break
    for i in range(end + 1, len(body)):
        if body[i]["x1"] >= BODY_WIDE and body[i]["x0"] <= 95:
            return end + 1, i
    return end + 1, end + 1             # 개요도 없음


def looks_like_start(lines):
    """사례가 시작하는 쪽인가. 제목 줄(짧다)로 열리고 곧 폭을 다 쓰는 지문이 이어진다.

    이어지는 쪽은 앞 쪽에서 넘어온 문장이라 첫 줄부터 폭을 다 쓴다.
    """
    if not lines or lines[0]["y"] > 90:
        return False
    if lines[0]["x1"] >= BODY_WIDE:            # 첫 줄이 이미 본문 = 이어지는 쪽
        return False
    return any(l["x1"] >= BODY_WIDE for l in lines[1:6])


def snap_start(doc, p0, span=3):
    """목차 쪽번호를 되메운 사례는 한두 쪽 어긋난다. 근처에서 진짜 시작 쪽을 찾는다."""
    for d in [0] + [s * k for k in range(1, span + 1) for s in (1, -1)]:
        p = p0 + d
        if 0 <= p < len(doc) and looks_like_start(split_columns(strip_footer(page_lines(doc[p])))[0]):
            return p
    return p0


def norm(s, no):
    """당사자 기호 등 전역 교정 → 지면 대조로 확정한 자리별 교정 순."""
    return parkss_body_fixes.apply(parkss_ocr_fixes.apply(s, no))


def extract():
    rows = fill_pages(parse())
    doc = fitz.open(PDF)
    last = LAST_PAGE or _index_page(doc)

    starts = []
    for r in rows:
        p = r["bookPage"] + OFFSET - 1
        starts.append(snap_start(doc, p) if r["pageGuessed"] else p)
    starts = _monotonic(starts)

    out = {}
    for i, (r, nxt) in enumerate(zip(rows, rows[1:] + [{"bookPage": last - OFFSET + 1}])):
        p0 = starts[i]
        p1 = min(starts[i + 1] if i + 1 < len(starts) else last, last)
        if p0 >= len(doc):
            break
        pages, notes = [], []
        for pi in range(p0, max(p1, p0 + 1)):
            body, note = split_columns(strip_footer(page_lines(doc[pi])))
            pages.append({"page": pi + 1, "lines": body})
            notes += [norm(l["text"], r["no"]) for l in note]

        head = pages[0]["lines"][0]["text"] if pages[0]["lines"] else ""
        opening, ans0 = find_answer_start(pages[0]["lines"])
        out[str(r["no"])] = {
            "no": r["no"], "title": r["title"], "stars": r["stars"],
            "part": r["part"], "bookPage": r["bookPage"],
            "pdfPages": [p0 + 1, max(p1, p0 + 1)],
            "pageGuessed": r["pageGuessed"],
            "rawHeader": head,
            # 재조립(reflow)은 사전이 있어야 하고 사전은 본문 전체가 있어야 만들 수 있어서,
            # 여기서는 줄과 wrap 표시를 그대로 담아 두고 마지막에 한꺼번에 잇는다.
            "_problem": _rows(trim_head(clean(pages[0]["lines"][1:opening])), r["no"]),
            "_outline": _rows(clean(pages[0]["lines"][opening:ans0]), r["no"]),
            "_answer": _rows(clean(pages[0]["lines"][ans0:]) +
                             [l for pg in pages[1:] for l in clean(pg["lines"])], r["no"]),
            "notes": [n for n in notes if not parkss_body_fixes.is_banner_noise(n)],
        }
    doc.close()
    return _reflow_all(out)


def _rows(lines, no):
    return [[norm(l["text"], no), bool(l.get("wrap"))] for l in lines]


def _reflow_all(cases):
    """조판 줄바꿈을 문단으로 되돌린다. 사전은 책 전체의 '줄 중간 토큰'으로 만든다."""
    vocab = build_vocab([[t for t, _ in c[k]] for c in cases.values()
                         for k in ("_problem", "_outline", "_answer")])
    for c in cases.values():
        for src, dst in (("_problem", "problemText"), ("_outline", "outlineText"),
                         ("_answer", "answerText")):
            rows = c.pop(src)
            c[dst] = reflow([t for t, _ in rows], [w for _, w in rows], vocab,
                            loose_item=True)
    return cases


def _monotonic(ps):
    """보정이 앞뒤 사례를 앞지르면 되돌린다 — 사례 순서는 뒤집힐 수 없다."""
    for i in range(1, len(ps)):
        if ps[i] <= ps[i - 1]:
            ps[i] = ps[i - 1] + 1
    return ps


def _index_page(doc):
    """판례색인이 시작하는 쪽 — 본문의 끝."""
    for i in range(len(doc) - 1, len(doc) - 90, -1):
        if re.search(r"판\s*[례레게]\s*색\s*인", doc[i].get_text()[:400]):
            return i
    return len(doc)


if __name__ == "__main__":
    cases = extract()
    path = CASEBOOK / "parkss_basic_cases.json"
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    n = len(cases)
    empty = [c["no"] for c in cases.values() if len(c["problemText"]) < 60]
    noans = [c["no"] for c in cases.values() if len(c["answerText"]) < 200]
    print(f"사례 {n}건 → {path}")
    print(f"  지문 60자 미만 {len(empty)}건: {empty[:15]}")
    print(f"  답안 200자 미만 {len(noans)}건: {noans[:15]}")
    print(f"  여백 메모 {sum(len(c['notes']) for c in cases.values())}줄")
    print(f"  개요도 있는 사례 {sum(1 for c in cases.values() if c['outlineText'])}건")
