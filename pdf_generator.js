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

// Extract username from URL for targeted debugging
const urlObj = new URL(url);
const pathname = urlObj.pathname;
const username = pathname.split('/').pop();

// Check if this is a problematic user that needs special handling
const isProblematicUser = username === 'fketelaars';
const debugMode = isProblematicUser;

async function generatePDF() {
    console.log(`Generating PDF from: ${url}`);
    console.log(`Output path: ${outputPath}`);
    if (isProblematicUser) {
        console.log(`Detected problematic user: ${username}, enabling enhanced rendering`);
    }
    
    try {
        // Launch a new browser instance with improved settings
        const browser = await puppeteer.launch({
            headless: true,
            args: [
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--font-render-hinting=none',
                '--disable-web-security',
                '--disable-features=IsolateOrigins',
                '--disable-site-isolation-trials'
            ]
        });
        
        // Create a new page
        const page = await browser.newPage();
        
        // Set up console log handling for debugging
        if (debugMode) {
            page.on('console', msg => console.log('PAGE LOG:', msg.text()));
            page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
        }
        
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
            timeout: 60000 // Increase timeout for problematic users
        });
        
        // Add CSS to ensure all sections are visible in print
        await page.addStyleTag({
            content: `
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
                }
            `
        });
        
        // Wait for React to hydrate and render
        console.log('Waiting for rendering to complete...');
        await page.waitForFunction(
            'typeof window.__NEXT_HYDRATED__ !== "undefined" || document.readyState === "complete"', 
            { timeout: 10000 }
        ).catch(e => console.log('No hydration flag found, proceeding anyway'));
        
        // Wait a bit more to ensure everything is rendered
        await page.waitForTimeout(3000);
        
        // Inject JavaScript to ensure all elements are visible
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
                        const computedStyle = window.getComputedStyle(el);
                        const backgroundColor = computedStyle.backgroundColor;
                        const backgroundImage = computedStyle.backgroundImage;
                        
                        if (backgroundColor !== 'rgba(0, 0, 0, 0)' && backgroundColor !== 'transparent') {
                            el.style.backgroundColor = backgroundColor;
                        }
                        
                        if (backgroundImage !== 'none') {
                            el.style.backgroundImage = backgroundImage;
                            el.style.webkitPrintColorAdjust = 'exact';
                            el.style.printColorAdjust = 'exact';
                        }
                    }
                });
                
                // Wait for potential repaints to complete
                return "Visibility enforced for all sections";
            } catch (error) {
                console.error('Error in visibility script:', error);
                return "Error: " + error.message;
            }
        }).then(result => console.log('Visibility script result:', result));
        
        // Take a screenshot for debugging if needed
        if (debugMode) {
            const screenshotPath = `${path.dirname(outputPath)}/${username}_debug_screenshot.png`;
            await page.screenshot({ path: screenshotPath, fullPage: true });
            console.log(`Debug screenshot saved to: ${screenshotPath}`);
        }
        
        // Calculate the full height of the page
        const bodyHeight = await page.evaluate(() => {
            return Math.max(
                document.body.scrollHeight,
                document.body.offsetHeight,
                document.documentElement.clientHeight,
                document.documentElement.scrollHeight,
                document.documentElement.offsetHeight
            );
        });
        
        // Adjust viewport if needed
        if (bodyHeight > 1056) {
            await page.setViewport({
                width: 816,
                height: bodyHeight,
                deviceScaleFactor: 2
            });
            console.log(`Adjusted viewport height to: ${bodyHeight}px`);
        }
        
        // Generate the PDF
        console.log('Generating PDF...');
        await page.pdf({
            path: outputPath,
            format: 'Letter',
            printBackground: true,
            preferCSSPageSize: false,
            margin: {
                top: '0.4in',
                right: '0.4in',
                bottom: '0.4in',
                left: '0.4in'
            },
            height: bodyHeight > 1056 ? `${bodyHeight}px` : undefined
        });
        
        // Check if the PDF was created and has content
        const stats = fs.statSync(outputPath);
        if (stats.size < 1000) {
            console.warn(`Warning: PDF file size is suspiciously small (${stats.size} bytes)`);
        } else {
            console.log(`PDF generated successfully! Size: ${stats.size} bytes`);
        }
        
        // Close the browser
        await browser.close();
        
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