# -*- coding: utf-8 -*-
r"""박승수 「민법 기본사례」 286사례를 CASE_Practice 민사법 데이터에 얹는다.

    set CASE_PDF_ROOT=D:\pdf
    python parse_parkss_toc.py
    python extract_parkss.py
    python build_parkss_민사법.py

로사정과 같은 **창작문제**로 넣는다(`build_rosajeong_민사법.py`와 같은 규약).
다른 점은 이 책이 **친족상속법 22사례를 다룬다**는 것이다 — 로사정에는 없는 영역이고,
노션 「로민정 단원」의 가족법 22단원을 채울 수 있는 유일한 자료다.

기존 데이터는 건드리지 않는다 — `민사법_박승수_*`만 걷어내고 새로 붙이므로 몇 번을 돌려도 같다.
"""
import json
import re
from collections import Counter

from paths import APP, CASEBOOK, REGISTRY

DATA = APP / "data" / "민사법"
EXAMS = DATA / "exams"
BOOK = "민법 기본사례"
AUTHOR = "박승수"
BOOK_KEY = "박승수 민법 기본사례"
PREFIX = "민사법_박승수_"
UID = "me"                       # ma/mb/mc/md는 이미 쓰고 있다
DEFAULT_POINTS = 20              # 배점 표시가 없는 123건 — 표시된 163건의 중앙값

MIN_LABEL = 4                    # 짧은 이름은 아무 데나 걸려 쟁점 매칭을 망친다
MAX_ISSUES = 12

PTS = re.compile(r"[(（]\s*(\d{1,3})\s*점\s*[)）]")
STARS = re.compile(r"\s*[(（]?\s*[★☆大*수]{1,4}\s*[)）]?\s*")
# 제목 끝에 붙은 기출 표시. 사례 메타로 따로 뽑는다.
SRC = re.compile(r"(변호사\s*['’`]?\s*\d\d|사시\s*기출|법전협\s*['’`]?\s*\d\d|"
                 r"법무사\s*['’`]?\s*\d\d|최근\s*변?경?\s*판[례레]\s*사?안?)")


# 제목에 남으면 안 되는 이물질. 개수를 세어 덜 깨진 쪽을 고른다.
TITLE_JUNK = re.compile(r"[^가-힣0-9\s()·\-—,.:'\"「」『』〈〉A-Za-z]")
# 본문 헤더는 `사레 274 …` 꼴이라 앞머리와 뒤의 기출표시를 떼야 비교가 된다.
HEAD_STRIP = re.compile(r"^\s*[사새시샤셔人ᄉ][^\d\s]{0,3}\s*\d{1,3}\s*")


def clean_title(t):
    t = STARS.sub(" ", t)
    t = SRC.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip(" .·-—()（）")
    return t


def best_title(toc_title, raw_header):
    """목차와 본문 헤더 중 **덜 깨진 쪽**을 제목으로 쓴다.

    둘 다 OCR이라 어느 쪽이 성한지는 사례마다 다르다(`낙태행위^ 샹속결격` 대
    `낙태행우！뫄 삼속결껵`). 이물질 개수로 고르고, 비기면 목차를 쓴다 —
    목차는 사례 번호와 짝이 맞는 것이 확인된 자료다.
    """
    a = clean_title(toc_title)
    b = clean_title(HEAD_STRIP.sub("", raw_header)) if HEAD_STRIP.match(raw_header) else ""
    if b and len(b) >= max(4, len(a) * 0.7) and _hangul(b) > _hangul(a) \
            and len(TITLE_JUNK.findall(b)) < len(TITLE_JUNK.findall(a)):
        return b
    return a or b or "(제목 확인 필요)"


def _hangul(s):
    """한글 비율. 낱말이 통째로 라틴으로 흘러버린 제목(`다바mi`)을 거른다."""
    return len(re.findall(r"[가-힣]", s)) / max(1, len(re.sub(r"\s", "", s)))


def load_cases():
    return json.load(open(CASEBOOK / "parkss_basic_cases.json", encoding="utf-8"))


def issue_matcher():
    reg = json.load(open(REGISTRY / "issues_민사법.json", encoding="utf-8"))
    pats = []
    for it in reg["issues"]:
        for name in [it["label"]] + it.get("aliases", []):
            key = re.sub(r"[\s·]", "", name)
            if len(key) >= MIN_LABEL:
                pats.append((key, it["id"]))
    pats.sort(key=lambda x: -len(x[0]))
    return pats, {it["label"]: it["id"] for it in reg["issues"]}


def questions_of(c):
    """배점 표시로 설문을 나눈다. 표시가 없으면 사례 하나를 설문 하나로 본다."""
    found = PTS.findall(c["problemText"])
    if len(found) >= 2:
        return [{"no": i, "points": int(v), "ask": ""}
                for i, v in enumerate(found, 1)], False
    if len(found) == 1:
        return [{"no": 1, "points": int(found[0]), "ask": ""}], False
    return [{"no": 1, "points": DEFAULT_POINTS, "ask": ""}], True


def fact_summary(problem):
    t = re.sub(r"^[〈<][^〉>\n]*[〉>]\s*", "", problem.strip())
    t = re.sub(r"\s+", " ", t).strip()
    return t[:220]


def answer_text(c):
    """모범답안 + 답안 개요 + 여백 메모. 셋 다 채점에 쓸모가 있어 표지만 달아 붙인다."""
    t = c["answerText"]
    if c["outlineText"]:
        t += "\n\n─── 답안 개요 ───\n" + c["outlineText"]
    if c["notes"]:
        t += "\n\n─── 여백 메모 ───\n" + "\n".join(c["notes"])
    return t


def build():
    cases = load_cases()
    pats, by_label = issue_matcher()

    exams_idx, new_cases, toc_parts = [], {}, {}
    for i, no in enumerate(sorted(cases, key=int), 1):
        c = cases[no]
        title = best_title(c["title"], c["rawHeader"])
        part = c["part"] or "제1편 민법총칙"
        eid = f"{PREFIX}{int(no):03d}_사례"
        flat = re.sub(r"[\s·]", "", c["problemText"] + c["answerText"])

        iids = []
        for key, iid in pats:
            if iid not in iids and key in flat:
                iids.append(iid)
            if len(iids) >= MAX_ISSUES:
                break

        qs, guessed = questions_of(c)
        groups = [{"key": f"문{q['no']}", "label": f"문{q['no']}",
                   "questions": [q], "points": q["points"]} for q in qs]
        total = sum(q["points"] for q in qs)
        src = SRC.search(c["title"] + " " + c["rawHeader"])
        label = f"박승수 {int(no)} · {title}"

        (EXAMS / f"{eid}.json").write_text(json.dumps({
            "id": eid, "label": label,
            "problemText": c["problemText"],
            "rubricText": None,
            "casebookAnswers": [{
                "author": AUTHOR, "area": "민법", "book": BOOK,
                "caseNo": int(no), "header": f"모범답안 {int(no)}",
                "answerText": answer_text(c),
            }],
            "caseCitations": [], "statutes": [],
            "questions": qs, "groups": groups, "issueIds": iids,
        }, ensure_ascii=False), encoding="utf-8")

        exams_idx.append({
            "id": eid, "label": label, "examType": "창작문제",
            "year": 2025, "round": None, "hoi": None,
            "majorField": "민법", "subFields": [part, title],
            "issueIds": iids,
            "factSummary": fact_summary(c["problemText"]),
            "questions": qs,
            "groups": [{"key": g["key"], "label": g["label"],
                        "count": 1, "points": g["points"]} for g in groups],
            "totalPoints": total, "hasRubric": False, "hasCasebook": True,
            "unmappedKeywords": [],
            "source": BOOK_KEY, "part": part, "topic": title,
            "stars": c["stars"], "bookPage": c["bookPage"],
            "tag": src.group(0) if src else None,
            "pointsGuessed": guessed,
        })

        uid = f"{UID}{i:03d}"
        new_cases[uid] = {
            "title": label,
            "source": {"kind": "창작", "examId": eid,
                       "label": src.group(0) if src else "기본사례"},
            "area": "민법", "book": BOOK, "author": AUTHOR,
            "text": c["problemText"] + "\n\n" + answer_text(c),
        }
        toc_parts.setdefault(part, []).append({
            "uid": uid, "caseNo": int(no),
            "source": src.group(0) if src else "기본사례",
            "label": f"{title} — " + fact_summary(c["problemText"])[:60],
            "examId": eid, "groupKey": None, "kind": "창작",
        })

    _merge_index(exams_idx)
    _merge_casebook(new_cases, toc_parts)
    return exams_idx


def _merge_index(exams_idx):
    idx = json.load(open(DATA / "index.json", encoding="utf-8"))
    idx["exams"] = [e for e in idx["exams"] if not e["id"].startswith(PREFIX)] + exams_idx

    by_issue = {}
    for e in idx["exams"]:
        for i in e["issueIds"]:
            by_issue.setdefault(i, []).append(e["id"])
    idx["byIssue"] = by_issue

    reg = json.load(open(REGISTRY / "issues_민사법.json", encoding="utf-8"))
    known = {it["id"]: it for it in reg["issues"]}
    idx["issues"] = sorted(
        ({"id": i, "label": known[i]["label"], "path": known[i]["path"],
          "examCount": len(v)} for i, v in by_issue.items() if i in known),
        key=lambda x: -x["examCount"])
    idx["meta"]["examCount"] = len(idx["exams"])
    idx["meta"]["issueCount"] = len(idx["issues"])
    (DATA / "index.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")


def _merge_casebook(new_cases, toc_parts):
    cb = json.load(open(DATA / "casebook_cases.json", encoding="utf-8"))
    cb = {k: v for k, v in cb.items() if not k.startswith(UID)}
    cb.update(new_cases)
    (DATA / "casebook_cases.json").write_text(
        json.dumps(cb, ensure_ascii=False), encoding="utf-8")

    toc = json.load(open(DATA / "casebook_toc.json", encoding="utf-8"))
    toc[BOOK_KEY] = {
        "meta": {"title": f"{AUTHOR} {BOOK} (2025)", "year": 2025},
        "parts": [{"title": f"{p} ({len(v)}사례)", "cases": v}
                  for p, v in toc_parts.items()],
    }
    (DATA / "casebook_toc.json").write_text(
        json.dumps(toc, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    ex = build()
    idx = json.load(open(DATA / "index.json", encoding="utf-8"))
    print(f"박승수 기본사례 {len(ex)}건 반영 → 민사법 시험 총 {idx['meta']['examCount']}건")
    print("  편별: " + " · ".join(f"{k} {v}" for k, v in Counter(e["part"] for e in ex).items()))
    print(f"  설문 {sum(len(e['questions']) for e in ex)}개 "
          f"(배점 추정 {sum(1 for e in ex if e['pointsGuessed'])}건)")
    print(f"  쟁점 매칭 {sum(len(e['issueIds']) for e in ex)}건 "
          f"(사례당 평균 {sum(len(e['issueIds']) for e in ex)/len(ex):.1f})")
    noiss = [e["id"] for e in ex if not e["issueIds"]]
    if noiss:
        print(f"  [주의] 쟁점 0건: {len(noiss)}건 {noiss[:5]}")
