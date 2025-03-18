"""
Module for downloading GitHub analysis reports in various formats (PDF, JSON).
This allows users to download and save their GitHub analysis results.
"""

from flask import Blueprint, request, jsonify, current_app, send_file
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import tempfile
import json
from datetime import datetime
import pdfkit
from jinja2 import Environment, FileSystemLoader
import base64

# Get module logger
logger = logging.getLogger(__name__)

# Blueprint definition
download_bp = Blueprint('download', __name__)

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT', '5432'),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

@download_bp.route('/report/<int:analysis_id>', methods=['GET'])
def download_report(analysis_id):
    """Generate and download a report for a GitHub analysis in PDF or JSON format."""
    format_type = request.args.get('format', 'pdf').lower()
    
    if format_type not in ['pdf', 'json']:
        return jsonify({'error': 'Unsupported format. Use "pdf" or "json"'}), 400
    
    conn = None
    try:
        # Get the analysis data
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get basic analysis data
        cur.execute('''
        SELECT a.*, d.full_analysis_data
        FROM github_analysis a
        LEFT JOIN github_analysis_details d ON a.id = d.analysis_id
        WHERE a.id = %s
        ''', (analysis_id,))
        
        analysis = cur.fetchone()
        
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
        
        # Get detailed metrics if available
        cur.execute('''
        SELECT * FROM github_analysis_details
        WHERE analysis_id = %s
        ''', (analysis_id,))
        
        details = cur.fetchone()
        
        # For JSON format, return the raw data
        if format_type == 'json':
            # Extract the relevant data
            result = {
                'github_username': analysis['github_username'],
                'impact_score': float(analysis['impact_score']) if analysis['impact_score'] else 0.0,
                'analyzed_at': analysis['analyzed_at'].isoformat() if analysis['analyzed_at'] else None,
            }
            
            # Include the full analysis data if available
            if details and details.get('full_analysis_data'):
                result['analysis'] = details['full_analysis_data'].get('analysis', {})
            elif analysis.get('full_analysis_data'):
                result['analysis'] = analysis['full_analysis_data'].get('analysis', {})
            
            # Generate filename
            safe_username = ''.join(c if c.isalnum() else '_' for c in analysis['github_username'])
            filename = f"CommitIQ_Analysis_{safe_username}_{datetime.now().strftime('%Y%m%d')}.json"
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
                tmp.write(json.dumps(result, indent=2).encode('utf-8'))
                tmp_path = tmp.name
                
            return send_file(
                tmp_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/json'
            )
            
        # For PDF format
        # Prepare data for template
        # Extract data for the report
        full_data = {}
        if details and details.get('full_analysis_data'):
            full_data = details['full_analysis_data']
        elif analysis.get('full_analysis_data'):
            full_data = analysis['full_analysis_data']
            
        analysis_data = full_data.get('analysis', {})
        contributions = analysis_data.get('contributions', {})
        
        # Generate a developer summary if none exists
        developer_summary = ''
        if analysis_data:
            try:
                username = analysis_data.get('username', analysis['github_username'])
                name = analysis_data.get('name', username)
                
                # Extract contribution metrics
                commits = contributions.get('commits', 0)
                pulls = contributions.get('pulls', 0)
                issues = contributions.get('issues', 0)
                reviews = contributions.get('reviews', 0)
                consistency = contributions.get('consistency', 0)
                
                # Generate a simple summary
                developer_summary = f"{name} has made {commits} commits and {pulls} pull requests on GitHub. "
                
                if consistency > 0:
                    consistency_pct = consistency * 100
                    if consistency_pct > 50:
                        developer_summary += f"They show consistent activity with {consistency_pct:.1f}% active days. "
                    else:
                        developer_summary += f"Their activity shows some gaps with {consistency_pct:.1f}% active days. "
                
                if issues > 0:
                    developer_summary += f"They've raised {issues} issues "
                    if reviews > 0:
                        developer_summary += f"and provided {reviews} code reviews. "
                    else:
                        developer_summary += ". "
                elif reviews > 0:
                    developer_summary += f"They've provided {reviews} code reviews. "
                    
                # Add impact score context
                impact_score = float(analysis['impact_score']) if analysis['impact_score'] else 0.0
                if impact_score > 80:
                    developer_summary += "Overall, they demonstrate exceptional contribution patterns."
                elif impact_score > 60:
                    developer_summary += "Overall, they show strong contribution patterns."
                elif impact_score > 40:
                    developer_summary += "Overall, they show moderate contribution activity."
                else:
                    developer_summary += "Their GitHub activity indicates they're still developing their contribution patterns."
            except Exception as e:
                logger.error(f"Error generating developer summary: {e}")
                # Default summary if generation fails
                developer_summary = f"GitHub profile analysis for {analysis['github_username']}"
        
        template_data = {
            'github_username': analysis['github_username'],
            'impact_score': float(analysis['impact_score']) if analysis['impact_score'] else 0.0,
            'developer_summary': developer_summary,
            'analyzed_at': analysis['analyzed_at'].strftime('%Y-%m-%d %H:%M:%S') if analysis['analyzed_at'] else datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_commits': contributions.get('commits', 0),
            'pull_requests': contributions.get('pulls', 0),
            'issues': contributions.get('issues', 0),
            'reviews': contributions.get('reviews', 0),
            'avatar_url': analysis_data.get('avatarUrl', ''),
            'name': analysis_data.get('name', ''),
            'company': analysis_data.get('company', ''),
            'location': analysis_data.get('location', ''),
            'email': analysis_data.get('email', ''),
            'followers': analysis_data.get('followers', 0),
            'following': analysis_data.get('following', 0),
            'top_languages': contributions.get('top_languages', []),
            'top_repositories': contributions.get('top_repositories', []),
            'date_generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'commitiq_logo_url': '/static/images/logo.png'  # Path to logo
        }
        
        # Load and render template
        templates_dir = os.path.join(current_app.root_path, 'templates')
        
        # Check if the template directory exists, if not create it
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
            
        # Check if the report template exists, if not create a basic one
        template_path = os.path.join(templates_dir, 'report_template.html')
        if not os.path.exists(template_path):
            with open(template_path, 'w') as f:
                f.write('''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>GitHub Analysis Report - {{ github_username }}</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }
                        .header { text-align: center; margin-bottom: 30px; }
                        .logo { max-width: 200px; }
                        .summary { background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
                        .score { font-size: 24px; font-weight: bold; color: #0066cc; }
                        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                        th { background-color: #f2f2f2; }
                        .section { margin: 30px 0; }
                        .footer { margin-top: 50px; font-size: 12px; color: #666; text-align: center; }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>GitHub Developer Analysis Report</h1>
                        <p>{{ github_username }}</p>
                        <p>Generated on {{ date_generated }}</p>
                    </div>
                    
                    <div class="summary">
                        <h2>Developer Summary</h2>
                        <p>{{ developer_summary }}</p>
                        <p><strong>Impact Score:</strong> <span class="score">{{ impact_score }}</span> out of 100</p>
                    </div>
                    
                    <div class="section">
                        <h2>Developer Profile</h2>
                        <table>
                            <tr><th>Username</th><td>{{ github_username }}</td></tr>
                            {% if name %}<tr><th>Name</th><td>{{ name }}</td></tr>{% endif %}
                            {% if company %}<tr><th>Company</th><td>{{ company }}</td></tr>{% endif %}
                            {% if location %}<tr><th>Location</th><td>{{ location }}</td></tr>{% endif %}
                            {% if email %}<tr><th>Email</th><td>{{ email }}</td></tr>{% endif %}
                            <tr><th>Followers</th><td>{{ followers }}</td></tr>
                            <tr><th>Following</th><td>{{ following }}</td></tr>
                        </table>
                    </div>
                    
                    <div class="section">
                        <h2>Contribution Metrics</h2>
                        <table>
                            <tr><th>Total Commits</th><td>{{ total_commits }}</td></tr>
                            <tr><th>Pull Requests</th><td>{{ pull_requests }}</td></tr>
                            <tr><th>Issues</th><td>{{ issues }}</td></tr>
                            <tr><th>Code Reviews</th><td>{{ reviews }}</td></tr>
                        </table>
                    </div>
                    
                    {% if top_languages %}
                    <div class="section">
                        <h2>Top Languages</h2>
                        <table>
                            <tr><th>Language</th><th>Usage Percentage</th></tr>
                            {% for lang in top_languages %}
                            <tr><td>{{ lang.name }}</td><td>{{ lang.percentage }}%</td></tr>
                            {% endfor %}
                        </table>
                    </div>
                    {% endif %}
                    
                    {% if top_repositories %}
                    <div class="section">
                        <h2>Top Repositories</h2>
                        <table>
                            <tr><th>Repository</th><th>Stars</th><th>Forks</th><th>Primary Language</th></tr>
                            {% for repo in top_repositories %}
                            <tr>
                                <td>{{ repo.name }}</td>
                                <td>{{ repo.stars }}</td>
                                <td>{{ repo.forks }}</td>
                                <td>{{ repo.primary_language or 'N/A' }}</td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                    {% endif %}
                    
                    <div class="footer">
                        <p>© CommitIQ - All rights reserved</p>
                        <p>This report contains data from public GitHub repositories and is intended for recruitment and evaluation purposes only.</p>
                    </div>
                </body>
                </html>
                ''')
                
        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template('report_template.html')
        
        # Render the template
        html_content = template.render(**template_data)
        
        # Generate PDF
        pdf_options = {
            'page-size': 'Letter',
            'encoding': 'UTF-8',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'title': f'GitHub Analysis Report - {analysis["github_username"]}',
            'footer-right': 'Page [page] of [topage]',
            'footer-font-size': '8'
        }
        
        # Create a temporary file for the PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = tmp.name
            
        # Try to generate the PDF
        try:
            pdfkit.from_string(html_content, pdf_path, options=pdf_options)
        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            return jsonify({'error': 'Failed to generate PDF report. See server logs for details.'}), 500
            
        # Create a sanitized filename for the download
        safe_username = ''.join(c if c.isalnum() else '_' for c in analysis['github_username'])
        filename = f"CommitIQ_Analysis_{safe_username}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        # Send the file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({'error': 'Failed to generate report. See server logs for details.'}), 500
    finally:
        if conn:
            conn.close() 