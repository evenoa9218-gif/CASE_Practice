# -*- coding: utf-8 -*-
r"""박승수 「민법 기본사례」 답안 속 «사례풀이구조 표»를 단별로 되돌린다.

기존 `extract_parkss.order_outline` 은 **첫 쪽의 표 하나**에만 걸렸다
(`pages[0]["lines"][opening:ans0]`). 그런데 이 책은 설문마다 표를 하나씩 두고,
설문 (2)·(3) 의 표는 둘째 쪽 이후에 나온다. 그것들은 `_answer` 로 통째로 들어가
**y순으로 읽혀** 3단이 가로로 섞였다. 사례 50 답안이 이렇게 깨졌다:

    1. 이행자처의 요건 / 3. 소결 / ③ 이행자체에 대하여 채무자에게 귀책사유가 있을 것
    Q 甲과 乙은 매매라는 쌍무겨약상의 채무가 / ④ 이행하지 않는 것이 위법할 것

지면(157쪽)에서 이 부분은 `1. 이행지체의 요건 | 2. 甲의 항변 | 3. 소결` 3단 표다.

**표 선이 없다.** 스캔본이라 `get_drawings()` 가 비어 있다. 그래서 **글자가 한 자도
없는 세로 틈(gutter)** 을 단 경계로 삼는다. 서술형 본문은 좌우로 꽉 차 틈이 없어
저절로 걸러진다.

찾지 못하면 **손대지 않는다.** 잘못 자르면 지금보다 나쁘다.
"""

# 표가 놓이는 가로 범위. 본문 왼쪽 여백 ~ 여백 메모 직전.
X_LO, X_HI = 40, 500
# 단 경계로 인정할 틈의 최소 너비(pt)와, 경계가 있을 수 있는 구간
MIN_GUTTER = 5
GUTTER_LO, GUTTER_HI = 130, 470
# 표로 인정할 최소 줄 수 / 한 단에 최소 몇 줄이 있어야 하는가
MIN_ROWS = 6
MIN_PER_BAND = 2



def _gutters(rows):
    """이 줄들이 공통으로 비워 두는 세로 틈의 중앙 x 목록."""
    if not rows:
        return []
    occ = [False] * (X_HI - X_LO + 1)
    for r in rows:
        a = max(X_LO, int(r["x0"]))
        b = min(X_HI, int(r["x1"]))
        for x in range(a, b + 1):
            occ[x - X_LO] = True
    out, s = [], None
    for i, v in enumerate(occ + [True]):
        if not v and s is None:
            s = i
        elif v and s is not None:
            if i - s >= MIN_GUTTER:
                mid = (s + i) // 2 + X_LO
                if GUTTER_LO <= mid <= GUTTER_HI:
                    out.append(mid)
            s = None
    return out


def _bands_ok(rows, cuts):
    """각 단에 줄이 충분히 있어야 진짜 표다. 한 단이 텅 비면 틈이 아니라 우연이다."""
    edges = [X_LO] + cuts + [X_HI + 1]
    for a, b in zip(edges, edges[1:]):
        if sum(1 for r in rows if a <= r["x0"] < b) < MIN_PER_BAND:
            return False
    return True


def _reorder(rows, cuts):
    edges = [X_LO] + cuts + [X_HI + 1]
    out = []
    for a, b in zip(edges, edges[1:]):
        out += [r for r in rows if a <= r["x0"] < b]
    return out if len(out) == len(rows) else rows


def order_tables(lines):
    """줄 목록에서 표 구간을 찾아 단별 읽기 순서로 되돌린다.

    표가 아닌 구간은 원래 순서 그대로 둔다. 반환 길이는 입력과 같다."""
    n = len(lines)
    if n < MIN_ROWS:
        return lines
    out, i = [], 0
    while i < n:
        # i 에서 시작해 «공통 틈»이 유지되는 데까지 늘린다.
        # ⚠ 길이를 우선하면 안 된다 — 창을 넓히면 3단 사이의 좁은 틈이 먼저 막혀
        # 2단으로 잡히고, 1·2단이 한 덩어리로 섞인다(사례 50에서 실제로 났다).
        # **단이 많은 쪽**을 먼저 고르고, 같으면 긴 쪽을 고른다.
        best_j, best_cuts, best_key = -1, None, ()
        j = i + MIN_ROWS - 1
        while j < n:
            win = lines[i:j + 1]
            cuts = _gutters(win)
            if not (1 <= len(cuts) <= 3) or not _bands_ok(win, cuts):
                break
            key = (len(cuts), j)
            if key > best_key:
                best_j, best_cuts, best_key = j, cuts, key
            j += 1
        if best_j >= 0:
            # 표 뒤에 오는 «왼쪽 정렬 짧은 줄»(Ⅱ. 결론·논점의 정리…)까지 창이 뻗는다.
            # 그것들은 표가 아니므로, 마지막 «1단 밖» 줄에서 표를 끊는다.
            while best_j > i and lines[best_j]["x0"] < best_cuts[0]:
                best_j -= 1
            if best_j - i + 1 >= MIN_ROWS:
                out += _reorder(lines[i:best_j + 1], best_cuts)
                i = best_j + 1
                continue
            out.append(lines[i])
            i += 1
        else:
            out.append(lines[i])
            i += 1
    return out if len(out) == n else lines
