import streamlit as st
import bcrypt
from db import get_database, create_indexes
from admin import admin_dashboard
from employee import employee_dashboard
import datetime

# Page configuration
st.set_page_config(
    page_title="Employee Attendance Management System",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def authenticate_user(username, password, user_type):
    """Authenticate user credentials"""
    db = get_database()
    
    if user_type == "Admin":
        collection = db.admins
    else:
        collection = db.employees
    
    user = collection.find_one({"username": username})
    
    if user and verify_password(password, user['password']):
        return user
    return None

def login_page():
    """Display login page"""
    st.title("🏢 Employee Attendance Management System")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("🔐 Login")
        
        user_type = st.selectbox("Select User Type", ["Employee", "Admin"])
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", use_container_width=True):
            if username and password:
                user = authenticate_user(username, password, user_type)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_type = user_type
                    st.session_state.user_data = user
                    st.rerun()
                else:
                    st.error("Invalid credentials!")
            else:
                st.error("Please enter both username and password!")

def main():
    """Main application logic"""
    # Initialize database indexes
    create_indexes()
    
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    # Sidebar logout
    if st.session_state.logged_in:
        with st.sidebar:
            st.markdown(f"**Logged in as:** {st.session_state.user_data['username']}")
            st.markdown(f"**Role:** {st.session_state.user_type}")
            st.markdown("---")
            
            if st.button("🚪 Logout", use_container_width=True):
                # Clear session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
    
    # Route to appropriate dashboard
    if not st.session_state.logged_in:
        login_page()
    else:
        if st.session_state.user_type == "Admin":
            admin_dashboard()
        else:
            employee_dashboard()

if __name__ == "__main__":
    main()
