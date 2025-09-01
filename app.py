from flask import Flask, render_template, request, redirect, url_for, session
import csv
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

CSV_FILE = "peer_reviews.csv"

@app.route("/", methods=["GET"])
def index():
    session.clear()
    return render_template("index.html")

@app.route("/form", methods=["GET"])
def form():
    return render_template("form.html")

@app.route("/self_assessment", methods=["GET", "POST"])
def self_assessment():
    if request.method == "POST":
        return render_template("self_assessment.html")
    return render_template("self_assessment.html")

@app.route("/submit", methods=["POST"])
def submit():
    reviewer = "Student A"  # Replace with session user later if needed
    
    reviewees = request.form.getlist("reviewee[]")
    scores = request.form.getlist("score[]")
    comments = request.form.getlist("comment[]")

    # Overwrite CSV file each time
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        for r, s, c in zip(reviewees, scores, comments):
            writer.writerow([reviewer, r, s, c])

    return redirect(url_for("results"))

@app.route("/finish", methods=["POST"])
def finish():
    return redirect(url_for("done"))

@app.route("/done")
def done():
    return render_template("done.html")

@app.route("/results", methods=["GET", "POST"])
def results():
    if request.method == "POST":
        try:
            session['group_mark'] = float(request.form.get("group_mark", 0))
            session['lecturer_eval'] = float(request.form.get("lecturer_eval", 0))
        except (ValueError, TypeError):
            session['group_mark'] = 0
            session['lecturer_eval'] = 0

    group_mark = session.get('group_mark', 0)
    lecturer_eval = session.get('lecturer_eval', 0)

    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)  # don’t skip the first row

    students = {}
    for row in rows:
        if len(row) >= 4:
            reviewer, reviewee, score, comment = row
            try:
                score = int(score)
                if reviewee not in students:
                    students[reviewee] = {"scores": [], "comments": []}
                students[reviewee]["scores"].append(score)
                students[reviewee]["comments"].append(f"{reviewer}: {comment}")
            except ValueError:
                continue

    results_data = []
    for student, data in students.items():
        avg_peer = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0

        base_group_mark = group_mark * 0.5
        peer_contribution = group_mark * 0.25 * (avg_peer / 5)
        lecturer_contribution = group_mark * 0.25 * (lecturer_eval / 5)
        final_score = base_group_mark + peer_contribution + lecturer_contribution

        results_data.append([
            student,
            round(avg_peer, 2),
            round(final_score, 2),
            "; ".join(data["comments"])
        ])

    return render_template("results.html",
                           rows=results_data,
                           group_mark=group_mark,
                           lecturer_eval=lecturer_eval)

if __name__ == "__main__":
    app.run(debug=True)
