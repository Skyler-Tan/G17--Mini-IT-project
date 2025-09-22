from flask import Flask, render_template, request, redirect, url_for, session, flash, current_app
from flask_migrate import Migrate
from models import db, User, PeerReview, SelfAssessment, AnonymousReview
from datetime import datetime
import os
import secrets

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_urlsafe(32))

# Single database configuration (instance/db.db)
class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(app.instance_path, 'db.db')

app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)


# ---------- Helpers ----------

def full_name_from_user(user):
    if not user:
        return ""
    fn = (user.first_name or "").strip()
    ln = (user.last_name or "").strip()
    return (fn + " " + ln).strip()


def get_user_by_fullname(fullname):
    """Try to find a User by a full name string (first + last).
    Splits by whitespace and uses first token and last token to match.
    """
    if not fullname:
        return None
    parts = fullname.strip().split()
    if len(parts) == 1:
        # Only one token, try matching either first_name or username
        return User.query.filter(
            (User.first_name == parts[0]) | (User.username == parts[0])
        ).first()
    first = parts[0]
    last = parts[-1]
    return User.query.filter_by(first_name=first, last_name=last).first()


# ----- Student list from DB (table: users) - EXCLUDE lecturers -----

def get_students_from_db(limit=4):
    try:
        # Use ORM to get students (role == student)
        students_q = User.query.filter(db.func.lower(User.role) == 'student').all()
        names = []
        for u in students_q:
            name = full_name_from_user(u)
            if name:
                names.append(name)
        return names[:limit]
    except Exception:
        app.logger.exception("Error fetching students from users table")
        return []


def is_lecturer(username):
    """Check if user is a lecturer"""
    if not username:
        return False
    user = get_user_by_fullname(username)
    if not user:
        return False
    return (user.role or "").lower() == 'lecturer'


# ---------- Helper Functions ----------

def get_completion_status(students):
    """Get completion status details for a given list of students.
    Returns mapping: { student_fullname: {reviews_count, has_assessment, completed} }
    """
    status = {}
    for student in students:
        user = get_user_by_fullname(student)
        if not user:
            status[student] = {'reviews_count': 0, 'has_assessment': False, 'completed': False}
            continue

        # Count reviews this user has given (as reviewer)
        reviews_count = PeerReview.query.filter_by(reviewer_student_id=user.student_id).count()

        # Check self-assessment — prefer student_id if available, fallback to student_name
        has_assessment = (
            SelfAssessment.query.filter_by(student_id=user.student_id).first() is not None
            or SelfAssessment.query.filter_by(student_name=student).first() is not None
        )

        status[student] = {
            'reviews_count': reviews_count,
            'has_assessment': has_assessment,
            'completed': (reviews_count > 0 and has_assessment)
        }
    return status


# ---------- Routes ----------

@app.route("/")
def index():
    return redirect(url_for('dashboard'))


@app.route("/dashboard")
def dashboard():
    students = get_students_from_db()
    completion_status = get_completion_status(students)

    completed_count = sum(1 for v in completion_status.values() if v['completed'])
    total_students = len(students)
    all_completed = all(v['completed'] for v in completion_status.values()) if students else False

    # Compute peer average results only when all students are completed
    results = []
    if all_completed:
        for student in students:
            student_user = get_user_by_fullname(student)
            if not student_user:
                continue
            reviews = PeerReview.query.filter_by(reviewee_student_id=student_user.student_id).all()
            avg_peer_score = (sum(r.score for r in reviews) / len(reviews)) if reviews else 0
            results.append([student, round(avg_peer_score, 2)])

    return render_template(
        "dashboard.html",
        students=students,
        completion_status=completion_status,
        completed_count=completed_count,
        total_students=total_students,
        all_completed=all_completed,
        results=results
    )


@app.route("/switch_user_and_form/<username>")
def switch_user_and_form(username):
    display_name = username.replace('_', ' ')
    students = get_students_from_db()
    if display_name in students:
        session["current_user"] = display_name
        flash(f"Switched to {display_name}", "info")
        return redirect(url_for("form"))
    else:
        flash("Invalid user selected", "error")
        return redirect(url_for("dashboard"))


@app.route("/results")
def results():
    students = get_students_from_db()
    status = get_completion_status(students)
    all_completed = all(v['completed'] for v in status.values()) if students else False
    completed_count = sum(1 for v in status.values() if v['completed'])

    current_user = session.get("current_user")
    is_current_lecturer = is_lecturer(current_user) if current_user else False

    rows = []

    for student in students:
        student_user = get_user_by_fullname(student)
        if student_user:
            reviews = PeerReview.query.filter_by(reviewee_student_id=student_user.student_id).all()
        else:
            reviews = []

        if all_completed and reviews:
            avg_peer_score = sum(r.score for r in reviews) / len(reviews)
            final_mark = round(avg_peer_score * 20, 2)  # Convert to 100-point scale
        else:
            avg_peer_score = None
            final_mark = None

        # Collect comments (only show to lecturer or the student themself)
        peer_comments = []
        if (current_user == student) or is_current_lecturer:
            for review in reviews:
                if review.comment and review.comment.strip():
                    # find reviewer name
                    reviewer_user = User.query.filter_by(student_id=review.reviewer_student_id).first()
                    reviewer_name = full_name_from_user(reviewer_user) or review.reviewer_student_id
                    peer_comments.append({
                        'reviewer': reviewer_name,
                        'comment': review.comment
                    })

        rows.append({
            'student_name': student,
            'avg_peer_score': round(avg_peer_score, 2) if avg_peer_score is not None else None,
            'final_mark': final_mark,
            'peer_comments': peer_comments
        })

    # Anonymous reviews (always shown)
    anonymous_reviews = AnonymousReview.query.all()

    # Self assessments (pass model objects or dicts — template should access fields accordingly)
    self_assessments = []
    for student in students:
        # Prefer looking up by student_id, fallback to student_name
        student_user = get_user_by_fullname(student)
        assessment = None
        if student_user:
            assessment = SelfAssessment.query.filter_by(student_id=student_user.student_id).first()
        if not assessment:
            assessment = SelfAssessment.query.filter_by(student_name=student).first()
        if assessment:
            # keep as object if your template expects object properties
            self_assessments.append(assessment)

    return render_template(
        "results.html",
        all_completed=all_completed,
        completed_count=completed_count,
        rows=rows,
        current_user=current_user,
        is_lecturer=is_current_lecturer,
        anonymous_reviews=anonymous_reviews,
        self_assessments=self_assessments
    )


@app.route("/form", methods=["GET", "POST"])
def form():
    current_user = session.get("current_user")
    students_list = get_students_from_db()
    if not current_user:
        flash("Select a student from the Dashboard first.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        try:
            reviewees = request.form.getlist("reviewee[]")
            scores = request.form.getlist("score[]")
            comments = request.form.getlist("comment[]")
            anon_text = request.form.get("anonymous_review", "").strip()

            if not (len(reviewees) == len(scores) == len(comments)):
                flash("Mismatch in submitted review data.", "error")
                return redirect(url_for("form"))

            # Map current_user -> reviewer User
            reviewer_user = get_user_by_fullname(current_user)
            if not reviewer_user:
                flash("Current user not found in database.", "error")
                return redirect(url_for("dashboard"))

            # Enforce review count limits: Must review all 3 other students (or 2-4 in other flows)
            filtered_reviewees = [r for r in reviewees if r != current_user and r in students_list]
            if len(filtered_reviewees) != (len(students_list) - 1):
                flash(f"You must review all {len(students_list)-1} other students.", "error")
                return redirect(url_for("form"))

            # Remove any previous reviews by this reviewer to allow re-submit/edit
            PeerReview.query.filter_by(reviewer_student_id=reviewer_user.student_id).delete()

            # Add reviews
            for reviewee_name, score_str, comment in zip(reviewees, scores, comments):
                if reviewee_name == current_user:
                    continue  # skip self-reviews
                if reviewee_name not in students_list:
                    continue
                try:
                    score = int(score_str)
                except (TypeError, ValueError):
                    flash("Invalid score provided.", "error")
                    return redirect(url_for("form"))
                if not (1 <= score <= 5):
                    flash("Scores must be between 1 and 5.", "error")
                    return redirect(url_for("form"))

                reviewee_user = get_user_by_fullname(reviewee_name)
                if not reviewee_user:
                    # skip if we can't find the reviewee
                    continue

                review = PeerReview(
                    reviewer_student_id=reviewer_user.student_id,
                    reviewee_student_id=reviewee_user.student_id,
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
    reviewer_user = get_user_by_fullname(current_user)
    if reviewer_user:
        existing = PeerReview.query.filter_by(reviewer_student_id=reviewer_user.student_id).all()
        for r in existing:
            reviewee_user = User.query.filter_by(student_id=r.reviewee_student_id).first()
            reviewee_name = full_name_from_user(reviewee_user) or r.reviewee_student_id
            prior_reviews[reviewee_name] = {"score": r.score, "comment": r.comment}

    # Get prior anonymous review - cannot reliably link to user without extra field
    prior_anon_review = ""

    return render_template(
        "form.html",
        current_user=current_user,
        prior_reviews=prior_reviews,
        students=students_list,
        prior_anon_review=prior_anon_review
    )


@app.route("/self_assessment", methods=["GET", "POST"])
def self_assessment():
    current_user = session.get("current_user")
    if not current_user:
        flash("Select a student from the Dashboard first.", "error")
        return redirect(url_for("dashboard"))

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

            # Find user (to set student_id on SelfAssessment)
            user = get_user_by_fullname(current_user)
            if user:
                # Replace existing self assessment for this user
                SelfAssessment.query.filter_by(student_id=user.student_id).delete()
                assessment = SelfAssessment(
                    student_id=user.student_id,
                    student_name=current_user,
                    summary=summary,
                    challenges=challenges,
                    different=different,
                    role=role,
                    feedback=feedback or None
                )
            else:
                # Fallback: keep using student_name only
                SelfAssessment.query.filter_by(student_name=current_user).delete()
                assessment = SelfAssessment(
                    student_id=None,
                    student_name=current_user,
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
    user = get_user_by_fullname(current_user)
    existing_assessment = None
    if user:
        existing_assessment = SelfAssessment.query.filter_by(student_id=user.student_id).first()
    if not existing_assessment:
        existing_assessment = SelfAssessment.query.filter_by(student_name=current_user).first()

    assessment_data = {}
    if existing_assessment:
        assessment_data = {
            'summary': existing_assessment.summary,
            'challenges': existing_assessment.challenges,
            'different': existing_assessment.different,
            'role': existing_assessment.role,
            'feedback': existing_assessment.feedback or ''
        }

    return render_template("self_assessment.html", current_user=current_user, assessment_data=assessment_data)


@app.route("/done")
def done():
    return render_template("done.html", current_user=session.get("current_user"))


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)
