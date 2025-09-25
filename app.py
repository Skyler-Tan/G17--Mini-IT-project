import os
import csv
from io import StringIO
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_migrate import Migrate
from config import Config
from models import db, User, Subject, Group, GroupMember, PeerReview, SelfAssessment, AnonymousReview, Setting

# ---------------- Flask app setup ---------------- #
ALLOWED_EXT = {"csv"}
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

app = Flask(__name__)
app.config.from_object(Config)

# Make sure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

db.init_app(app)
migrate = Migrate()
migrate.init_app(app, db)

# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    return redirect(url_for("list_subjects"))

# ---------------- SUBJECT ---------------- #
@app.route("/subjects", methods=["GET", "POST"])
def list_subjects():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        lecturer_id = int(request.form.get("lecturer_id") or 0)
        if not name or not lecturer_id:
            flash("Subject name and lecturer required", "error")
        else:
            try:
                s = Subject(name=name, lecturer_id=lecturer_id)
                db.session.add(s)
                db.session.commit()
                flash("Subject created", "success")
                return redirect(url_for("list_subjects"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating subject: {e}", "error")

    subjects = Subject.query.order_by(Subject.name).all()
    lecturer = User.query.filter_by(role="lecturer").order_by(User.first_name).all()
    return render_template("subject.html", subjects=subjects, lecturer=lecturer)

@app.route("/subjects/<int:subject_id>/delete", methods=["POST"])
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

# ---------------- GROUP ---------------- #
@app.route("/subjects/<int:subject_id>/groups", methods=["GET", "POST"])
def manage_groups(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Group name required", "error")
        else:
            try:
                g = Group(name=name, subject_id=subject_id)
                db.session.add(g)
                db.session.commit()
                flash("Group created", "success")
                return redirect(url_for("manage_groups", subject_id=subject_id))
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating group: {e}", "error")

    groups = Group.query.filter_by(subject_id=subject_id).order_by(Group.name).all()
    students = User.query.filter_by(role="student").all()
    return render_template("groups.html", subject=subj, groups=groups, students=students)

@app.route("/subjects/<int:subject_id>/add_student_to_group", methods=["POST"])
def add_student_to_group(subject_id):
    student_id = (request.form.get("student_id") or 0)
    group_id = int(request.form.get("group_id") or 0)
    if student_id and group_id:
        try:
            membership = GroupMember(group_id=group_id, id_number=student_id)
            db.session.add(membership)
            db.session.commit()
            flash("Student added to group", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding student to group: {e}", "error")
    return redirect(url_for("manage_groups", subject_id=subject_id))

     

@app.route("/groups/<int:group_id>/delete", methods=["POST"])
def delete_group(group_id):
    grp = Group.query.get_or_404(group_id)
    subject_id = grp.subject_id
    try:
        db.session.delete(grp)
        db.session.commit()
        flash("Group deleted", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting group: {e}", "error")
    return redirect(url_for("manage_groups", subject_id=subject_id))

# ---------------- STUDENTS / USERS ---------------- #
@app.route("/students", methods=["GET", "POST"])
def manage_students():
    subjects = Subject.query.order_by(Subject.name).all()
    groups = Group.query.order_by(Group.name).all()
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        role = "student"
        subject_id = int(request.form.get("subject_id") or 0) or None
        group_id = int(request.form.get("group_id") or 0) or None

        if not first_name or not last_name or not email or not username or not password:
            flash("All fields are required", "error")
        else:
            try:
                user = User(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    username=username,
                    password=password,
                    role=role
                )
                db.session.add(user)
                db.session.commit()

                # Add to group if selected
                if group_id:
                    membership = GroupMember(group_id=group_id,  id_number=user.id)
                    db.session.add(membership)
                    db.session.commit()

                flash("Student added", "success")
                return redirect(url_for("manage_students"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding student: {e}", "error")

    students = User.query.filter_by(role="student").order_by(User.first_name).all()
    for s in students:
        for m in s.memberships:
            print(f"Student: {s.first_name}, Group: {m.group.name}, Subject: {m.group.subject.name}")
    return render_template("students.html", students=students, subjects=subjects, groups=groups)

@app.route("/students/<id_number>/delete", methods=["POST"])
def delete_student( id_number):
    user = User.query.get_or_404(id_number)
    try:
        db.session.delete(user)
        db.session.commit()
        flash("Student removed", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing student: {e}", "error")
    return redirect(url_for("manage_students"))

# ---------------- IMPORT CSV ---------------- #
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
                print("CSV Headers:", reader.fieldnames)
                for row in reader:
                    print("Row data:", row)
                    first_name = (row.get("first_name") or "").strip()
                    last_name = (row.get("last_name") or "").strip()
                    email = (row.get("email") or "").strip()
                    username = (row.get("username") or "").strip()
                    password = (row.get("password") or "").strip()
                    if not first_name or not last_name or not email or not username or not password:
                        skipped += 1
                        continue
                    user = User(
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        username=username,
                        password=password,
                        role="student"
                    )
                    db.session.add(user)
                    db.session.flush()  # get user.id for group

                    group_id = int(row.get("group_id") or 0) or None
                    if group_id:
                        membership = GroupMember(group_id=group_id, id_number=user.id)
                        db.session.add(membership)

                    inserted += 1
                db.session.commit()
            flash(f"CSV processed: {inserted} inserted, {skipped} skipped", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error processing CSV: {e}", "error")
            print(f"Error details: {e}")
        finally:
            try: os.remove(path)
            except: pass

        return redirect(url_for("manage_students"))
    return render_template("import_students.html")

# ---------------- PEER REVIEWS ---------------- #
@app.route("/reviews")
def show_reviews():
    reviews = PeerReview.query.order_by(PeerReview.created_at.desc()).all()
    return render_template("reviews.html", reviews=reviews)

@app.route("/reviews/export")
def export_reviews():
    reviews = PeerReview.query.all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Reviewer", "Reviewee", "Score", "Comment", "Timestamp"])
    for r in reviews:
        writer.writerow([
            f"{r.reviewer_user.first_name} {r.reviewer_user.last_name}" if r.reviewer_user else "-",
            f"{r.reviewee_user.first_name} {r.reviewee_user.last_name}" if r.reviewee_user else "-",
            r.score,
            r.comment or "",
            r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        ])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=reviews.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# ---------------- SETTINGS ---------------- #
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

# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    app.run(debug=True)