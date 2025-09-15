from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_migrate import Migrate
from models import db, PeerReview, SelfAssessment, AnonymousReview
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

# ----- Student list from DB (table: user) -----

def get_students_from_db():
    try:
        from sqlalchemy import text
        rows = db.session.execute(text("SELECT first_name, last_name FROM user WHERE LOWER(role) = 'student'")) \
            .fetchall()
        names = []
        for r in rows:
            fn = (r[0] or "").strip()
            ln = (r[1] or "").strip()
            full = (fn + " " + ln).strip() or fn or ln
            if full:
                names.append(full)
        return names
    except Exception:
        app.logger.exception("Error fetching students from user table")
        return []

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
    all_completed = all(v['completed'] for v in completion_status.values())

    # Compute peer average results only (no teacher marks anymore)
    results = []
    if all_completed:
        for student in students:
            reviews = PeerReview.query.filter_by(reviewee_name=student).all()
            avg_peer_score = (
                sum(r.score for r in reviews) / len(reviews) if reviews else 0
            )
            # Keep a 3rd placeholder to satisfy current template; will be removed in template cleanup
            results.append([student, round(avg_peer_score, 2), "Pending"])  # Final mark no longer uses teacher marks

    # teacher_marks is no longer used; pass None for compatibility with current template
    teacher_marks = None

    return render_template(
        "dashboard.html",
        students=students,
        completion_status=completion_status,
        completed_count=completed_count,
        total_students=total_students,
        all_students_completed=all_completed,
        teacher_marks=teacher_marks,
        results=results,
        # legacy keys removed: db_comparison, student_comparison
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

@app.route("/teacher_input", methods=["POST"])  # kept for compatibility with existing template; does nothing now
def teacher_input():
    flash("Teacher inputs have been removed. This project now uses only peer reviews.", "info")
    return redirect(url_for("dashboard"))

@app.route("/results", methods=["GET", "POST"])
def results():
    students = get_students_from_db()
    status = get_completion_status(students)
    all_completed = all(v['completed'] for v in status.values())

    group_mark = None
    lecturer_eval = None
    if request.method == "POST":
        try:
            gm = request.form.get("group_mark")
            le = request.form.get("lecturer_eval")
            group_mark = float(gm) if gm not in (None, "") else None
            lecturer_eval = float(le) if le not in (None, "") else None
        except (TypeError, ValueError):
            group_mark = None
            lecturer_eval = None
            flash("Invalid input for group mark or lecturer evaluation.", "error")

    rows = []
    if all_completed and group_mark is not None and lecturer_eval is not None:
        for student in students:
            reviews = PeerReview.query.filter_by(reviewee_name=student).all()
            avg_peer_score = (sum(r.score for r in reviews) / len(reviews)) if reviews else 0
            comments = "; ".join([r.comment for r in reviews if r.comment]) if reviews else "No comments"
            final_mark = (
                (group_mark * 0.5)
                + (group_mark * 0.25 * (avg_peer_score / 5.0))
                + (group_mark * 0.25 * (lecturer_eval / 5.0))
            )
            rows.append([student, round(avg_peer_score, 2), round(final_mark, 2), comments if comments else "No comments"])

    return render_template(
        "results.html",
        all_completed=all_completed,
        group_mark=group_mark,
        lecturer_eval=lecturer_eval,
        rows=rows,
    )

@app.route("/view_db")
def view_db():
    try:
        review_count = PeerReview.query.count()
        assessment_count = SelfAssessment.query.count()
        anon_count = AnonymousReview.query.count()
        try:
            from sqlalchemy import text
            users_count = db.session.execute(text("SELECT COUNT(*) FROM user")).scalar() or 0
        except Exception:
            users_count = 0
        html_out = "<h2>Database Overview</h2>"
        html_out += f"<p>Users: {users_count}</p>"
        html_out += f"<p>Peer Reviews: {review_count}</p>"
        html_out += f"<p>Self Assessments: {assessment_count}</p>"
        html_out += f"<p>Anonymous Reviews: {anon_count}</p>"
        html_out += '<p><a href="/dashboard">Back to Dashboard</a></p>'
        return html_out
    except Exception:
        app.logger.exception("Error rendering DB overview")
        return '<p>Error rendering DB overview. Check logs.</p>'

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

            # Remove any previous reviews by this reviewer to allow re-submit/edit
            PeerReview.query.filter_by(reviewer_name=current_user).delete()

            for reviewee, score_str, comment in zip(reviewees, scores, comments):
                if reviewee == current_user:
                    # skip self-reviews
                    continue
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
                    reviewer_name=current_user,
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
            flash("Peer reviews submitted.", "success")
            return redirect(url_for("self_assessment"))
        except Exception:
            db.session.rollback()
            app.logger.exception("Error saving peer reviews")
            flash("An error occurred while saving your reviews.", "error")
            return redirect(url_for("form"))

    # GET: Pre-fill prior reviews if any
    prior_reviews = {}
    existing = PeerReview.query.filter_by(reviewer_name=current_user).all()
    for r in existing:
        prior_reviews[r.reviewee_name] = {"score": r.score, "comment": r.comment}

    return render_template("form.html", current_user=current_user, prior_reviews=prior_reviews, students=students_list)

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

            # Replace existing self assessment for this user
            SelfAssessment.query.filter_by(student_name=current_user).delete()
            assessment = SelfAssessment(
                student_name=current_user,
                summary=summary,
                challenges=challenges,
                different=different,
                role=role,
                feedback=feedback or None
            )
            db.session.add(assessment)
            db.session.commit()

            flash("Self assessment submitted.", "success")
            return redirect(url_for("done"))
        except Exception:
            db.session.rollback()
            app.logger.exception("Error saving self assessment")
            flash("An error occurred while saving your self assessment.", "error")
            return redirect(url_for("self_assessment"))

    return render_template("self_assessment.html")

@app.route("/done")
def done():
    return render_template("done.html", current_user=session.get("current_user"))

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)
