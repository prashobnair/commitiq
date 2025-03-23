/**
 * Optimized PDF Generator for CommitIQ
 * 
 * This script generates a PDF from a URL (either a website or a local HTML file)
 * with optimized handling of rendering and resources.
 * 
 * Usage:
 *   node generate_pdf.js <url> <output_path>
 * 
 * Example:
 *   node generate_pdf.js http://localhost:3000/print/username output.pdf
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');

// Get command line arguments
const url = process.argv[2];
const outputPath = process.argv[3];

// Validate arguments
if (!url || !outputPath) {
    console.error('Usage: node generate_pdf.js <url> <output_path>');
    process.exit(1);
}

// Create output directory if it doesn't exist
const outputDir = path.dirname(outputPath);
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

// Extract username from URL for targeted debugging
const urlObj = new URL(url);
const pathname = urlObj.pathname;
const username = pathname.split('/').pop();

// Browser launch options
const BROWSER_OPTIONS = {
    headless: true,
    args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas', 
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu',
        '--font-render-hinting=none',
        '--disable-web-security',
        '--disable-features=IsolateOrigins',
        '--disable-site-isolation-trials'
    ]
};

// Page settings
const PAGE_SETTINGS = {
    width: 816,     // Letter width at 96 DPI
    height: 1056,   // Letter height at 96 DPI
    deviceScaleFactor: 2,  // Higher resolution for better quality
    waitTimeMs: 3000, // Wait time after page load
    navigationTimeout: 60000 // 60 seconds timeout for navigation
};

// CSS to ensure all elements are visible in print
const PRINT_CSS = `
    @media print {
        .print-section, .print-container, body, html {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            height: auto !important;
            overflow: visible !important;
            position: relative !important;
            page-break-inside: avoid;
        }
        * {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }
        .background-gradient, [class*='gradient'] {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
            color-adjust: exact !important;
        }
        
        /* Ensure headings stay with their content */
        h1, h2, h3, h4, h5, h6 {
            page-break-after: avoid;
            page-break-inside: avoid;
        }
        
        /* Keep images on one page if possible */
        img {
            page-break-inside: avoid;
            max-width: 100% !important;
        }
        
        /* Ensure charts are fully visible */
        canvas, svg, [id*="chart"], [id*="graph"] {
            page-break-inside: avoid;
            max-width: 100% !important;
        }
    }
`;

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

async function generatePDF() {
    const startTime = performance.now();
    safeLogger.log(`Starting PDF generation for ${url}`);
    safeLogger.log(`Output path: ${outputPath}`);
    
    let browser = null;
    
    try {
        // Launch browser
        safeLogger.log('Launching browser...');
        browser = await puppeteer.launch(BROWSER_OPTIONS);
        
        // Create a new page
        const page = await browser.newPage();
        
        // Set up logging if needed
        if (process.env.NODE_ENV !== 'production') {
          page.on('console', msg => safeLogger.log(`PAGE LOG: ${msg.text()}`));
          page.on('pageerror', error => safeLogger.log(`PAGE ERROR: ${error.message}`));
        }
        
        // Set viewport size
        await page.setViewport({
            width: PAGE_SETTINGS.width,
            height: PAGE_SETTINGS.height,
            deviceScaleFactor: PAGE_SETTINGS.deviceScaleFactor
        });
        
        // Navigate to the page
        safeLogger.log(`Navigating to ${url}...`);
        await page.goto(url, { 
            waitUntil: 'networkidle0',
            timeout: PAGE_SETTINGS.navigationTimeout
        });
        
        // Add CSS to ensure all sections are visible in print
        await page.addStyleTag({ content: PRINT_CSS });
        
        // Wait for any client-side rendering to complete
        safeLogger.log('Waiting for rendering to complete...');
        await Promise.race([
            page.waitForFunction(
                'typeof window.__NEXT_HYDRATED__ !== "undefined" || document.readyState === "complete"', 
                { timeout: 10000 }
            ).catch(() => safeLogger.log('No hydration flag found, proceeding anyway')),
            new Promise(resolve => setTimeout(resolve, PAGE_SETTINGS.waitTimeMs))
        ]);
        
        // Additional wait to ensure everything is rendered
        await page.waitForTimeout(PAGE_SETTINGS.waitTimeMs);
        
        // Execute JavaScript to ensure all elements are visible
        await page.evaluate(() => {
            try {
                // Force visibility on all elements
                const sections = document.querySelectorAll('.print-section, .print-container, section, [data-testid], [id*="chart"], [id*="graph"]');
                sections.forEach(section => {
                    if (section) {
                        section.style.display = 'block';
                        section.style.visibility = 'visible';
                        section.style.opacity = '1';
                        section.style.height = 'auto';
                        section.style.overflow = 'visible';
                    }
                });
                
                // Ensure all images are loaded
                const images = Array.from(document.querySelectorAll('img'));
                images.forEach(img => {
                    if (img.loading === 'lazy') {
                        img.loading = 'eager';
                    }
                    if (!img.complete) {
                        img.src = img.src; // Force reload
                    }
                });
                
                // Make background colors and gradients visible for printing
                const elementsWithBackground = document.querySelectorAll('[class*="bg-"], [class*="background"], [style*="background"]');
                elementsWithBackground.forEach(el => {
                    if (el) {
                        el.setAttribute('data-print-background', 'true');
                    }
                });
                
                // Ensure all charts and graphs are visible
                const charts = document.querySelectorAll('canvas, svg, [id*="chart"], [id*="graph"]');
                charts.forEach(chart => {
                    if (chart) {
                        chart.style.display = 'block';
                        chart.style.visibility = 'visible';
                        chart.style.opacity = '1';
                        chart.style.maxWidth = '100%';
                    }
                });
                
                // Return rendering statistics for debugging
                return {
                    elements: document.querySelectorAll('*').length,
                    images: images.length,
                    charts: charts.length
                };
            } catch (error) {
                console.error('Error preparing page for PDF:', error);
                return { error: error.message };
            }
        });
        
        // Generate PDF
        safeLogger.log('Generating PDF...');
        await page.pdf({
            path: outputPath,
            format: 'Letter',
            printBackground: true,
            margin: {
                top: '0.5in',
                right: '0.5in',
                bottom: '0.5in',
                left: '0.5in'
            },
            displayHeaderFooter: true,
            headerTemplate: '<div></div>', // Empty header
            footerTemplate: `
                <div style="width: 100%; font-size: 8px; padding: 0 0.5in; display: flex; justify-content: space-between;">
                    <div>CommitIQ Analysis: ${username}</div>
                    <div>Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>
                </div>
            `,
            timeout: 60000 // 60 seconds timeout for PDF generation
        });
        
        // Verify the PDF was created
        if (fs.existsSync(outputPath)) {
            const stats = fs.statSync(outputPath);
            const endTime = performance.now();
            safeLogger.log(`PDF generated successfully at ${outputPath}`);
            safeLogger.log(`File size: ${(stats.size / 1024).toFixed(2)} KB`);
            safeLogger.log(`Generation time: ${((endTime - startTime) / 1000).toFixed(2)} seconds`);
            
            await browser.close();
            process.exit(0);
        } else {
            safeLogger.error(`PDF file was not created at ${outputPath}`);
            await browser.close();
            process.exit(1);
        }
        
    } catch (error) {
        safeLogger.error(`Error generating PDF: ${error.message}`);
        if (process.env.NODE_ENV !== 'production') {
          safeLogger.error(error.stack);
        }
        
        if (browser) {
            await browser.close();
        }
        
        process.exit(1);
    }
}

// Execute the PDF generation
generatePDF();
                