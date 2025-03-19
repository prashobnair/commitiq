const puppeteer = require('puppeteer');
const path = require('path');

async function generatePDF() {
    // Get command-line arguments
    const args = process.argv.slice(2);
    const url = args[0];
    const outputPath = args[1];
    
    if (!url || !outputPath) {
        console.error('URL and output path are required');
        process.exit(1);
    }
    
    try {
        console.log(`Generating PDF from URL: ${url}`);
        console.log(`Saving to: ${outputPath}`);
        
        // Launch browser
        const browser = await puppeteer.launch({
            args: ['--no-sandbox', '--disable-setuid-sandbox'],
            headless: 'new' // Use new headless mode
        });
        
        const page = await browser.newPage();
        
        // Set viewport size to match letter size paper in pixels (at 96 DPI)
        await page.setViewport({
            width: 816,
            height: 1056,
            deviceScaleFactor: 2 // Higher resolution
        });
        
        // Navigate to the URL
        await page.goto(url, { waitUntil: 'networkidle0' });
        
        // Wait for content to fully render
        await page.waitForTimeout(2000);
        
        // Generate PDF
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
        
        await browser.close();
        console.log('PDF generated successfully');
    } catch (error) {
        console.error('Error generating PDF:', error);
        process.exit(1);
    }
}

generatePDF();
                