# -*- coding: utf-8 -*-
r"""박승수 「민법 기본사례」(2025) 목차 파싱 — 사례 경계의 뼈대.

    python parse_parkss_toc.py

**본문 헤더는 못 믿는다.** OCR이 `사례`를 `사레`·`새게`·`사갱`·`사겠`·`Wl`·`사-0`까지
망가뜨려 286개 중 48개가 어떤 정규식으로도 안 걸린다. 반면 목차는 점선(dot leader) 뒤에
**책 쪽번호**가 붙어 있어, 번호가 깨진 몇 줄만 앞뒤로 메우면 전 사례의 위치가 확정된다.

**PDF쪽 = 책쪽 + 26.** 본문 하단에 인쇄된 쪽번호로 검증한다(`verify_offset`).
"""
import re

import fitz

from paths import CASEBOOK, PDF_ROOT

PDF = PDF_ROOT / "사례" / "민사법" / "(2025) 박승수 민법 기본사례 OCR.pdf"
TOC_PAGES = range(19, 27)          # 0-based. p20~p27
OFFSET = 26                        # PDF쪽 = 책쪽 + OFFSET

# `사례 12 …`. 첫 글자는 사/새/시/人/샤로 튀고, 둘째~셋째는 례/레/게/日1/R#/脚/［례 등
# 무엇으로든 깨진다. 그래서 둘째 이후는 "숫자·공백이 아닌 아무 글자 0~3개"로 열어 두고,
# 대신 뒤에 오는 제목이 한글로 시작하는지로 오탐을 막는다.
# 제목이 통째로 깨진 줄(`사례 286 ^^S.^***)`)도 있어, 한글이 없으면 점선 꼬리로 대신 확인한다.
ENTRY = re.compile(r"^\s*[사새시샤셔人ᄉ][^\d\s]{0,3}\s*(\d{1,3})\s+"
                   r"(?=.*(?:[가-힣]|[.·•‥…]{6,}))(.*)$")
# 편 표제도 `저n 편 민법%`·`저 I3 편 j태권그I론`처럼 깨진다. 번호·제목을 읽지 않고
# 나오는 순서대로 1~5편을 붙인다 — 이 책의 편 구성은 다섯으로 고정이다.
PART = re.compile(r"^\s*[제저]\s*[\dInl|]{0,3}\s*편\b")
PART_NAMES = ["제1편 민법총칙", "제2편 채권총론", "제3편 채권각론",
              "제4편 물권법", "제5편 친족상속법"]
# 두 자리 앞머리가 한글 한 글자로 뭉개진다: `거0`=210 · `건9`=219.
# 앞뒤 항목이 209~219라 단조성으로 검증된다.
NO_FIX = [(re.compile(r"^거(\d)$"), r"21\1"), (re.compile(r"^건(\d)$"), r"21\1")]
# 줄 끝 점선 + 쪽번호. 점(.)이 OCR에서 ·,•,‥ 등으로 튄다.
TAIL = re.compile(r"[.·•‥…\s]{4,}(\d{1,3})\s*$")
STARS = re.compile(r"[★☆大*수]{1,3}")


def _entry(line):
    """목차 한 줄 → (사례번호, 제목). 번호가 한글로 뭉개진 것도 되살린다."""
    m = ENTRY.match(line)
    if m:
        no, rest = int(m.group(1)), m.group(2)
        # `人日1 73 채권자취소…` — `례`가 `日1`로 깨져 그 `1`을 번호로 읽은 것이다.
        # 제목이 다시 숫자로 시작하면 그쪽이 진짜 번호다.
        m2 = re.match(r"^(\d{1,3})\s+(.*)$", rest)
        if m2 and no < 10:
            return int(m2.group(1)), m2.group(2)
        return no, rest
    # `사례 거0 …` — 번호 자리가 통째로 한글일 때
    m = re.match(r"^\s*[사새시샤셔人ᄉ][^\d\s]{0,3}\s*(\S{2})\s+(?=.*[가-힣])(.*)$", line)
    if not m:
        return None
    raw = m.group(1)
    for rx, rep in NO_FIX:
        if rx.match(raw):
            return int(rx.sub(rep, raw)), m.group(2)
    return None


def _clean_title(t):
    """제목에서 점선 꼬리·별점·괄호를 떼어 사람이 읽을 형태로."""
    t = TAIL.sub("", t)
    t = re.sub(r"[.·•‥…]{4,}.*$", "", t)
    return re.sub(r"\s+", " ", t).strip(" .·-—")


def parse():
    doc = fitz.open(PDF)
    rows, part, npart = [], None, 0
    for i in TOC_PAGES:
        for raw in doc[i].get_text().split("\n"):
            line = raw.rstrip()
            if PART.match(line):
                part = PART_NAMES[npart] if npart < len(PART_NAMES) else line.strip()
                npart += 1
                continue
            m = _entry(line)
            if not m:
                continue
            no, rest = m
            if no > 286:
                continue
            tail = TAIL.search(rest)
            rows.append({
                "no": no,
                "title": _clean_title(rest),
                "stars": len(STARS.search(rest).group()) if STARS.search(rest) else 0,
                "bookPage": int(tail.group(1)) if tail else None,
                "part": part,
            })
    doc.close()
    return _dedupe(rows)


def _dedupe(rows):
    """같은 번호가 두 번 잡히면 쪽번호가 있는 쪽을, 둘 다 있으면 앞의 것을 남긴다."""
    best = {}
    for r in rows:
        cur = best.get(r["no"])
        if cur is None or (cur["bookPage"] is None and r["bookPage"] is not None):
            best[r["no"]] = r
    return [best[n] for n in sorted(best)]


def fill_pages(rows):
    """쪽번호가 깨진 줄을 앞뒤로 메운다. 목차는 단조증가라 사이를 균등 분배하면 된다.

    되메운 자리는 `pageGuessed`로 표시해 둔다 — 나중에 본문 쪽번호로 대조할 때 쓴다.
    """
    known = [i for i, r in enumerate(rows) if r["bookPage"]]
    for r in rows:
        r["pageGuessed"] = r["bookPage"] is None
    # 단조성을 깨는 값은 오인식이므로 버린다(예: 213 다음에 21)
    for a, b in zip(known, known[1:]):
        if rows[b]["bookPage"] < rows[a]["bookPage"]:
            rows[b]["bookPage"], rows[b]["pageGuessed"] = None, True
    known = [i for i, r in enumerate(rows) if r["bookPage"]]
    for a, b in zip(known, known[1:]):
        gap = b - a
        if gap == 1:
            continue
        lo, hi = rows[a]["bookPage"], rows[b]["bookPage"]
        for k in range(1, gap):
            rows[a + k]["bookPage"] = lo + round((hi - lo) * k / gap)
    if known:                           # 양 끝이 비면 이웃 간격을 이어서 늘린다
        step = max(1, round((rows[known[-1]]["bookPage"] - rows[known[0]]["bookPage"])
                            / max(1, known[-1] - known[0])))
        for k in range(known[0] - 1, -1, -1):
            rows[k]["bookPage"] = max(1, rows[k + 1]["bookPage"] - step)
        for k in range(known[-1] + 1, len(rows)):
            rows[k]["bookPage"] = rows[k - 1]["bookPage"] + step
    return rows


def verify_offset(rows, doc, n=40):
    """본문 하단에 인쇄된 쪽번호로 OFFSET을 검증한다."""
    ok = bad = 0
    for r in rows[:n]:
        p = r["bookPage"] + OFFSET - 1
        if not 0 <= p < len(doc):
            continue
        foot = doc[p].get_text().strip().split("\n")[-1].strip()
        (ok := ok + 1) if foot == str(r["bookPage"]) else (bad := bad + 1)
    return ok, bad


if __name__ == "__main__":
    rows = fill_pages(parse())
    doc = fitz.open(PDF)
    ok, bad = verify_offset(rows, doc)
    out = CASEBOOK / "parkss_toc.json"
    import json
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    miss = [n for n in range(1, 287) if n not in {r["no"] for r in rows}]
    guessed = [r["no"] for r in rows if r["pageGuessed"]]
    print(f"목차 {len(rows)}건 (번호 {rows[0]['no']}~{rows[-1]['no']})")
    print(f"  누락 번호 {len(miss)}개: {miss[:20]}")
    print(f"  쪽번호 되메움 {len(guessed)}개: {guessed[:20]}")
    print(f"  편 {len({r['part'] for r in rows})}개")
    print(f"  쪽번호 대조: 일치 {ok} / 불일치 {bad}")
    print(f"→ {out}")
