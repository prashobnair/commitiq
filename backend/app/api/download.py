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

@download_bp.route('/report', methods=['GET'])
def download_report_by_username():
    """
    Generate and download a report for a GitHub analysis based on username.
    This endpoint is more resilient as it doesn't require a specific analysis ID,
    allowing it to work even if database operations are asynchronous.
    """
    username = request.args.get('username')
    format_type = request.args.get('format', 'pdf').lower()
    
    if not username:
        return jsonify({'error': 'Username parameter is required'}), 400
        
    if format_type not in ['pdf', 'json']:
        return jsonify({'error': 'Unsupported format. Use "pdf" or "json"'}), 400
    
    conn = None
    try:
        # Get the analysis data by username (most recent)
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the most recent analysis for this username
        cur.execute('''
        SELECT a.*, d.full_analysis_data
        FROM github_analysis a
        LEFT JOIN github_analysis_details d ON a.id = d.analysis_id
        WHERE a.github_username = %s AND a.is_successful = true
        ORDER BY a.analyzed_at DESC
        LIMIT 1
        ''', (username,))
        
        analysis = cur.fetchone()
        
        if not analysis:
            # If no data in database yet (could be due to async storage),
            # return a simple error message suggesting to try again later
            return jsonify({'error': 'Analysis data not available yet. Please try again in a few moments.'}), 404
        
        # Use the existing download_report function logic by calling it with the found analysis ID
        return download_report(analysis['id'])
        
    except Exception as e:
        logger.error(f"Error looking up analysis by username: {e}")
        return jsonify({'error': f'Failed to generate report: {str(e)}'}), 500
    finally:
        if conn:
            conn.close()

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
        repos_impact = contributions.get('repos_impact', 0)
        
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
        
        developer_name = name or username
        consistency_percent = consistency * 100 if isinstance(consistency, (int, float)) else 0
        
        # Determine primary language focus if available
        languageFocus = ""
        top_languages = contributions.get('top_languages', [])
        if top_languages and len(top_languages) > 0:
            topLang = top_languages[0]
            langName = topLang.get('language', topLang.get('name', ''))
            if langName:
                languageFocus = f" with particular focus on {langName} development"
        
        # Create a list of key insights, prioritized by importance
        insights = []
        
        # Collaboration style (highest priority)
        if pulls > 30 and reviews > 20:
            insights.append(f"{developer_name} demonstrates a highly collaborative approach, actively contributing to team projects and providing thoughtful feedback{languageFocus}")
        elif pulls > 15 and reviews > 10:
            insights.append(f"{developer_name} shows good team collaboration skills, regularly contributing to shared codebases{languageFocus}")
        elif commits > 100 and (pulls < 10 or reviews < 5):
            insights.append(f"{developer_name} tends to focus on independent development, with strong contribution volume but less emphasis on collaborative workflows{languageFocus}")
        else:
            insights.append(f"{developer_name} balances independent work with team collaboration{languageFocus}")
        
        # Consistency and reliability (medium priority)
        if consistency > 0.8:
            insights.append("Their highly consistent activity pattern indicates strong reliability and sustained engagement over time")
        elif consistency > 0.6:
            insights.append("They maintain good consistency in their development work, suggesting reliable engagement")
        elif consistency > 0.4:
            insights.append("Their moderate consistency suggests periodic focused engagement rather than continuous development")
        elif commits > 50:
            insights.append("Their engagement pattern shows variability, potentially indicating project-based work rather than ongoing maintenance")
        
        # Code quality focus (medium priority)
        if reviews > commits * 0.3:
            insights.append("Their significant focus on code reviews demonstrates a commitment to code quality and mentorship")
        elif reviews > commits * 0.1:
            insights.append("They regularly participate in code reviews, showing attention to quality and collaborative improvement")
        elif reviews > 10:
            insights.append("They occasionally engage in code review processes, providing some quality oversight")
        
        # Project impact (lower priority)
        if repos_impact > 0.05:
            insights.append("Their contributions demonstrate significant impact across repositories, suggesting influence on important projects")
        elif repos_impact > 0.02 and commits > 50:
            insights.append("They show meaningful impact on the repositories they contribute to")
        
        # Limit to the most important 4 insights
        summaryText = ""
        maxSentences = 4
        sentenceCount = 0
        
        for i in range(min(len(insights), maxSentences)):
            if summaryText:
                summaryText += " "
            summaryText += insights[i] + "."
            sentenceCount += 1
        
        developer_summary = summaryText
        
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
        allStrengths = []
        allConsiderations = []
        
        # Analyze collaboration patterns
        if pulls > 30 and commits > 100:
            allStrengths.append('Strong balance of code contribution and collaborative development through pull requests')
        elif pulls > 20:
            allStrengths.append('Demonstrates effective collaborative workflow through regular pull request contributions')
        elif commits > 200 and pulls > 10:
            allStrengths.append('High volume of code contributions with moderate collaborative engagement')
        
        # Analyze consistency patterns
        if consistency > 0.8:
            allStrengths.append('Exceptional consistency in development activity, suggesting strong reliability and sustained engagement')
        elif consistency > 0.6:
            allStrengths.append('Maintains good consistency in development work, indicating reliable contribution patterns')
        elif consistency < 0.4 and commits > 100:
            allConsiderations.append('Contributions tend to be concentrated in intense periods rather than consistent engagement')
        
        # Analyze code quality focus
        if reviews > 30:
            allStrengths.append('Strong commitment to code quality through frequent and detailed code reviews')
        elif reviews > 15:
            allStrengths.append('Regular participation in code review processes, demonstrating attention to quality')
        elif commits > 100 and reviews < 5:
            allConsiderations.append('Limited engagement in code review processes compared to contribution volume')
        
        # Analyze specialization and focus areas
        if top_languages and len(top_languages) > 0:
            topLang = top_languages[0]
            langName = topLang.get('language', topLang.get('name', ''))
            if langName:
                allStrengths.append(f'Demonstrates strong specialization in {langName} development')
            
            # Check for language diversity
            if len(top_languages) >= 3:
                allStrengths.append('Versatile across multiple programming languages, suggesting adaptability to different technical requirements')
        else:
            allConsiderations.append('Limited data on language specialization, making it difficult to assess technical focus areas')
        
        # Analyze project impact
        if repos_impact > 0.05:
            allStrengths.append('Significant impact on project repositories, suggesting meaningful contributions to important codebases')
        elif repos_impact < 0.02 and commits > 100:
            allConsiderations.append('Contributions may be spread across many repositories or focused on less central codebases')
        
        # Analyze repository contribution patterns
        top_repositories = contributions.get('top_repositories', [])
        if top_repositories and len(top_repositories) > 0:
            hasHighStarRepo = any(repo.get('stars', 0) > 100 for repo in top_repositories)
            if hasHighStarRepo:
                allStrengths.append('Experience contributing to popular, widely-used repositories')
            
            hasHighImpactContributions = any(
                repo.get('impact_score', 0) > 0.05 or 
                (
                    isinstance(repo.get('num_commits', ''), str) and 
                    any(float(match) > 10 for match in [num.strip('%') for num in repo.get('num_commits', '').split() if num.strip('%').replace('.', '', 1).isdigit()])
                )
                for repo in top_repositories
            )
            
            if hasHighImpactContributions:
                allStrengths.append('Demonstrated ability to make significant contributions to individual projects')
        
        # Ensure we have at least one strength
        if not allStrengths:
            if commits > 0 or pulls > 0:
                allStrengths.append('Shows engagement with GitHub projects, demonstrating basic version control competence')
            else:
                allStrengths.append('Has established a GitHub presence, though activity metrics are limited')
        
        # If no considerations, add an appropriate one
        if not allConsiderations:
            if consistency < 0.7 and consistency > 0.4:
                allConsiderations.append('Moderate consistency in development activity may indicate varying engagement levels over time')
            elif pulls < 20 and reviews < 15 and pulls > 0:
                allConsiderations.append('Could benefit from increased engagement with collaborative development workflows')
            elif commits < 50 and pulls < 10:
                allConsiderations.append('Limited volume of public GitHub activity, which may not fully represent technical capabilities')
            else:
                allConsiderations.append('No significant concerns identified in the contribution pattern')
        
        # Prioritize and limit strengths and considerations to 3 each
        strengths = allStrengths[:3]
        considerations = allConsiderations[:3]
            
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
            bottomMargin=72,
            title=f"CommitIQ GitHub Developer Impact Report - {username}"
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
                # Check both possible field names for language
                repo_lang = repo.get('primaryLanguage') or repo.get('primary_language', 'N/A')
                
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
        
        # Create footer text with hyperlinks - ReportLab's Paragraph supports hyperlinks with <a> tags
        footer_text = (
            "This report was generated by "
            f"<a href='{website_url}' color='blue'><u>CommitIQ.ai</u></a>, "
            "a platform that analyzes GitHub activity to provide objective insights into developer skills and contributions."
        )
        
        elements.append(Paragraph(footer_text, center_style))
        elements.append(Spacer(1, 0.1 * inch))
        
        copyright_text = (
            f"© {datetime.now().year} CommitIQ. All rights reserved. "
        )
        
        elements.append(Paragraph(copyright_text, center_style))
        
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