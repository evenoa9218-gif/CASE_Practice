# -*- coding: utf-8 -*-
r"""로사정 PDF → 사례별 정규화 텍스트 (`pipeline/casebook/rosajeong_cases.json`).

    python extract_rosajeong.py

원본: 정연석 「로스쿨 사례의 정석」(26.02) — 632쪽, 저작권 자료라 커밋하지 않는다.
경로는 환경변수 `ROSAJEONG_PDF`로 지정한다(기본값은 아래 상수).

**PDF에 텍스트 레이어는 온전히 들어 있다(누락 없음).** 지면 이미지와 대조해 확인했다.
문제는 글자 오인식이고, 하필 당사자 기호가 통째로 깨져 있다 — 원문에 `乙`이 한 번도
등장하지 않고 전부 `江`·`己`로 읽힌다. 사례집에서 甲乙丙이 뒤바뀌면 답안이 무의미해지므로
이 교정은 선택이 아니다.

자동 교정으로 못 잡는 잔여 의심 구간은 `rosajeong_verify.txt`로 따로 뽑는다.
해당 쪽을 렌더링해 눈으로 대조하면 된다(지면 이미지 자체는 깨끗해서 정확히 읽힌다).
"""
import collections
import io
import json
import os
import re
from pathlib import Path

import fitz  # PyMuPDF

import rosajeong_ocr_fixes
from paths import CASEBOOK

PDF = Path(os.environ.get(
    "ROSAJEONG_PDF", r"D:\pdf\사례\민사법\(26.02)[정연석] 로사정.pdf"))
OUT = CASEBOOK / "rosajeong_cases.json"
VERIFY = CASEBOOK / "rosajeong_verify.txt"

PART_NAME = {1: "채권총론", 2: "채권각론", 3: "물권법", 4: "민법총칙"}
BOOK_OFFSET = 18          # PDF쪽 = 책쪽 + 18
BODY_FROM = 20            # 앞부분은 표지·머리말·차례

# ── 러닝 헤더/푸터 ────────────────────────────────────────────────
# "22 • Part 1 채권총론" / "1 8 • Part 1 채권총론"(자간이 벌어져 숫자가 갈라진 경우)
FOOT_PART = re.compile(r"^\s*[\d\s]*[•·♦»]?\s*Part\s*\d\s*"
                       r"(채권총론|채권각론|물권법|민법총칙)\s*$")
# "채무불이행, 손해배상 • 25" — 가운뎃점이 »·♦로도 읽혀서 셋 다 받는다
FOOT_TOPIC = re.compile(r"^(.*?)\s*[•·♦»]\s*[\d\s]+$")
BARE_NUM = re.compile(r"^[\d\s]{1,5}$")

# ── OCR 오인식 교정 ───────────────────────────────────────────────
REPL = [
    ("江", "乙"), ("己", "乙"), ("內", "丙"), ("因", "丙"), ("成", "戊"),
    ("仁", "C"), ("日", "B"),
    ("乂", "※"), ("宗", "※"), ("災", "※"), ("洪", "※"),
    ("采", "※"), ("米", "※"), ("炎", "※"), ("凶", "※"),
    ("•", "·"), ("（", "("), ("）", ")"), ("：", ":"),
    ("，", ","), ("［", "["), ("］", "]"),
]
NUM_GROUP = re.compile(r"(\d),\s+(\d{3})")

# 자동 교정으로 못 잡는 것 — 눈으로 볼 목록에 넣는다
# 책이 한글 옆 괄호에 붙이는 정상 한자들. 지면 대조로 하나씩 확인했다 —
# 여기 없으면 `rosajeong_verify.txt`에 올라와 계속 눈으로 봐야 할 목록으로 남는다.
KNOWN_HANJA = set("甲乙丙丁戊判例私見大法院全合條決"
                  "補修報酬利理始終期永久燒想使者代償塡非父母生月年市")
SUSPECT = [
    (re.compile(r"\(\s*[XＸ×xO0]{1,3}\s*\)"), "숫자가 (X)로 깨짐"),
    (re.compile(r"\d\s*[이애]\s*\d"), "숫자가 이/애로 깨짐"),
    (re.compile(r"[☆◎■□♦€»]"), "정체불명 기호"),
    (re.compile(r"(?<![A-Za-z])[A-Z][/?][A-Za-z가-힣]"), "당사자기호 깨짐(Z/…)"),
    (re.compile(r"으(?=[는의가에])"), "으 = 라틴문자?"),
    (re.compile(r"(?<![A-Za-z])Z[LlIi]?(?=[은는이가의에을로과와])"), "Z = 당사자?"),
]


def strip_footer(body):
    lines = body.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    for _ in range(3):
        if not lines:
            break
        last = lines[-1].strip()
        if FOOT_PART.match(last):
            lines.pop()
            continue
        m = FOOT_TOPIC.match(last)
        if m and len(m.group(1)) < 25 and not m.group(1).endswith(("다", "고", "며", "나", ".")):
            lines.pop()
            continue
        if BARE_NUM.match(last):
            lines.pop()
            if lines and 0 < len(lines[-1].strip()) < 25 \
               and not lines[-1].strip().endswith(("다", ".", "고", "며")):
                lines.pop()
            continue
        break
    return "\n".join(lines)


def normalize(s):
    for a, b in REPL:
        s = s.replace(a, b)
    while True:                     # "100, 000, 000" — 한 번만 돌리면 뒷그룹이 남는다
        t = NUM_GROUP.sub(r"\1,\2", s)
        if t == s:
            break
        s = t
    s = re.sub(r"(\d{2})이다(\d)", r"\g<1>01다\g<2>", s)   # 20이다44338 → 2001다44338
    s = s.replace("제4이조", "제401조")
    s = re.sub(r"\s*·\s*", "·", s)
    return rosajeong_ocr_fixes.apply(s)                     # 지면 대조로 확정한 개별 교정


def wrap_flags(page, nlines):
    """줄별로 '오른쪽 끝까지 찬 줄'인지 표시한다 — 조판 줄바꿈과 문단 끝을 가르는 근거.

    오른쪽 여백은 **블록마다 따로** 잰다. 문제 지문은 음영 박스 안에 있어 본문보다
    여백이 10pt쯤 좁은데, 쪽 전체의 최댓값 하나로 재면 박스 안의 줄이 전부
    '문단 끝'으로 잘못 분류되어 지문만 재조립이 안 된다.
    """
    flags = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        xs = [max(s["bbox"][2] for s in l["spans"]) for l in b["lines"]]
        right = max(xs)
        flags += [x >= right - 6 for x in xs]
    if not flags:
        return [False] * nlines
    return (flags + [False] * nlines)[:nlines]


def main():
    doc = fitz.open(PDF)
    raw = {n + 1: doc[n].get_text() for n in range(doc.page_count)}
    pages, wraps = {}, {}
    for n in range(doc.page_count):
        stripped = strip_footer(raw[n + 1])
        lines = stripped.split("\n")
        wraps[n + 1] = wrap_flags(doc[n], len(lines))
        pages[n + 1] = normalize(stripped)
        # 교정으로 줄 수가 바뀌면 플래그가 어긋나므로 맞춰 준다
        d = len(pages[n + 1].split("\n")) - len(wraps[n + 1])
        wraps[n + 1] = (wraps[n + 1] + [False] * d)[:len(pages[n + 1].split("\n"))]

    # ── 목차(pdf 10~17): PART · 논점 · 책쪽 ──
    toc, part, topic = {}, None, None
    for n in range(10, 18):
        for line in raw[n].split("\n"):
            l = line.strip()
            if not l:
                continue
            m = re.match(r"^PART\s*(\d)$", l)
            if m:
                part, topic = int(m.group(1)), None
                continue
            m = re.match(r"^핵심사례\s*([0-9]{1,3}(?:\s*-\s*[0-9])?)\s*\.*\s*(\d+)?\s*$", l)
            if m:
                toc[m.group(1).replace(" ", "")] = {
                    "part": part, "topic": topic,
                    "bookPage": int(m.group(2)) if m.group(2) else None}
                continue
            if re.match(r"^(차례|xi+|x+|PART)", l, re.I):
                continue
            if re.match(r"^[가-힣0-9·,\s()]{2,30}$", l) and not l[0].isdigit():
                topic = l
    # 목차에 없는 가지번호 — 바로 앞 사례의 논점을 물려받는다
    toc.setdefault("072-1", {"part": 2, "topic": "불법행위", "bookPage": None})
    toc.setdefault("121-1", {"part": 3, "topic": "비전형담보", "bookPage": None})

    # ── 본문에서 사례 시작 쪽 찾기 ──
    starts = []
    for n in sorted(pages):
        if n < BODY_FROM:
            continue
        for m in re.finditer(r"^핵심(?:사례|시려I)\s*([0-9]{1,3}(?:\s*-\s*[0-9])?)\s*$",
                             pages[n], re.M):
            no = m.group(1).replace(" ", "")
            if no not in [s[0] for s in starts]:
                starts.append((no, n))
    starts.sort(key=lambda x: x[1])

    # 본문의 끝 — 뒤에 붙은 판례색인·저자소개는 사례가 아니다.
    # 이걸 안 자르면 마지막 사례에 색인 12쪽이 통째로 딸려 들어간다.
    body_end = next((n for n in sorted(pages)
                     if n > starts[-1][1] and pages[n].lstrip().startswith("판례 색인")),
                    doc.page_count + 1) - 1

    cases = {}
    for i, (no, start) in enumerate(starts):
        end = starts[i + 1][1] - 1 if i + 1 < len(starts) else body_end
        e = toc.get(no, {})
        cases[no] = {
            "no": no,
            "part": PART_NAME.get(e.get("part"), "?"),
            "topic": e.get("topic"),
            "bookPage": e.get("bookPage") or (start - BOOK_OFFSET),
            "pdfPages": [start, end],
            # 쪽 경계를 남긴다 — 각주는 언제나 그 쪽의 맨 아래에 붙으므로,
            # 경계를 잃으면 각주와 다음 쪽 본문을 구분할 수 없다.
            # 세 번째 값은 줄별 '오른쪽 끝까지 찬 줄' 표시(문단 재조립 근거).
            "pages": [[n, pages[n], "".join("1" if w else "0" for w in wraps[n])]
                      for n in range(start, end + 1)],
        }
        cases[no]["text"] = "\n".join(p[1] for p in cases[no]["pages"]).strip()

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 눈으로 볼 잔여 의심 구간 ──
    o, total = io.StringIO(), 0
    o.write("로사정 OCR 잔여 의심 구간 — 해당 쪽을 렌더링해 지면과 대조할 것\n")
    o.write("=" * 70 + "\n")
    for no, c in cases.items():
        hits = []
        for m in re.finditer(r"[\u4e00-\u9fff]", c["text"]):
            if m.group(0) not in KNOWN_HANJA:
                hits.append((m.start(), "낯선 한자 " + m.group(0)))
        for rx, name in SUSPECT:
            hits += [(m.start(), name) for m in rx.finditer(c["text"])]
        if not hits:
            continue
        total += len(hits)
        o.write(f"\n### 핵심사례 {no} ({c['part']}/{c['topic']}) "
                f"PDF p.{c['pdfPages'][0]}~{c['pdfPages'][1]} — {len(hits)}건\n")
        for pos, name in sorted(hits)[:40]:
            frag = c["text"][max(0, pos - 30):pos + 30].replace("\n", "⏎")
            o.write(f"   [{name}] …{frag}…\n")
    o.write(f"\n\n합계 {total}건\n")
    VERIFY.write_text(o.getvalue(), encoding="utf-8")

    by_part = collections.Counter(c["part"] for c in cases.values())
    print(f"사례 {len(cases)}건 → {OUT.name}")
    print("  " + " · ".join(f"{k} {v}" for k, v in by_part.items()))
    print(f"눈으로 볼 구간 {total}건 → {VERIFY.name}")


if __name__ == "__main__":
    main()
