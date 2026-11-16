-- 앱에서 들어온 의견 1건 = 1행. 다섯 앱(허브·선택형·사례형·기록형·암기장·율리)이 같은 표에 쌓인다.
-- 채점 기록(usage)과 같은 D1 에 둔다 — 워커도 바인딩도 하나로 끝난다.
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),   -- UTC
  app TEXT NOT NULL,             -- HUB / MCQ / CASE / RECORD / NOTES / ETHICS
  kind TEXT NOT NULL,            -- 오류 / 제안 / 기타
  text TEXT NOT NULL,
  contact TEXT,                  -- 답을 받고 싶은 사람만 적는다(선택)
  user TEXT,                     -- 앱 로그인 ID (lawhub_uid). 없으면 NULL
  ctx TEXT,                      -- 보고 있던 화면 — JSON {path,title,heads,vw,vh,theme}
  ua TEXT,
  ip_hash TEXT,                  -- 도배 추적용. IP 원문은 저장하지 않는다
  status TEXT NOT NULL DEFAULT 'new',   -- new(새 것) / seen(읽음) / done(처리함)
  note TEXT,                     -- 관리자 메모(무엇을 고쳤는지)
  done_ts TEXT
);
CREATE INDEX IF NOT EXISTS feedback_status ON feedback(status, ts);
