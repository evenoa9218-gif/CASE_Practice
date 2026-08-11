"""사례집이 없는 과목의 쟁점 레지스트리 + 앱 데이터를 한 번에 만든다.

국제법·국제거래법용이다. 이 두 과목은 사례집도 창작문제도 없어서 기존 4단계
(merge_casebook → clean → registry → app_data) 중 뒤 두 단계만 있으면 된다.
과목마다 스크립트를 복사해 두는 대신 과목명과 접두사를 인자로 받는다.

입력  pipeline/source/{과목}_사례_final.json   (태깅 결과 = 정본)
출력  data/{과목}/index.json + exams/*.json, data/issues_{과목}.json

사용
  python pipeline/scripts/build_subject_simple.py 국제법 INT
  python pipeline/scripts/build_subject_simple.py 국제거래법 ITL
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from clean_text import clean_hwp

ROOT = Path(__file__).resolve().parents[2]

# 쟁점명으로 분야를 가른다. 두 과목 다 큰 갈래가 둘씩이라 낱말로 충분히 갈린다.
# 태깅 데이터의 `subFields`에 실제로 쓰인 표현에서 뽑았다.
# 순서가 뜻을 가진다 — 위에서부터 먼저 맞는 분야를 쓴다. 좁은 쪽을 앞에 둬야
# 「근로계약의 준거법」이 국제사법으로 가지 CISG로 새지 않는다.
AREAS = {
    "국제법": [
        ("국제경제법", ["WTO", "GATT", "최혜국", "내국민대우", "반덤핑", "상계관세",
                       "세이프가드", "긴급수입제한", "보조금", "관세", "무역", "수량제한",
                       "일반예외", "일반적예외", "분쟁해결양해", "패널", "상소기구",
                       "동종상품", "SPS", "TBT", "FTA", "특혜", "수입", "수출", "덤핑"]),
        ("국제공법", ["조약", "유보", "국가책임", "대응조치", "외교", "영사", "관할권",
                     "국가면제", "승인", "국제기구", "무력사용", "자위권", "인권", "난민",
                     "해양", "영토", "환경", "재판소", "ICJ", "국적", "보호",
                     "위법성", "강행규범", "불가항력", "긴급피난", "조난", "강박", "강제",
                     "귀속", "국내구제", "국내적구제", "해석", "대세적", "비례성",
                     "전권위임", "지시", "통제", "무효", "월경", "손해배상", "원상회복",
                     "금전배상", "만족", "사건", "협약", "의무", "국가"]),
    ],
    "국제거래법": [
        ("국제사법", ["준거법", "관할", "국제사법", "반정", "공서", "가장밀접",
                     "소비자계약", "근로계약", "부부재산", "상속", "불법행위지",
                     "송달", "외국판결", "승인집행", "물권", "연결", "선결문제",
                     "소재지법", "실질적관련", "실질법", "지정", "선적국", "강행규정",
                     "혼인", "친자", "부양", "행위능력", "법정지", "본국법", "속인법",
                     "지식재산", "해상", "어음수표", "당사자자치", "선택"]),
        ("CISG", ["CISG", "청약", "승낙", "물품", "매도인", "매수인", "인도", "위험",
                  "계약", "대금", "손해배상", "적합성", "검사", "통지", "이행",
                  "본질적", "대체물", "수리", "면책", "이자", "보관", "매매", "협약"]),
    ],
}


def canon(kw):
    k = re.sub(r"\s+", "", kw.strip()).replace("‧", "·").replace("・", "·")
    return k


def area_of(subject, label):
    key = re.sub(r"[\s·()（）]", "", label)
    for area, words in AREAS.get(subject, []):
        if any(w in key for w in words):
            return area
    return subject + "일반"


def group_key(no):
    """문항 라벨. 시험지가 없는 과목이라 태깅 데이터의 설문 번호를 그대로 쓴다."""
    s = re.sub(r"\s", "", no or "")
    m = re.match(r"(설문|문제|질문|제|문)?\s*([0-9１-９]+)", s)
    if m:
        pre = m.group(1) or "문"
        return f"제{m.group(2)}문" if pre == "제" else pre + m.group(2)
    return s[:6] or "기타"


def build_groups(qs):
    groups, order = {}, []
    for q in qs:
        g = group_key(q.get("no"))
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(q)
    return [{"key": g, "label": g, "questions": groups[g],
             "points": sum(q.get("points") or 0 for q in groups[g])} for g in order]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    subject, prefix = sys.argv[1], sys.argv[2]
    src = ROOT / "pipeline" / "source" / f"{subject}_사례_final.json"
    data = json.loads(src.read_text(encoding="utf-8"))

    # ── 쟁점 모으기 ─────────────────────────────────────────
    count, surface = Counter(), defaultdict(set)
    by_exam = defaultdict(set)
    stat_link, case_link = defaultdict(Counter), defaultdict(Counter)
    for r in data:
        for raw in r.get("issueKeywords") or []:
            k = canon(raw)
            count[k] += 1
            surface[k].add(raw.strip())
            by_exam[r["id"]].add(k)
            for s in (r.get("statutes") or [])[:12]:
                stat_link[k][s] += 1
            for c in (r.get("caseCitations") or [])[:12]:
                case_link[k][c] += 1

    ordered = sorted(count, key=lambda k: (-count[k], k))
    issues = [{
        "id": f"{prefix}-{i:04d}",
        "label": k,
        "subject": subject,
        "path": [subject, area_of(subject, k)],
        "aliases": sorted(surface[k] - {k}),
        "examCount": count[k],
        "statutes": [s for s, _ in stat_link[k].most_common(6)],
        "cases": [c for c, _ in case_link[k].most_common(8)],
    } for i, k in enumerate(ordered, start=1)]
    label2id = {it["label"]: it["id"] for it in issues}
    alias2id = {a: it["id"] for it in issues for a in it["aliases"]}

    # ── 앱 데이터 ───────────────────────────────────────────
    out = ROOT / "data" / subject
    exams_dir = out / "exams"
    exams_dir.mkdir(parents=True, exist_ok=True)

    index = []
    for r in data:
        iids, unmapped = [], []
        for raw in r.get("issueKeywords") or []:
            i = label2id.get(canon(raw)) or alias2id.get(raw.strip())
            (iids.append(i) if i else unmapped.append(raw))
        iids = sorted(set(iids))
        qs = r.get("questionStructure") or []
        groups = build_groups(qs)

        index.append({
            "id": r["id"], "label": r["label"], "examType": r["examType"],
            "year": r["year"], "round": r.get("round"), "hoi": r.get("hoi"),
            "majorField": r.get("majorField"), "subFields": r.get("subFields"),
            "issueIds": iids,
            "factSummary": r.get("factSummary"),
            "questions": qs,
            "groups": [{"key": g["key"], "label": g["label"],
                        "count": len(g["questions"]), "points": g["points"]}
                       for g in groups],
            "totalPoints": sum(q.get("points") or 0 for q in qs),
            "hasRubric": bool(r.get("rubricText")),
            "hasCasebook": False,          # 이 두 과목은 사례집이 없다
            # 선택과목 모의고사 일부는 과목별로 분리되지 않은 통합 파일만 남아
            # 있어 지문을 못 뽑았다. 목록에서 눈에 띄게 하려고 표시를 남긴다.
            "hasProblem": len((r.get("problemText") or "").strip()) >= 200,
            "unmappedKeywords": unmapped,
        })
        # hwp 추출본이라 표·그림 자리표시자와 잉여 빈 줄이 그대로 남아 있다.
        # 다른 과목이 `clean_apply_*.py`에서 하는 일을 여기서 함께 한다.
        (exams_dir / f"{r['id']}.json").write_text(json.dumps({
            "id": r["id"], "label": r["label"],
            "problemText": clean_hwp(r.get("problemText") or ""),
            "rubricText": clean_hwp(r.get("rubricText") or ""),
            "casebookAnswers": [],
            "caseCitations": r.get("caseCitations") or [],
            "statutes": (r.get("statutes") or [])[:20],
            "questions": qs,
            "groups": groups,
            "issueIds": iids,
        }, ensure_ascii=False), encoding="utf-8")

    index.sort(key=lambda x: (0 if x["examType"] == "실제기출" else 1,
                              -(x["hoi"] or 0), -x["year"], -(x["round"] or 0)))
    by_issue = {}
    for e in index:
        for i in e["issueIds"]:
            by_issue.setdefault(i, []).append(e["id"])
    used = [it for it in issues if it["id"] in by_issue]

    (out / "index.json").write_text(json.dumps({
        "meta": {"subject": subject, "prefix": prefix,
                 "examCount": len(index), "issueCount": len(used)},
        "issues": [{"id": it["id"], "label": it["label"], "path": it["path"],
                    "examCount": len(by_issue.get(it["id"], []))}
                   for it in sorted(used, key=lambda x: -len(by_issue.get(x["id"], [])))],
        "byIssue": by_issue,
        "exams": index,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (ROOT / "data" / f"issues_{subject}.json").write_text(json.dumps(
        {"subject": subject, "prefix": prefix, "count": len(issues), "issues": issues},
        ensure_ascii=False, indent=1), encoding="utf-8")

    noprob = [e["id"] for e in index
              if len((json.loads((exams_dir / f"{e['id']}.json").read_text('utf-8'))
                      ["problemText"])) < 200]
    print(f"■ {subject} — 시험 {len(index)}건 · 쟁점 {len(used)}종 "
          f"({prefix}-0001~{prefix}-{len(issues):04d})")
    print(f"   분야 {dict(Counter(it['path'][1] for it in used))}")
    print(f"   기준표 있음 {sum(1 for e in index if e['hasRubric'])}건 · "
          f"쟁점 매핑 실패 {sum(len(e['unmappedKeywords']) for e in index)}건")
    if noprob:
        print(f"   [확인 필요] 지문이 없는 시험 {len(noprob)}건: {noprob}")


if __name__ == "__main__":
    main()
