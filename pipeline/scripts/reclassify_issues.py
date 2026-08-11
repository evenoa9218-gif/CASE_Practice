"""쟁점의 분야(헌법/행정법, 형법/형사소송법, 민법/상법/민사소송법)를 다시 매긴다.

왜 필요한가
  기존 분류는 쟁점명에 미리 적어 둔 낱말(행정 27개·헌법 25개)이 들어 있는지만
  봤다. 그 목록에 없으면 전부 "공법일반"·"형사법일반"으로 떨어져서, 공법 424개
  중 205개(48%)와 형사법 550개 중 227개(41%)가 미분류로 남았다. 민사법은 반대로
  미분류는 없지만 상법이 27개(5.6%)뿐이라, 명의개서·대표소송·신주인수권 같은
  명백한 상법 쟁점이 죄다 "민법"에 섞여 있었다.

근거
  낱말 목록을 늘리는 대신 **이미 분야가 정해진 자료**를 쓴다.
  ① 사례집 목차 — 「강성민 헌법 사례형 연습」에 실린 항목은 헌법, 「이인규 형법」은
     형법이다. 책이 곧 분야 라벨이다. 이미 분류돼 있던 쟁점으로 재어 보니
     공법 95%(83/87), 형사법 90%(62/69)가 기존 분류와 일치했다.
  ② **전용** 사례집 본문 — 그 분야만 다루는 책에 쏠려 나오는 쟁점은 그 분야로 본다.

     "전용"이 핵심이다. 통합서를 넣으면 근거가 망가진다. 실제로 민사법 코퍼스에
     통합서(「로스쿨 사례의 정석」·「CBT실전답안」)를 넣고 돌렸더니 기판력·
     처분권주의·재소금지가 "민법"으로 뒤집혔다. 형사소송법 사례집도 죄명을
     잔뜩 인용하기 때문에 뇌물죄·준강간죄의불능미수가 "형사소송법"이 됐다.

새로 붙이는 것과 뒤집는 것을 구분한다
  - **미분류를 채울 때**는 가장 엄격하게 본다. 목차가 한 분야를 가리키거나,
    한 분야 전용 사례집에서만 세 번 이상 나올 때만 붙인다.
  - **이미 붙어 있는 분야를 뒤집을 때**는 목차의 뒷받침이 있거나, 그게 없으면
    한 분야가 95% 이상을 차지하면서 20회 이상 나와야 한다. 이 선이 사실관계에
    스쳐 나온 낱말(뇌물죄 15회)과 그 책의 논점(대표소송 249회)을 가른다.

기존 분류를 정답 삼아 정밀도를 재고 그걸로 자동 게이팅하지는 않는다. 고치려는
대상이 기존 분류인데 그걸 정답으로 삼으면 순환이다 — 실제로 그렇게 재면 상법
판정 정밀도가 19%로 나오지만, 그 42건을 눈으로 보면 명의개서·대표소송·신주인수권처럼
전부 명백한 상법이다. 틀린 건 판정이 아니라 기존 분류였다. 대신 바뀔 내용을
빠짐없이 찍어 사람이 훑을 수 있게 한다.

사용
  python pipeline/scripts/reclassify_issues.py [과목...] [--write]
  --write 없이 돌리면 바뀔 내용을 전부 찍어 보여 준다. 목록이 길어도 다 찍는다 —
  근거를 눈으로 확인할 수 있어야 하기 때문이다.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 목차의 책 이름 → 분야.
TOC_BOOKS = {
    "공법": {"헌법": "헌법", "행정법": "행정법", "정선균 행정법": "행정법"},
    "형사법": {"이창현 형사소송법": "형사소송법", "이인규 형법": "형법",
               "작은변사기 형소": "형사소송법"},
    "민사법": {"인사이트 상법": "상법", "송영곤 민사소송법": "민사소송법",
               "박승수 민법 기본사례": "민법"},
}

# **그 분야만 다루는** 사례집. 통합서는 절대 넣지 않는다(위 설명 참고).
# 공법은 행정법 사례집만 있어서 본문 근거를 아예 쓰지 않는다 — 한쪽만 있으면
# 헌법 쟁점까지 전부 행정법으로 쏠린다.
EXCLUSIVE_BOOKS = {
    "공법": {},
    "형사법": {"사례형사소송법": "형사소송법", "형법 변사기": "형법",
               "작은변사기 형사소송법": "형사소송법"},
    "민사법": {"인사이트 상법 사례형 해설편": "상법", "민소사연": "민사소송법",
               "민법 기본사례": "민법"},
}

MIN_HITS = 3       # 전용 사례집에 이보다 적게 나오면 우연일 수 있다
FLIP_HITS = 20     # 목차 뒷받침 없이 기존 분야를 뒤집으려면 이만큼은 나와야 한다.
                   # 사실관계에 스쳐 나온 낱말(뇌물죄 15회)과 그 책의 논점
                   # (대표소송 249회·명의개서 388회)이 이 선에서 갈린다.
FLIP_SHARE = 0.95  # 뒤집을 때 한 분야가 차지해야 할 최소 비율
MIN_LABEL = 3      # 너무 짧은 쟁점명은 아무 데나 걸린다


def norm(s):
    return re.sub(r"[\s·‧・,()\[\]<>「」『』/.\-–—:;'\"]", "", s or "")


def load(subject):
    toc = json.loads((ROOT / "data" / subject / "casebook_toc.json").read_text("utf-8"))
    labels = defaultdict(list)
    for book, field in TOC_BOOKS[subject].items():
        for part in toc.get(book, {}).get("parts", []):
            for c in part.get("cases", []):
                if c.get("label"):
                    labels[field].append(norm(c["label"]))

    cases = json.loads((ROOT / "data" / subject / "casebook_cases.json").read_text("utf-8"))
    texts = defaultdict(list)
    for v in cases.values():
        field = EXCLUSIVE_BOOKS[subject].get(v.get("book"))
        if field:
            texts[field].append(v.get("text") or "")
    return labels, {f: norm("\n".join(t)) for f, t in texts.items()}


def by_toc(key, labels):
    """목차 항목명과 겹치는 분야. 여러 분야에 걸치면 판정하지 않는다."""
    votes = Counter(f for f, ls in labels.items() for L in ls if key in L or L in key)
    if not votes:
        return None
    (top, n), = votes.most_common(1)
    return top if n > sum(votes.values()) - n else None


def only_in(key, corpus):
    """한 분야 전용 사례집에서만 나오는가. 그렇다면 그 분야, 아니면 None.

    미분류를 채울 때 쓴다. 새로 라벨을 붙이는 일이라 가장 엄격하게 본다.
    """
    hits = {f: t.count(key) for f, t in corpus.items()}
    seen = [f for f, n in hits.items() if n]
    if len(seen) == 1 and hits[seen[0]] >= MIN_HITS:
        return seen[0], hits[seen[0]]
    return None, 0


def dominant(key, corpus):
    """한 분야가 압도적인가. 기존 분야를 뒤집을 때 쓴다.

    "다른 분야에 한 번도 안 나올 것"까지 요구하면 「명의개서」(상법 388회 대
    나머지 4회)처럼 명백한 것도 빠진다. 스쳐 지나간 몇 번은 눈감아 준다.
    """
    hits = {f: t.count(key) for f, t in corpus.items()}
    total = sum(hits.values())
    if not total:
        return None, 0, 0.0
    field, n = max(hits.items(), key=lambda x: x[1])
    share = n / total
    return (field, n, share) if n >= MIN_HITS and share >= FLIP_SHARE else (None, 0, 0.0)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    subjects = args or ["공법", "형사법", "민사법"]
    write = "--write" in sys.argv

    for subject in subjects:
        ipath = ROOT / "data" / subject / "index.json"
        index = json.loads(ipath.read_text(encoding="utf-8"))
        raw = index["issues"]
        issues = list(raw.values()) if isinstance(raw, dict) else raw
        labels, corpus = load(subject)

        before = Counter(it["path"][1] for it in issues)
        filled, moved = [], []
        for it in issues:
            cur = it["path"][1]
            key = norm(it["label"])
            if len(key) < MIN_LABEL:
                continue

            if cur.endswith("일반"):
                got = by_toc(key, labels)
                src = "목차"
                if not got:
                    got, _ = only_in(key, corpus)
                    src = "전용사례집"
                if got:
                    filled.append((it["label"], got, src))
                    if write:
                        it["path"], it["pathSource"] = [subject, got], src
                continue

            # 이미 분야가 붙어 있는 쟁점은 웬만하면 건드리지 않는다. 뒤집을 때는
            # 목차가 같은 분야를 가리키거나, 그게 없으면 등장이 압도적이어야 한다.
            #
            # 목차를 필수로 걸 수는 없다. 책마다 목차의 성격이 달라서다 —
            # 「강성민 헌법/행정법」·「송영곤 민사소송법」의 항목은 쟁점명이지만,
            # 「인사이트 상법」은 사례 지문 첫 문장이고 「이인규 형법」은 편 제목이다.
            # 목차를 필수로 걸었더니 명의개서·대표소송·신주인수권 같은 명백한
            # 상법 쟁점 36건이 통째로 걸러졌다.
            #
            # 그렇다고 본문만 보면 반대로 오판이 난다. 「뇌물죄」가 그렇다 —
            # 형사소송법 사례집에 15회 나오고 형법 사례집에는 안 나오는데, 그건
            # 그 형법 책이 뇌물죄를 안 다뤘을 뿐이지 뇌물죄가 절차법이어서가 아니다.
            # 사실관계에 스쳐 나온 것과 그 책의 논점인 것을 등장 횟수로 가른다.
            got, n, share = dominant(key, corpus)
            backed = got and by_toc(key, labels) == got
            if got and got != cur and (backed or n >= FLIP_HITS):
                moved.append((it["label"], cur, got, n,
                              "목차" if backed else f"{share*100:.0f}%"))
                if write:
                    it["path"] = [subject, got]
                    it["pathSource"] = "목차+전용사례집" if backed else "전용사례집"

        print(f"\n■ {subject}  (이전 {dict(before)})")
        print(f"   미분류 채움 {len(filled)}건 "
              f"{dict(Counter(f'{g}·{s}' for _, g, s in filled))}")
        print(f"   분야 교정 {len(moved)}건 "
              f"{dict(Counter(f'{a}→{b}' for _, a, b, _, _ in moved))}")
        for lab, a, b, n, why in moved:
            print(f"      {lab:28s} {a} → {b}  ({n}회, {why})")
        if write:
            ipath.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            print(f"   결과 {dict(Counter(it['path'][1] for it in issues))} → 기록함")
        else:
            print(f"   결과(예정) {dict(Counter(g for _, g, _ in filled))} 반영 시 "
                  f"미분류 {before.get(subject + '일반', 0) - len(filled)}건 남음")


if __name__ == "__main__":
    main()
