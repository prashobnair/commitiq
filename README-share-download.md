# CommitIQ - Share & Download Features

## Overview

The Share & Download features allow users to share GitHub analysis results with others and download reports for offline use. These features enhance the utility of CommitIQ by enabling recruiters to share candidate profiles with hiring managers and download formatted reports for their records.

## Features

### Share Analysis

The sharing functionality enables users to:

- Generate unique, shareable links to GitHub analysis results
- Set expiration dates for shared links (7 days, 30 days, 90 days, or never)
- Choose between public and private sharing options
- Track how many times a shared link has been viewed
- Copy links to clipboard or share directly via email

### Download Reports

The download functionality enables users to:

- Download analysis reports in PDF format with professional formatting
- Download raw analysis data in JSON format for integration with other tools
- Customize filenames based on the GitHub username being analyzed

## Implementation Details

### Backend Components

- `share.py`: Flask blueprint with endpoints for sharing and downloading functionality
- `report_template.html`: HTML template for PDF report generation
- Database tables: `shared_analysis` for tracking shared links and their metadata

### Frontend Components

- `ShareOptions.tsx`: React component for share and download UI
- `SharedAnalysisView.tsx`: Page for viewing shared analysis
- `AuthContext.tsx`: Authentication context to associate shares with users

### Security Considerations

- All shared links use UUID v4 for high entropy, making them difficult to guess
- Expiration dates prevent indefinite access to outdated analysis
- Access counts track usage of shared links
- Public/private sharing options provide flexibility for different use cases

## Installation Requirements

To enable the PDF report generation feature, additional dependencies are required:

- wkhtmltopdf: HTML to PDF conversion tool
- pdfkit: Python wrapper for wkhtmltopdf
- Jinja2: Template engine for HTML generation

Use the provided installation script to set up these dependencies:

```bash
./install_pdf_dependencies.sh
```

## API Endpoints

### Share Endpoints

- `POST /api/share/create/<analysis_id>`: Create a new shareable link
- `GET /api/share/view/<share_id>`: View a shared analysis
- `GET /api/share/user-shares?email=<email>`: Get all shares created by a user

### Download Endpoints

- `GET /api/share/download/<analysis_id>?format=<pdf|json>`: Download analysis report

## Future Enhancements

Planned enhancements for these features include:

1. **Password Protection**: Add optional password protection for sensitive analysis shares
2. **Custom Branding**: Allow enterprise users to apply custom branding to PDF reports
3. **Comparative Reports**: Enable downloading reports that compare multiple developers
4. **Analytics Dashboard**: Provide analytics on share usage and engagement
5. **Batch Export**: Allow exporting multiple analyses in a single operation 