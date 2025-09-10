from app import app, db
from models import PeerReview, SelfAssessment, TeacherMark
import os

def test_database():
    with app.app_context():
        # Check if database file exists
        print(f"Database file exists: {os.path.exists('db.db')}")
        print(f"Current directory: {os.getcwd()}")
        
        # Test a simple database operation
        try:
            # Create a test review
            test_review = PeerReview(
                reviewer_name="Test Student",
                reviewee_name="Test Reviewee", 
                score=4,
                comment="Test comment"
            )
            
            print(f"Before add - Review ID: {test_review.id}")
            db.session.add(test_review)
            print(f"After add, before commit - Review ID: {test_review.id}")
            
            db.session.commit()
            print(f"After commit - Review ID: {test_review.id}")
            
            # Verify it was saved
            count = PeerReview.query.count()
            print(f"Total reviews in database: {count}")
            
            # Check file modification time
            if os.path.exists('db.db'):
                stat = os.stat('db.db')
                print(f"Database last modified: {stat.st_mtime}")
                
        except Exception as e:
            print(f"Test failed: {e}")
            db.session.rollback()

if __name__ == "__main__":
    test_database()