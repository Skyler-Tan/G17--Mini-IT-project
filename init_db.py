# init_db.py - Run this file first to initialize the database
from flask import Flask
from models import db, User, PeerReview, SelfAssessment, LecturerMark

def init_database():
    """Initialize the database with tables"""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    db.init_app(app)
    
    with app.app_context():
        # Drop all tables and recreate (for clean start)
        print("Dropping existing tables...")
        db.drop_all()
        
        # Create all tables
        print("Creating new tables...")
        db.create_all()
        
        # Verify tables were created
        print("Tables created:")
        inspector = db.inspect(db.engine)
        for table_name in inspector.get_table_names():
            print(f"  - {table_name}")
            columns = inspector.get_columns(table_name)
            for column in columns:
                print(f"    * {column['name']} ({column['type']})")
        
        print("Database initialization complete!")

if __name__ == "__main__":
    init_database()