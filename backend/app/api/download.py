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
import base64
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

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
                result['analysis'] = details['full_analysis_data']
            elif analysis.get('full_analysis_data'):
                result['analysis'] = analysis['full_analysis_data']
            
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
            
        # For PDF format using ReportLab (no external dependencies)
        # Prepare data for the report
        full_data = {}
        if details and details.get('full_analysis_data'):
            full_data = details['full_analysis_data']
        elif analysis.get('full_analysis_data'):
            full_data = analysis['full_analysis_data']
            
        analysis_data = full_data.get('analysis', {})
        contributions = analysis_data.get('contributions', {})
        
        # Generate a developer summary if none exists
        developer_summary = ''
        name = analysis_data.get('name', '')
        username = analysis_data.get('username', analysis['github_username'])
        commits = contributions.get('commits', 0)
        pulls = contributions.get('pulls', 0)
        consistency = contributions.get('consistency', 0)
        reviews = contributions.get('reviews', 0)
        
        # Helper function to determine rating based on value
        def get_rating(value, type_str):
            if type_str == 'prs':
                if value > 50: return 'High'
                if value > 20: return 'Above Average'
                if value > 10: return 'Moderate'
                return 'Low'
            elif type_str == 'commits':
                if value > 300: return 'High'
                if value > 100: return 'Above Average'
                if value > 50: return 'Moderate'
                return 'Low'
            elif type_str == 'consistency':
                if value > 0.8: return 'Excellent'
                if value > 0.6: return 'Good'
                if value > 0.4: return 'Moderate'
                return 'Inconsistent'
            elif type_str == 'issues':
                if value > 40: return 'High'
                if value > 20: return 'Above Average'
                if value > 10: return 'Moderate'
                return 'Low'
            return 'Moderate'
            
        pr_rating = get_rating(pulls, 'prs')
        commit_rating = get_rating(commits, 'commits')
        consistency_rating = get_rating(consistency, 'consistency')
        
        developer_name = name or username
        consistency_percent = consistency * 100 if isinstance(consistency, (int, float)) else 0
        
        developer_summary = f"{developer_name} has made {commits} commits and {pulls} pull requests, showing {pr_rating.lower()} collaboration. Their consistency is {consistency_percent:.1f}%, indicating {consistency_rating.lower()} regular activity. With {reviews} code reviews, they actively engage in code discussions. Overall, they're a {commit_rating.lower()} contributor who {'frequently' if pulls > 30 else 'occasionally'} participates in various projects."
        
        # Determine overall rating
        impact_score = float(analysis['impact_score']) if analysis['impact_score'] else 0.0
        overall_rating = 'Exceptional Contributor'
        if impact_score <= 40:
            overall_rating = 'Developing Contributor'
        elif impact_score <= 50:
            overall_rating = 'Solid Contributor'
        elif impact_score <= 60:
            overall_rating = 'Above Average Contributor'
        elif impact_score <= 70:
            overall_rating = 'Strong Contributor'
        elif impact_score <= 80:
            overall_rating = 'Exceptional Contributor'
            
        # Determine strengths and considerations
        strengths = []
        considerations = []
        
        # Analyze strengths
        if pulls > 30:
            strengths.append('High number of pull requests, indicating strong collaboration')
        if consistency > 0.7:
            strengths.append(f'Excellent consistency ({consistency_percent:.1f}% active days)')
        if reviews > 20:
            strengths.append('Frequent code reviews, showing willingness to provide feedback')
        if commits > 200:
            strengths.append('Significant number of commits, demonstrating active development')
            
        # Analyze considerations
        repos_impact = contributions.get('repos_impact', 0)
        if repos_impact < 0.03:
            considerations.append('Lower repository impact score—contributions may be in less popular repos')
        if pulls < 10 and commits > 100:
            considerations.append('High commits but low PRs may indicate solo work rather than collaboration')
        if consistency < 0.5:
            considerations.append('Inconsistent contribution pattern may indicate sporadic engagement')
            
        # Ensure we have at least one strength
        if not strengths:
            strengths.append('Shows engagement with GitHub projects')
            
        # If no considerations, add a neutral one
        if not considerations:
            considerations.append('No significant concerns identified in the contribution pattern')
            
        # Extract top languages and repositories
        top_languages = contributions.get('top_languages', [])
        top_repositories = contributions.get('top_repositories', [])
        
        # Create a PDF using ReportLab
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Create custom styles with unique names
        title_style = ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        subtitle_style = ParagraphStyle(
            name='CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=6
        )
        
        center_style = ParagraphStyle(
            name='CustomCenter',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            # Enable link functionality in this style
            linkUnderline=True 
        )
        
        # Add a style specifically for hyperlinks if needed
        link_style = ParagraphStyle(
            name='HyperlinkStyle',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            textColor=colors.blue,
            linkUnderline=True
        )
        
        # Build the PDF content
        elements = []
        
        # Title
        elements.append(Paragraph("GitHub Developer Impact Report", title_style))
        elements.append(Paragraph(f"Generated by <a href='https://commitiq.ai' color='blue'><u>CommitIQ.ai</u></a>, on {datetime.now().strftime('%Y-%m-%d %H:%M')}", center_style))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Developer Profile
        elements.append(Paragraph(f"Developer Profile: {username}", subtitle_style))
        elements.append(Spacer(1, 0.1 * inch))
        
        # Impact Score
        elements.append(Paragraph(f"Impact Score: {impact_score:.1f}/100 - {overall_rating}", styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))
        
        # Summary
        elements.append(Paragraph("Developer Summary:", subtitle_style))
        elements.append(Paragraph(developer_summary, styles['Normal']))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Activity Metrics
        elements.append(Paragraph("Activity Metrics", subtitle_style))
        
        issues = contributions.get('issues', 0)
        
        metrics_data = [
            ["Metric", "Value", "Rating"],
            ["Total Commits", str(commits), get_rating(commits, 'commits')],
            ["Pull Requests", str(pulls), get_rating(pulls, 'prs')],
            ["Issues Raised", str(issues), get_rating(issues, 'issues')],
            ["Code Reviews", str(reviews), get_rating(reviews, 'prs')],
            ["Consistency", f"{consistency_percent:.1f}%", get_rating(consistency, 'consistency')],
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2*inch, 1*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(metrics_table)
        elements.append(Spacer(1, 0.2 * inch))
        
        # Strengths and Considerations
        elements.append(Paragraph("Key Strengths", subtitle_style))
        for strength in strengths:
            elements.append(Paragraph(f"• {strength}", styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))
        
        elements.append(Paragraph("Considerations", subtitle_style))
        for consideration in considerations:
            elements.append(Paragraph(f"• {consideration}", styles['Normal']))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Top Languages
        if top_languages:
            elements.append(Paragraph("Most Used Languages", subtitle_style))
            
            lang_data = [["Language", "Percentage"]]
            for lang in top_languages:
                # Handle different language data formats
                lang_name = lang.get('name', lang.get('language', 'Unknown'))
                
                # Check if percentage is already in percentage format (> 1) or decimal format (< 1)
                lang_percentage = 0
                if 'percentage' in lang:
                    lang_percentage = lang['percentage']
                    if lang_percentage <= 1:
                        lang_percentage *= 100
                elif 'percent' in lang:
                    lang_percentage = lang['percent']
                    if lang_percentage <= 1:
                        lang_percentage *= 100
                    
                lang_data.append([lang_name, f"{lang_percentage:.1f}%"])
            
            lang_table = Table(lang_data, colWidths=[3*inch, 2*inch])
            lang_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(lang_table)
            elements.append(Spacer(1, 0.2 * inch))
        
        # Top Repositories
        if top_repositories:
            elements.append(Paragraph("Top Repositories", subtitle_style))
            
            repo_data = [["Repository", "Stars", "Forks", "Language"]]
            for repo in top_repositories:
                repo_name = repo.get('name', 'Unknown')
                repo_stars = repo.get('stars', 0)
                repo_forks = repo.get('forks', 0)
                repo_lang = repo.get('primary_language', 'N/A')
                
                repo_data.append([repo_name, str(repo_stars), str(repo_forks), repo_lang or 'N/A'])
            
            repo_table = Table(repo_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.5*inch])
            repo_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(repo_table)
            elements.append(Spacer(1, 0.2 * inch))
        
        # Footer with clickable link
        website_url = "https://commitiq.ai"
        
        copyright_text = (
            f"© {datetime.now().year} CommitIQ. All rights reserved. "
        )
        
        elements.append(Paragraph(copyright_text, center_style))
        
        # Add a direct Visit Website link as a standalone element for better visibility
        elements.append(Spacer(1, 0.05 * inch))
        elements.append(Paragraph(
            f"<a href='{website_url}' color='blue'><u>Visit www.commitiq.ai</u></a>",
            link_style
        ))
        
        # Build the document
        doc.build(elements)
        
        # Reset buffer position to the beginning
        buffer.seek(0)
        
        # Create a sanitized filename for the download
        safe_username = ''.join(c if c.isalnum() else '_' for c in analysis['github_username'])
        filename = f"CommitIQ_Analysis_{safe_username}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(buffer.getvalue())
            tmp_path = tmp.name
            
        # Send the file
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({'error': f'Failed to generate report: {str(e)}'}), 500
    finally:
        if conn:
            conn.close() 