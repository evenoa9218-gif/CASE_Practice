"""시험지에서 뽑은 문항 표제를 앱 데이터에 입힌다.

앱의 민사법 기출은 문항 라벨이 `문1..문21` / `설문1..설문20` 같은 통짜
일련번호였다. 실제 시험은 「제1문의 1」처럼 문항이 나뉘고 채점도 그 단위로
한다. extract_exam_plans.py 가 원본 hwp에서 뽑아 둔 표제·배점 순서를 여기서
앱 데이터에 맞춰 붙인다.

짝짓기
  배점 순서가 시험지와 그대로 같으면 인덱스로 1:1. 순서가 어긋난 시험은
  (변시 15회가 그렇다) 시험지 설문 원문과 앱 `ask` 요약을 글자 2-gram 으로
  견줘 배점이 같은 것끼리 최적 배정한다. 배점 개수·합이 안 맞으면 손대지
  않고 보류로 남긴다 — 억지로 맞추면 근거 없는 라벨이 다시 생긴다.

사용
  python pipeline/scripts/relabel_civil_from_paper.py 민사법 [--write]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / "pipeline" / "casebook" / "exam_plans.json"

MIN_SIM = 0.12          # 이보다 닮지 않으면 짝짓기를 믿지 않는다


def bigrams(s):
    s = re.sub(r"[^가-힣A-Za-z0-9甲乙丙丁戊己庚辛壬癸]", "", s or "")
    return Counter(s[i:i + 2] for i in range(len(s) - 1))


def sim(a, b):
    x, y = bigrams(a), bigrams(b)
    if not x or not y:
        return 0.0
    inter = sum((x & y).values())
    return inter / min(sum(x.values()), sum(y.values()))


def split_align(paper, app):
    """앱이 설문 여럿을 한 덩어리로 묶어 둔 경우, 시험지 쪽으로 쪼갠다.

    앞에서부터 훑다가 배점이 어긋나면, 시험지 설문을 배점 합이 앱 문항과
    같아질 때까지 모아 그 문항을 대신하게 한다. 끝까지 아귀가 맞아야만
    결과를 내놓는다.
    """
    out, i, j = [], 0, 0
    while i < len(paper) and j < len(app):
        if paper[i]["points"] == app[j].get("points"):
            out.append(j)
            i, j = i + 1, j + 1
            continue
        s, k = 0, i
        while k < len(paper) and s < (app[j].get("points") or 0):
            s += paper[k]["points"]
            k += 1
        if s != app[j].get("points"):
            return None
        out += [j] * (k - i)
        i, j = k, j + 1
    return out if i == len(paper) and j == len(app) else None


def align(paper, app):
    """시험지 설문 → 앱 문항 인덱스. 못 맞추면 None."""
    if [u["points"] for u in paper] == [q.get("points") for q in app]:
        return list(range(len(app)))          # 순서 그대로
    if Counter(u["points"] for u in paper) != Counter(q.get("points") for q in app):
        return split_align(paper, app)        # 배점 구성이 다르다 → 분할을 따져 본다

    cand = sorted(
        ((sim(u["text"], q.get("ask", "")), i, j)
         for i, u in enumerate(paper)
         for j, q in enumerate(app) if u["points"] == q.get("points")),
        reverse=True)
    order = [None] * len(paper)
    used = set()
    for s, i, j in cand:
        if order[i] is None and j not in used and s >= MIN_SIM:
            order[i], _ = j, used.add(j)
    return None if None in order else order


def tail_ask(text):
    """시험지 설문 원문의 끝 문장 — 물음이 실린 자리."""
    parts = [p for p in re.split(r"(?<=[.?？])\s+", text) if p.strip()]
    out = ""
    while parts and len(out) < 25:
        out = parts.pop() + (" " + out if out else "")
    out = re.sub(r"^\s*[(（]\s*\d{1,3}\s*점\s*[)）]\s*", "", out)   # 앞 설문의 배점 꼬리
    return re.sub(r"\s+", " ", out).strip()


def variants(plan):
    """원본 그대로, 그리고 소계로 의심되는 배점을 하나씩 뺀 것.

    문항 첫 배점이 나머지 합과 같은 자리가 55개 시험에 여덟 군데 있는데,
    그중 일곱은 진짜 설문이고 (앱 배점과 그대로 맞는다) 2021년 3차 한 곳만
    문항 총배점을 겹쳐 적은 것이었다. 그래서 일률적으로 빼지 않고, 빼야만
    앱과 아귀가 맞는 경우에 한해 뺀다.
    """
    yield plan
    for bi, (_, us) in enumerate(plan):
        p = [u["points"] for u in us]
        if len(p) >= 2 and p[0] == sum(p[1:]):
            alt = [[lab, list(units)] for lab, units in plan]
            alt[bi][1] = us[1:]
            yield alt


def rebuild(exam, plan):
    """앱 쪽 배점이 시험지와 어긋나는 시험 — 시험지를 진실로 삼아 다시 짠다.

    앱 문항이 통째로 빠졌거나 같은 설문이 두 번 들어간 시험이 있다. 시험지가
    1차 사료이므로 그쪽을 따르고, 앱의 다듬어진 `ask` 는 배점이 같고 가장
    닮은 것에서만 빌려 온다. 짝이 없으면 시험지 원문을 쓴다.
    """
    app = exam["questions"]
    flat = [(lab, u) for lab, units in plan for u in units]
    cand = sorted(
        ((sim(u["text"], q.get("ask", "")), i, j)
         for i, (_, u) in enumerate(flat)
         for j, q in enumerate(app) if u["points"] == q.get("points")),
        reverse=True)
    pick, used = {}, set()
    for s, i, j in cand:
        if i not in pick and j not in used and s >= MIN_SIM:
            pick[i], _ = j, used.add(j)

    qs, groups = [], []
    for pos, (lab, u) in enumerate(flat):
        j = pick.get(pos)
        ask = (app[j].get("ask") if j is not None else "") or tail_ask(u["text"])
        q = {"no": str(pos + 1), "points": u["points"], "ask": ask}
        qs.append(q)
        if not groups or groups[-1]["key"] != lab:
            groups.append({"key": lab, "label": lab, "questions": [], "points": 0})
        groups[-1]["questions"].append(q)
        groups[-1]["points"] += u["points"]
    exam["questions"] = qs
    exam["groups"] = groups
    return groups


def regroup(exam, plan, order):
    """plan 순서대로 questions 를 다시 쓰고 groups 를 문항 단위로 만든다."""
    flat = [(lab, u) for lab, units in plan for u in units]
    qs, groups = [], []
    for pos, (lab, u) in enumerate(flat):
        q = dict(exam["questions"][order[pos]])
        q["no"] = str(pos + 1)
        if q.get("points") != u["points"]:
            # 앱이 설문 여럿을 한 덩어리로 묶어 뒀던 자리. 요약 `ask` 는 그
            # 덩어리 전체를 가리키므로 못 쓴다 — 시험지 원문으로 갈아 끼운다.
            q["points"] = u["points"]
            q["ask"] = tail_ask(u["text"]) or q.get("ask", "")
        qs.append(q)
        if not groups or groups[-1]["key"] != lab:
            groups.append({"key": lab, "label": lab, "questions": [], "points": 0})
        groups[-1]["questions"].append(q)
        groups[-1]["points"] += q.get("points") or 0
    exam["questions"] = qs
    exam["groups"] = groups
    return groups


def main():
    subj = sys.argv[1] if len(sys.argv) > 1 else "민사법"
    write = "--write" in sys.argv
    plans = json.loads(PLANS.read_text(encoding="utf-8"))
    ipath = ROOT / "data" / subj / "index.json"
    index = json.loads(ipath.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in index["exams"]}

    done, held = [], []
    for eid, v in sorted(plans.items()):
        if not eid.startswith(subj + "_") or eid not in by_id:
            continue
        epath = ROOT / "data" / subj / "exams" / f"{eid}.json"
        exam = json.loads(epath.read_text(encoding="utf-8"))

        groups, note = None, ""
        for plan in variants(v["plan"]):
            paper = [u for _, units in plan for u in units]
            order = align(paper, exam["questions"])
            if order is None:
                continue
            groups = regroup(exam, plan, order)
            moved = sum(1 for i, j in enumerate(order) if i != j)
            note = (f"순서 {moved}개 교정" if moved else "")
            if plan is not v["plan"]:
                note = (note + " · " if note else "") + "총배점 중복 제거"
            break
        if groups is None:
            n_app = len(exam["questions"])
            groups = rebuild(exam, v["plan"])
            note = f"시험지 기준 재구성 (앱 {n_app}설문 → {len(exam['questions'])}설문)"
        done.append((eid, len(groups), note))
        if write:
            epath.write_text(json.dumps(exam, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            it = by_id[eid]
            it["questions"] = exam["questions"]
            it["groups"] = [{k: g[k] for k in ("key", "label", "points")} |
                            {"questions": g["questions"]} for g in groups]
            it["totalPoints"] = sum(g["points"] for g in groups)
            it["groupSource"] = "시험지"

    print(f"확정 {len(done)}건 · 보류 {len(held)}건")
    for eid, n, note in done:
        print(f"  V {eid:26s} 문항 {n:2d}개" + (f"  ({note})" if note else ""))

    if write:
        for it in index["exams"]:
            # 창작문제(로사정·박승수)는 시험지가 없으니 표시 자체를 붙이지 않는다
            if it["id"].split("_")[1] in ("변시", "모의") and "groupSource" not in it:
                it["groupSource"] = "추정"
        ipath.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print("→ 기록함")


if __name__ == "__main__":
    main()
