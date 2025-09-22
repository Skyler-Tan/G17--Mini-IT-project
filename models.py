from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'   # renamed to plural for consistency

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200))                # for login
    role = db.Column(db.String(20), default="student")
    gender = db.Column(db.String(20), default="Other")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    given_reviews = db.relationship(
        'PeerReview',
        foreign_keys='PeerReview.reviewer_student_id',
        backref='reviewer',
        lazy='dynamic'
    )
    received_reviews = db.relationship(
        'PeerReview',
        foreign_keys='PeerReview.reviewee_student_id',
        backref='reviewee',
        lazy='dynamic'
    )
    self_assessment = db.relationship(
        'SelfAssessment',
        backref='student',
        uselist=False
    )

    def __repr__(self):
        return f'<User {self.username}>'


class PeerReview(db.Model):
    __tablename__ = 'peer_reviews'

    id = db.Column(db.Integer, primary_key=True)

    reviewer_student_id = db.Column(
        db.String(20),
        db.ForeignKey('users.student_id'),
        nullable=False
    )
    reviewee_student_id = db.Column(
        db.String(20),
        db.ForeignKey('users.student_id'),
        nullable=False
    )

    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.CheckConstraint('score >= 1 AND score <= 5', name='check_score_range'),
    )

    def __repr__(self):
        return f'<PeerReview {self.reviewer_student_id} -> {self.reviewee_student_id}: {self.score}>'


class AnonymousReview(db.Model):
    __tablename__ = 'anonymous_reviews'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AnonymousReview {self.id}>'


class SelfAssessment(db.Model):
    __tablename__ = 'self_assessments'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.String(20),
        db.ForeignKey('users.student_id'),
        nullable=False
    )
    student_name = db.Column(db.String(100), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    challenges = db.Column(db.Text, nullable=False)
    different = db.Column(db.Text, nullable=False)
    role = db.Column(db.Text, nullable=False)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f'<SelfAssessment {self.student_name}>'


class LecturerMark(db.Model):
    __tablename__ = 'lecturer_marks'

    id = db.Column(db.Integer, primary_key=True)
    group_mark = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.CheckConstraint('group_mark >= 0 AND group_mark <= 100', name='check_group_mark_range'),
        db.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
    )

    def __repr__(self):
        return f'<LecturerMark Group:{self.group_mark}% Rating:{self.rating}/5>'


__all__ = ['db', 'User', 'PeerReview', 'AnonymousReview', 'SelfAssessment', 'LecturerMark']
