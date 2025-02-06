# Firmador Frontend

A modern web interface for digital document signing and validation.

## Features

- PDF document signing with digital certificates
- JSON index signing for digital reports
- PDF and JSON signature validation
- Complete report (ZIP) validation
- PDF merging with optional watermarks
- Protocol documentation for JSON and ZIP structures

## Tech Stack

- React 18 with TypeScript
- Vite for fast development and building
- TailwindCSS for styling
- ShadCN/UI for component library
- React Query for API state management
- React Router for navigation
- React Beautiful DnD for drag-and-drop functionality
- Zustand for lightweight state management

## Prerequisites

- Node.js 18 or higher
- npm or yarn package manager
- Running backend services (Java and Python)

## Development Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

## Docker Setup

The frontend can be run in a Docker container using the provided Dockerfile and docker-compose.yml.

1. Build and start with docker-compose:
   ```bash
   docker-compose up --build
   ```

2. Access the application at `http://localhost:3000`

## Project Structure

```
src/
├── components/         # Reusable UI components
│   ├── ui/            # Base UI components
│   └── Layout.tsx     # Main layout component
├── lib/               # Utilities and API functions
│   ├── api.ts         # API client and types
│   └── utils.ts       # Helper functions
├── pages/             # Page components
│   ├── PDFSigning.tsx
│   ├── JSONSigning.tsx
│   ├── JSONValidation.tsx
│   ├── PDFValidation.tsx
│   ├── ReportValidation.tsx
│   ├── PDFMerge.tsx
│   └── Protocol.tsx
└── App.tsx            # Main application component
```

## API Integration

The frontend communicates with two backend services:

1. Python Flask API (`/api`) - Main document processing
2. Java Service - Digital signature operations

API endpoints are configured in `src/lib/api.ts` and proxied through nginx in production.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is proprietary and confidential. 