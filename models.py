from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

class Class(db.Model):
    __tablename__ = "classes"   # avoid reserved keyword "class"

    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))

    groups = db.relationship("Group", backref="class_", lazy=True)


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)

    students = db.relationship("Student", backref="group", lazy=True)

class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
