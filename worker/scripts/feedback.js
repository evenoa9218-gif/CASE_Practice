// 의견함 읽기. 앱의 「의견 보내기」로 들어온 글이 D1(grade-usage)의 feedback 표에 쌓인다.
//
//   npm run feedback                 새 의견만 (status = new)
//   npm run feedback -- all          최근 50건 (상태 무관)
//   npm run feedback -- seen 12 13   12·13번을 「읽음」으로
//   npm run feedback -- done 12 "채점 칸을 넓혔다 (7a8e504)"   처리함 + 메모
//
// 관리자 열쇠가 필요 없다 — wrangler 로그인이 곧 열쇠다.
// (브라우저에서 보려면 허브의 /feedback-admin.html. 그쪽은 FEEDBACK_ADMIN_KEY 가 있어야 열린다)
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const [cmd = 'new', ...rest] = process.argv.slice(2);
const KST = (ts) => {            // D1 은 UTC 로 적는다. 읽을 때만 한국 시각으로 옮긴다
  const d = new Date(ts.replace(' ', 'T') + 'Z');
  return isNaN(d) ? ts : new Date(d.getTime() + 9 * 3600e3).toISOString().slice(0, 16).replace('T', ' ');
};

// SELECT 는 --command 로 한 줄에 — --file 은 원격에서 진행 표시가 JSON 에 섞인다.
function select(sql) {
  const out = execSync(`npx wrangler d1 execute grade-usage --remote --json --command "${sql.replace(/\s+/g, ' ')}"`,
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
  return JSON.parse(out)[0].results;
}
// UPDATE 는 메모에 따옴표·한글이 들어가므로 파일로 넘긴다(셸 따옴표에 안 걸린다).
function update(sql) {
  const f = path.join(os.tmpdir(), `fb_${Date.now()}.sql`);
  fs.writeFileSync(f, sql, 'utf8');
  try {
    execSync(`npx wrangler d1 execute grade-usage --remote --file "${f}"`, { stdio: ['ignore', 'ignore', 'inherit'] });
  } finally { fs.unlinkSync(f); }
}
const q = (s) => `'${String(s).replace(/'/g, "''")}'`;

if (cmd === 'seen' || cmd === 'done') {
  const ids = rest.filter((x) => /^\d+$/.test(x)).map(Number);
  const note = rest.filter((x) => !/^\d+$/.test(x)).join(' ').trim();
  if (!ids.length) { console.error('번호를 적어 주세요. 예: npm run feedback -- done 12 "메모"'); process.exit(1); }
  update(`UPDATE feedback SET status = ${q(cmd)}${note ? `, note = ${q(note)}` : ''}${
    cmd === 'done' ? ", done_ts = datetime('now')" : ''} WHERE id IN (${ids.join(',')});`);
  console.log(`${ids.join(', ')}번 → ${cmd === 'done' ? '처리함' : '읽음'}${note ? ` · 메모: ${note}` : ''}`);
  process.exit(0);
}

const where = cmd === 'all' ? '' : "WHERE status = 'new'";
const rows = select(`SELECT id, ts, app, kind, text, contact, user, ctx, status, note
                     FROM feedback ${where} ORDER BY id DESC LIMIT 50`);
const counts = select('SELECT status, count(*) n FROM feedback GROUP BY status');
const c = Object.fromEntries(counts.map((r) => [r.status, r.n]));
console.log(`\n의견함 — 새 것 ${c.new || 0} · 읽음 ${c.seen || 0} · 처리함 ${c.done || 0}\n`);
if (!rows.length) console.log(cmd === 'all' ? '아직 들어온 의견이 없습니다.' : '새 의견이 없습니다.  (전부 보려면: npm run feedback -- all)');

for (const r of rows.reverse()) {          // 오래된 것부터 — 맨 아래가 가장 새 것
  let ctx = {};
  try { ctx = JSON.parse(r.ctx || '{}'); } catch {}
  const mark = { new: '●', seen: '○', done: '✓' }[r.status] || '?';
  console.log(`${mark} #${r.id}  [${r.app} · ${r.kind}]  ${KST(r.ts)}${r.user ? `  · ${r.user}` : ''}`);
  console.log(r.text.split('\n').map((l) => '    ' + l).join('\n'));
  const where2 = [ctx.path, (ctx.heads || []).join(' › ')].filter(Boolean).join('  —  ');
  if (where2) console.log(`    ↳ 화면: ${where2}`);
  if (ctx.vw) console.log(`    ↳ 기기: ${ctx.vw}×${ctx.vh}${ctx.theme ? ` · ${ctx.theme}` : ''}`);
  if (r.contact) console.log(`    ↳ 연락처: ${r.contact}`);
  if (r.note) console.log(`    ↳ 메모: ${r.note}`);
  console.log('');
}
