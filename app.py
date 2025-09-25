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
from models import db, User, Subject, Group, GroupMember, PeerReview, Setting
import secrets
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



#SkylerTan
# ----- Student list from DB (table: user) - EXCLUDE lecturers -----
# Replace these functions in your app.py (keep everything else the same)

# Replace ONLY these functions in your app.py - keep everything else exactly the same
def get_students_from_db():
    try:
        from sqlalchemy import text
        # Only get users with role 'student', exclude lecturers
        rows = db.session.execute(text("SELECT first_name, last_name FROM user WHERE LOWER(role) = 'student'")) \
            .fetchall()
        names = []
        for r in rows:
            fn = (r[0] or "").strip()
            ln = (r[1] or "").strip()
            full = (fn + " " + ln).strip() or fn or ln
            if full:
                names.append(full)
        
        # Return only the first 4 students
        return names[:4]
    except Exception:
        app.logger.exception("Error fetching students from user table")
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

# ---------- Helper Functions ----------
def get_completion_status(students):
    """Get completion status details for a given list of students.
    Returns mapping: { student: {reviews_count, has_assessment, completed} }
    """
    status = {}
    for student in students:
        reviews_count = PeerReview.query.filter_by(reviewer_name=student).count()
        has_assessment = SelfAssessment.query.filter_by(student_name=student).first() is not None
        status[student] = {
            'reviews_count': reviews_count,
            'has_assessment': has_assessment,
            'completed': reviews_count > 0 and has_assessment
        }
    return status

# ---------- Peer Review Routes (Main Flow) ----------
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/start_peer_review")
@login_required
def start_peer_review():
    """Clear session and start fresh peer review"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    # Clear any existing session data
    session.pop("current_user", None)
    
    return redirect(url_for('peer_review'))

# 2. Modify the existing peer_review route to clear session when needed
@app.route("/peer_review")
@login_required
def peer_review():
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    # Clear session if coming fresh (no current_user set or coming from dashboard)
    referrer = request.referrer or ""
    if 'dashboard' in referrer or not session.get("current_user"):
        session.pop("current_user", None)
    
    students = get_students_from_db()
    completion_status = get_completion_status(students)

    completed_count = sum(1 for v in completion_status.values() if v['completed'])
    total_students = len(students)
    all_completed = all(v['completed'] for v in completion_status.values())

    # Compute peer average results only when all students are completed
    results = []
    if all_completed:
        for student in students:
            reviews = PeerReview.query.filter_by(reviewee_name=student).all()
            avg_peer_score = (
                sum(r.score for r in reviews) / len(reviews) if reviews else 0
            )
            results.append([student, round(avg_peer_score, 2)])
            
    return render_template(
        "peer_review.html",
        students=students,
        completion_status=completion_status,
        completed_count=completed_count,
        total_students=total_students,
        all_completed=all_completed,
        results=results
    )

# 3. Modify form route to better handle missing session
@app.route("/form", methods=["GET", "POST"])
@login_required
def form():
    """Peer review form"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    current_user_name = session.get("current_user")
    students_list = get_students_from_db()
    
    # If no current_user in session, redirect to peer review selection
    if not current_user_name:
        flash("Please select yourself from the peer review page first.", "info")
        return redirect(url_for("peer_review"))

    if request.method == "POST":
        try:
            reviewees = request.form.getlist("reviewee[]")
            scores = request.form.getlist("score[]")
            comments = request.form.getlist("comment[]")
            anon_text = request.form.get("anonymous_review", "").strip()

            if not (len(reviewees) == len(scores) == len(comments)):
                flash("Mismatch in submitted review data.", "error")
                return redirect(url_for("form"))

            # Enforce review count limits: Must review all 3 other students
            filtered_reviewees = [r for r in reviewees if r != current_user_name and r in students_list]
            if len(filtered_reviewees) != 3:
                flash("You must review all 3 other students.", "error")
                return redirect(url_for("form"))

            # Remove any previous reviews by this reviewer to allow re-submit/edit
            PeerReview.query.filter_by(reviewer_name=current_user_name).delete()
            
            for reviewee, score_str, comment in zip(reviewees, scores, comments):
                if reviewee == current_user_name:
                    continue  # skip self-reviews
                if reviewee not in students_list:
                    continue
                try:
                    score = int(score_str)
                except (TypeError, ValueError):
                    flash("Invalid score provided.", "error")
                    return redirect(url_for("form"))
                if not (1 <= score <= 5):
                    flash("Scores must be between 1 and 5.", "error")
                    return redirect(url_for("form"))

                review = PeerReview(
                    reviewer_name=current_user_name,
                    reviewee_name=reviewee,
                    score=score,
                    comment=comment or ""
                )
                db.session.add(review)

            # Save anonymous review if provided
            if anon_text:
                anon = AnonymousReview(content=anon_text)
                db.session.add(anon)

            db.session.commit()
            flash("Peer reviews submitted successfully.", "success")
            return redirect(url_for("self_assessment"))
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Error saving peer reviews")
            flash(f"An error occurred while saving your reviews: {str(e)}", "error")
            return redirect(url_for("form"))

    # GET: Pre-fill prior reviews if any
    prior_reviews = {}
    existing = PeerReview.query.filter_by(reviewer_name=current_user_name).all()
    for r in existing:
        prior_reviews[r.reviewee_name] = {"score": r.score, "comment": r.comment}

    prior_anon_review = ""

    return render_template(
        "form.html", 
        current_user=current_user_name, 
        prior_reviews=prior_reviews, 
        students=students_list,
        prior_anon_review=prior_anon_review
    )


@app.route("/self_assessment", methods=["GET", "POST"])
@login_required
def self_assessment():
    """Self assessment form"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    current_user_name = session.get("current_user")
    if not current_user_name:
        flash("Please select yourself from the peer review page first.", "error")
        return redirect(url_for("peer_review"))

    if request.method == "POST":
        try:
            summary = request.form.get("summary", "").strip()
            challenges = request.form.get("challenges", "").strip()
            different = request.form.get("different", "").strip()
            role = request.form.get("role", "").strip()
            feedback = request.form.get("feedback", "").strip()

            if not all([summary, challenges, different, role]):
                flash("Please complete all required fields.", "error")
                return redirect(url_for("self_assessment"))

            # Replace existing self assessment for this user
            SelfAssessment.query.filter_by(student_name=current_user_name).delete()
            assessment = SelfAssessment(
                student_name=current_user_name,
                summary=summary,
                challenges=challenges,
                different=different,
                role=role,
                feedback=feedback or None
            )
            db.session.add(assessment)
            db.session.commit()

            flash("Self assessment submitted successfully.", "success")
            return redirect(url_for("done"))
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Error saving self assessment")
            flash(f"An error occurred while saving your self assessment: {str(e)}", "error")
            return redirect(url_for("self_assessment"))

    # Pre-fill existing self assessment data when editing
    existing_assessment = SelfAssessment.query.filter_by(student_name=current_user_name).first()
    assessment_data = {}
    if existing_assessment:
        assessment_data = {
            'summary': existing_assessment.summary,
            'challenges': existing_assessment.challenges,
            'different': existing_assessment.different,
            'role': existing_assessment.role,
            'feedback': existing_assessment.feedback or ''
        }

    return render_template("self_assessment.html", current_user=current_user_name, assessment_data=assessment_data)

@app.route("/done")
@login_required
def done():
    """Completion page"""
    if current_user.role != "student":
        flash("This page is for students only.", "error")
        return redirect(url_for('dashboard'))
    
    return render_template("done.html", current_user=session.get("current_user"))

@app.route("/results")
@login_required
def results():
    """Results page"""
    students = get_students_from_db()
    status = get_completion_status(students)
    all_completed = all(v['completed'] for v in status.values())
    completed_count = sum(1 for v in status.values() if v['completed'])
    
    current_user_name = session.get("current_user")
    is_current_lecturer = is_lecturer(current_user_name) if current_user_name else False

    rows = []
    # Only show results when all students have completed their reviews and assessments
    for student in students:
        reviews = PeerReview.query.filter_by(reviewee_name=student).all()
        
        # Only calculate scores if all students have completed everything
        if all_completed and reviews:
            avg_peer_score = sum(r.score for r in reviews) / len(reviews)
            final_mark = round(avg_peer_score * 20, 2)  # Convert 5-point scale to 100-point scale
        else:
            avg_peer_score = None
            final_mark = None
        
        # Get comments from other students about this student
        peer_comments = []
        if current_user_name == student or is_current_lecturer:  # Show to student themselves or lecturer
            for review in reviews:
                if review.comment and review.comment.strip():
                    peer_comments.append({
                        'reviewer': review.reviewer_name,
                        'comment': review.comment
                    })
        
        rows.append({
            'student_name': student,
            'avg_peer_score': round(avg_peer_score, 2) if avg_peer_score is not None else None,
            'final_mark': final_mark,
            'peer_comments': peer_comments
        })

    # Get anonymous reviews (always show them)
    anonymous_reviews = AnonymousReview.query.all()

    self_assessments = []
    for student in students:
        assessment = SelfAssessment.query.filter_by(student_name=student).first()
        if assessment:
            self_assessments.append({
                'student_name': student,
                'assessment': assessment
            })

    return render_template(
        "results.html",
        all_completed=all_completed,
        completed_count=completed_count,
        rows=rows,
        current_user=current_user_name,
        is_lecturer=is_current_lecturer,
        anonymous_reviews=anonymous_reviews,
        self_assessments=self_assessments
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)