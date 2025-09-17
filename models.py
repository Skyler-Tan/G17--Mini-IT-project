from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Subject(db.Model):
    __tablename__ = "subjects"   # ✅ renamed table
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    groups = db.relationship(
        "Group",
        backref=db.backref("subject", lazy='select'),  # ✅ renamed
        cascade="all, delete",
        passive_deletes=True,
        lazy='selectin'
    )
    students = db.relationship(
        "Student",
        backref=db.backref("subject", lazy='select'),  # ✅ renamed
        passive_deletes=True,
        lazy='selectin'
    )

    def __repr__(self):
        return f"<Subject id={self.id} name={self.name!r}>"

class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)  # ✅

    students = db.relationship(
        "Student",
        backref=db.backref("group", lazy='select'),
        passive_deletes=True,
        lazy='selectin'
    )

    __table_args__ = (
        db.UniqueConstraint('name', 'subject_id', name='uq_group_name_per_subject'),  # ✅
    )

    def __repr__(self):
        return f"<Group id={self.id} name={self.name!r} subject_id={self.subject_id}>"

class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)  # ✅
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_id', name='uq_student_id_per_subject'),  # ✅
        db.Index('ix_students_email', 'email'),
        db.Index('ix_students_student_id', 'student_id'),
    )

    def __repr__(self):
        return f"<Student id={self.id} name={self.name!r} email={self.email!r} subject_id={self.subject_id} group_id={self.group_id}>"

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship(
        "Student",
        foreign_keys=[reviewer_id],
        backref=db.backref("given_reviews", lazy='selectin', passive_deletes=True)
    )
    reviewee = db.relationship(
        "Student",
        foreign_keys=[reviewee_id],
        backref=db.backref("received_reviews", lazy='selectin', passive_deletes=True)
    )

    __table_args__ = (
        db.CheckConstraint('reviewer_id <> reviewee_id', name='ck_review_not_self'),
        db.CheckConstraint('score >= 0', name='ck_review_score_non_negative'),
        db.Index('ix_reviews_reviewer_id', 'reviewer_id'),
        db.Index('ix_reviews_reviewee_id', 'reviewee_id'),
    )

    def __repr__(self):
        return f"<Review id={self.id} reviewer_id={self.reviewer_id} reviewee_id={self.reviewee_id} score={self.score}>"

class Setting(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    criteria = db.Column(db.String(255), default="Collaboration, Contribution, Communication")
    max_score = db.Column(db.Integer, default=10)
    deadline = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Setting id={self.id} max_score={self.max_score} deadline={self.deadline}>"
