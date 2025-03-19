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

// Ensure arguments are provided
const url = process.argv[2];
const outputPath = process.argv[3];

if (!url || !outputPath) {
    console.error('Usage: node pdf_generator.js <url> <output_path>');
    process.exit(1);
}

// Get the path to the optimized generator script
const optimizedGeneratorPath = path.join(__dirname, 'backend', 'app', 'utils', 'generate_pdf.js');

// Check if the optimized generator exists
if (!fs.existsSync(optimizedGeneratorPath)) {
    console.error(`Optimized PDF generator not found at ${optimizedGeneratorPath}`);
    process.exit(1);
}

console.log(`Using optimized PDF generator from: ${optimizedGeneratorPath}`);
console.log(`Generating PDF for: ${url}`);
console.log(`Output path: ${outputPath}`);

// Run the optimized generator
const generator = spawn('node', [optimizedGeneratorPath, url, outputPath], {
    stdio: 'inherit' // Show all output
});

generator.on('close', (code) => {
    if (code !== 0) {
        console.error(`PDF generation failed with code ${code}`);
        process.exit(code);
    } else {
        console.log(`PDF generated successfully: ${outputPath}`);
        process.exit(0);
    }
}); 