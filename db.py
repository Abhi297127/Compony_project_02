import streamlit as st
from pymongo import MongoClient, ASCENDING
import pymongo.errors
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_resource
def get_database():
    """Get MongoDB database connection"""
    try:
        # Get MongoDB URI from secrets
        mongodb_uri = st.secrets["mongodb"]["uri"]
        
        # Create MongoDB client
        client = MongoClient(mongodb_uri)
        
        # Test connection
        client.admin.command('ping')
        logger.info("MongoDB connection successful")
        
        # Return database
        return client.attendance_db
        
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        st.error(f"Database connection failed: {e}")
        st.stop()

def create_indexes():
    """Create database indexes for better performance"""
    try:
        db = get_database()
        
        # Create indexes for admins collection
        db.admins.create_index([("username", ASCENDING)], unique=True)
        
        # Create indexes for employees collection
        db.employees.create_index([("username", ASCENDING)], unique=True)
        db.employees.create_index([("employee_id", ASCENDING)], unique=True)
        
        # Create indexes for attendance collection
        db.attendance.create_index([("employee_id", ASCENDING), ("date", ASCENDING)], unique=True)
        db.attendance.create_index([("date", ASCENDING)])
        
        # Create indexes for attendance_images collection
        db.attendance_images.create_index([("date", ASCENDING)])
        
        # Create indexes for attendance_requests collection  
        db.attendance_requests.create_index([("employee_id", ASCENDING)])
        db.attendance_requests.create_index([("status", ASCENDING)])
        
        logger.info("Database indexes created successfully")
        
    except pymongo.errors.DuplicateKeyError:
        # Indexes already exist
        pass
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

def test_connection():
    """Test database connection"""
    try:
        db = get_database()
        result = db.command("ping")
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False

def get_collections():
    """Get all database collections"""
    db = get_database()
    return {
        'admins': db.admins,
        'employees': db.employees,
        'attendance': db.attendance,
        'attendance_images': db.attendance_images,
        'attendance_requests': db.attendance_requests,
        'edit_logs': db.edit_logs
    }