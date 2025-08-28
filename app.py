from flask import Flask, request, jsonify
from models import db, Class, Group, Student

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/classes', methods=['POST'])
def create_class():
    data = request.json
    new_class = Class(class_name=data['class_name'], description=data.get('description'))
    db.session.add(new_class)
    db.session.commit()
    return jsonify({"message": "Class created successfully"}), 201

@app.route('/classes', methods=['GET'])
def get_classes():
    classes = Class.query.all()
    return jsonify([{"id": c.id, "class_name": c.class_name, "description": c.description} for c in classes])


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

