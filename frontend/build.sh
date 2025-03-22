#!/bin/bash
# Frontend build script for production deployment on Render

# Log the build process
echo "Starting CommitIQ frontend build process..."
echo "Using API URL: $REACT_APP_API_URL"

# Install dependencies with legacy peer deps to avoid TypeScript conflicts
echo "Installing dependencies..."
npm install --legacy-peer-deps

# Install specific TypeScript version compatible with react-scripts
echo "Installing compatible TypeScript version..."
npm install --legacy-peer-deps typescript@4.9.5

# Build the application
echo "Building the application..."
npm run build

echo "Build process completed successfully!" 