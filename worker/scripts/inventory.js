// 반영 자료 목록 — 네 앱(암기장·선택형·사례형·기록형)에 무슨 과목·무슨 유형에 무슨 책이 들어 있는지
// **데이터에서 직접 세어** 표로 만든다. 손으로 적은 목록은 금방 낡는다.
//
//   npm run inventory            세어서 화면에 찍는다
//   npm run inventory -- --push  D1(admin_kv.inventory)에 올린다 → 관리자 앱 「반영 자료」 탭에 뜬다
//
// 공개 저장소에 책 목록을 따로 내걸지 않으려고 D1 에 두고, 관리자 열쇠가 있어야 읽게 했다.
// 형제 저장소가 같은 폴더 아래 있어야 한다: CASE_Practice · RECORD · MCQ_check · Core_Notes
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const os = require('os');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '..', '..', '..');
const P = (...a) => path.join(ROOT, ...a);
const J = (f) => JSON.parse(fs.readFileSync(f, 'utf8').replace(/^﻿/, ''));
const rows = [];
const add = (app, subject, kind, title, count, unit, note) => rows.push({ app, subject, kind, title, count, unit: unit || '', note: note || '' });
// 「(26.04)[강성민] 행정법 사례형 연습 OCR.txt」 → 「행정법 사례형 연습 (26.04)」
const bookName = (b) => { const y = (b.match(/^\(([\d.]+)\)/) || [])[1]; return b.replace(/\.txt$/, '').replace(/^\([\d.]+\)\s*/, '').replace(/^\[[^\]]+\]\s*/, '').replace(/^강성민\s+|^류정모\s+/, '').replace(/\s*(ocr|OCR)(\+선명도)?$/, '').trim() + (y ? ` (${y})` : ''); };
const span = (a) => { a = a.filter((x) => x != null).sort((x, y) => x - y); return a.length ? (a[0] === a[a.length - 1] ? String(a[0]) : `${a[0]}~${a[a.length - 1]}`) : ''; };

// ── 사례형 ─────────────────────────────────────────────
{
  const dir = P('CASE_Practice', 'data');
  for (const s of fs.readdirSync(dir).filter((x) => fs.existsSync(path.join(dir, x, 'index.json')))) {
    const ix = J(path.join(dir, s, 'index.json'));
    const by = {};
    for (const e of ix.exams) (by[e.examType] = by[e.examType] || []).push(e);
    for (const [type, list] of Object.entries(by)) {
      const isMock = type === '모의고사', isBar = /변호사시험|변시|실제기출/.test(type);
      const range = isMock ? `${span(list.map((e) => e.year))}년` : isBar ? `제${span(list.map((e) => e.hoi))}회` : '';
      const src = isMock ? '법전협 모의시험 문제지' : isBar ? '법무부 변호사시험 문제지' : '사례집 수록 문제';
      add('사례형', s, '문제', `${isBar ? '변호사시험' : type} ${range}`.trim(), list.length, '회차', src + (list.some((e) => e.hasProblem === false) ? ` · 문제지 없는 회차 ${list.filter((e) => e.hasProblem === false).length}` : ''));
      const rub = list.filter((e) => e.hasRubric).length;
      if (rub) add('사례형', s, '채점기준표', `${type} 공식 채점기준표`, rub, '회차', isMock ? '법전협 배포본' : '');
    }
    const books = {};
    for (const e of ix.exams) {
      const d = J(path.join(dir, s, 'exams', e.id + '.json'));
      for (const a of d.casebookAnswers || []) {
        const k = [a.author, a.book || '', a.area || ''].join('|');
        const b = books[k] || (books[k] = { author: a.author, book: a.book || '', area: a.area || '', n: 0, exams: new Set(), chars: 0, types: new Set() });
        b.n++; b.exams.add(e.id); b.chars += (a.answerText || '').length; b.types.add(e.examType);
      }
    }
    for (const b of Object.values(books)) {
      add('사례형', s, '모범답안', `${b.author} 「${bookName(b.book)}」`, b.n, '답안',
        `${b.area} · ${b.exams.size}회차에 연결 · ${Math.round(b.chars / 1000)}천 자 · ${[...b.types].join('+')}`);
    }
  }
}

// ── 기록형 ─────────────────────────────────────────────
{
  const dir = P('RECORD', 'data');
  for (const s of ['공법', '민사법', '형사법']) {
    const ix = J(path.join(dir, s, 'index.json'));
    const by = {};
    for (const e of ix.exams) (by[e.kind] = by[e.kind] || []).push(e);
    for (const [kind, list] of Object.entries(by)) {
      const mock = kind === '모의';
      add('기록형', s, '문제', mock ? `법전협 모의시험 ${span(list.map((e) => +e.year))}년` : `변호사시험 제${span(list.map((e) => +(e.id.match(/변시_(\d+)회/) || [])[1]))}회`, list.length, '회차', mock ? '법전협 모의시험 기록' : '법무부 변호사시험 기록');
      const rub = list.filter((e) => e.hasRubric).length;
      if (rub) add('기록형', s, '채점기준표', `${mock ? '모의시험' : '변호사시험'} 공식 채점기준표`, rub, '회차', '');
    }
    const books = {};
    for (const e of ix.exams.filter((x) => x.hasCommentary)) {
      const d = J(path.join(dir, s, 'exams', e.id + '.json'));
      for (const c of d.commentaries || []) {
        const k = c.author + '|' + (c.title || '');
        const b = books[k] || (books[k] = { author: c.author, title: c.title || '', n: 0, cut: 0 });
        b.n++; if (c.truncated) b.cut++;
      }
    }
    for (const b of Object.values(books)) add('기록형', s, '해설', `${b.author} 「${b.title}」`, b.n, '회차', b.cut ? `분량이 많아 앞부분만 실은 회차 ${b.cut}` : '');
  }
}

// ── 선택형 ─────────────────────────────────────────────
{
  const dir = P('MCQ_check');
  const PAGES = [['index.src.html', '민사법'], ['criminal.html', '형사법'], ['public-law.html', '공법']];
  // 앱 화면에 적힌 출처 그대로(쪽 제목·안내문)
  const SRC = { 민사법: '「3000제 OX」 민법·민소법 선택형 기출', 형사법: '「반반OX」 형사법 선택형 기출 최신빈출지문' };
  const count = (f) => { try { const d = J(path.join(dir, 'data', f)); return Array.isArray(d) ? d.length : Object.keys(d).length; } catch (e) { return null; } };
  for (const [page, subj] of PAGES) {
    const s = fs.readFileSync(path.join(dir, page), 'utf8');
    const a = s.indexOf('MODULE_REGISTRY');
    const blk = s.slice(a, a + 60000);
    const re = /id:\s*"([^"]+)",\s*label:\s*"([^"]+)"/g;
    let m;
    while ((m = re.exec(blk))) {
      const [, id, label] = m;
      if (['civil', 'criminal', 'public'].includes(id)) continue;
      const tail = blk.slice(m.index, m.index + 500);
      const sub = (tail.match(/subtitle:\s*"([^"]*)"/) || [])[1] || '';
      const status = (tail.match(/status:\s*"(\w+)"/) || [])[1] || '';
      const n = count(id + '.json');
      if (id === '회차모아') { add('선택형', subj, '문항 묶음', `${label} (${sub})`, +(tail.match(/count:\s*(\d+)/) || [])[1] || null, '문항', '다른 모듈의 문항을 회차별로 다시 모은 것 — 새 자료 아님'); continue; }
      if (id === '상법') {
        add('선택형', subj, 'OX', '상법 · 김남훈 기출지문총정리 (단원별)', count('상법.json'), '지문', '변시 지문');
        add('선택형', subj, 'OX', '상법 · 기말범위 OX (회차별)', count('상법기말OX.json'), '지문', '변시 1~15회 + 법전협 모의 2024~2026 5지선다 선지를 OX 로');
        add('선택형', subj, '5지선다', '상법 · 5지선다 원문 (회차별)', count('상법5지.json'), '문항', '법무부·법전협 원본 문제지');
        continue;
      }
      if (/모의26$/.test(id)) { add('선택형', subj, '5지선다', `${label} · ${sub}`, n, '문항', '법전협 모의시험 원본 문제지·정답표 (8월 민사·공법은 스캔본을 옮긴 것, 해설 없음)'); continue; }
      if (n === null && !sub) continue;
      add('선택형', subj, 'OX', `${label}${sub && sub !== label ? ' · ' + sub : ''}`, n, '문항', status === 'soon' ? '준비 중 — 아직 문항 없음' : (SRC[subj] || ''));
    }
  }
}

// ── 암기장 ─────────────────────────────────────────────
{
  const dir = P('Core_Notes');
  const html = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
  const a = html.indexOf('const DATASETS = {');
  const blk = html.slice(a, html.indexOf('};', a));
  const win = {};
  const ctx = vm.createContext({ window: win, console });
  for (const f of fs.readdirSync(dir).filter((x) => /^data-(?!examlinks)[\w-]+\.js$/.test(x))) {
    try { vm.runInContext(fs.readFileSync(path.join(dir, f), 'utf8'), ctx); } catch (e) { /* 일부는 전역에 기대어 있다 */ }
  }
  const re = /([가-힣]+):\s*\{\s*key:'(\w+)',\s*label:'([^']+)',\s*unit:'([^']+)'/g;
  let m;
  while ((m = re.exec(blk))) {
    const [, subj, key, label, unit] = m;
    const v = win[key];
    const n = Array.isArray(v) ? v.length : v && typeof v === 'object' ? Object.keys(v).length : null;
    add('암기장', subj.replace('행정법강성민', '행정법'), '교재', label, n, unit, '');
  }
  const ex = fs.readdirSync(dir).filter((x) => /^data-examlinks-.+\.js$/.test(x)).length;
  if (ex) add('암기장', '전 과목', '기출 연결', '논점별 기출·채점기준표 연결', ex, '과목 파일', '사례형·선택형 기출을 암기장 논점에 이어 붙인 것');
}

// ── 내보내기 ───────────────────────────────────────────
const inv = { generated: new Date().toISOString(), rows };
if (!process.argv.includes('--push')) {
  let last = '';
  for (const r of rows) {
    const head = `${r.app} · ${r.subject}`;
    if (head !== last) { console.log('\n■ ' + head); last = head; }
    console.log(`   [${r.kind}] ${r.title} — ${r.count == null ? '?' : r.count.toLocaleString()}${r.unit}${r.note ? '  (' + r.note + ')' : ''}`);
  }
  console.log(`\n${rows.length}줄. D1 에 올리려면: npm run inventory -- --push`);
} else {
  const WRANGLER = path.join(__dirname, '..', 'node_modules', 'wrangler', 'bin', 'wrangler.js');
  const sql = `CREATE TABLE IF NOT EXISTS admin_kv (k TEXT PRIMARY KEY, v TEXT NOT NULL, ts TEXT NOT NULL DEFAULT (datetime('now')));\n` +
    `INSERT INTO admin_kv (k, v, ts) VALUES ('inventory', '${JSON.stringify(inv).replace(/'/g, "''")}', datetime('now')) ` +
    `ON CONFLICT(k) DO UPDATE SET v = excluded.v, ts = excluded.ts;`;
  const f = path.join(os.tmpdir(), `inv_${Date.now()}.sql`);
  fs.writeFileSync(f, sql, 'utf8');
  try {
    execFileSync(process.execPath, [WRANGLER, 'd1', 'execute', 'grade-usage', '--remote', '--file', f],
      { cwd: path.join(__dirname, '..'), stdio: ['ignore', 'ignore', 'pipe'] });
    console.log(`올렸다 — ${rows.length}줄, ${Buffer.byteLength(sql)}바이트`);
  } finally { fs.unlinkSync(f); }
}
