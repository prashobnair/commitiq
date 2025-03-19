/**
 * PDF Generator for CommitIQ
 * 
 * This script generates a PDF from a URL (either a website or a local HTML file)
 * 
 * Usage:
 *   node pdf_generator.js <url> <output_path>
 * 
 * Example:
 *   node pdf_generator.js http://localhost:3000/print/username output.pdf
 *   node pdf_generator.js file:///path/to/local/file.html output.pdf
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Get command line arguments
const url = process.argv[2];
const outputPath = process.argv[3];

if (!url || !outputPath) {
    console.error('Usage: node pdf_generator.js <url> <output_path>');
    process.exit(1);
}

async function generatePDF() {
    console.log(`Generating PDF from: ${url}`);
    console.log(`Output path: ${outputPath}`);
    
    try {
        // Launch a new browser instance
        const browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        
        // Create a new page
        const page = await browser.newPage();
        
        // Set the viewport size to letter size (at 96 DPI)
        await page.setViewport({
            width: 816,
            height: 1056,
            deviceScaleFactor: 2
        });
        
        // Navigate to the URL and wait for all resources to load
        console.log('Loading page...');
        await page.goto(url, { 
            waitUntil: 'networkidle0',
            timeout: 30000 
        });
        
        // Wait a bit to ensure everything is rendered
        console.log('Waiting for rendering to complete...');
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Generate the PDF
        console.log('Generating PDF...');
        await page.pdf({
            path: outputPath,
            format: 'Letter',
            printBackground: true,
            margin: {
                top: '0.4in',
                right: '0.4in',
                bottom: '0.4in',
                left: '0.4in'
            }
        });
        
        // Close the browser
        await browser.close();
        
        console.log('PDF generated successfully!');
        console.log(`File saved to: ${outputPath}`);
        process.exit(0);
    } catch (error) {
        console.error('Error generating PDF:');
        console.error(error);
        process.exit(1);
    }
}

// Run the PDF generator
generatePDF(); 