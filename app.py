from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_migrate import Migrate
from models import db, User, PeerReview, SelfAssessment

app = Flask(__name__)
app.secret_key = "secret-key"  # needed for session + flash

# Database config (using instance/db.db)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Init database + migration
db.init_app(app)
migrate = Migrate(app, db)

# Create tables if they don't exist
with app.app_context():
    db.create_all()

# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/form", methods=["GET", "POST"])
def form():
    if request.method == "POST":
        reviewees = request.form.getlist("reviewee[]")
        scores = request.form.getlist("score[]")
        comments = request.form.getlist("comment[]")

        current_user = session.get("current_user", "Student A")

        # delete old reviews
        PeerReview.query.filter_by(reviewer_name=current_user).delete()

        # add new reviews
        for r, s, c in zip(reviewees, scores, comments):
            if r and s:
                review = PeerReview(
                    reviewer_name=current_user,
                    reviewee_name=r,
                    score=int(s),
                    comment=c
                )
                db.session.add(review)

        db.session.commit()
        flash("Peer reviews submitted successfully!", "success")
        return redirect(url_for("self_assessment"))
    
    return render_template("form.html")


@app.route("/self_assessment", methods=["GET", "POST"])
def self_assessment():
    if request.method == "POST":
        current_user = session.get("current_user", "Student A")
        
        # Check if assessment already exists
        existing = SelfAssessment.query.filter_by(student_name=current_user).first()
        if existing:
            # Update existing
            existing.summary = request.form["summary"]
            existing.challenges = request.form["challenges"]
            existing.different = request.form["different"]
            existing.role = request.form["role"]
            existing.feedback = request.form["feedback"]
        else:
            # Create new
            sa = SelfAssessment(
                student_name=current_user,
                summary=request.form["summary"],
                challenges=request.form["challenges"],
                different=request.form["different"],
                role=request.form["role"],
                feedback=request.form["feedback"]
            )
            db.session.add(sa)
        
        db.session.commit()
        flash("Self-assessment saved successfully!", "success")
        return redirect(url_for("index"))

    return render_template("self_assessment.html")


@app.route("/submit", methods=["POST"])  # Fixed missing @
def submit():
    current_user = session.get("current_user", "Student A")
    reviewees = request.form.getlist("reviewee[]")
    scores = request.form.getlist("score[]")
    comments = request.form.getlist("comment[]")

    if not reviewees or not scores or len(reviewees) != len(scores):
        flash("Invalid form data. Please try again.", "error")
        return redirect(url_for("form"))

    try:
        # Delete old reviews
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


@app.route("/finish", methods=["POST"])
def finish():
    current_user = session.get("current_user", "Student A")

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

        # overwrite peer reviews if present
        reviewees = request.form.getlist("reviewee[]")
        scores = request.form.getlist("score[]")
        comments = request.form.getlist("comment[]")

        if reviewees and scores:
            PeerReview.query.filter_by(reviewer_name=current_user).delete()
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
        flash("Assessment completed successfully!", "success")
        return redirect(url_for("done"))
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while saving: {str(e)}", "error")
        return redirect(url_for("self_assessment"))


@app.route("/done")
def done():
    return render_template("done.html")


@app.route("/results", methods=["GET", "POST"])
def results():
    if request.method == "POST":
        try:
            session["group_mark"] = float(request.form.get("group_mark", 0))
            session["lecturer_eval"] = float(request.form.get("lecturer_eval", 0))
        except (ValueError, TypeError):
            session["group_mark"] = 0
            session["lecturer_eval"] = 0

    group_mark = session.get("group_mark", 0)
    lecturer_eval = session.get("lecturer_eval", 0)

    students = ["Student A", "Student B", "Student C", "Student D"]
    rows = []

    if group_mark and lecturer_eval:  # Only calculate if both values are set
        for student in students:
            reviews = PeerReview.query.filter_by(reviewee_name=student).all()
            if reviews:
                avg_score = sum(r.score for r in reviews) / len(reviews)
                comments = "; ".join([r.comment for r in reviews if r.comment]) or "No comments"
            else:
                avg_score = 0
                comments = "No comments"

            # Formula (matches your template explanation)
            final_mark = (group_mark * 0.5) \
                         + (group_mark * 0.25 * (avg_score / 5)) \
                         + (group_mark * 0.25 * (lecturer_eval / 5))

            rows.append([
                student,
                round(avg_score, 2),
                round(final_mark, 2),
                comments
            ])

    return render_template("results.html",
                           rows=rows,
                           group_mark=group_mark,
                           lecturer_eval=lecturer_eval)


@app.route("/edit_reviews")
def edit_reviews():
    return redirect(url_for("form"))


@app.route("/switch_user/<username>")
def switch_user(username):
    valid_users = ["Student A", "Student B", "Student C", "Student D"]
    if username in valid_users:
        session["current_user"] = username
        flash(f"Switched to {username}", "info")
    return redirect(url_for("index"))


@app.route("/inspect_db")
def inspect_db():
    """Inspect your existing database structure"""
    try:
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        table_info = {t: inspector.get_columns(t) for t in tables}
        return f"<pre>Tables in db.db: {tables}\n\nTable Info: {table_info}</pre>"
    except Exception as e:
        return f"Error inspecting database: {e}"


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
        
        return result
    except Exception as e:
        return f"Error viewing database: {e}"


# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)