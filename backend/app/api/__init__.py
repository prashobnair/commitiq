from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
from .config import Config
from .api.github import github_bp  # Import the blueprint

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app)  # Enable CORS for all routes

    # Load environment variables
    load_dotenv()

    # Register blueprints
    app.register_blueprint(github_bp, url_prefix='/api/github')  # Register the blueprint

    return app