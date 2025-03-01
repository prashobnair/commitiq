# backend/app/config.py
import os

class Config:
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    # Add other configuration variables as needed