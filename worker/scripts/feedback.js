// 의견함 읽기. 앱의 「의견 보내기」로 들어온 글이 D1(grade-usage)의 feedback 표에 쌓인다.
//
//   npm run feedback                 새 의견만 (status = new)
//   npm run feedback -- all          최근 50건 (상태 무관)
//   npm run feedback -- seen 12 13   12·13번을 「읽음」으로
//   npm run feedback -- done 12 "채점 칸을 넓혔다 (7a8e504)"   처리함 + 메모
//
// 관리자 열쇠가 필요 없다 — wrangler 로그인이 곧 열쇠다.
// (브라우저에서 보려면 허브의 /feedback-admin.html. 그쪽은 FEEDBACK_ADMIN_KEY 가 있어야 열린다)
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

// ⚠ wrangler 를 `npx wrangler` 로 부르면 안 된다. npx 가 부를 때마다 패키지를 다시 살피느라
//   **한 번에 18초**가 걸린다(직접 부르면 4.5초). 조회 둘을 따로 부르던 첫 판은 진짜 터미널에서
//   1분 가까이 빈 화면이었고, 「보낸 의견이 안 보인다」는 말이 바로 나왔다 — 글은 와 있었다.
//   설치된 wrangler 를 node 로 직접 돌리고, 조회는 한 번에 묶는다.
// 셸을 거치지 않으므로(execFileSync) 따옴표·한글이 깨질 일도 없다.
const WRANGLER = path.join(__dirname, '..', 'node_modules', 'wrangler', 'bin', 'wrangler.js');
if (!fs.existsSync(WRANGLER)) {
  console.error('wrangler 가 설치되어 있지 않습니다. 이 폴더(worker)에서 npm install 을 먼저 실행하세요.');
  process.exit(1);
}
function d1(args, stdio) {
  return execFileSync(process.execPath, [WRANGLER, 'd1', 'execute', 'grade-usage', '--remote', ...args],
    { encoding: 'utf8', stdio, cwd: path.join(__dirname, '..') });
}

const [cmd = 'new', ...rest] = process.argv.slice(2);
const KST = (ts) => {            // D1 은 UTC 로 적는다. 읽을 때만 한국 시각으로 옮긴다
  const d = new Date(ts.replace(' ', 'T') + 'Z');
  return isNaN(d) ? ts : new Date(d.getTime() + 9 * 3600e3).toISOString().slice(0, 16).replace('T', ' ');
};

// SELECT 는 --command 로 — --file 은 원격에서 진행 표시가 JSON 에 섞인다.
// 문장을 ; 로 이어 한 번에 보내면 결과도 문장 수만큼 배열로 온다.
function select(sql) {
  const out = d1(['--json', '--command', sql.replace(/\s+/g, ' ')], ['ignore', 'pipe', 'ignore']);
  return JSON.parse(out).map((r) => r.results);
}
// UPDATE 는 메모가 길 수 있어 파일로 넘긴다.
function update(sql) {
  const f = path.join(os.tmpdir(), `fb_${Date.now()}.sql`);
  fs.writeFileSync(f, sql, 'utf8');
  // wrangler 는 잘 돼도 경고 여러 줄을 쏟는다. 삼켜 두고, 실패했을 때만 보여 준다.
  try { d1(['--file', f], ['ignore', 'ignore', 'pipe']); }
  catch (e) { console.error(String(e.stderr || e.message)); process.exit(1); }
  finally { fs.unlinkSync(f); }
}
const q = (s) => `'${String(s).replace(/'/g, "''")}'`;

// ── 폰 알림 기기 관리 ──
//   npm run feedback -- push          신청된 기기 목록
//   npm run feedback -- push-ok 3     3번 기기 승인 — 그때부터 새 의견이 그 기기로 간다
//   npm run feedback -- push-del 3    3번 기기 지우기
if (cmd === 'push-ok' || cmd === 'push-del') {
  const ids = rest.filter((x) => /^\d+$/.test(x)).map(Number);
  if (!ids.length) { console.error('번호를 적어 주세요. 예: npm run feedback -- push-ok 3'); process.exit(1); }
  update(cmd === 'push-ok'
    ? `UPDATE push_subs SET status = 'active' WHERE id IN (${ids.join(',')});`
    : `DELETE FROM push_subs WHERE id IN (${ids.join(',')});`);
  console.log(`${ids.join(', ')}번 기기 → ${cmd === 'push-ok' ? '승인 (이제 새 의견이 갑니다)' : '지움'}`);
  process.exit(0);
}
if (cmd === 'push') {
  const [subs] = select(`SELECT id, ts, label, ua, status, last_ok, last_err,
                         substr(endpoint, 1, 40) AS ep FROM push_subs ORDER BY id`);
  if (!subs.length) console.log('신청된 기기가 없습니다. 폰에서 /feedback-admin.html 을 열고 「알림 켜기」를 누르세요.');
  for (const s of subs) {
    console.log(`${s.status === 'active' ? '✓ 받음' : '… 대기'}  #${s.id}  ${s.label || '?'}  ${KST(s.ts)}  ${s.ep}…`);
    if (s.last_ok) console.log(`      마지막 성공 ${KST(s.last_ok)}`);
    if (s.last_err) console.log(`      마지막 실패: ${s.last_err}`);
  }
  process.exit(0);
}

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
// 몇 초는 걸린다. 그동안 빈 화면이면 멈춘 줄 안다.
process.stdout.write('의견함을 불러오는 중…');
const [rows, counts] = select(`SELECT id, ts, app, kind, text, contact, user, ctx, status, note
                               FROM feedback ${where} ORDER BY id DESC LIMIT 50;
                               SELECT status, count(*) n FROM feedback GROUP BY status`);
process.stdout.write('\r' + ' '.repeat(30) + '\r');
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
