# -*- coding: utf-8 -*-
"""민사법 문항 라벨을 공식 채점기준표 기준으로 재부여한다.

`relabel_groups.py`의 100점 규칙은 민사법에 성립하지 않는다. 제15회 실제 PDF로
확인한 배점은 제1문 150 / 제2문 100 / 제3문 100(합 350)이고, 문항 수도 3개다
(100점 규칙은 4개로 잘랐다). 민사법은 총점이 350점이면서 문당 배점이 일정하지
않으므로 배점 누적으로는 경계를 찾을 수 없다.

대신 채점기준표(`rubricText`)에 `[제N문의 M]` 형식으로 공식 라벨이 들어 있다.
이 라벨 뒤에 인용된 설문 원문을 `problemText`에서 찾아 위치를 확정하고, 그
위치로 설문(배점)을 그룹에 배정한다.

라벨 소스가 없는 시험(변시 15건 등)은 건드리지 않는다 — 근거 없는 라벨을
붙이느니 기존 상태를 두는 편이 낫다. 제15회 변시만 실제 PDF 대조 결과를
`MANUAL`에 직접 넣었다.
"""
import json
import re
import sys
from paths import APP

DATA = APP / 'data' / '민사법'

SEC_RE = re.compile(r'\[\s*제\s*(\d+)\s*문(?:\s*의\s*(\d+))?\s*\]')
PT_RE = re.compile(r'\((\d+)\s*점\)')
# 문제 원문에 시험지 그대로의 문항 표제가 남아 있는 회차가 있다. 가장 신뢰할
# 수 있는 소스라 이것이 있으면 채점기준표보다 우선한다.
HEAD_RE = re.compile(r'[\[\(〈<【]\s*제\s*(\d+)\s*문(?:\s*의\s*(\d+))?\s*[\]\)〉>】]')

# 제15회 변시 — 실제 PDF(제15회 변호사시험 민사법 사례형.pdf)로 직접 대조한 결과.
# 제1문 150(35+15+25+25+30+20) / 제2문 100(20+15+30+35) / 제3문 100(50+50) = 350
#
# order: 시험지 설문 순서 → questions 배열 인덱스. 태깅 데이터가 제2문의2·3을
#   제2문의4 뒤에 넣어 두어(9,10,11 ↔ 12,13) 그대로 자르면 배점이 어긋난다.
# plan: 라벨별 설문 개수. order를 적용한 뒤 순서대로 소비한다.
MANUAL = {
    '민사법_변시_15회_사례': {
        'order': [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 13, 9, 10, 11,
                  14, 15, 16, 17, 18, 19, 20],
        'plan': [
            ('제1문의1', 2), ('제1문의2', 1), ('제1문의3', 1), ('제1문의4', 1),
            ('제1문의5', 1), ('제1문의6', 1),
            ('제2문의1', 2), ('제2문의2', 1), ('제2문의3', 1), ('제2문의4', 3),
            ('제3문의1', 4), ('제3문의2', 3),
        ],
    },
}


# 당사자 표기는 문서마다 한자(甲)와 한글(갑)이 뒤섞인다. 채점기준표가 한글로
# 풀어 쓴 설문을 한자로 된 원문에서 찾으려면 한쪽으로 통일해야 한다.
PARTY = str.maketrans('갑을병정무기경신임계', '甲乙丙丁戊己庚辛壬癸')


def norm(s):
    """위치 매칭용 정규화 — 공백과 문장부호를 걷어낸다.

    채점기준표는 설문을 옮겨 적으면서 띄어쓰기와 괄호가 원문과 미묘하게
    달라지는 일이 잦다. 한글·한자·숫자만 남겨 비교한다.
    """
    return re.sub(r'[^가-힣一-鿿0-9A-Za-z]', '', s.translate(PARTY))


def find_anchor(needle, haystack, min_len=12):
    """정규화한 needle을 haystack에서 찾아 원문 인덱스를 돌려준다.

    haystack의 정규화 위치 → 원문 위치를 되짚기 위해 인덱스 맵을 함께 만든다.
    """
    hn, hmap = [], []
    for i, ch in enumerate(haystack.translate(PARTY)):
        if re.match(r'[가-힣一-鿿0-9A-Za-z]', ch):
            hn.append(ch)
            hmap.append(i)
    hn = ''.join(hn)
    nn = norm(needle)
    for ln in range(min(len(nn), 40), min_len - 1, -1):
        pos = hn.find(nn[:ln])
        if pos >= 0:
            return hmap[pos]
    return -1


def sections_from_rubric(rubric):
    """채점기준표에서 (라벨, 설문원문 후보) 목록을 뽑는다."""
    out = []
    ms = list(SEC_RE.finditer(rubric))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(rubric)
        body = rubric[m.start():end]
        lab = '제%s문' % m.group(1) + ('의%s' % m.group(2) if m.group(2) else '')
        # 헤더 직후 텍스트에서 "문제 N." 같은 머리표를 걷어내고 설문 문장을 집는다
        after = rubric[m.end():end]
        after = re.sub(r'^\s*(?:문제|문)\s*\d*\s*[.,]?\s*', '', after.lstrip())
        out.append((lab, after[:200]))
    return out


def dedup_labels(secs):
    """OCR 중복으로 같은 라벨이 연달아 나오면 첫 것만 남긴다."""
    seen, out = set(), []
    for lab, txt in secs:
        if lab in seen:
            continue
        seen.add(lab)
        out.append((lab, txt))
    return out


def build_groups(exam):
    """한 시험의 groups를 다시 만든다. 실패하면 (None, 사유)."""
    eid = exam['id']
    qs = exam.get('questions') or []
    if not qs:
        return None, '설문 없음'

    if eid in MANUAL:
        spec = MANUAL[eid]
        plan, order = spec['plan'], spec['order']
        if sorted(order) != list(range(len(qs))):
            return None, '수동 매핑 순서표가 설문 %d개와 안 맞음' % len(qs)
        if sum(n for _, n in plan) != len(qs):
            return None, '수동 매핑 설문 수 불일치(%d vs %d)' % (
                sum(n for _, n in plan), len(qs))
        ordered = [qs[i] for i in order]
        groups, at = [], 0
        for lab, n in plan:
            groups.append((lab, ordered[at:at + n]))
            at += n
        return groups, 'PDF 대조'

    rubric = exam.get('rubricText') or ''
    pt = exam.get('problemText') or ''
    marks_all = [m.start() for m in PT_RE.finditer(pt)]

    # 1순위 — 원문에 박혀 있는 시험지 표제
    heads = []
    for m in HEAD_RE.finditer(pt):
        lab = '제%s문' % m.group(1) + ('의%s' % m.group(2) if m.group(2) else '')
        if not heads or heads[-1][0] != lab:
            heads.append((lab, m.start()))
    if len(heads) >= 2 and len(marks_all) == len(qs):
        groups, bad = [], False
        for i, (lab, pos) in enumerate(heads):
            nxt = heads[i + 1][1] if i + 1 < len(heads) else len(pt)
            idx = [j for j, mk in enumerate(marks_all) if pos <= mk < nxt]
            if not idx:
                bad = True
                break
            groups.append((lab, [qs[j] for j in idx]))
        if not bad and sum(len(g[1]) for g in groups) == len(qs):
            return groups, '원문 표제'

    secs = dedup_labels(sections_from_rubric(rubric))
    if len(secs) < 2:
        return None, '채점기준표에 라벨 없음'

    # 각 섹션의 설문 원문을 problemText에서 찾아 위치 확정
    anchors = []
    for lab, txt in secs:
        pos = find_anchor(txt, pt)
        if pos < 0:
            return None, '원문 매칭 실패: %s' % lab
        anchors.append((lab, pos))

    if [p for _, p in anchors] != sorted(p for _, p in anchors):
        return None, '매칭 위치 순서 역전'

    # problemText의 배점 출현 위치 = 설문 경계
    marks = [m.start() for m in PT_RE.finditer(pt)]
    if len(marks) != len(qs):
        return None, '배점 개수 불일치(원문 %d vs 설문 %d)' % (len(marks), len(qs))

    groups = []
    for i, (lab, pos) in enumerate(anchors):
        nxt = anchors[i + 1][1] if i + 1 < len(anchors) else len(pt)
        idx = [j for j, mk in enumerate(marks) if pos <= mk < nxt]
        if not idx:
            return None, '빈 그룹: %s' % lab
        groups.append((lab, [qs[j] for j in idx]))

    used = sum(len(g[1]) for g in groups)
    if used != len(qs):
        return None, '설문 배정 누락(%d/%d)' % (used, len(qs))
    return groups, '채점기준표'


def apply_to_exam(exam):
    groups, why = build_groups(exam)
    if groups is None:
        # 라벨 근거가 없는 시험은 그룹을 건드리지 않되, 지금 붙어 있는
        # "제N문"이 100점 규칙으로 만든 추정값임을 데이터에 남긴다.
        # 민사법은 문당 배점이 일정하지 않아 그 규칙이 성립하지 않는다.
        exam['groupSource'] = 'estimated'
        return False, why
    # 키 순서는 build_case_app_data_민사법.py의 build_groups()와 맞춘다
    exam['groups'] = [{
        'key': lab,
        'label': lab,
        'questions': qs,
        'points': sum(q.get('points') or 0 for q in qs),
    } for lab, qs in groups]
    exam['groupSource'] = {'PDF 대조': 'pdf', '원문 표제': 'exam-heading',
                           '채점기준표': 'rubric'}[why]
    return True, why


def main():
    idx_path = DATA / 'index.json'
    index = json.loads(idx_path.read_text(encoding='utf-8'))
    dry = '--apply' not in sys.argv

    ok, fail = [], []
    changed, sources = {}, {}
    for f in sorted((DATA / 'exams').glob('*.json')):
        exam = json.loads(f.read_text(encoding='utf-8'))
        done, why = apply_to_exam(exam)
        sources[exam['id']] = exam['groupSource']
        if done:
            ok.append((exam['id'], why, len(exam['groups'])))
            changed[exam['id']] = exam['groups']
        else:
            fail.append((exam['id'], why))
        if not dry:
            f.write_text(json.dumps(exam, ensure_ascii=False), encoding='utf-8')

    # index.json의 groups 요약도 같이 맞춘다
    if not dry:
        for it in index.get('exams', []):
            it['groupSource'] = sources.get(it.get('id'), 'estimated')
            g = changed.get(it.get('id'))
            if g:
                it['groups'] = [{'key': x['key'], 'label': x['label'],
                                 'count': len(x['questions']),
                                 'points': x['points']} for x in g]
        idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                            encoding='utf-8')

    print('[%s] 재라벨 %d건 / 보류 %d건' %
          ('적용' if not dry else '미리보기', len(ok), len(fail)))
    for eid, why, n in ok:
        print('  OK  %-32s %-8s 문항 %d개' % (eid, why, n))
    for eid, why in fail:
        print('  --  %-32s %s' % (eid, why))


if __name__ == '__main__':
    main()
