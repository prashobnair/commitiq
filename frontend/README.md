# CommitIQ Frontend

A modern React application for analyzing GitHub profiles and providing meaningful insights for technical recruiters.

## Features

- Clean, modern UI built with Material-UI
- Real-time GitHub profile analysis
- Comprehensive metrics visualization
- Responsive design for all devices
- TypeScript for type safety
- Optimized performance and code splitting

## Tech Stack

- React 18
- TypeScript
- Material-UI v5
- Axios for API calls
- Chart.js for data visualization
- React Router for navigation

## Getting Started

### Prerequisites

- Node.js 16.x or later
- npm 7.x or later

### Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/commitiq.git
cd commitiq/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file in the frontend directory:
```bash
REACT_APP_API_URL=http://localhost:5000/api
```

4. Start the development server:
```bash
npm start
```

The application will be available at `http://localhost:3000`.

## Project Structure

```
src/
├── components/          # React components
│   ├── analysis/       # Analysis-related components
│   ├── common/         # Shared components
│   └── layout/         # Layout components
├── hooks/              # Custom React hooks
├── types/              # TypeScript type definitions
├── utils/              # Utility functions
└── styles/             # Global styles and theme
```

## Development

### Code Style

The project uses ESLint and Prettier for code formatting. To format the code:

```bash
npm run format
```

To check for linting issues:

```bash
npm run lint
```

### Building for Production

To create a production build:

```bash
npm run build
```

The build artifacts will be stored in the `build/` directory.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
