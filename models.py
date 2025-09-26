from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import text

db = SQLAlchemy()

# ---------------- USERS ---------------- #
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    id_number = db.Column(db.String(64), nullable=True, unique=False)  # optional, only for students
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # "student" or "lecturer"
    gender = db.Column(db.String(20), nullable=False, server_default=text("'Other'"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    subjects = db.relationship("Subject", backref="lecturer", lazy="selectin")  # was teacher
    memberships = db.relationship("GroupMember", backref="student_user", lazy="selectin")  # if student
    given_reviews = db.relationship("PeerReview", foreign_keys="PeerReview.reviewer_id", backref="reviewer_user")
    received_reviews = db.relationship("PeerReview", foreign_keys="PeerReview.reviewee_id", backref="reviewee_user")

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role} id_number={self.id_number}>"


# ---------------- SUBJECT & GROUP ---------------- #
class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    code = db.Column(db.String(50), unique=True, nullable=True)

    lecturer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

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
    id_number = db.Column(db.String(64), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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

    score = db.Column(db.Integer, db.CheckConstraint("score BETWEEN 1 AND 5", name="ck_review_score_range"), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("reviewer_id <> reviewee_id", name="ck_review_not_self"),
    )

    def __repr__(self):
        return f"<PeerReview id={self.id} reviewer_id={self.reviewer_id} reviewee_id={self.reviewee_id} score={self.score}>"


class SelfAssessment(db.Model):
    __tablename__ = "self_assessments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True)

    score = db.Column(db.Integer, db.CheckConstraint("score BETWEEN 1 AND 5", name="ck_self_score_range"), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="self_assessments")
    group = db.relationship("Group", backref="self_assessments")

    def __repr__(self):
        return f"<SelfAssessment id={self.id} user_id={self.user_id} score={self.score}>"

class AnonymousReview(db.Model):
    __tablename__ = "anonymous_reviews"

    id = db.Column(db.Integer, primary_key=True)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=True)
    peer_review_id = db.Column(db.Integer, db.ForeignKey("peer_reviews.id", ondelete="SET NULL"), nullable=True)

    score = db.Column(db.Integer, db.CheckConstraint("score BETWEEN 1 AND 5", name="ck_anon_score_range"), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewee = db.relationship("User", backref="anonymous_reviews")
    group = db.relationship("Group", backref="anonymous_reviews")
    peer_review = db.relationship("PeerReview", backref="anonymous_feedback")

    def __repr__(self):
        return f"<AnonymousReview id={self.id} reviewee_id={self.reviewee_id} score={self.score}>"

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
