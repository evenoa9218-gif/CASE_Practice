# -*- coding: utf-8 -*-
r"""로사정 163사례를 CASE_Practice 민사법 데이터에 얹는다.

    python extract_rosajeong.py     # PDF → pipeline/casebook/rosajeong_cases.json
    python build_rosajeong_민사법.py  # → data/민사법/exams/*.json + index.json + 사례집 목차

기출(변시 15 · 모의 40)과 **같은 스키마**로 넣는다. 다른 점은 `examType`이 `창작문제`이고
공식 채점기준표가 없다는 것뿐이다. 채점 근거는 정연석의 최고답안과 각주가 대신한다.

기존 데이터는 건드리지 않는다 — `민사법_로사정_*` 항목만 걷어내고 새로 붙이므로
몇 번을 다시 돌려도 결과가 같다.
"""
import json
import re
from collections import Counter

from paths import APP, CASEBOOK, REGISTRY
from parse_rosajeong import parse_case
from reflow_rosajeong import build_vocab

DATA = APP / "data" / "민사법"
EXAMS = DATA / "exams"
BOOK = "로스쿨 사례의 정석"
AUTHOR = "정연석"
BOOK_KEY = "정연석 로사정"
PREFIX = "민사법_로사정_"
UID = "md"                       # 사례집 목차용 uid 접두사 (ma/mb/mc는 이미 쓰고 있다)

# 짧은 이름은 아무 데나 걸려서 쟁점 매칭을 망친다("변제"·"상계"는 거의 모든 답안에 나온다).
# 로사정 자체의 논점(=교재 목차)으로 큰 갈래를 잡고, 세부 쟁점만 본문에서 캐낸다.
MIN_LABEL = 4
MAX_ISSUES = 12


def load_cases():
    cases = json.load(open(CASEBOOK / "rosajeong_cases.json", encoding="utf-8"))
    # 문단 재조립용 사전 — 책 전체의 '줄 중간에 온전히 들어 있는 토큰'으로 만든다
    vocab = build_vocab([pg[1].split("\n")
                         for c in cases.values() for pg in c["pages"]])
    out, last = [], None
    for c in sorted(cases.values(), key=lambda x: x["pdfPages"][0]):
        p = parse_case(c, last, vocab)
        last = p["lastFootnote"]
        p.update(part=c["part"], topic=c["topic"],
                 bookPage=c["bookPage"], pdfPages=c["pdfPages"])
        out.append(p)
    return out


def issue_matcher():
    reg = json.load(open(REGISTRY / "issues_민사법.json", encoding="utf-8"))
    pats = []
    for it in reg["issues"]:
        for name in [it["label"]] + it.get("aliases", []):
            key = re.sub(r"[\s·]", "", name)
            if len(key) >= MIN_LABEL:
                pats.append((key, it["id"]))
    by_label = {it["label"]: it["id"] for it in reg["issues"]}
    pats.sort(key=lambda x: -len(x[0]))
    return pats, by_label, reg


def fact_summary(problem):
    """목록 카드에 보일 요약. 표지(〈기초적 사실관계〉)와 지시문(※)은 정보가 없어 뺀다."""
    t = re.sub(r"^[〈<][^〉>\n]*[〉>]\s*", "", problem.strip())
    t = re.sub(r"^\s*※[^\n]*\n?", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:220]


def answer_text(p):
    """모범답안 본문 + 각주. 각주는 판례번호와 해설이 섞여 있는데 둘 다 채점에 쓸모가 있다."""
    t = p["answerText"]
    if p["footnotes"]:
        t += "\n\n─── 각주 ───\n" + "\n".join(f"{n} {x}" for n, x in p["footnotes"])
    return t


def build():
    cases = load_cases()
    pats, by_label, reg = issue_matcher()

    exams_idx, new_cases, toc_parts = [], {}, {}
    for i, p in enumerate(cases, 1):
        no, topic = p["no"], p["topic"] or p["part"]
        eid = f"{PREFIX}{no}_사례"
        flat = re.sub(r"[\s·]", "", p["problemText"] + p["answerText"])

        iids = []
        if topic in by_label:
            iids.append(by_label[topic])
        for key, iid in pats:
            if iid not in iids and key in flat:
                iids.append(iid)
            if len(iids) >= MAX_ISSUES:
                break

        groups = [{"key": f"문{q['no']}", "label": f"문{q['no']}",
                   "questions": [q], "points": q["points"]} for q in p["questions"]]
        total = sum(q["points"] for q in p["questions"])
        label = f"로사정 {no} · {topic}"

        (EXAMS / f"{eid}.json").write_text(json.dumps({
            "id": eid, "label": label,
            "problemText": p["problemText"],
            "rubricText": None,
            "casebookAnswers": [{
                "author": AUTHOR, "area": "민법", "book": BOOK,
                "caseNo": no, "header": f"최고답안 {no}",
                "answerText": answer_text(p),
            }],
            "caseCitations": [], "statutes": [],
            "questions": p["questions"], "groups": groups, "issueIds": iids,
        }, ensure_ascii=False), encoding="utf-8")

        exams_idx.append({
            "id": eid, "label": label, "examType": "창작문제",
            "year": 2026, "round": None, "hoi": None,
            "majorField": "민법", "subFields": [p["part"], topic],
            "issueIds": iids,
            "factSummary": fact_summary(p["problemText"]),
            "questions": p["questions"],
            "groups": [{"key": g["key"], "label": g["label"],
                        "count": 1, "points": g["points"]} for g in groups],
            "totalPoints": total, "hasRubric": False, "hasCasebook": True,
            "unmappedKeywords": [],
            "source": BOOK_KEY, "part": p["part"], "topic": topic,
            "bookPage": p["bookPage"], "tag": p["tag"],
        })

        uid = f"{UID}{i:03d}"
        new_cases[uid] = {
            "title": label,
            "source": {"kind": "창작", "examId": eid, "label": p["tag"] or "신작문제"},
            "area": "민법", "book": BOOK, "author": AUTHOR,
            "text": p["problemText"] + "\n\n" + answer_text(p),
        }
        toc_parts.setdefault(p["part"], []).append({
            "uid": uid, "caseNo": no, "source": p["tag"] or "신작문제",
            "label": f"{topic} — " + fact_summary(p["problemText"])[:60],
            "examId": eid, "groupKey": None, "kind": "창작",
        })

    _merge_index(exams_idx)
    _merge_casebook(new_cases, toc_parts, len(cases))
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


def _merge_casebook(new_cases, toc_parts, n):
    cb = json.load(open(DATA / "casebook_cases.json", encoding="utf-8"))
    cb = {k: v for k, v in cb.items() if not k.startswith(UID)}
    cb.update(new_cases)
    (DATA / "casebook_cases.json").write_text(
        json.dumps(cb, ensure_ascii=False), encoding="utf-8")

    toc = json.load(open(DATA / "casebook_toc.json", encoding="utf-8"))
    toc[BOOK_KEY] = {
        "meta": {"title": f"{AUTHOR} 로스쿨 사례형의 정석 (26.02)", "year": 2026},
        "parts": [{"title": f"{part} ({len(v)}사례)", "cases": v}
                  for part, v in toc_parts.items()],
    }
    (DATA / "casebook_toc.json").write_text(
        json.dumps(toc, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    ex = build()
    idx = json.load(open(DATA / "index.json", encoding="utf-8"))
    print(f"로사정 {len(ex)}건 반영 → 민사법 시험 총 {idx['meta']['examCount']}건")
    print("  PART별: " + " · ".join(f"{k} {v}" for k, v in
                                    Counter(e["part"] for e in ex).items()))
    print(f"  설문 {sum(len(e['questions']) for e in ex)}개 · "
          f"쟁점 매칭 {sum(len(e['issueIds']) for e in ex)}건 "
          f"(사례당 평균 {sum(len(e['issueIds']) for e in ex)/len(ex):.1f})")
    noiss = [e["id"] for e in ex if not e["issueIds"]]
    if noiss:
        print(f"  [주의] 쟁점 0건: {len(noiss)}건 {noiss[:5]}")
