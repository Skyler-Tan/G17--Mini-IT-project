import os
import csv
from io import StringIO
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_migrate import Migrate
from config import Config
from models import db, Subject, Group, Student, Review, Setting  # ✅ Class → Subject

# ✅ Flask app setup
ALLOWED_EXT = {"csv"}
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

app = Flask(__name__)
app.config.from_object(Config)

# Make sure instance & upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

db.init_app(app)
migrate = Migrate()
migrate.init_app(app, db)

@app.route("/")
def home():
    return redirect(url_for("list_subjects"))  # ✅

@app.route("/subjects", methods=["GET", "POST"])  # ✅
def list_subjects():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Subject name required", "error")
        else:
            try:
                s = Subject(name=name)  # ✅
                db.session.add(s)
                db.session.commit()
                flash("Subject created", "success")
                return redirect(url_for("list_subjects"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating subject: {e}", "error")

    subjects = Subject.query.order_by(Subject.name).all()
    return render_template("subject.html", subjects=subjects)  # ✅

@app.route("/subjects/<int:subject_id>/delete", methods=["POST"])  # ✅
def delete_subject(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    try:
        db.session.delete(subj)
        db.session.commit()
        flash("Subject deleted", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting subject: {e}", "error")
    return redirect(url_for("list_subjects"))

@app.route("/subjects/<int:subject_id>/groups", methods=["GET", "POST"])  # ✅
def manage_groups(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Group name required", "error")
        else:
            try:
                g = Group(name=name, subject_id=subject_id)  # ✅
                db.session.add(g)
                db.session.commit()
                flash("Group created", "success")
                return redirect(url_for("manage_groups", subject_id=subject_id))
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating group: {e}", "error")

    groups = Group.query.filter_by(subject_id=subject_id).order_by(Group.name).all()
    return render_template("groups.html", subj=subj, groups=groups)  # ✅ cls → subj

@app.route("/groups/<int:group_id>/delete", methods=["POST"])
def delete_group(group_id):
    grp = Group.query.get_or_404(group_id)
    subject_id = grp.subject_id  # ✅
    try:
        db.session.delete(grp)
        db.session.commit()
        flash("Group deleted", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting group: {e}", "error")
    return redirect(url_for("manage_groups", subject_id=subject_id))  # ✅

@app.route("/students", methods=["GET", "POST"])
def manage_students():
    subjects = Subject.query.order_by(Subject.name).all()  # ✅
    groups = Group.query.order_by(Group.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        student_id = (request.form.get("student_id") or "").strip() or None
        subject_id = int(request.form.get("subject_id") or 0) or None  # ✅
        group_id = int(request.form.get("group_id") or 0) or None

        if not name or not email:
            flash("Name and email required", "error")
        else:
            try:
                s = Student(name=name, email=email, student_id=student_id,
                            subject_id=subject_id, group_id=group_id)  # ✅
                db.session.add(s)
                db.session.commit()
                flash("Student added", "success")
                return redirect(url_for("manage_students"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding student: {e}", "error")

    students = Student.query.order_by(Student.name).all()
    return render_template("students.html", students=students, subjects=subjects, groups=groups)  # ✅

@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    s = Student.query.get_or_404(student_id)
    try:
        db.session.delete(s)
        db.session.commit()
        flash("Student removed", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing student: {e}", "error")
    return redirect(url_for("manage_students"))

@app.route("/students/import", methods=["GET", "POST"])
def import_students():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or f.filename == "":
            flash("Please choose a CSV file", "error")
            return redirect(url_for("import_students"))
        if not allowed_file(f.filename):
            flash("Only .csv allowed", "error")
            return redirect(url_for("import_students"))

        filename = secure_filename(f.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)

        inserted = skipped = 0
        try:
            with open(path, newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = (row.get("name") or "").strip()
                    email = (row.get("email") or "").strip()
                    if not name or not email:
                        skipped += 1
                        continue
                    s = Student(name=name, email=email,
                                student_id=row.get("student_id") or None,
                                subject_id=int(row.get("subject_id")) if row.get("subject_id") else None,  # ✅
                                group_id=int(row.get("group_id")) if row.get("group_id") else None)
                    db.session.add(s)
                    inserted += 1
                db.session.commit()
            flash(f"CSV processed: {inserted} inserted, {skipped} skipped", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error processing CSV: {e}", "error")
        finally:
            try: os.remove(path)
            except: pass

        return redirect(url_for("manage_students"))
    return render_template("import_students.html")

@app.route("/reviews")
def show_reviews():
    reviews = Review.query.order_by(Review.timestamp.desc()).all()
    return render_template("reviews.html", reviews=reviews)

@app.route("/reviews/export")
def export_reviews():
    reviews = Review.query.all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Reviewer", "Reviewee", "Score", "Comment", "Timestamp"])
    for r in reviews:
        writer.writerow([
            r.reviewer.name if r.reviewer else "-",
            r.reviewee.name if r.reviewee else "-",
            r.score, r.comment or "",
            r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else ""
        ])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=reviews.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route("/settings", methods=["GET", "POST"])
def manage_settings():
    setting = Setting.query.first()
    if not setting:
        setting = Setting()
        db.session.add(setting)
        db.session.commit()

    if request.method == "POST":
        try:
            setting.criteria = request.form.get("criteria") or setting.criteria
            setting.max_score = int(request.form.get("max_score") or setting.max_score)
            deadline_str = request.form.get("deadline")
            setting.deadline = datetime.strptime(deadline_str, "%Y-%m-%dT%H:%M") if deadline_str else None
            db.session.commit()
            flash("Settings updated successfully", "success")
            return redirect(url_for("manage_settings"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating settings: {e}", "error")

    return render_template("settings.html", setting=setting)

if __name__ == "__main__":
    app.run(debug=True)
