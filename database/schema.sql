PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agent_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_ms INTEGER,
  input_json TEXT,
  output_json TEXT,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_date_agent
ON agent_runs(run_date, agent_name);

CREATE TABLE IF NOT EXISTS source_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  source_name TEXT NOT NULL,
  status TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  row_count INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL,
  error TEXT
);

CREATE TABLE IF NOT EXISTS data_quality_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  source_name TEXT NOT NULL,
  check_name TEXT NOT NULL,
  status TEXT NOT NULL,
  metric_value REAL,
  expected_value REAL,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_state (
  run_date TEXT PRIMARY KEY,
  signal_vector_json TEXT NOT NULL,
  max_position_pct REAL NOT NULL,
  force_cash_reasons_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_scores (
  run_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  name TEXT NOT NULL,
  risk_grade TEXT NOT NULL,
  one_veto INTEGER NOT NULL DEFAULT 0,
  risk_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(run_date, symbol)
);

CREATE TABLE IF NOT EXISTS research_scores (
  run_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  name TEXT NOT NULL,
  logic_score REAL NOT NULL,
  narrative_score REAL NOT NULL,
  alpha_score REAL NOT NULL,
  research_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(run_date, symbol)
);

CREATE TABLE IF NOT EXISTS pm_plans (
  run_date TEXT PRIMARY KEY,
  plan_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  symbol TEXT NOT NULL,
  action TEXT NOT NULL,
  approved INTEGER NOT NULL DEFAULT 0,
  approved_by TEXT,
  reason TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sim_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  name TEXT NOT NULL,
  entry_date TEXT NOT NULL,
  planned_price REAL NOT NULL,
  simulated_entry_price REAL NOT NULL,
  position_pct REAL NOT NULL,
  stop_loss_condition TEXT NOT NULL,
  market_state_json TEXT NOT NULL,
  status TEXT NOT NULL,
  exit_date TEXT,
  exit_price REAL,
  exit_reason TEXT,
  pnl_pct REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  period TEXT NOT NULL,
  report_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta_learning_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  layer TEXT NOT NULL,
  action TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guard_alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL,
  level TEXT NOT NULL,
  category TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

