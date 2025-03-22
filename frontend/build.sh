#!/bin/bash
# Frontend build script for production deployment on Render

# Log the build process
echo "Starting CommitIQ frontend build process..."
echo "Using API URL: $REACT_APP_API_URL"

# Install dependencies
echo "Installing dependencies..."
npm install

# Build the application
echo "Building the application..."
npm run build

echo "Build process completed successfully!" 