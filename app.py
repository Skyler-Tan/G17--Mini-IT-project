from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import abort
from flask_login import current_user 
from datetime import datetime
from flask_migrate import Migrate
from sqlalchemy import or_
from sqlalchemy import text
app = Flask(__name__)
app.config['SECRET_KEY'] = 'yoursecretkey'   # change this
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@app.route("/")
def home():
    return render_template("login.html", title="Login Page", current_year=datetime.now().year)

@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year}


#Database
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), nullable=False, unique=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # hashed password
    role = db.Column(db.String(20), nullable=False, default='student')
    gender = db.Column(db.String(20), nullable=False, server_default=text("'Other"))


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
        return render_template('lecturer_dashboard.html', user=current_user, prefix=prefix, current_year=datetime.now().year)
    elif current_user.role == "admin":
        return render_template('admin_dashboard.html', user=current_user, current_year=datetime.now().year)
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
    if request.method == "POST":
        current_user.username = request.form["username"]
        current_user.email = request.form["email"]

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=current_user)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)