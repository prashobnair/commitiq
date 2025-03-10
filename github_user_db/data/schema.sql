-- For PostgreSQL
CREATE TABLE github_users (
  id SERIAL PRIMARY KEY,  -- Use SERIAL for auto-incrementing integer
  login TEXT NOT NULL UNIQUE,
  node_id TEXT,
  type TEXT,
  site_admin BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sync_status (
  id SERIAL PRIMARY KEY,
  last_user_id INTEGER DEFAULT 0,
  last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);