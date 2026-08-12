# -*- coding: utf-8 -*-
r"""`parkss_text_fixes` 를 `parkss_basic_cases.json` 에 적용한다.

    python fix_parkss_apply.py            # 드라이런 — 무엇이 바뀌는지만 본다
    python fix_parkss_apply.py --write    # 실제로 쓴다

여러 번 돌려도 결과가 같다(멱등). 결과는 `pipeline/work/_parkss_fix_report.txt`.
"""
import io, json, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parkss_text_fixes as F

SRC = r"C:\Users\82109\CASE_Practice\pipeline\casebook\parkss_basic_cases.json"
REP = r"C:\Users\82109\CASE_Practice\pipeline\work\_parkss_fix_report.txt"

write = "--write" in sys.argv
cases = json.load(io.open(SRC, encoding="utf-8"))

out = io.open(REP, "w", encoding="utf-8")
n_num = n_join = n_pull = 0
for no in sorted(cases, key=lambda x: int(x)):
    c = cases[no]
    p0, a0 = c.get("problemText") or "", c.get("answerText") or ""
    p1, a1, moved = F.apply(p0, a0, no)

    if F.fix_numbers(p0) != p0 or F.fix_numbers(a0) != a0:
        n_num += 1
        out.write("[숫자] 사례 %s\n" % no)
        for m in re.finditer(r".{0,45}\(\s*X[XW]?\s*\).{0,25}", p0 + "\n" + a0):
            out.write("   전: %s\n" % m.group(0).replace("\n", " "))
        for m in re.finditer(r".{0,45}000.{0,25}", (p1 + "\n" + a1)[:0] or ""):
            pass
        out.write("\n")
    if F.join_wrapped(p0) != p0:
        n_join += 1
    if moved:
        n_pull += 1
        out.write("[설문 되돌림] 사례 %s — %d개\n" % (no, moved))
        out.write("   %s\n\n" % p1[len(F.join_wrapped(F.fix_numbers(p0))):].strip()[:220].replace("\n", " / "))

    c["problemText"], c["answerText"] = p1, a1

out.write("\n=== 요약 ===\n숫자 교정 %d건 / 줄바꿈 정리 %d건 / 설문 되돌림 %d건 (전체 %d)\n"
          % (n_num, n_join, n_pull, len(cases)))
out.close()

if write:
    io.open(SRC, "w", encoding="utf-8").write(json.dumps(cases, ensure_ascii=False))
    print("적용 완료 →", SRC)
else:
    print("드라이런 — 쓰지 않았다.")
print("숫자 %d / 줄바꿈 %d / 설문되돌림 %d" % (n_num, n_join, n_pull))
print("리포트:", REP)
