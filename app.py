import os
import csv
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash

from config import Config
from models import db, Class, Group, Student

ALLOWED_EXT = {"csv"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

db.init_app(app)
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return redirect(url_for("list_classes"))

@app.route("/classes", methods=["GET", "POST"])
def list_classes():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Class name required", "error")
        else:
            try:
                c = Class(name=name)
                db.session.add(c)
                db.session.commit()
                flash("Class created", "success")
                return redirect(url_for("list_classes"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating class: {e}", "error")

    classes = Class.query.order_by(Class.name).all()
    return render_template("classes.html", classes=classes)

@app.route("/classes/<int:class_id>/delete", methods=["POST"])
def delete_class(class_id):
    cls = Class.query.get_or_404(class_id)
    try:
        db.session.delete(cls)
        db.session.commit()
        flash("Class deleted", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting class: {e}", "error")
    return redirect(url_for("list_classes"))

@app.route("/classes/<int:class_id>/groups", methods=["GET", "POST"])
def manage_groups(class_id):
    cls = Class.query.get_or_404(class_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Group name required", "error")
        else:
            try:
                g = Group(name=name, class_id=class_id)
                db.session.add(g)
                db.session.commit()
                flash("Group created", "success")
                return redirect(url_for("manage_groups", class_id=class_id))
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating group: {e}", "error")

    groups = Group.query.filter_by(class_id=class_id).order_by(Group.name).all()
    return render_template("groups.html", cls=cls, groups=groups)

@app.route("/groups/<int:group_id>/delete", methods=["POST"])
def delete_group(group_id):
    grp = Group.query.get_or_404(group_id)
    class_id = grp.class_id
    try:
        db.session.delete(grp)
        db.session.commit()
        flash("Group deleted", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting group: {e}", "error")
    return redirect(url_for("manage_groups", class_id=class_id))

@app.route("/students", methods=["GET", "POST"])
def manage_students():
    classes = Class.query.order_by(Class.name).all()
    groups = Group.query.order_by(Group.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        student_id = (request.form.get("student_id") or "").strip() or None
        class_id = request.form.get("class_id") or None
        group_id = request.form.get("group_id") or None
        class_id = int(class_id) if class_id else None
        group_id = int(group_id) if group_id else None

        if not name or not email:
            flash("Name and email required", "error")
        else:
            try:
                s = Student(name=name, email=email, student_id=student_id,
                            class_id=class_id, group_id=group_id)
                db.session.add(s)
                db.session.commit()
                flash("Student added", "success")
                return redirect(url_for("manage_students"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding student: {e}", "error")

    students = Student.query.order_by(Student.name).all()
    return render_template("students.html", students=students, classes=classes, groups=groups)

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
        errors = []
        try:
            with open(path, newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames:
                    flash("CSV has no header", "error")
                    return redirect(url_for("import_students"))
                # normalize headers
                headers = [h.strip().lower() for h in reader.fieldnames]
                required = {"name", "email"}
                if not required.issubset(set(headers)):
                    miss = required - set(headers)
                    flash(f"Missing required columns: {', '.join(miss)}", "error")
                    return redirect(url_for("import_students"))

                for idx, row in enumerate(reader, start=2):
                    try:
                        # case-insensitive access
                        row_norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
                        name = row_norm.get('name', '')
                        email = row_norm.get('email', '')
                        student_id = row_norm.get('student_id') or None
                        class_id = row_norm.get('class_id') or None
                        group_id = row_norm.get('group_id') or None

                        class_id = int(class_id) if class_id and class_id.isdigit() else None
                        group_id = int(group_id) if group_id and group_id.isdigit() else None

                        if not name or not email:
                            skipped += 1
                            errors.append(f"Row {idx}: name/email missing")
                            continue

                        if class_id and not Class.query.get(class_id):
                            skipped += 1
                            errors.append(f"Row {idx}: class_id {class_id} not found")
                            continue
                        if group_id and not Group.query.get(group_id):
                            skipped += 1
                            errors.append(f"Row {idx}: group_id {group_id} not found")
                            continue

                        s = Student(name=name, email=email, student_id=student_id,
                                    class_id=class_id, group_id=group_id)
                        db.session.add(s)
                        inserted += 1
                    except Exception as row_err:
                        skipped += 1
                        errors.append(f"Row {idx}: {row_err}")
                db.session.commit()
            flash(f"CSV processed: {inserted} inserted, {skipped} skipped", "success")
            
            for e in errors[:10]:
                flash(e, "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"Error processing CSV: {e}", "error")
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        return redirect(url_for("manage_students"))

    return render_template("import_students.html")

if __name__ == "__main__":
    app.run(debug=True)
