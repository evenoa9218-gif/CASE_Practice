# 박승수 사례집 파일의 파손 유형별 실태 조사.
# 화면에 보이는 증상: ① 문1 아래 무의미한 「1」 ② 금액 OCR 파손 ③ 문장 중간 줄바꿈 ④ 띄어쓰기
# 고치기 전에 각 유형이 몇 건인지부터 센다.
import io, os, re, json, collections

D = r"C:\Users\82109\CASE_Practice\data\민사법\exams"
files = sorted(f for f in os.listdir(D) if "박승수" in f and f.endswith(".json"))

cnt = collections.Counter()
samples = collections.defaultdict(list)


def note(k, fn, s=""):
    cnt[k] += 1
    if len(samples[k]) < 6:
        samples[k].append("%s  %s" % (fn.replace("민사법_박승수_", "").replace("_사례.json", ""), s))


# 금액·숫자 OCR 파손 후보
MONEY_BAD = re.compile(r"\d[,\.]?\s*\(\s*[Xx]+\s*\)|\(\s*[Xx]+\s*\)\s*만|[0-9]\s*,\s*\(")
# 문장 중간 줄바꿈 — 개행 앞이 종결부호가 아니고 뒤가 이어지는 말
MID_BREAK = re.compile(r"[가-힣A-Za-z0-9,·]\n(?=[가-힣])")
# 흔한 OCR 글자 파손
GLYPH = re.compile(r"[０-９]|[Ａ-Ｚａ-ｚ]|[ｰ]|[·]{2,}|[一]\s|\bffi\b|囚|ffl|Sffli")

for fn in files:
    p = os.path.join(D, fn)
    j = json.load(io.open(p, encoding="utf-8"))
    pt = j.get("problemText") or ""

    # ① 비어 있는 질문 — 화면에 「1」만 뜨는 원인
    qs = j.get("questions") or []
    if qs and all(not (q.get("ask") or "").strip() for q in qs):
        note("① 질문 ask 전부 빈값", fn, "questions=%d" % len(qs))
    elif any(not (q.get("ask") or "").strip() for q in qs):
        note("① 질문 ask 일부 빈값", fn)
    if not qs:
        note("① questions 자체가 없음", fn)

    gs = j.get("groups") or []
    for g in gs:
        gq = g.get("questions") or []
        if gq and all(not (q.get("ask") or "").strip() for q in gq):
            note("① 그룹 질문도 빈값", fn, g.get("key", ""))
            break

    # ② 금액·숫자 파손
    m = MONEY_BAD.search(pt)
    if m:
        i = m.start()
        note("② 금액 OCR 파손", fn, "…" + pt[max(0, i - 25):i + 25].replace("\n", "⏎") + "…")

    # ③ 문장 중간 줄바꿈
    n = len(MID_BREAK.findall(pt))
    if n:
        mm = MID_BREAK.search(pt)
        i = mm.start()
        note("③ 문장 중간 줄바꿈", fn, "%d건  …%s…" % (n, pt[max(0, i - 20):i + 20].replace("\n", "⏎")))

    # ④ 설문이 problemText 에 없고 답안 앞머리에 밀려 있는지
    ans = ""
    for a in (j.get("casebookAnswers") or []):
        ans += a.get("answerText") or ""
    q_in_prob = len(re.findall(r"^\s*\(\d\)", pt, re.M))
    q_in_ans = len(re.findall(r"^\s*\(\d\)", ans[:1500], re.M))
    if q_in_ans and q_in_ans > 0:
        note("④ 설문이 답안 앞머리로 밀림", fn, "본문 %d개 / 답안머리 %d개" % (q_in_prob, q_in_ans))

    # ⑤ 글자 파손
    if GLYPH.search(pt):
        note("⑤ 본문 글자 파손", fn)

    if not pt.strip():
        note("⑥ problemText 비어 있음", fn)

out = io.open(r"C:\Users\82109\CASE_Practice\pipeline\_survey.txt", "w", encoding="utf-8")
out.write("박승수 파일 %d개\n\n" % len(files))
for k in sorted(cnt, key=lambda x: -cnt[x]):
    out.write("%-28s %4d건\n" % (k, cnt[k]))
    for s in samples[k]:
        out.write("      " + s + "\n")
    out.write("\n")
out.close()
print("ok")
