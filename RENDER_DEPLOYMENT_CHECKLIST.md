# CommitIQ Deployment Checklist - Render Free Tier

Use this checklist to ensure a successful deployment of CommitIQ to Render's free tier.

## Pre-Deployment Setup

- [ ] Remove all sensitive information from code and environment files
- [ ] Update `.gitignore` to exclude `.env` and other sensitive files
- [ ] Create a GitHub repository for your code if not already done
- [ ] Ensure `render.yaml` file is properly configured for your GitHub repository URL
- [ ] Run the application locally to verify it works with environment variables

## GitHub Repository Preparation

- [ ] Push all code changes to your GitHub repository
- [ ] Verify all needed files are committed:
  - [ ] `render.yaml` at the root level
  - [ ] `backend/init_db.py` for database initialization
  - [ ] `frontend/build.sh` for frontend build process

## Render Account Setup

- [ ] Create a Render account at [render.com](https://render.com)
- [ ] Connect your GitHub account to Render
- [ ] Prepare a new GitHub API token for production use
  - Get it from [GitHub Developer Settings](https://github.com/settings/tokens)
  - Ensure it has the necessary permissions for public repository read

## Database Deployment

- [ ] In Render dashboard, click "New" and select "PostgreSQL"
- [ ] Configure your PostgreSQL service:
  - [ ] Name: `commitiq-db`
  - [ ] Database: `github_data`
  - [ ] User: `commitiq`
  - [ ] Plan: Free
- [ ] Create the database and note its connection details

## Backend Deployment

- [ ] In Render dashboard, click "New" and select "Web Service"
- [ ] Connect to your GitHub repository
- [ ] Configure the backend service:
  - [ ] Name: `commitiq-api`
  - [ ] Root Directory: `backend`
  - [ ] Environment: Python
  - [ ] Build Command: `pip install -r requirements.txt`
  - [ ] Start Command: `python init_db.py && hypercorn run:app --bind 0.0.0.0:$PORT`
  - [ ] Plan: Free
- [ ] Set environment variables:
  - [ ] `FLASK_ENV`: `production`
  - [ ] `FLASK_APP`: `run.py`
  - [ ] `DB_HOST`: [Your PostgreSQL host]
  - [ ] `DB_PORT`: [Your PostgreSQL port]
  - [ ] `DB_NAME`: `github_data`
  - [ ] `DB_USER`: `commitiq`
  - [ ] `DB_PASSWORD`: [Your PostgreSQL password]
  - [ ] `FRONTEND_URL`: [Your frontend URL, e.g., https://commitiq-frontend.onrender.com]
  - [ ] `EMAIL_HASH_PEPPER`: [Generate a secure random string]
  - [ ] `GITHUB_TOKEN`: [Your GitHub API token]
- [ ] Deploy the backend service
- [ ] Verify its status by checking logs and `/health` endpoint

## Frontend Deployment

- [ ] In Render dashboard, click "New" and select "Static Site"
- [ ] Connect to your GitHub repository
- [ ] Configure the frontend service:
  - [ ] Name: `commitiq-frontend`
  - [ ] Root Directory: `frontend`
  - [ ] Build Command: `chmod +x build.sh && ./build.sh`
  - [ ] Publish Directory: `build`
  - [ ] Plan: Free
- [ ] Set environment variables:
  - [ ] `REACT_APP_API_URL`: [Your backend API URL, e.g., https://commitiq-api.onrender.com/api]
- [ ] Deploy the frontend service
- [ ] Verify its status by checking logs and visiting the frontend URL

## Alternative: Blueprint Deployment

- [ ] In Render dashboard, click "New" and select "Blueprint"
- [ ] Connect to your GitHub repository
- [ ] Select the repository that contains your `render.yaml`
- [ ] Review the services Render will create
- [ ] Add any missing environment variables:
  - [ ] `GITHUB_TOKEN`: [Your GitHub API token]
- [ ] Apply the blueprint

## Post-Deployment Verification

- [ ] Visit your frontend URL
- [ ] Check application functionality:
  - [ ] Analyze a GitHub profile
  - [ ] Check for proper UI rendering
  - [ ] Verify data is being stored in the database
- [ ] Check backend logs for any errors
- [ ] Verify CORS is working properly between frontend and backend
- [ ] Test all main features of the application

## Security Checks

- [ ] Verify sensitive information is not exposed in frontend code
- [ ] Check that GitHub token is not visible in any response
- [ ] Ensure database credentials are secure
- [ ] Verify CORS is properly configured to restrict access
- [ ] Check that environment variables are properly set

## Documentation and Maintenance

- [ ] Document all deployed service URLs
- [ ] Save database connection details securely
- [ ] Schedule regular GitHub token rotation
- [ ] Plan for database monitoring and backups
- [ ] Note Render free tier limitations in your documentation 