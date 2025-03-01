# backend/run.py
from app import create_app  # Import from app, not app.api

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)