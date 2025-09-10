from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    given_reviews = db.relationship('PeerReview', foreign_keys='PeerReview.reviewer_id', backref='reviewer_user')
    received_reviews = db.relationship('PeerReview', foreign_keys='PeerReview.reviewee_id', backref='reviewee_user')
    self_assessment = db.relationship('SelfAssessment', backref='student_user', uselist=False)
    
    def __repr__(self):
        return f'<User {self.username}>'

class PeerReview(db.Model):
    __tablename__ = 'peer_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Made nullable for now
    reviewee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Made nullable for now
    reviewer_name = db.Column(db.String(100), nullable=False)  # For easy querying
    reviewee_name = db.Column(db.String(100), nullable=False)  # For easy querying
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.CheckConstraint('score >= 1 AND score <= 5', name='check_score_range'),
    )
    
    def __repr__(self):
        return f'<PeerReview {self.reviewer_name} -> {self.reviewee_name}: {self.score}>'

class SelfAssessment(db.Model):
    __tablename__ = 'self_assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Made nullable for now
    student_name = db.Column(db.String(100), nullable=False)  # For easy querying
    summary = db.Column(db.Text, nullable=False)
    challenges = db.Column(db.Text, nullable=False)
    different = db.Column(db.Text, nullable=False)
    role = db.Column(db.Text, nullable=False)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SelfAssessment {self.student_name}>'

class TeacherMark(db.Model):
    __tablename__ = 'teacher_marks'
    
    id = db.Column(db.Integer, primary_key=True)
    group_mark = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.CheckConstraint('group_mark >= 0 AND group_mark <= 100', name='check_group_mark_range'),
        db.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
    )
    
    def __repr__(self):
        return f'<TeacherMark Group:{self.group_mark}% Rating:{self.rating}/5>'

# ---------- Database Manager ----------
class DatabaseManager:
    @staticmethod
    def init_sample_data():
        """Initialize sample users if they don't exist"""
        sample_users = [
            ('student_a', 'Student A'),
            ('student_b', 'Student B'),
            ('student_c', 'Student C'),
            ('student_d', 'Student D')
        ]
        
        for username, full_name in sample_users:
            if not User.query.filter_by(username=username).first():
                user = User(username=username, full_name=full_name)
                db.session.add(user)
        
        try:
            db.session.commit()
            print("Sample users created successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating sample users: {e}")
    
    @staticmethod
    def clear_all_data():
        """Clear all data from the database"""
        try:
            TeacherMark.query.delete()
            SelfAssessment.query.delete()
            PeerReview.query.delete()
            User.query.delete()
            db.session.commit()
            print("All data cleared successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing data: {e}")
    
    @staticmethod
    def get_completion_summary():
        """Get a summary of completion status"""
        students = ["Student A", "Student B", "Student C", "Student D"]
        summary = {}
        
        for student in students:
            reviews_count = PeerReview.query.filter_by(reviewer_name=student).count()
            has_self_assessment = SelfAssessment.query.filter_by(student_name=student).first() is not None
            summary[student] = {
                'reviews_count': reviews_count,
                'has_self_assessment': has_self_assessment,
                'completed': reviews_count > 0 and has_self_assessment
            }
        
        return summary