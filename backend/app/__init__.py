# backend/app/__init__.py
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
from .config import Config
from .api import api_bp  # Import api_bp instead of github_bp
# from asgiref.wsgi import WsgiToAsgi  # Comment out for now

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app)  # Enable CORS for all routes

    # Load environment variables
    load_dotenv()

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')  # Register api_bp

    # Return the Flask app directly
    return app
    
    # Comment out ASGI conversion for now
    # asgi_app = WsgiToAsgi(app)
    # return asgi_app