from flask import Flask, render_template, request
import csv
import os

app = Flask(__name__)

DATA_FILE = "data/peer_reviews.csv"
DEFAULT_GROUP = ["STUDENT BAT", "STUDENT BEE", "STUDENT BER", "STUDENT BIR"]

# --- Normalization Function ---
def normalize_scores(scores):
    scores = np.array(scores, dtype=float)
    avg = np.mean(scores)
    if avg == 0:
        return [3.0] * len(scores)
    normalized = scores * (3 / avg)
    return normalized.round(2).tolist()

@app.route("/")
def index():
    return render_template("index.html", group=DEFAULT_GROUP)

@app.route("/submit", methods=["POST"])
def submit():
    # Collect peer scores
    peer_scores = [int(request.form.get(f"score_{i}", 0)) for i in range(len(DEFAULT_GROUP))]
    comments = [request.form.get(f"comment_{i}", "") for i in range(len(DEFAULT_GROUP))]
    
    # Lecturer self-eval (for demo: take from form OR default = 4)
    lecturer_eval = int(request.form.get("lecturer_eval", 4))

    # Normalize peer scores
    normalized_scores = normalize_scores(peer_scores)

    # Calculate final scores
    final_scores = [
        round(0.83 * lecturer_eval + 0.17 * s, 2) for s in normalized_scores
    ]

    # Save into CSV
    file_exists = os.path.isfile(DATA_FILE)
    with open(DATA_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Name", "Raw Score", "Normalized", "Final Score", "Comment"])
        for i, name in enumerate(DEFAULT_GROUP):
            writer.writerow([name, peer_scores[i], normalized_scores[i], final_scores[i], comments[i]])

    # Show results immediately after submit
    results = zip(DEFAULT_GROUP, peer_scores, normalized_scores, final_scores, comments)
    return render_template("results.html", results=results, lecturer_eval=lecturer_eval)
