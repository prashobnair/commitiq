import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

db = SQLAlchemy()

class User(db.Model):
    """User model for tracking application users."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    github_username = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(64), nullable=True)
    role = db.Column(db.String(20), default='user')  # user, admin
    
    # Relationships
    analyses = relationship("Analysis", back_populates="user")
    
    def __repr__(self):
        return f'<User {self.email}>'


class WaitlistEntry(db.Model):
    """Model for waitlist entries."""
    __tablename__ = 'waitlist'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    github_username = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    invited_at = db.Column(db.DateTime, nullable=True)
    joined_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, invited, joined
    invite_token = db.Column(db.String(64), nullable=True)
    
    def __repr__(self):
        return f'<WaitlistEntry {self.email}>'


class Analysis(db.Model):
    """Model for GitHub profile analyses."""
    __tablename__ = 'analyses'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    github_username = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)  # For guest analyses
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    result = db.Column(JSON, nullable=False)  # Store the complete analysis result
    impact_score = db.Column(db.Float, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 support
    user_agent = db.Column(db.String(255), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="analyses")
    shares = relationship("Share", back_populates="analysis")
    
    def __repr__(self):
        return f'<Analysis {self.github_username} {self.created_at}>'


class Share(db.Model):
    """Model for shared analyses."""
    __tablename__ = 'shares'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = db.Column(UUID(as_uuid=True), db.ForeignKey('analyses.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    access_count = db.Column(db.Integer, default=0)
    last_accessed_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    analysis = relationship("Analysis", back_populates="shares")
    
    def __repr__(self):
        return f'<Share {self.id}>'


class AnalysisTracking(db.Model):
    """Model for tracking analysis metrics over time."""
    __tablename__ = 'analysis_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    github_username = db.Column(db.String(120), nullable=False)
    analysis_date = db.Column(db.Date, nullable=False)
    impact_score = db.Column(db.Float, nullable=False)
    metrics = db.Column(JSON, nullable=False)  # Store individual metrics
    
    def __repr__(self):
        return f'<AnalysisTracking {self.github_username} {self.analysis_date}>'


class PDFExport(db.Model):
    """Model for tracking PDF exports."""
    __tablename__ = 'pdf_exports'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = db.Column(UUID(as_uuid=True), db.ForeignKey('analyses.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    file_path = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    error_message = db.Column(db.String(255), nullable=True)
    
    # Relationships
    analysis = relationship("Analysis")
    
    def __repr__(self):
        return f'<PDFExport {self.id}>'
