import os
import logging
import subprocess
import time
import uuid
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from ..models import PDFExport, Analysis, db

# Get logger for this module
logger = logging.getLogger(__name__)

class PDFService:
    """
    Service for generating and managing PDFs from analysis data.
    """
    
    # Configuration
    PDF_OUTPUT_DIR = os.environ.get("PDF_OUTPUT_DIR", "./pdfs")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000")
    
    def __init__(self):
        """Initialize the PDF service."""
        # Create output directory if it doesn't exist
        os.makedirs(self.PDF_OUTPUT_DIR, exist_ok=True)
        logger.info(f"PDF output directory: {self.PDF_OUTPUT_DIR}")
    
    def generate_pdf(self, analysis_id, username):
        """
        Generate a PDF for a specific analysis.
        
        Args:
            analysis_id (str): Analysis ID
            username (str): GitHub username
            
        Returns:
            dict: Result with file path or error details
        """
        logger.info(f"Generating PDF for analysis {analysis_id} (user: {username})")
        
        # Create a unique filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{username}_{timestamp}_{str(uuid.uuid4())[:8]}.pdf"
        output_path = os.path.join(self.PDF_OUTPUT_DIR, filename)
        
        # Create a PDF export record in the database
        pdf_export = PDFExport(
            analysis_id=analysis_id,
            file_path=output_path,
            status='pending'
        )
        db.session.add(pdf_export)
        db.session.commit()
        
        try:
            # Generate the PDF using the optimized generator
            print_url = f"{self.BASE_URL}/print/{username}?id={analysis_id}"
            
            # Set up the command to run the PDF generator script
            node_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'app/utils/generate_pdf.js')
            
            # Run the PDF generator
            result = self._run_pdf_generator(node_script_path, print_url, output_path)
            
            if result['success']:
                # Update the PDF export record
                pdf_export.status = 'completed'
                db.session.commit()
                
                logger.info(f"PDF generated successfully: {output_path}")
                return {
                    'success': True,
                    'file_path': output_path,
                    'id': str(pdf_export.id)
                }
            else:
                # Update the PDF export record
                pdf_export.status = 'failed'
                pdf_export.error_message = result['error']
                db.session.commit()
                
                logger.error(f"PDF generation failed: {result['error']}")
                return {
                    'success': False,
                    'error': result['error']
                }
                
        except Exception as e:
            logger.exception(f"Error generating PDF: {str(e)}")
            
            # Update the PDF export record
            pdf_export.status = 'failed'
            pdf_export.error_message = str(e)
            db.session.commit()
            
            return {
                'success': False,
                'error': f"Failed to generate PDF: {str(e)}"
            }
    
    def _run_pdf_generator(self, script_path, url, output_path):
        """
        Run the PDF generator script.
        
        Args:
            script_path (str): Path to the Node.js PDF generator script
            url (str): URL to render
            output_path (str): Path to save the PDF
            
        Returns:
            dict: Result with success flag and error details if any
        """
        try:
            # Prepare the command
            command = ['node', script_path, url, output_path]
            
            # Run the command with a timeout
            logger.info(f"Running PDF generator: {' '.join(command)}")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for the process to complete with a timeout
            try:
                stdout, stderr = process.communicate(timeout=60)  # 60 second timeout
                
                if process.returncode != 0:
                    logger.error(f"PDF generator failed with code {process.returncode}: {stderr}")
                    return {
                        'success': False,
                        'error': f"PDF generation failed with code {process.returncode}: {stderr}"
                    }
                
                # Check if the output file exists
                if not os.path.exists(output_path):
                    logger.error(f"PDF file was not created: {output_path}")
                    return {
                        'success': False,
                        'error': "PDF file was not created"
                    }
                
                logger.info(f"PDF generated successfully at {output_path}")
                return {
                    'success': True
                }
                
            except subprocess.TimeoutExpired:
                # Kill the process if it times out
                process.kill()
                logger.error("PDF generation timed out")
                return {
                    'success': False,
                    'error': "PDF generation timed out"
                }
                
        except Exception as e:
            logger.exception(f"Error running PDF generator: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to run PDF generator: {str(e)}"
            }
    
    async def generate_pdf_async(self, analysis_id, username):
        """
        Generate a PDF asynchronously.
        
        Args:
            analysis_id (str): Analysis ID
            username (str): GitHub username
            
        Returns:
            dict: Result with task ID for tracking
        """
        # Create a task ID for tracking
        task_id = str(uuid.uuid4())
        
        # Launch the PDF generation in a separate task
        asyncio.create_task(self._async_pdf_generation(task_id, analysis_id, username))
        
        return {
            'success': True,
            'task_id': task_id,
            'message': "PDF generation started"
        }
    
    async def _async_pdf_generation(self, task_id, analysis_id, username):
        """
        Internal method to handle asynchronous PDF generation.
        
        Args:
            task_id (str): Task ID for tracking
            analysis_id (str): Analysis ID
            username (str): GitHub username
        """
        # Use the synchronous method but in an async context
        result = self.generate_pdf(analysis_id, username)
        
        # Here you could update a task status in Redis or another storage mechanism
        logger.info(f"Async PDF generation completed for task {task_id}: {result['success']}")
    
    def get_pdf_status(self, pdf_id):
        """
        Get the status of a PDF export.
        
        Args:
            pdf_id (str): PDF export ID
            
        Returns:
            dict: PDF export status and details
        """
        try:
            # Query the database for the PDF export
            pdf_export = PDFExport.query.get(pdf_id)
            
            if not pdf_export:
                return {
                    'success': False,
                    'error': "PDF export not found"
                }
            
            return {
                'success': True,
                'status': pdf_export.status,
                'created_at': pdf_export.created_at.isoformat(),
                'file_exists': os.path.exists(pdf_export.file_path) if pdf_export.file_path else False,
                'error': pdf_export.error_message
            }
            
        except Exception as e:
            logger.exception(f"Error getting PDF status: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to get PDF status: {str(e)}"
            }
    
    def delete_pdf(self, pdf_id):
        """
        Delete a PDF export.
        
        Args:
            pdf_id (str): PDF export ID
            
        Returns:
            dict: Result with success flag
        """
        try:
            # Query the database for the PDF export
            pdf_export = PDFExport.query.get(pdf_id)
            
            if not pdf_export:
                return {
                    'success': False,
                    'error': "PDF export not found"
                }
            
            # Delete the file if it exists
            if pdf_export.file_path and os.path.exists(pdf_export.file_path):
                os.remove(pdf_export.file_path)
            
            # Delete the database record
            db.session.delete(pdf_export)
            db.session.commit()
            
            return {
                'success': True,
                'message': "PDF export deleted"
            }
            
        except Exception as e:
            logger.exception(f"Error deleting PDF: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to delete PDF: {str(e)}"
            }
    
    def cleanup_old_pdfs(self, days=7):
        """
        Clean up old PDF files.
        
        Args:
            days (int): Delete PDFs older than this many days
            
        Returns:
            dict: Result with count of deleted files
        """
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Query for old PDF exports
            old_exports = PDFExport.query.filter(PDFExport.created_at < cutoff_date).all()
            
            count = 0
            for export in old_exports:
                # Delete the file if it exists
                if export.file_path and os.path.exists(export.file_path):
                    os.remove(export.file_path)
                    count += 1
                
                # Delete the database record
                db.session.delete(export)
            
            db.session.commit()
            
            logger.info(f"Cleaned up {count} old PDF files")
            return {
                'success': True,
                'count': count
            }
            
        except Exception as e:
            logger.exception(f"Error cleaning up old PDFs: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to clean up old PDFs: {str(e)}"
            }

# Create a singleton instance
pdf_service = PDFService() 