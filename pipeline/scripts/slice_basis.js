// 사례형 채점 근거를 문항별로 잘라 둔다 — AI 채점 비용 절감.
//
// 왜: 채점 Worker는 문항 하나를 채점할 때 그 회차의 채점기준표·모범답안 **전체**를 모델에 보냈다.
// 형사법 변시 14회는 문항당 11만 자(약 9만 토큰)라 채점 1회에 $0.9 가 들었다.
// 그 문항 몫만 보내면 된다.
//
// 무엇을: data/{과목}/exams/*.json 의 groups[i] 에 `basisSlice` 를 적는다.
//   기준표:   { src:"rubric",   sig:<rubricText 길이>, ranges:[[시작,끝], ...] }
//   모범답안: { src:"casebook", sig:"<답안별 길이를 , 로 이은 것>", idx:[답안 번호, ...] }
//   한 덩어리 답안: { src:"casebookText", sig:<위와 같음>, ai:<답안 번호>, ranges:[[시작,끝]] }
// Worker는 sig 가 지금 데이터와 같을 때만 쓴다. 파이프라인이 데이터를 다시 만들어 원문이
// 바뀌면 sig 가 어긋나 **자동으로 전체 전송으로 돌아간다** — 틀린 조각을 보내는 일은 없다.
// (그래도 데이터를 다시 만든 뒤에는 이 스크립트를 다시 돌려야 절감이 유지된다.)
//
// 어떻게 자르나 — 확실할 때만 자른다. 애매하면 그 회차는 자르지 않는다.
//   기준표: 기준표의 「(N점)」 표시를 앱 문항의 배점 순서와 맞춰 줄 세운다(동적계획법).
//           같은 점수가 여러 번 나오므로 질문 요지(ask)와 그 자리 본문의 낱말 겹침으로 고른다.
//   모범답안: 답안 머리글(「제1문의 2」「문제1」)에서 문·의 번호를 읽어 문항에 붙인다.
//           번호를 못 읽은 답안은 모든 문항에 넣는다(빼는 것보다 넣는 쪽이 안전하다).
//
// 글자 위치는 JS 문자열 기준이어야 Worker(JS)와 어긋나지 않는다 — 그래서 이 스크립트만 JS다.
//
//   node pipeline/scripts/slice_basis.js            보고만 (데이터 안 바꿈)
//   node pipeline/scripts/slice_basis.js --write    데이터에 기록
//   node pipeline/scripts/slice_basis.js --show <examId> <groupKey>   조각 내용 보기

const fs = require('fs');
const path = require('path');

const DATA = path.join(__dirname, '..', '..', 'data');
const WRITE = process.argv.includes('--write');
const SHOW = process.argv.indexOf('--show');

// ── 낱말 겹침 ────────────────────────────────────────────────
const STOP = new Set(('검토 여부 판단 논하시오 서술 서술하시오 경우 대한 관한 대하여 관하여 그리고 이에 따라 ' +
  '어떠한 어떻게 인정 인정되는지 인정될 해당 해당하는지 있는지 없는지 가능 가능한지 가능성 문제 설문 ' +
  '근거 함께 입장 법원 주장 타당 타당한지 위와 같은 이유 사안 사안의 하시오 것인지 경우에 따른 ' +
  '위한 위하여 대해 판례 법리 효력 성립 요건 결론').split(' '));
const words = (s) => [...new Set(((s || '').match(/[가-힣一-鿿]{2,}/g) || [])
  .map((w) => w.replace(/(은|는|이|가|을|를|의|에|에게|에서|으로|로|과|와|도|만|이다|인지|하는지|한|된|되는|하여|하고)$/, ''))
  .filter((w) => w.length >= 2 && !STOP.has(w)))];
function overlap(askWords, text) {
  if (!askWords.length) return 0;
  let hit = 0;
  for (const w of askWords) if (text.includes(w)) hit++;
  return hit / askWords.length;
}

// ── 기준표: 배점 표시 줄 세우기 ─────────────────────────────
const MARK_RE = /[(（]\s*(\d{1,3})\s*점\s*[)）]/g;

function markers(text) {
  const out = [];
  let m;
  MARK_RE.lastIndex = 0;
  while ((m = MARK_RE.exec(text))) {
    const lineStart = text.lastIndexOf('\n', m.index) + 1;
    out.push({ at: m.index, lineStart, pts: +m[1] });
  }
  // 한 줄에 표시가 둘 이상이면(「제2문 (1)(20점)」 같은 경우 말고는 드물다) 첫 것만 쓴다
  return out.filter((x, i) => i === 0 || x.lineStart !== out[i - 1].lineStart);
}

// units: [{pts, askWords}] 을 markers 에 순서대로 대응시킨다. 점수 합이 최대인 경로.
function align(units, marks, text) {
  const K = units.length, M = marks.length;
  const win = marks.map((mk) => text.slice(mk.lineStart, mk.lineStart + 1500));
  const sim = units.map((u) => marks.map((mk, j) => (mk.pts === u.pts ? overlap(u.askWords, win[j]) : -1)));
  const best = Array.from({ length: K }, () => new Array(M).fill(-Infinity));
  const prev = Array.from({ length: K }, () => new Array(M).fill(-1));
  for (let j = 0; j < M; j++) if (sim[0][j] >= 0) best[0][j] = sim[0][j];
  for (let k = 1; k < K; k++) {
    let run = -Infinity, runAt = -1;
    for (let j = 0; j < M; j++) {
      if (j > 0 && best[k - 1][j - 1] > run) { run = best[k - 1][j - 1]; runAt = j - 1; }
      if (sim[k][j] >= 0 && run > -Infinity) { best[k][j] = run + sim[k][j]; prev[k][j] = runAt; }
    }
  }
  let end = -1, top = -Infinity;
  for (let j = 0; j < M; j++) if (best[K - 1][j] > top) { top = best[K - 1][j]; end = j; }
  if (end < 0) return null;
  const path = new Array(K);
  for (let k = K - 1, j = end; k >= 0; k--) { path[k] = j; j = prev[k][j]; }
  return { path, sims: path.map((j, k) => sim[k][j]) };
}

const HEADING = /^\s*(<\s*문\s*제|〈\s*문\s*제|\[?\s*문\s*제\s*\d|제\s*\d+\s*문|\[?\s*설\s*문|[IⅠⅡⅢⅣⅤ]\s*[.．]?\s*$)/;

function sliceRubric(exam) {
  const text = exam.rubricText;
  const groups = exam.groups;
  const marks = markers(text);
  if (marks.length < groups.length) return { ok: false, why: `배점 표시 ${marks.length}개 < 문항 ${groups.length}개` };

  // 문항(질문) 단위로 먼저 맞추고, 안 되면 그룹 단위로
  const qUnits = [], qGroup = [];
  groups.forEach((g, gi) => (g.questions || []).forEach((q) => {
    qUnits.push({ pts: +q.points, askWords: words(q.ask) }); qGroup.push(gi);
  }));
  const gUnits = groups.map((g) => ({ pts: +g.points, askWords: words((g.questions || []).map((q) => q.ask).join(' ')) }));

  let starts = null, level = '';
  const qa = qUnits.length && qUnits.every((u) => u.pts > 0) ? align(qUnits, marks, text) : null;
  if (qa) {
    starts = groups.map((_, gi) => marks[qa.path[qGroup.indexOf(gi)]]);
    level = '질문';
  } else {
    const ga = gUnits.every((u) => u.pts > 0) ? align(gUnits, marks, text) : null;
    if (ga) { starts = ga.path.map((j) => marks[j]); level = '문항'; }
  }
  if (!starts || starts.some((s) => !s)) return { ok: false, why: '배점 순서가 맞지 않음' };

  // 조각 경계: 표시가 있는 줄에서, 바로 위의 짧은 머리글 줄(「<문제>」「문제 2.」)까지 끌어올린다
  const lines = (from) => text.slice(0, from).split('\n');
  const bounds = starts.map((s, gi) => {
    let at = gi === 0 ? 0 : s.lineStart;
    if (gi > 0) {
      // ⚠ 앞 문항의 배점 줄을 넘어 올라가면 안 된다. 넘으면 앞 문항 조각이 머리글만 남고
      //    그 내용이 이 문항에 딸려 온다(형사 모의 2018-2에서 실제로 그랬다 — 짧은 조각 검수가 잡았다).
      for (let n = 0; n < 3; n++) {
        const before = text.lastIndexOf('\n', at - 2) + 1;
        const line = text.slice(before, at).trim();
        if (before <= starts[gi - 1].lineStart) break;
        if (!(line.length <= 40 && (HEADING.test(line) || line === ''))) break;
        at = before;
      }
    }
    return at;
  });
  for (let i = 1; i < bounds.length; i++) if (bounds[i] <= bounds[i - 1]) return { ok: false, why: '경계 역전' };

  const prob = exam.problemText || '';
  const flat = (x) => x.replace(/\s+/g, '');
  const probFlat = flat(prob);
  // 다음 문항 앞에 기준표가 되풀이한 사실관계·안내 줄
  const FACT_HEAD = /^\s*(※\s*아래|<\s*(추가된|기초|공통)|〈\s*(추가된|기초|공통))/;
  const ranges = bounds.map((a, i) => {
    let b = i + 1 < bounds.length ? bounds[i + 1] : text.length;
    // 꼬리 정리: 다음 문항의 사실관계를 기준표가 되풀이한 줄(문제 전문에 그대로 있는 줄)은 뺀다
    for (;;) {
      const ls = text.lastIndexOf('\n', b - 2) + 1;
      const line = text.slice(ls, b).trim();
      if (ls <= a) break;
      if (line === '' || FACT_HEAD.test(line) || (line.length >= 15 && probFlat.includes(flat(line)))) { b = ls; continue; }
      break;
    }
    return [a, b];
  });

  // 검수: 조각마다 자기 문항 요지와 가장 잘 맞아야 한다
  const own = ranges.map(([a, b], gi) => overlap(gUnits[gi].askWords, text.slice(a, b)));
  const cross = ranges.map(([a, b], gi) => Math.max(0, ...gUnits.map((u, j) => (j === gi ? 0 : overlap(u.askWords, text.slice(a, b))))));
  const weak = own.map((o, gi) => (o < 0.3 || o + 0.001 < cross[gi] ? gi : -1)).filter((x) => x >= 0);
  const tiny = ranges.map(([a, b], gi) => (b - a < 150 ? gi : -1)).filter((x) => x >= 0);
  if (tiny.length) return { ok: false, why: `너무 짧은 조각 ${tiny.map((i) => groups[i].key)}` };
  if (weak.length > Math.max(0, Math.floor(groups.length / 5))) {
    return { ok: false, why: `요지와 안 맞는 조각 ${weak.map((i) => `${groups[i].key}(${own[i].toFixed(2)}/${cross[i].toFixed(2)})`)}` };
  }
  return { ok: true, level, ranges, own, cross, weak };
}

// ── 모범답안: 머리글로 붙이기 ───────────────────────────────
function numOf(s) {
  const t = (s || '').replace(/\s+/g, '');
  // 「제1문의2」「1문의2」「제1문-2」「문제1」「제2문」 — 회차 숫자(「10회」)와 헷갈리지 않게 문 앞 숫자만 본다
  let m = t.match(/(?:^|[^0-9회])(\d)문(?:의(\d))?/);
  if (m) return { mun: +m[1], ui: m[2] ? +m[2] : null };
  m = t.match(/문제(\d)/);
  if (m) return { mun: +m[1], ui: null };
  return null;
}

function sliceCasebook(exam) {
  const ans = exam.casebookAnswers;
  const groups = exam.groups;
  const gnum = groups.map((g) => {
    const t = g.key.replace(/\s+/g, '');
    // 「제1문의2」「제1문-3」「제2문」과 로사정 창작문제의 「문1」을 함께 받는다.
    const m = t.match(/제(\d)문(?:의(\d)|-(\d))?/) || t.match(/^문(\d)$/);
    return m ? { mun: +m[1], ui: m[2] ? +m[2] : null } : null;
  });
  if (gnum.some((x) => !x)) return { ok: false, why: '문항 이름에서 번호를 못 읽음' };
  // 「제1문-3」은 제1문 안의 질문이지 「의」가 아니다 — 머리글도 문 단위뿐이다
  const hnum = ans.map((a) => numOf(a.header));
  const sizes = ans.map((a) => (a.answerText || '').length);
  const idx = groups.map((g, gi) => {
    const G = gnum[gi];
    return ans.map((_, i) => i).filter((i) => {
      const H = hnum[i];
      if (!H) return true;                                  // 못 읽은 답안은 모두에 넣는다
      if (H.mun !== G.mun) return false;
      if (H.ui === null || G.ui === null) return true;      // 문 전체 답안이거나, 문 단위 문항
      return H.ui === G.ui;
    });
  });
  const orphan = groups.map((_, gi) => gi).filter((gi) => !idx[gi].some((i) => hnum[i]));
  if (orphan.length) {
    // 머리글을 하나라도 못 읽었으면 그 답안이 이 문항 것일 수 있다 — 판단을 미룬다
    if (hnum.some((h) => !h)) return { ok: false, why: `안 붙은 문항 ${orphan.map((gi) => groups[gi].key)}(못 읽은 머리글 있음)` };
    // 전부 읽었는데도 안 붙으면 사례집에 그 문항 답안이 없는 것이다(민사 변시의 제3문 상법 등).
    // 지금까지는 다른 문항의 모범답안을 근거로 채점하고 있었다 — 근거 없음으로 돌린다.
    if (orphan.length === groups.length) return { ok: false, why: '모든 문항이 안 붙음' };
    // 머리글이 틀렸을 수도 있다 — 문항 요지 낱말이 어떤 답안과 꽤 겹치면 판정을 미룬다
    for (const gi of orphan) {
      const aw = words((groups[gi].questions || []).map((q) => q.ask).join(' '));
      const hit = Math.max(0, ...ans.map((a) => overlap(aw, a.answerText || '')));
      if (hit >= 0.5) return { ok: false, why: `안 붙은 문항 ${groups[gi].key}의 낱말이 답안과 겹침(${hit.toFixed(2)})` };
    }
    for (const gi of orphan) idx[gi] = [];
  }
  const total = sizes.reduce((a, b) => a + b, 0);
  const kept = idx.map((l) => l.reduce((a, i) => a + sizes[i], 0));
  if (kept.every((k) => k === total)) return { ok: false, why: '자를 게 없음(모든 답안이 모든 문항에 붙음)' };
  return { ok: true, idx, kept, total, unread: hnum.filter((h) => !h).length, orphan: orphan.map((gi) => groups[gi].key) };
}

/**
 * 사례집 답안이 회차당 한 덩어리인 경우(로사정 창작문제). 머리글로는 나눌 수 없고,
 * 본문 안에 「〈문제 1〉」 같은 표지가 있어 그 자리에서 자른다.
 * 반환: { ok, ai:<답안 번호>, ranges:[[시작,끝], ...] }  — 문항 순서대로
 */
function sliceCasebookText(exam) {
  const groups = exam.groups;
  const gnum = groups.map((g) => {
    const m = g.key.replace(/\s+/g, '').match(/제?(\d)문$|^문(\d)$/);
    return m ? +(m[1] || m[2]) : null;
  });
  if (gnum.some((x) => !x)) return { ok: false, why: '문항 이름에서 번호를 못 읽음' };
  if (new Set(gnum).size !== gnum.length) return { ok: false, why: '문항 번호가 겹침' };

  if (exam.casebookAnswers.length > 1) return { ok: false, why: '답안이 여럿이라 본문 자르기를 쓰지 않음' };
  const ai = 0;
  const text = exam.casebookAnswers[ai].answerText || '';

  // 표지 표기는 책마다 다르다. 로사정은 「〈문제 1〉」, 박승수는 줄머리의 「[설문 (1)」이다.
  // 「설문 (1)」은 본문 중간에서 앞 설문을 가리키며 나오기도 해서 **줄머리만** 표지로 본다.
  const MARKS = [
    /〈\s*문\s*제?\s*(\d+)\s*〉/g,
    /(?:^|\n)\s*[\[［]?\s*설\s*문\s*[（(]\s*(\d+)\s*[）)]/g,
  ];
  let marks = [];
  for (const re of MARKS) {
    const found = [...text.matchAll(re)]
      .map((m) => ({ no: +m[1], at: m.index + m[0].length - m[0].replace(/^[\s\n]*/, '').length }));
    if (found.length > marks.length) marks = found;
  }
  if (marks.length < 2) return { ok: false, why: '답안 본문에 쓸 만한 문제 표지가 없음' };
  // 표지가 본문에서 다시 언급될 수 있다 — 번호가 올라가는 첫 자리만 경계로 본다.
  const heads = [];
  for (const m of marks) if (!heads.some((h) => h.no === m.no)) heads.push(m);
  for (let i = 1; i < heads.length; i++) if (heads[i].no !== heads[i - 1].no + 1) {
    return { ok: false, why: `문제 표지 번호가 이어지지 않음(${heads.map((h) => h.no)})` };
  }

  const ranges = gnum.map((n) => {
    const i = heads.findIndex((h) => h.no === n);
    if (i < 0) return null;
    return [heads[i].at, i + 1 < heads.length ? heads[i + 1].at : text.length];
  });
  if (ranges.some((r) => !r)) return { ok: false, why: '표지에 없는 문항이 있음' };
  const tiny = ranges.map(([a, b], gi) => (b - a < 150 ? gi : -1)).filter((x) => x >= 0);
  if (tiny.length) return { ok: false, why: `너무 짧은 조각 ${tiny.map((i) => groups[i].key)}` };
  return { ok: true, ai, ranges, kept: ranges.map(([a, b]) => b - a), total: text.length };
}

// ── 원래 형식 그대로 쓰기 ─────────────────────────────────────
// 파이프라인(파이썬)이 쓴 파일은 두 가지다: json.dump(indent=1) 과 한 줄짜리 json.dumps(기본 구분자 ", " ": ").
// JSON.stringify 로 그냥 쓰면 형식이 바뀌어 저장소 diff 가 수만 줄이 된다 — 원래 형식을 따라 쓴다.
function pyDumps(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(pyDumps).join(', ') + ']';
  return '{' + Object.keys(v).map((k) => JSON.stringify(k) + ': ' + pyDumps(v[k])).join(', ') + '}';
}
function dumpLike(raw, obj) {
  const m = raw.match(/^\{\r?\n([ \t]+)/);
  const body = m ? JSON.stringify(obj, null, m[1]) : pyDumps(obj);
  return body + (raw.endsWith('\n') ? '\n' : '');
}

// ── 실행 ───────────────────────────────────────────────────
const report = [];
let before = 0, after = 0, units = 0;
for (const subj of fs.readdirSync(DATA)) {
  const dir = path.join(DATA, subj, 'exams');
  if (!fs.existsSync(dir)) continue;
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    const raw = fs.readFileSync(p, 'utf8');
    const exam = JSON.parse(raw);
    const groups = exam.groups || [];
    let changed = false;
    for (const g of groups) if (g.basisSlice) { delete g.basisSlice; changed = true; }
    if (groups.length < 2) { if (changed && WRITE) fs.writeFileSync(p, dumpLike(raw, exam)); continue; }

    let res, src;
    if (exam.rubricText) { src = 'rubric'; res = sliceRubric(exam); }
    else if (exam.casebookAnswers?.length) {
      src = 'casebook'; res = sliceCasebook(exam);
      if (!res.ok) {
        const alt = sliceCasebookText(exam);
        if (alt.ok) { src = 'casebookText'; res = alt; }
      }
    }
    else { if (changed && WRITE) fs.writeFileSync(p, dumpLike(raw, exam)); continue; }

    const full = src === 'rubric' ? exam.rubricText.length
      : exam.casebookAnswers.reduce((a, x) => a + (x.answerText || '').length, 0);
    units += groups.length; before += full * groups.length;
    if (res.ok) {
      groups.forEach((g, gi) => {
        if (src === 'rubric') {
          g.basisSlice = { src, sig: exam.rubricText.length, ranges: [res.ranges[gi]] };
          after += res.ranges[gi][1] - res.ranges[gi][0];
        } else {
          const sig = exam.casebookAnswers.map((x) => (x.answerText || '').length).join(',');
          g.basisSlice = src === 'casebookText'
            ? { src, sig, ai: res.ai, ranges: [res.ranges[gi]] }
            : { src, sig, idx: res.idx[gi] };
          after += res.kept[gi];
        }
      });
      changed = true;
    } else {
      after += full * groups.length;
    }
    report.push({ id: exam.id, src, ok: res.ok, why: res.why, level: res.level,
      ratio: res.ok ? +((src === 'rubric' ? res.ranges.reduce((a, [x, y]) => a + y - x, 0) : res.kept.reduce((a, b) => a + b, 0)) / (full * groups.length)).toFixed(2) : 1,
      weak: res.weak && res.weak.map((i) => groups[i].key), unread: res.unread, orphan: res.orphan });

    if (SHOW > -1 && exam.id === process.argv[SHOW + 1]) {
      const gi = groups.findIndex((g) => g.key === process.argv[SHOW + 2]);
      const bs = groups[gi]?.basisSlice;
      if (!bs) console.log('조각 없음', res.why);
      else if (bs.src === 'rubric') console.log(exam.rubricText.slice(...bs.ranges[0]));
      else console.log(bs.idx.map((i) => `@@ ${exam.casebookAnswers[i].header}\n${exam.casebookAnswers[i].answerText.slice(0, 400)} …`).join('\n'));
    }
    if (changed && WRITE) fs.writeFileSync(p, dumpLike(raw, exam));
  }
}

if (SHOW < 0) {
  const by = {};
  for (const r of report) {
    const k = r.id.split('_')[0] + '/' + r.src;
    const o = by[k] = by[k] || { exams: 0, sliced: 0, ratioSum: 0, fails: {} };
    o.exams++;
    if (r.ok) { o.sliced++; o.ratioSum += r.ratio; } else { const w = r.why.replace(/[\d().\/,]+/g, '#').slice(0, 30); o.fails[w] = (o.fails[w] || 0) + 1; }
  }
  for (const [k, o] of Object.entries(by)) {
    console.log(`${k}: ${o.sliced}/${o.exams} 자름, 자른 회차 평균 근거 ${(o.sliced ? o.ratioSum / o.sliced * 100 : 0).toFixed(0)}%만 전송`, JSON.stringify(o.fails));
  }
  console.log(`\n다문항 채점단위 ${units}개 — 근거 전송량 ${(before / 1e6).toFixed(1)}M자 → ${(after / 1e6).toFixed(1)}M자 (${(after / before * 100).toFixed(0)}%)`);
  if (process.argv.includes('--list')) for (const r of report) console.log(JSON.stringify(r));
  console.log(WRITE ? '\n데이터에 기록했다.' : '\n보고만 했다. 기록하려면 --write');
}
