from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Class(db.Model):
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    groups = db.relationship("Group", backref="class_", cascade="all, delete", lazy=True)
    students = db.relationship("Student", backref="class_", lazy=True)

class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    students = db.relationship("Student", backref="group", lazy=True)

    __table_args__ = (
        db.UniqueConstraint('name', 'class_id', name='uq_group_name_per_class'),
    )

class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship("Student", foreign_keys=[reviewer_id], backref="given_reviews")
    reviewee = db.relationship("Student", foreign_keys=[reviewee_id], backref="received_reviews")

class Setting(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    criteria = db.Column(db.String(255), default="Collaboration, Contribution, Communication")
    max_score = db.Column(db.Integer, default=10)
    deadline = db.Column(db.DateTime, nullable=True)
