-- 채점 1건 = 1행. 비용은 기록 시점 단가로 계산해 함께 넣는다(단가가 바뀌어도 과거 행은 그대로).
CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  mode TEXT NOT NULL,            -- 사례 / 기록
  subject TEXT NOT NULL,
  exam_id TEXT NOT NULL,
  unit TEXT,                     -- 사례형 groupKey 또는 기록형 taskNo
  status TEXT NOT NULL,          -- ok / max_tokens / refusal / error / aborted
  input_tokens INTEGER,
  cache_write_tokens INTEGER,
  cache_read_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd REAL,
  answer_chars INTEGER,
  sliced INTEGER,
  ip_hash TEXT
);
CREATE INDEX IF NOT EXISTS usage_ts ON usage(ts);
