import os
import secrets
from flask import Flask, render_template, redirect, url_for, flash, request, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from flask_migrate import Migrate
from sqlalchemy import or_, text
from dotenv import load_dotenv

# Load .env file FIRST, before importing config
load_dotenv()

from config import Config
from models import db, User, Subject, Group, GroupMember, PeerReview, SelfAssessment, AnonymousReview, Setting

# ---------------- Flask app setup ---------------- #
app = Flask(__name__, instance_relative_config=True)

# Config from Config class
app.config.from_object(Config)

# Debug: Check database configuration
print("=== DATABASE CONFIGURATION ===")
print("DATABASE_URL from env:", os.environ.get('DATABASE_URL'))
print("DIRECT_URL from env:", os.environ.get('DIRECT_URL'))
print("SQLALCHEMY_DATABASE_URI:", app.config.get('SQLALCHEMY_DATABASE_URI'))

# Ensure instance folder exists
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

# Init extensions
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ----- Student list from DB (table: user) - EXCLUDE lecturers -----
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
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)