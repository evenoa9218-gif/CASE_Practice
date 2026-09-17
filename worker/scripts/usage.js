// 채점 비용 조회. 사용: npm run usage [-- 일수]   (기본 30일)
// D1(grade-usage)에 워커가 채점 1건마다 남긴 행을 모아 보여준다.
const { execSync } = require('child_process');

const days = Number(process.argv[2]) || 30;
const since = `datetime('now', '-${days} days')`;
const queries = {
  '월별': `SELECT substr(ts,1,7) 월, count(*) 건수, round(sum(cost_usd),2) 달러
           FROM usage GROUP BY 1 ORDER BY 1`,
  [`최근 ${days}일 · 유형별`]: `SELECT mode 유형, subject 과목, count(*) 건수,
           round(sum(cost_usd),2) 달러, round(avg(cost_usd),3) 건당,
           round(avg(output_tokens)) 평균출력토큰
           FROM usage WHERE ts >= ${since} GROUP BY 1, 2 ORDER BY 4 DESC`,
  [`최근 ${days}일 · 실패/중단`]: `SELECT status 상태, count(*) 건수, round(sum(cost_usd),2) 달러
           FROM usage WHERE ts >= ${since} AND status <> 'ok' GROUP BY 1`,
  [`최근 ${days}일 · 많이 쓴 사용자(IP 해시)`]: `SELECT ip_hash, count(*) 건수, round(sum(cost_usd),2) 달러
           FROM usage WHERE ts >= ${since} GROUP BY 1 ORDER BY 3 DESC LIMIT 5`,
};

// SQL은 한 줄로 펴서 큰따옴표로 감싼다(--file 은 원격에서 업로드 절차로 빠져 JSON이 아닌 진행 표시가 섞인다).
for (const [title, sql] of Object.entries(queries)) {
  const one = sql.replace(/\s+/g, ' ');
  const out = execSync(`npx wrangler d1 execute grade-usage --remote --json --command "${one}"`,
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
  console.log(`\n■ ${title}`);
  console.table(JSON.parse(out)[0].results);
}
