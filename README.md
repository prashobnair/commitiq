# CommitIQ - GitHub Developer Impact Analysis Platform

CommitIQ is a SaaS platform that revolutionizes technical recruiting by providing objective and insightful assessments of developers' skills based on their public GitHub activity.

## Project Overview

CommitIQ analyzes a developer's public GitHub profile data (repositories, commits, pull requests, issues, reviews, etc.) to generate a comprehensive "Impact Score" and detailed insights. This score goes beyond simple activity counts and considers factors like:

- Code Quality
- Project Impact
- Collaboration
- Consistency
- Code Evolution

## Architecture

The application follows a modern client-server architecture:

### Backend
- Flask-based Python API server
- PostgreSQL database
- Redis caching with in-memory fallback
- PDF generation using Node.js/Puppeteer

### Frontend
- React with TypeScript
- Material UI components
- Chart.js for data visualization

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 16+
- PostgreSQL
- Redis (optional, falls back to in-memory cache)

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/commitiq.git
cd commitiq
```

2. Install backend dependencies
```bash
cd backend
pip install -r requirements.txt
```

3. Install frontend dependencies
```bash
cd ../frontend
npm install
```

4. Install PDF generation dependencies
```bash
cd ..
bash install_pdf_dependencies.sh
```

5. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your settings
```

### Running the Application

1. Start the backend server
```bash
cd backend
python run.py
```

2. Start the frontend development server
```bash
cd frontend
npm start
```

3. Access the application at `http://localhost:3000`

## Key Features

- **GitHub Profile Analysis**: Deep analysis of a developer's GitHub contributions
- **Impact Score**: Objective metric for evaluating developer impact
- **Detailed Metrics**: Breakdowns of contributions, consistency, and project impact
- **Profile Sharing**: Generate shareable links to developer profiles
- **PDF Export**: Create professional PDF reports of developer profiles

## Project Structure

```
├── backend/              # Flask API server
│   ├── app/              # Main application package
│   │   ├── api/          # API endpoints
│   │   ├── utils/        # Utility services and functions
│   │   └── models.py     # Database models
│   └── run.py            # Application entry point
├── frontend/             # React frontend application
│   ├── public/           # Static files
│   └── src/              # Source code
│       ├── components/   # React components
│       ├── contexts/     # React contexts for state management
│       └── utils/        # Utility functions
└── pdfs/                 # Generated PDF files directory
```

## API Documentation

The API provides the following main endpoints:

- `POST /api/analyze`: Analyze a GitHub profile
- `GET /api/analyze/<username>`: Analyze a GitHub profile (GET method)
- `GET /api/share/<id>`: Get a shared analysis
- `POST /api/download`: Generate a PDF for an analysis

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary and confidential. All rights reserved.
