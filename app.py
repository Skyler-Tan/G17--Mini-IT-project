from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_migrate import Migrate
from sqlalchemy import inspect
import os
from pathlib import Path
from models import db, User, PeerReview, SelfAssessment, TeacherMark, DatabaseManager

app = Flask(__name__)
app.secret_key = "secret-key"  # needed for session + flash

# Database config (using instance/db.db)
os.makedirs(app.instance_path, exist_ok=True)
db_path = Path(app.instance_path) / "db.db"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Init database + migration
db.init_app(app)
migrate = Migrate(app, db)


# ---------- Helper Functions ----------

def check_student_completion(student_name):
    """Check if a student has completed both peer reviews and self assessment"""
    has_reviews = PeerReview.query.filter_by(reviewer_name=student_name).count() > 0
    has_self_assessment = SelfAssessment.query.filter_by(student_name=student_name).first() is not None
    return has_reviews and has_self_assessment

def get_completion_status():
    """Get completion status for all students"""
    students = ["Student A", "Student B", "Student C", "Student D"]
    status = {}
    for student in students:
        status[student] = check_student_completion(student)
    return status

def all_students_completed():
    """Check if all students have completed their reviews"""
    completion = get_completion_status()
    return all(completion.values())

def get_teacher_marks():
    """Get the latest teacher marks"""
    return TeacherMark.query.order_by(TeacherMark.id.desc()).first()

def calculate_results():
    """Calculate final results if all conditions are met"""
    if not all_students_completed():
        return None
    
    teacher_marks = get_teacher_marks()
    if not teacher_marks:
        return None
    
    students = ["Student A", "Student B", "Student C", "Student D"]
    results = []
    
    for student in students:
        reviews = PeerReview.query.filter_by(reviewee_name=student).all()
        if reviews:
            avg_peer_score = sum(r.score for r in reviews) / len(reviews)
        else:
            avg_peer_score = 0
        
        # Final Mark Formula: 
        # Final Mark = (Group Mark × 50%) + (Group Mark × 25% × Peer Score/5) + (Group Mark × 25% × Teacher Rating/5)
        final_mark = (teacher_marks.group_mark * 0.5) + \
                    (teacher_marks.group_mark * 0.25 * (avg_peer_score / 5)) + \
                    (teacher_marks.group_mark * 0.25 * (teacher_marks.rating / 5))
        
        results.append([student, round(avg_peer_score, 2), round(final_mark, 2)])
    
    return results

# ---------- Routes ----------

@app.route("/")
def index():
    return redirect(url_for('dashboard'))
@app.route("/dashboard")
def dashboard():
    students = ["Student A", "Student B", "Student C", "Student D"]
    completion_status = DatabaseManager.get_completion_summary()
    completed_count = sum(1 for s in completion_status.values() if s["completed"])
    total_students = len(students)
    all_completed = all(s["completed"] for s in completion_status.values())
    teacher_marks = get_teacher_marks()
    
    results = None
    if all_completed:
        results = []
        for student in students:
            reviews = PeerReview.query.filter_by(reviewee_name=student).all()
            avg_peer_score = (
                sum(r.score for r in reviews) / len(reviews) if reviews else 0
            )
            
            if teacher_marks:
                final_mark = (
                    (teacher_marks.group_mark * 0.5)
                    + (teacher_marks.group_mark * 0.25 * (avg_peer_score / 5))
                    + (teacher_marks.group_mark * 0.25 * (teacher_marks.rating / 5))
                )
                results.append([student, round(avg_peer_score, 2), round(final_mark, 2)])
            else:
                results.append([student, round(avg_peer_score, 2), "Pending"])
    
    return render_template(
        "dashboard.html",
        students=students,
        completion_status=completion_status,
        completed_count=completed_count,
        total_students=total_students,
        all_students_completed=all_completed,
        teacher_marks=teacher_marks,
        results=results
    )

@app.route("/switch_user_and_form/<username>")
def switch_user_and_form(username):
    # Convert username back from URL format
    display_name = username.replace('_', ' ')
    valid_users = ["Student A", "Student B", "Student C", "Student D"]
    
    if display_name in valid_users:
        session["current_user"] = display_name
        flash(f"Switched to {display_name}", "info")
        return redirect(url_for("form"))
    else:
        flash("Invalid user selected", "error")
        return redirect(url_for("dashboard"))

@app.route("/teacher_input", methods=["POST"])
def teacher_input():
    try:
        group_mark = float(request.form.get("group_mark", 0))
        rating = float(request.form.get("rating", 0))
        
        # Validation
        if not (0 <= group_mark <= 100):
            flash("Group mark must be between 0 and 100", "error")
            return redirect(url_for("dashboard"))
        
        if not (1 <= rating <= 5):
            flash("Rating must be between 1 and 5", "error")
            return redirect(url_for("dashboard"))
        
        # Upsert teacher marks (single latest record)
        teacher_mark = TeacherMark.query.order_by(TeacherMark.id.desc()).first()
        if teacher_mark:
            teacher_mark.group_mark = group_mark
            teacher_mark.rating = rating
        else:
            teacher_mark = TeacherMark(group_mark=group_mark, rating=rating)
            db.session.add(teacher_mark)
        db.session.commit()
        
        flash("Teacher marks saved successfully!", "success")
        
    except (ValueError, TypeError):
        flash("Invalid input. Please enter valid numbers.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving marks: {str(e)}", "error")
    
    return redirect(url_for("dashboard"))

@app.route("/form", methods=["GET", "POST"])
def form():
    current_user = session.get("current_user")
    if not current_user:
        flash("Please select a student first", "error")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        reviewees = request.form.getlist("reviewee[]")
        scores = request.form.getlist("score[]")
        comments = request.form.getlist("comment[]")

        # Validation
        if not reviewees or not scores or len(reviewees) != len(scores):
            flash("Invalid form data. Please try again.", "error")
            return redirect(url_for("form"))

        try:
            # Delete old reviews from this user
            PeerReview.query.filter_by(reviewer_name=current_user).delete()

            # Add new reviews
            for reviewee, score, comment in zip(reviewees, scores, comments):
                if reviewee and score:
                    review = PeerReview(
                        reviewer_name=current_user,
                        reviewee_name=reviewee,
                        score=int(score),
                        comment=comment or ""
                    )
                    db.session.add(review)

            db.session.commit()
            flash("Peer reviews submitted successfully!", "success")
            return redirect(url_for("self_assessment"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "error")
            return redirect(url_for("form"))
    
    # Prefill existing peer reviews for this user
    existing_reviews = PeerReview.query.filter_by(reviewer_name=current_user).all()
    prior_reviews = {r.reviewee_name: {"score": r.score, "comment": r.comment or ""} for r in existing_reviews}

    return render_template("form.html", current_user=current_user, prior_reviews=prior_reviews)

@app.route("/self_assessment", methods=["GET", "POST"])
def self_assessment():
    current_user = session.get("current_user")
    if not current_user:
        flash("Please select a student first", "error")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        summary = request.form.get("summary", "").strip()
        challenges = request.form.get("challenges", "").strip()
        different = request.form.get("different", "").strip()
        role = request.form.get("role", "").strip()
        feedback = request.form.get("feedback", "").strip()

        if not all([summary, challenges, different, role]):
            flash("Please fill in all required self-assessment fields.", "error")
            return redirect(url_for("self_assessment"))

        try:
            # Save or update self assessment
            existing = SelfAssessment.query.filter_by(student_name=current_user).first()
            if existing:
                existing.summary = summary
                existing.challenges = challenges
                existing.different = different
                existing.role = role
                existing.feedback = feedback
            else:
                sa = SelfAssessment(
                    student_name=current_user,
                    summary=summary,
                    challenges=challenges,
                    different=different,
                    role=role,
                    feedback=feedback
                )
                db.session.add(sa)

            db.session.commit()
            flash("Self-assessment completed successfully!", "success")
            return redirect(url_for("done"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while saving: {str(e)}", "error")
            return redirect(url_for("self_assessment"))

    return render_template("self_assessment.html", current_user=current_user)

@app.route("/done")
def done():
    current_user = session.get("current_user", "Student")
    return render_template("done.html", current_user=current_user)

@app.route("/results", methods=["GET", "POST"])
def results():
    # Handle legacy form submission for backward compatibility
    if request.method == "POST":
        try:
            group_mark = float(request.form.get("group_mark", 0))
            rating = float(request.form.get("lecturer_eval", 0))
            
            if 0 <= group_mark <= 100 and 1 <= rating <= 5:
                # Upsert as teacher mark
                teacher_mark = TeacherMark.query.order_by(TeacherMark.id.desc()).first()
                if teacher_mark:
                    teacher_mark.group_mark = group_mark
                    teacher_mark.rating = rating
                else:
                    teacher_mark = TeacherMark(group_mark=group_mark, rating=rating)
                    db.session.add(teacher_mark)
                db.session.commit()
                flash("Marks saved successfully!", "success")
            else:
                db.session.rollback()
                flash("Invalid input values", "error")
        except (ValueError, TypeError):
            db.session.rollback()
            flash("Invalid input values", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving marks: {e}", "error")

    teacher_marks = get_teacher_marks()
    students = ["Student A", "Student B", "Student C", "Student D"]
    rows = []

    # Check if all students completed both peer reviews and self-assessment
    completion_status = DatabaseManager.get_completion_summary()
    all_completed = all(s['completed'] for s in completion_status.values())
    if not all_completed:
        return render_template("results.html", all_completed=False)

    if teacher_marks:
        for student in students:
            reviews = PeerReview.query.filter_by(reviewee_name=student).all()
            if reviews:
                avg_score = sum(r.score for r in reviews) / len(reviews)
                comments = "; ".join([r.comment for r in reviews if r.comment]) or "No comments"
            else:
                avg_score = 0
                comments = "No comments"

            # Calculate final mark using the same formula
            final_mark = (teacher_marks.group_mark * 0.5) + \
                        (teacher_marks.group_mark * 0.25 * (avg_score / 5)) + \
                        (teacher_marks.group_mark * 0.25 * (teacher_marks.rating / 5))

            rows.append([
                student,
                round(avg_score, 2),
                round(final_mark, 2),
                comments
            ])

    return render_template("results.html",
                         rows=rows,
                         group_mark=teacher_marks.group_mark if teacher_marks else 0,
                         lecturer_eval=teacher_marks.rating if teacher_marks else 0,
                         all_completed=True)

@app.route("/submit", methods=["POST"])
def submit():
    return redirect(url_for("form"))  # Redirect to form to handle submission

@app.route("/finish", methods=["POST"])
def finish():
    return redirect(url_for("self_assessment"))  # Redirect to self_assessment to handle

@app.route("/edit_reviews")
def edit_reviews():
    return redirect(url_for("form"))

@app.route("/switch_user/<username>")
def switch_user(username):
    valid_users = ["Student A", "Student B", "Student C", "Student D"]
    if username in valid_users:
        session["current_user"] = username
        flash(f"Switched to {username}", "info")
    return redirect(url_for("dashboard"))

@app.route("/debug_db")
def debug_db():
    """Debug route to check database status"""
    try:
        result = "<h2>🔍 Database Debug Info</h2>"
        
        # Check if database file exists
        db_path = Path(app.instance_path) / "db.db"
        result += f"<p><strong>Database file:</strong> {db_path} (exists: {db_path.exists()})</p>"
        
        # Check tables
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        result += f"<p><strong>Tables:</strong> {tables}</p>"
        
        # Test queries
        try:
            reviews_count = PeerReview.query.count()
            result += f"<p><strong>Peer Reviews count:</strong> {reviews_count}</p>"
        except Exception as e:
            result += f"<p><strong>Peer Reviews error:</strong> {e}</p>"
        
        try:
            assessments_count = SelfAssessment.query.count()
            result += f"<p><strong>Self Assessments count:</strong> {assessments_count}</p>"
        except Exception as e:
            result += f"<p><strong>Self Assessments error:</strong> {e}</p>"
        
        try:
            teacher_marks_count = TeacherMark.query.count()
            result += f"<p><strong>Teacher Marks count:</strong> {teacher_marks_count}</p>"
        except Exception as e:
            result += f"<p><strong>Teacher Marks error:</strong> {e}</p>"
        
        return result
    except Exception as e:
        return f"<h2>❌ Debug Error</h2><p>{str(e)}</p>"

@app.route("/view_db")
def view_db():
    """View actual database content"""
    try:
        result = "<h2>Database Content</h2>"
        
        # Show Peer Reviews
        reviews = PeerReview.query.all()
        result += f"<h3>Peer Reviews ({len(reviews)} records):</h3><pre>"
        for review in reviews:
            result += f"ID: {review.id}, Reviewer: {review.reviewer_name}, Reviewee: {review.reviewee_name}, Score: {review.score}, Comment: {review.comment}\n"
        result += "</pre>"
        
        # Show Self Assessments
        assessments = SelfAssessment.query.all()
        result += f"<h3>Self Assessments ({len(assessments)} records):</h3><pre>"
        for assessment in assessments:
            result += f"ID: {assessment.id}, Student: {assessment.student_name}, Summary: {assessment.summary[:50] if assessment.summary else 'None'}...\n"
        result += "</pre>"
        
        # Show Teacher Marks
        teacher_marks = TeacherMark.query.all()
        result += f"<h3>Teacher Marks ({len(teacher_marks)} records):</h3><pre>"
        for mark in teacher_marks:
            result += f"ID: {mark.id}, Group Mark: {mark.group_mark}%, Rating: {mark.rating}/5\n"
        result += "</pre>"
        
        return result
    except Exception as e:
        return f"Error viewing database: {e}"

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)