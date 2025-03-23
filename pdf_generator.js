/**
 * PDF Generator for CommitIQ (Legacy Wrapper)
 * 
 * This is a legacy wrapper that uses the optimized backend/app/utils/generate_pdf.js
 * script to maintain backward compatibility.
 * 
 * Usage:
 *   node pdf_generator.js <url> <output_path>
 * 
 * Example:
 *   node pdf_generator.js http://localhost:3000/print/username output.pdf
 */

const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// Safe logging wrapper that prevents sensitive data exposure in production
const safeLogger = {
  log: (message, ...args) => {
    // In production, we don't log detailed information
    if (process.env.NODE_ENV === 'production') {
      // SECURITY: Console log removed to prevent data exposure
      return;
    }
    console.log(message, ...args);
  },
  
  error: (message, ...args) => {
    // Even in production, we log errors but sanitize sensitive data
    if (process.env.NODE_ENV === 'production') {
      // Only log the error message, not the detailed args which could contain sensitive data
      console.error(message);
    } else {
      console.error(message, ...args);
    }
  }
};

// Ensure arguments are provided
const url = process.argv[2];
const outputPath = process.argv[3];

if (!url || !outputPath) {
    safeLogger.error('Usage: node pdf_generator.js <url> <output_path>');
    process.exit(1);
}

// Get the path to the optimized generator script
const optimizedGeneratorPath = path.join(__dirname, 'backend', 'app', 'utils', 'generate_pdf.js');

// Check if the optimized generator exists
if (!fs.existsSync(optimizedGeneratorPath)) {
    safeLogger.error(`Optimized PDF generator not found at ${optimizedGeneratorPath}`);
    process.exit(1);
}

safeLogger.log(`Using optimized PDF generator from: ${optimizedGeneratorPath}`);
safeLogger.log(`Generating PDF for: ${url}`);
safeLogger.log(`Output path: ${outputPath}`);

// Run the optimized generator
const generator = spawn('node', [optimizedGeneratorPath, url, outputPath], {
    stdio: 'inherit' // Show all output
});

generator.on('close', (code) => {
    if (code !== 0) {
        safeLogger.error(`PDF generation failed with code ${code}`);
        process.exit(code);
    } else {
        safeLogger.log(`PDF generated successfully: ${outputPath}`);
        process.exit(0);
    }
}); 