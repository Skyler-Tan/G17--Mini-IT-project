from flask import Flask, render_template, redirect, url_for, flash, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import abort
from flask_login import current_user 
from sqlalchemy import or_
from sqlalchemy import text
import os
import csv
from io import StringIO
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from config import Config
from models import db, User, Subject, Group, GroupMember, PeerReview, Setting

#Isyraf
# ---------------- Flask app setup ---------------- #
ALLOWED_EXT = {"csv"}
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

app = Flask(__name__)
app.config.from_object(Config)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Make sure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

db.init_app(app)
migrate = Migrate()
migrate.init_app(app, db)

# ---------------- ROUTES ---------------- #

# ---------------- SUBJECT ---------------- #
@app.route("/subjects", methods=["GET", "POST"])
def list_subjects():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        
        # If lecturer, automatically assign teacher_id
        if current_user.role == "teacher":
            teacher_id = current_user.id
        else:
            # Admin or other roles need to select a teacher
            teacher_id = int(request.form.get("teacher_id") or 0)
        
        if not name or not teacher_id:
            flash("Subject name and teacher required", "error")
        else:
            try:
                s = Subject(name=name, teacher_id=teacher_id)
                db.session.add(s)
                db.session.commit()
                flash("Subject created", "success")
                return redirect(url_for("list_subjects"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error creating subject: {e}", "error")

    subjects = Subject.query.order_by(Subject.name).all()
    teachers = User.query.filter_by(role="teacher").order_by(User.first_name).all()
    return render_template("subject.html", subjects=subjects, teachers=teachers)

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
@app.route("/groups")
def groups():
    return render_template("groups.html")

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
    return render_template("groups.html", subj=subj, groups=groups)

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
                    membership = GroupMember(group_id=group_id, student_id=user.id)
                    db.session.add(membership)
                    db.session.commit()

                flash("Student added", "success")
                return redirect(url_for("manage_students"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding student: {e}", "error")

    students = User.query.filter_by(role="student").order_by(User.first_name).all()
    return render_template("students.html", students=students, subjects=subjects, groups=groups)

@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    user = User.query.get_or_404(student_id)
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
                for row in reader:
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
                        membership = GroupMember(group_id=group_id, student_id=user.id)
                        db.session.add(membership)

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

#THANISH

@app.route("/")
def home():
    return render_template("login.html", title="Login Page", current_year=datetime.now().year)

@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def role_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            
            if current_user.role != role:
                abort(403)
            
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper
        
    


#Route to webpages

@app.route('/change_password', methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not check_password_hash(current_user.password, old_password):
            flash("Old password is incorrect.", "danger")
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for('change password'))
        
        current_user.password = generate_password_hash(new_password)
        db.session.commit()

        flash("Password updated successfully!", "success")
        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')
                            
                        



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form.get("student_id")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password") 
        role = request.form.get('role', 'student') 
        gender = request.form.get('gender') 

        existing_user = User.query.filter(or_(User.username == username, User.email == email, User.student_id == student_id)).first()
        if existing_user:
            flash("Username, Email or Student ID already exists. Please try again.", "warning")
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(student_id = student_id, first_name = first_name, last_name = last_name, username=username, email=email, password=hashed_pw, role=role, gender=gender)
        
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Try again.", "danger")

    return render_template("login.html")



@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == "student":
        return render_template('student_dashboard.html', user=current_user, current_year=datetime.now().year)
    elif current_user.role == "lecturer":
        if current_user.gender.lower() == "male":
            prefix = "Mr."
        else:
            prefix = "Ms."

        subjects = Subject.query.order_by(Subject.name).all()
        
        return render_template('lecturer_dashboard.html', user=current_user, prefix=prefix, current_year=datetime.now().year, subjects=subjects)
    else:
        flash("Role is not recognized", "danger")
        return redirect(url_for("logout"))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if current_user.role == "student":
        return redirect(url_for("student_profile"))
    elif current_user.role == "lecturer":
        return redirect(url_for("lecturer_profile"))
    else:
        flash("Role is not recognized.", "danger")
        return redirect(url_for("dashboard"))
    
@app.route("/student/profile")
@login_required
def student_profile():
    if current_user.role != "student":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))
    
    return render_template("student_profile.html", user=current_user)

@app.route("/lecturer/profile")
@login_required
def lecturer_profile():
    if current_user.role != "lecturer":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        current_user.first_name = request.form["first_name"]
        current_user.last_name = request.form["last_name"]
        current_user.email = request.form["email"]
        current_user.student_id = request.form["student_id"]
        current_user.username = request.form["username"]

        db.session.commit()
        flash("Profile updated successfully!", "success")
    
    return render_template("lecturer_profile.html", user=current_user)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)