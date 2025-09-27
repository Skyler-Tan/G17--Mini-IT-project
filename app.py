from flask import Flask, render_template, redirect, url_for, flash, request, make_response, session
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
from models import db, User, Subject, Group, GroupMember, PeerReview, Setting, SelfAssessment, AnonymousReview
from dotenv import load_dotenv


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
#Isyraf
# ---------------- SUBJECT ---------------- #
@app.route("/subjects", methods=["GET"])
def list_subjects():
    subjects = Subject.query.order_by(Subject.name).all()
    lecturer = User.query.filter_by(role="lecturer").order_by(User.first_name).all()
    return render_template("subject.html", subjects=subjects, lecturer=lecturer)

@app.route("/subjects/create", methods=["POST"])
@login_required
def create_subject():
    if current_user.role != "lecturer":
        flash("Only lecturers can create subjects", "danger")
        return redirect(url_for("dashboard"))

    name = (request.form.get("name") or "").strip()
    lecturer_id = request.form.get("lecturer_id")

    if not name or not lecturer_id:
        flash("Subject name and lecturer are required", "error")
    else:
        try:
            s = Subject(name=name, lecturer_id=int(lecturer_id))
            db.session.add(s)
            db.session.commit()
            flash("Subject created", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating subject: {e}", "error")

    return redirect(url_for("dashboard"))


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




@app.route("/subjects/<int:subject_id>/groups/view", methods=["GET"])
@login_required
def view_groups(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    groups = Group.query.filter_by(subject_id=subject_id).order_by(Group.name).all()

    # Assuming you have a PeerReview model linked to groups
    peer_reviews = {}
    for group in groups:
        reviews = PeerReview.query.filter_by(group_id=group.id).all()
        peer_reviews[group.id] = reviews

    return render_template("view_groups.html", subject=subject, groups=groups, peer_reviews=peer_reviews)


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
                        membership = GroupMember(group_id=group_id, id_number=user.id)
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
        id_number = request.form.get("id_number")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password") 
        role = request.form.get('role', 'student') 
        gender = request.form.get('gender') 

        existing_user = User.query.filter(or_(User.username == username, User.email == email, User.id_number == id_number)).first()
        if existing_user:
            flash("Username, Email or Student ID already exists. Please try again.", "warning")
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(id_number = id_number, first_name = first_name, last_name = last_name, username=username, email=email, password=hashed_pw, role=role, gender=gender)
        
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
        subjects = Subject.query.order_by(Subject.name).all()
        assigned_subjects = get_assigned_subjects(current_user.id)
        return render_template (
            'dashboard.html',
            user=current_user,
            current_year=datetime.now().year,
            subjects=subjects,
            assigned_subjects=assigned_subjects
        )

    elif current_user.role == "lecturer":
        subjects = Subject.query.filter_by(lecturer_id=current_user.id).order_by(Subject.name).all()
        prefix = "Mr." if current_user.gender.lower() == "male" else "Ms."
        return render_template(
            'dashboard.html',
            user=current_user,
            prefix=prefix,
            current_year=datetime.now().year,
            subjects=subjects
        )

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
    
@app.route("/student/profile", methods=["GET", "POST"])
@login_required
def student_profile():
    if current_user.role != "student":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))
    
    return render_template("student_profile.html", user=current_user)

@app.route("/lecturer/profile", methods=["GET", "POST"])
@login_required
def lecturer_profile():
    if current_user.role != "lecturer":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        current_user.first_name = request.form["first_name"]
        current_user.last_name = request.form["last_name"]
        current_user.email = request.form["email"]
        current_user.id_number = request.form["id_number"]
        current_user.username = request.form["username"]

        db.session.commit()
        flash("Profile updated successfully!", "success")
    
    return render_template("lecturer_profile.html", user=current_user)


def get_assigned_subjects(student_id):
    group_ids = db.session.query(GroupMember.group_id).filter_by(id_number=student_id).subquery()

    subjects = (
        db.session.query(Subject)
        .join(Group, Subject.id == Group.subject_id)
        .filter(Group.id.in_(group_ids))
        .distinct()
        .all()
    )

    return subjects


#SkylerTan
# ----- Student list from DB (table: user) - EXCLUDE lecturers -----
def get_students_in_group(group_id):
    """Get all students in a specific group"""
    try:
        students = (
            db.session.query(User)
            .join(GroupMember, GroupMember.id_number == User.id)
            .filter(GroupMember.group_id == group_id, User.role == 'student')
            .all()
        )
        return students
    except Exception as e:
        print(f"Error getting students in group: {e}")
        return []

def is_lecturer(username):
    """Check if user is a lecturer"""
    try:
        from sqlalchemy import text
        result = db.session.execute(text("SELECT role FROM user WHERE CONCAT(first_name, ' ', last_name) = :username"), 
                                  {'username': username}).fetchone()
        return result and result[0].lower() == 'lecturer'
    except Exception:
        return False

# ---------------- PEER REVIEW ROUTES ---------------- #

@app.route("/start_peer_review")
@login_required
def start_peer_review():
    """Clear session and start fresh peer review"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    # Get group and subject from query parameters or user's default
    group_id = request.args.get('group_id')
    subject_id = request.args.get('subject_id')
    
    if not group_id or not subject_id:
        # Get user's groups from GroupMember
        user_groups = GroupMember.query.filter_by(id_number=current_user.id).all()
        if user_groups:
            group_id = user_groups[0].group_id
            group = Group.query.get(group_id)
            if group and group.subject_id:
                subject_id = group.subject_id
    
    # Clear any existing session data
    session.pop("current_user_id", None)
    session.pop("current_group_id", None)
    session.pop("current_subject_id", None)
    
    if group_id and subject_id:
        return redirect(url_for('peer_review', group_id=group_id, subject_id=subject_id))
    else:
        flash("Please select a group and subject first.", "error")
        return redirect(url_for('dashboard'))

@app.route("/peer_review")
@login_required
def peer_review():
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    # Get group and subject from query parameters
    group_id = request.args.get('group_id')
    subject_id = request.args.get('subject_id')
    
    if not group_id or not subject_id:
        flash("Please select a group and subject.", "error")
        return redirect(url_for('dashboard'))

    # Store in session
    session['current_group_id'] = group_id
    session['current_subject_id'] = subject_id
    session['current_user_id'] = current_user.id

    # Fetch students in this group with a join (no helper)
    group_students = (
        db.session.query(User)
        .join(GroupMember, GroupMember.id_number == User.id)  # NOTE: id_number points to users.id
        .filter(GroupMember.group_id == group_id, User.role == "student")
        .all()
    )

    students = [{"id": s.id, "full_name": f"{s.first_name} {s.last_name}"} for s in group_students]

    # Completion status
    completion_status = get_completion_status(group_students, group_id)
    completed_count = sum(1 for v in completion_status.values() if v['completed'])
    total_students = len(students)
    all_completed = all(v['completed'] for v in completion_status.values())

    # Compute peer averages only when all students are done
    results = []
    if all_completed:
        for student in group_students:
            reviews = PeerReview.query.filter_by(reviewee_id=student.id, group_id=group_id).all()
            avg_peer_score = (sum(r.score for r in reviews) / len(reviews)) if reviews else 0
            results.append({
                'student_name': f"{student.first_name} {student.last_name}",
                'avg_score': round(avg_peer_score, 2)
            })

    # Group and subject info
    group = Group.query.get(group_id)
    subject = Subject.query.get(subject_id)

    return render_template(
        "peer_review.html",
        students=students,
        group_students=group_students,
        completion_status=completion_status,
        completed_count=completed_count,
        total_students=total_students,
        all_completed=all_completed,
        results=results,
        group=group,
        subject=subject
    )


@app.route("/switch_user_and_form/<int:user_id>")
@login_required
def switch_user_and_form(user_id):
    """Switch to a specific user and go to form"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    # Get group and subject from query parameters or session
    group_id = request.args.get('group_id') or session.get('current_group_id')
    subject_id = request.args.get('subject_id') or session.get('current_subject_id')
    
    if not group_id or not subject_id:
        flash("Please select a group and subject first.", "error")
        return redirect(url_for('dashboard'))
    
    # Verify the user is in the same group
    target_user = User.query.get(user_id)
    if not target_user or target_user.role != "student":
        flash("Invalid student selection.", "error")
        return redirect(url_for('peer_review', group_id=group_id, subject_id=subject_id))
    
    # Set the current user in session
    session["current_user_id"] = user_id
    session['current_group_id'] = group_id
    session['current_subject_id'] = subject_id
    
    return redirect(url_for('form', group_id=group_id, subject_id=subject_id))

@app.route("/form", methods=["GET", "POST"])
@login_required
def form():
    """Peer review form"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    group_id = request.args.get('group_id') or session.get('current_group_id')
    subject_id = request.args.get('subject_id') or session.get('current_subject_id')
    if not group_id or not subject_id:
        flash("Please select a group and subject first.", "error")
        return redirect(url_for('dashboard'))
    
    current_user_id = session.get("current_user_id")
    if not current_user_id:
        flash("Please select yourself from the peer review page first.", "info")
        return redirect(url_for("peer_review", group_id=group_id, subject_id=subject_id))
    
    current_user_obj = User.query.get(current_user_id)
    if not current_user_obj:
        flash("Invalid user session.", "error")
        return redirect(url_for("peer_review", group_id=group_id, subject_id=subject_id))
    
    group_students = get_students_in_group(group_id)
    students_list = [{"id": s.id, "full_name": f"{s.first_name} {s.last_name}"} for s in group_students]

    if request.method == "POST":
        try:
            reviewee_ids = request.form.getlist("reviewee_id[]")
            scores = request.form.getlist("score[]")
            comments = request.form.getlist("comment[]")
            anon_text = request.form.get("anonymous_review", "").strip()

            if not (len(reviewee_ids) == len(scores) == len(comments)):
                flash("Mismatch in submitted review data.", "error")
                return redirect(url_for("form", group_id=group_id, subject_id=subject_id))

            # Must review all others
            filtered_reviewees = [int(rid) for rid in reviewee_ids if int(rid) != current_user_id]
            required_reviews = len(students_list) - 1
            if len(filtered_reviewees) != required_reviews:
                flash(f"You must review all {required_reviews} other students in your group.", "error")
                return redirect(url_for("form", group_id=group_id, subject_id=subject_id))

            # Remove prior reviews
            PeerReview.query.filter_by(reviewer_id=current_user_id, group_id=group_id).delete()

            for reviewee_id, score_str, comment in zip(reviewee_ids, scores, comments):
                reviewee_id = int(reviewee_id)
                if reviewee_id == current_user_id:
                    continue
                if reviewee_id not in [s.id for s in group_students]:
                    continue

                try:
                    score = int(score_str)
                except ValueError:
                    flash("Invalid score provided.", "error")
                    return redirect(url_for("form", group_id=group_id, subject_id=subject_id))

                if not (1 <= score <= 5):
                    flash("Scores must be between 1 and 5.", "error")
                    return redirect(url_for("form", group_id=group_id, subject_id=subject_id))

                review = PeerReview(
                    reviewer_id=current_user_id,
                    reviewee_id=reviewee_id,
                    score=score,
                    comment=comment or "",
                    group_id=group_id
                )
                db.session.add(review)

            # Save anonymous review if given
            if anon_text:
                anon = AnonymousReview(
                    reviewee_id=current_user_id,
                    group_id=group_id,
                    comment=anon_text
                )
                db.session.add(anon)
                
            db.session.commit()
            flash("Peer reviews submitted successfully.", "success")
            return redirect(url_for("self_assessment", group_id=group_id, subject_id=subject_id))
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Error saving peer reviews")
            flash(f"An error occurred while saving your reviews: {str(e)}", "error")
            return redirect(url_for("form", group_id=group_id, subject_id=subject_id))

    # GET: load existing reviews
    prior_reviews = {}
    existing = PeerReview.query.filter_by(reviewer_id=current_user_id, group_id=group_id).all()
    for r in existing:
        prior_reviews[r.reviewee_id] = {"score": r.score, "comment": r.comment}

    group = Group.query.get(group_id)
    subject = Subject.query.get(subject_id)
    
    return render_template(
        "form.html", 
        current_user=current_user_obj,
        current_user_id=current_user_id,
        prior_reviews=prior_reviews, 
        students=students_list,
        group=group,
        subject=subject
    )


@app.route("/self_assessment/<int:group_id>/<int:subject_id>", methods=["GET", "POST"])
@login_required
def self_assessment(group_id, subject_id):
    group = Group.query.get_or_404(group_id)
    subject = Subject.query.get_or_404(subject_id)

    if request.method == "POST":
        # Save/update self-assessment
        summary = request.form.get("summary")
        challenges = request.form.get("challenges")
        different = request.form.get("different")
        role = request.form.get("role")
        feedback = request.form.get("feedback")

        assessment = SelfAssessment.query.filter_by(
            user_id=current_user.id,
            group_id=group.id
        ).first()

        if assessment:
            assessment.summary = summary
            assessment.challenges = challenges
            assessment.different = different
            assessment.role = role
            assessment.feedback = feedback
        else:
            assessment = SelfAssessment(
                user_id=current_user.id,
                group_id=group.id,
                summary=summary,
                challenges=challenges,
                different=different,
                role=role,
                feedback=feedback
            )
            db.session.add(assessment)

        db.session.commit()
        flash("Your self-assessment has been submitted successfully.", "success")

        # 🔑 redirect to done page
        return redirect(url_for("done", group_id=group.id, subject_id=subject.id))

    # GET request → show the form
    assessment_data = SelfAssessment.query.filter_by(
        user_id=current_user.id,
        group_id=group.id
    ).first()

    return render_template(
        "self_assessment.html",
        subject=subject,
        group=group,
        assessment_data=assessment_data
    )

@app.route("/results")
@login_required
def results():
    """Results page"""
    group_id = request.args.get("group_id") or session.get("current_group_id")
    subject_id = request.args.get("current_subject_id") or session.get("current_subject_id")

    if not group_id or not subject_id:
        flash("Please select a group and subject first.", "error")
        return redirect(url_for("dashboard"))

    group_students = get_students_in_group(group_id)

    # Completion tracking
    status = get_completion_status(group_students, group_id)
    all_completed = all(v["completed"] for v in status.values())
    completed_count = sum(1 for v in status.values() if v["completed"])

    current_user_id = session.get("current_user_id") or current_user.id
    is_current_lecturer = current_user.role == "lecturer"

    results = {}

    for student_obj in group_students:
        reviews = PeerReview.query.filter_by(
            reviewee_id=student_obj.id, group_id=group_id
        ).all()

        # Avg / Final mark only when everyone finished
        if all_completed and reviews:
            avg_peer_score = sum(r.score for r in reviews) / len(reviews)
            final_mark = round(avg_peer_score * 20, 2)
        else:
            avg_peer_score = None
            final_mark = None

        peer_comments = []
        for review in reviews:
            if review.comment and review.comment.strip():
                reviewer_name = (
                    f"{review.reviewer_user.first_name} {review.reviewer_user.last_name}"
                    if review.reviewer_user
                    else "Unknown"
                )
                peer_comments.append(
                    {
                        "reviewer_id": review.reviewer_id,
                        "reviewer": reviewer_name,
                        "comment": review.comment.strip(),
                    }
                )

        results[student_obj.id] = {
            "avg_score": avg_peer_score,
            "final_mark": final_mark,
            "comments": peer_comments,
        }

    # Anonymous reviews (just text, linked to group)
    anonymous_reviews = AnonymousReview.query.filter_by(group_id=group_id).all()

    # Self-assessments
    self_assessments = []
    for student_obj in group_students:
        assessment = SelfAssessment.query.filter_by(
            user_id=student_obj.id, group_id=group_id
        ).first()
        if assessment:
            self_assessments.append(
                {
                    "student_id": student_obj.id,
                    "student_name": f"{student_obj.first_name} {student_obj.last_name}",
                    "assessment": assessment,
                }
            )

    group = Group.query.get(group_id)
    subject = Subject.query.get(subject_id)

    return render_template(
        "results.html",
        all_completed=all_completed,
        completed_count=completed_count,
        results=results,
        current_user=current_user,
        is_lecturer=is_current_lecturer,
        anonymous_reviews=anonymous_reviews,
        self_assessments=self_assessments,
        group_students=group_students,
        group=group,
        subject=subject,
    )

@app.route("/done")
@login_required  
def done():
    """Completion page"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    group_id = request.args.get('group_id') or session.get('current_group_id')
    subject_id = request.args.get('subject_id') or session.get('current_subject_id')
    
    group = Group.query.get(group_id) if group_id else None
    subject = Subject.query.get(subject_id) if subject_id else None
    
    return render_template("done.html", 
                         current_user=session.get("current_user"),
                         group=group, 
                         subject=subject)

# Helper functions
def get_students_in_group(group_id):
    """Get all students in a specific group"""
    try:
        group_members = GroupMember.query.filter_by(group_id=group_id).all()
        # IMPORTANT: here id_number is actually a foreign key to users.id
        student_ids = [gm.id_number for gm in group_members]
        students = User.query.filter(User.id.in_(student_ids), User.role == 'student').all()
        return students
    except Exception as e:
        print(f"Error getting students in group: {e}")
        return []

def get_completion_status(group_students, group_id):
    """Get completion status for students in a specific group"""
    status = {}
    for student_obj in group_students:
        # Check if student has completed all reviews (reviewed all other students)
        total_students = len(group_students)
        required_reviews = total_students - 1  # Review everyone except yourself
        
        completed_reviews = PeerReview.query.filter_by(
            reviewer_id=student_obj.id, 
            group_id=group_id
        ).count()
        
        # Check if student has completed self-assessment
        has_self_assessment = SelfAssessment.query.filter_by(
            user_id=student_obj.id, 
            group_id=group_id
        ).first() is not None
        
        status[student_obj.id] = {
            'reviews_count': completed_reviews,
            'completed': completed_reviews >= required_reviews and has_self_assessment
        }
    
    return status

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)