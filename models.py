from flask_sqlalchemy import SQLAlchemy
<<<<<<< HEAD
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import text

db = SQLAlchemy()

# ---------------- USERS ---------------- #
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(64), nullable=True, unique=False)  # optional, only for students
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # "student" or "teacher"
    gender = db.Column(db.String(20), nullable=False, server_default=text("'Other'"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    subjects = db.relationship("Subject", backref="teacher", lazy="selectin")  # if teacher
    memberships = db.relationship("GroupMember", backref="student_user", lazy="selectin")  # if student
    given_reviews = db.relationship("PeerReview", foreign_keys="PeerReview.reviewer_id", backref="reviewer_user")
    received_reviews = db.relationship("PeerReview", foreign_keys="PeerReview.reviewee_id", backref="reviewee_user")

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role}>"


# ---------------- SUBJECT & GROUP ---------------- #
class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    code = db.Column(db.String(50), unique=True, nullable=True)

    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    groups = db.relationship("Group", backref="subject", cascade="all, delete", lazy="selectin")
    settings = db.relationship("Setting", backref="subject", uselist=False, cascade="all, delete")

    def __repr__(self):
        return f"<Subject id={self.id} name={self.name!r}>"


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)

    members = db.relationship("GroupMember", backref="group", cascade="all, delete", lazy="selectin")
    reviews = db.relationship("PeerReview", backref="group", cascade="all, delete", lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint("name", "subject_id", name="uq_group_name_per_subject"),
    )

    def __repr__(self):
        return f"<Group id={self.id} name={self.name!r} subject_id={self.subject_id}>"


class GroupMember(db.Model):
    __tablename__ = "group_members"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GroupMember group_id={self.group_id} student_id={self.student_id}>"


# ---------------- PEER REVIEWS ---------------- #
class PeerReview(db.Model):
    __tablename__ = "peer_reviews"

    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)

    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("reviewer_id <> reviewee_id", name="ck_review_not_self"),
        db.CheckConstraint("score >= 0", name="ck_review_score_non_negative"),
    )

    def __repr__(self):
        return f"<PeerReview id={self.id} reviewer_id={self.reviewer_id} reviewee_id={self.reviewee_id} score={self.score}>"


# ---------------- SETTINGS (per subject) ---------------- #
class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)

    criteria = db.Column(db.String(255), default="Collaboration, Contribution, Communication")
    max_score = db.Column(db.Integer, default=10)
    deadline = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Setting id={self.id} subject_id={self.subject_id} max_score={self.max_score}>"
=======
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

class AnonymousReview(db.Model):
    __tablename__ = 'anonymous_reviews'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AnonymousReview {self.id}>'

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
            AnonymousReview.query.delete()
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
>>>>>>> Tan
