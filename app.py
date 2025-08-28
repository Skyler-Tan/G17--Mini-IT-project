from flask import Flask, render_template, request, url_for, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Thanish@2006'
app.config['MYSQL_DB'] = 'flaskapp'

mysql = MySQL(app)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor = mysql.connection.cursor(MySQLdb.cursors.Dictcursor)
        cursor.execute('SELECT *FROM accounts where username = %s', (username,))
        account = cursor.fetchone()
        if account:
            msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid Email Address!'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Invalid username! Username must only contain numbers and letters!'
        elif not username or not password or not email:
            msg = 'Please fill out the form!'
        else:
            cursor.execute('INSERT INTO accounts VALUES(NULL, %s, %s, %s)' , (username, password, email) )
            mysql.connection.commit()
            msg = 'Congrats! You have successfully registered!'
        return render_template('register.html' , msg=msg)
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.Dictcursor)
        cursor.execute('SELECT *FROM accounts where username = %s', (username,))
        account = cursor.fetchone()

if __name__ == '__main__':
     app.run(debug=True)