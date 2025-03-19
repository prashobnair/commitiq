# CommitIQ PDF Generation Utility

This utility provides a reliable way to generate PDFs from HTML content using Puppeteer.

## Requirements

- Node.js (v12 or higher)
- npm (included with Node.js)

## Installation

1. Install Puppeteer:

```bash
npm install puppeteer
```

If you want to install it globally:

```bash
npm install -g puppeteer
```

## Included Utilities

### 1. PDF Generator (`pdf_generator.js`)

This script generates a PDF from a URL (either a website or a local HTML file).

#### Usage

```bash
node pdf_generator.js <url> <output_path>
```

#### Examples

```bash
# Generate a PDF from a website
node pdf_generator.js http://localhost:3000/print/username output.pdf

# Generate a PDF from a local HTML file
node pdf_generator.js file:///path/to/local/file.html output.pdf
```

### 2. Test HTML Generator (`create_test_html.js`)

This script creates a simple HTML file for testing PDF generation.

#### Usage

```bash
node create_test_html.js <output_path>
```

#### Example

```bash
node create_test_html.js test.html
```

## Complete Example Workflow

1. Create a test HTML file:

```bash
node create_test_html.js test.html
```

2. Generate a PDF from the test HTML file:

```bash
node pdf_generator.js file://$(pwd)/test.html output.pdf
```

3. View the generated PDF with your system's default PDF viewer.

## Troubleshooting

### PDF Generation Issues

If you experience issues with PDF generation, try the following:

1. **Check Puppeteer Installation**:
   Ensure Puppeteer is installed correctly.

2. **Chrome Executable Issues**:
   Puppeteer depends on Chrome. If Chrome cannot be found, try reinstalling Puppeteer:
   ```bash
   npm uninstall puppeteer
   npm install puppeteer
   ```

3. **Permission Issues**:
   If you get permission errors, try running with `--no-sandbox` and `--disable-setuid-sandbox` arguments (already included in the script).

4. **Memory Issues**:
   If PDF generation fails due to memory issues, try reducing the size of the HTML content or increasing the available memory.

### Web Server Issues

If you're trying to generate a PDF from a local web server:

1. **Ensure the Server is Running**:
   Check if your frontend server is running on the expected port.

2. **CORS Issues**:
   If using a local server, ensure CORS headers are set correctly.

3. **URL Format**:
   Make sure your URL format is correct. For local files, use `file:///absolute/path/to/file.html`.

## Integration with Flask

For integrating with Flask or other backends, we recommend:

1. Creating a separate Node.js script (like `pdf_generator.js`)
2. Executing it from your backend using subprocess or similar
3. Capturing the output and handling errors appropriately

This approach provides better isolation between the Node.js and Python environments, reducing potential issues. 