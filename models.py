from flask_sqlalchemy import SQLAlchemy

# create SQLAlchemy object here so app can import it
db = SQLAlchemy()

class Class(db.Model):
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    groups = db.relationship("Group", backref="class_", cascade="all, delete", lazy=True)
    students = db.relationship("Student", backref="class_", lazy=True)

    def __repr__(self):
        return f"<Class {self.name}>"

class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)

    students = db.relationship("Student", backref="group", lazy=True)

    __table_args__ = (
        db.UniqueConstraint('name', 'class_id', name='uq_group_name_per_class'),
    )

    def __repr__(self):
        return f"<Group {self.name} (Class {self.class_id})>"

class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(64), nullable=True)   # optional matric / id
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)

    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)

    def __repr__(self):
        return f"<Student {self.name} ({self.email})>"
