-- Import github_users data
\copy github_users FROM '/tmp/github_users.csv' WITH CSV HEADER;

-- Import sync_status data
\copy sync_status FROM '/tmp/sync_status.csv' WITH CSV HEADER; 