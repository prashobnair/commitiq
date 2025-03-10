-- Drop tables if they exist
DROP TABLE IF EXISTS github_users;
DROP TABLE IF EXISTS sync_status;

-- Create github_users table
CREATE TABLE github_users (
    id INTEGER PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    node_id TEXT,
    type TEXT,
    site_admin BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on login
CREATE INDEX idx_login ON github_users(login);

-- Create sync_status table
CREATE TABLE sync_status (
    id INTEGER PRIMARY KEY,
    last_user_id INTEGER DEFAULT 0,
    last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
); 