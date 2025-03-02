# backend/run.py
from app import create_app  # Import from app, not app.api
# import asyncio
# from hypercorn.config import Config
# from hypercorn.asyncio import serve

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)  # Use port 5001 instead of default 5000
    
    # Comment out Hypercorn for now
    # config = Config()
    # config.bind = ["localhost:5001"]  # Changed port from 5000 to 5001
    # config.use_reloader = True
    # asyncio.run(serve(app, config))