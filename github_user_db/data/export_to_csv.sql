.mode csv
.headers on
.output github_users.csv
SELECT * FROM github_users;
.output sync_status.csv
SELECT * FROM sync_status; 