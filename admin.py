import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import time
from db import get_database
from utils import (
    hash_password, generate_employee_id, validate_date_range,
    calculate_attendance_stats, format_date_for_display, get_date_range_options
)


def convert_image_to_base64(uploaded_file):
    """Convert uploaded image to base64 string with proper format handling"""
    try:
        from PIL import Image
        import base64
        import io
        
        # Open the image
        image = Image.open(uploaded_file)
        
        # Convert RGBA to RGB if necessary (for PNG with transparency)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create a white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode not in ('RGB', 'L'):
            # Convert other modes to RGB
            image = image.convert('RGB')
        
        # Resize image if too large (optional - helps with storage)
        max_size = (1200, 1200)
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        
        # Determine format based on original file extension
        file_extension = uploaded_file.name.lower().split('.')[-1]
        if file_extension in ['jpg', 'jpeg']:
            save_format = 'JPEG'
            quality = 85
        else:
            # Save as PNG for better quality, or convert to JPEG if you prefer smaller files
            save_format = 'PNG'
            quality = None
        
        # If you want to force all images to JPEG for smaller file sizes, uncomment below:
        # save_format = 'JPEG'
        # quality = 85
        
        if save_format == 'JPEG':
            image.save(buffer, format=save_format, quality=quality, optimize=True)
        else:
            image.save(buffer, format=save_format, optimize=True)
        
        # Get base64 string
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return image_base64
        
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return None

def base64_to_image(base64_string):
    """Convert base64 string back to PIL Image"""
    try:
        from PIL import Image
        import base64
        import io
        
        # Decode base64
        image_data = base64.b64decode(base64_string)
        
        # Create PIL Image
        image = Image.open(io.BytesIO(image_data))
        
        return image
        
    except Exception as e:
        print(f"Error converting base64 to image: {e}")
        return None

def admin_dashboard():
    """Main admin dashboard"""
    st.title("🔧 Admin Dashboard")
    st.markdown("---")
    
    # Sidebar navigation
    with st.sidebar:
        st.header("📋 Admin Menu")
        menu_option = st.selectbox(
            "Select Action",
            [
                "📊 Dashboard Overview",
                "👥 Manage Employees", 
                "✅ Mark Attendance",
                "📝 Edit Attendance",
                "📅 View Attendance",
                "📸 Manage TBT Images",
                "📋 Attendance Requests",
                "📈 Reports & Analytics"
            ]
        )
    
    # Route to appropriate function
    if menu_option == "📊 Dashboard Overview":
        dashboard_overview()
    elif menu_option == "👥 Manage Employees":
        manage_employees()
    elif menu_option == "✅ Mark Attendance":
        mark_attendance()
    elif menu_option == "📝 Edit Attendance":
        edit_attendance()
    elif menu_option == "📅 View Attendance":
        view_attendance()
    elif menu_option == "📸 Manage TBT Images":
        manage_tbt_images()
    elif menu_option == "📋 Attendance Requests":
        attendance_requests()
    elif menu_option == "📈 Reports & Analytics":
        reports_analytics()

def dashboard_overview():
    """Dashboard overview with key metrics"""
    st.subheader("📊 Dashboard Overview")
    
    db = get_database()
    
    # Get metrics - Convert date to datetime for MongoDB compatibility
    total_employees = db.employees.count_documents({})
    today = datetime.now().date()
    # Convert date to datetime range for MongoDB query
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    today_attendance = db.attendance.count_documents({
        "date": {"$gte": today_start, "$lte": today_end}
    })
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Employees", total_employees)
    
    with col2:
        st.metric("Today's Attendance", today_attendance)
    
    with col3:
        pending_requests = db.attendance_requests.count_documents({"status": "pending"})
        st.metric("Pending Requests", pending_requests)
    
    with col4:
        present_today = db.attendance.count_documents({
            "date": {"$gte": today_start, "$lte": today_end}, 
            "status": "present"
        })
        attendance_rate = f"{(present_today/total_employees*100):.1f}%" if total_employees > 0 else "0%"
        st.metric("Today's Attendance Rate", attendance_rate)
    
    st.markdown("---")
    
    # Recent activities
    st.subheader("📋 Recent Activities")
    
    # Get recent attendance records
    recent_attendance = list(db.attendance.find().sort("created_at", -1).limit(10))
    
    if recent_attendance:
        for record in recent_attendance:
            employee = db.employees.find_one({"employee_id": record["employee_id"]})
            employee_name = employee["full_name"] if employee else "Unknown"
            
            status_color = "🟢" if record["status"] == "present" else "🔴"
            # Handle both date and datetime objects
            record_date = record['date']
            if isinstance(record_date, datetime):
                record_date = record_date.date()
            st.write(f"{status_color} **{employee_name}** - {record['status'].title()} - {format_date_for_display(record_date)}")
    else:
        st.info("No recent attendance records found.")

def manage_employees():
    """Manage employee accounts"""
    st.subheader("👥 Manage Employees")
    
    tab1, tab2, tab3 = st.tabs(["➕ Add Employee", "📋 View Employees", "✏️ Edit Employee"])
    
    with tab1:
        add_employee()
    
    with tab2:
        view_employees()
    
    with tab3:
        edit_employee()

def add_employee():
    """Add new employee"""
    st.write("### Add New Employee")
    
    with st.form("add_employee_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name*")
            email = st.text_input("Email*")
            phone = st.text_input("Phone Number")
        
        with col2:
            department = st.text_input("Department*")
            position = st.text_input("Position*")
            join_date = st.date_input("Join Date*", value=datetime.now().date(), key="add_employee_join_date")
        
        username = st.text_input("Username*")
        password = st.text_input("Password*", type="password")
        confirm_password = st.text_input("Confirm Password*", type="password")
        
        submitted = st.form_submit_button("Add Employee")
        
        if submitted:
            if not all([full_name, email, department, position, username, password]):
                st.error("Please fill all required fields!")
                return
            
            if password != confirm_password:
                st.error("Passwords do not match!")
                return
            
            db = get_database()
            
            # Check if username already exists
            if db.employees.find_one({"username": username}):
                st.error("Username already exists!")
                return
            
            # Generate employee ID
            employee_id = generate_employee_id()
            
            # Create employee record - convert date to datetime
            employee_data = {
                "employee_id": employee_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "department": department,
                "position": position,
                "join_date": datetime.combine(join_date, datetime.min.time()),
                "username": username,
                "password": hash_password(password),
                "created_at": datetime.now(),
                "is_active": True
            }
            
            try:
                db.employees.insert_one(employee_data)
                st.success(f"Employee added successfully! Employee ID: {employee_id}")
            except Exception as e:
                st.error(f"Error adding employee: {e}")

def view_employees():
    """View all employees"""
    st.write("### Employee List")
    
    db = get_database()
    employees = list(db.employees.find({}, {"password": 0}).sort("employee_id", 1))
    
    if employees:
        df = pd.DataFrame(employees)
        df = df[['employee_id', 'full_name', 'department', 'position', 'email', 'is_active']]
        df.columns = ['Employee ID', 'Name', 'Department', 'Position', 'Email', 'Active']
        
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No employees found.")

def edit_employee():
    """Edit employee details"""
    st.write("### Edit Employee")
    
    db = get_database()
    employees = list(db.employees.find({}, {"password": 0}).sort("full_name", 1))
    
    if not employees:
        st.info("No employees found.")
        return
    
    # Employee selection
    employee_options = {f"{emp['full_name']} ({emp['employee_id']})": emp['employee_id'] for emp in employees}
    selected_employee = st.selectbox("Select Employee", list(employee_options.keys()))
    
    if selected_employee:
        employee_id = employee_options[selected_employee]
        employee = db.employees.find_one({"employee_id": employee_id})
        
        with st.form("edit_employee_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                full_name = st.text_input("Full Name", value=employee['full_name'])
                email = st.text_input("Email", value=employee['email'])
                phone = st.text_input("Phone", value=employee.get('phone', ''))
            
            with col2:
                department = st.text_input("Department", value=employee['department'])
                position = st.text_input("Position", value=employee['position'])
                is_active = st.checkbox("Active", value=employee.get('is_active', True))
            
            submitted = st.form_submit_button("Update Employee")
            
            if submitted:
                update_data = {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "department": department,
                    "position": position,
                    "is_active": is_active,
                    "updated_at": datetime.now()
                }
                
                try:
                    db.employees.update_one(
                        {"employee_id": employee_id},
                        {"$set": update_data}
                    )
                    st.success("Employee updated successfully!")
                except Exception as e:
                    st.error(f"Error updating employee: {e}")


import pandas as pd
import streamlit as st
from io import BytesIO
from datetime import datetime

# Custom CSS for professional mobile-responsive design
def inject_custom_css():
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    .main {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }
    
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Header Styles */
    .attendance-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 1.5rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        color: white;
        text-align: center;
    }
    
    .attendance-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .attendance-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
        font-weight: 300;
    }
    
    /* Card Styles */
    .attendance-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .attendance-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
    }
    
    /* Employee Card Styles */
    .employee-card {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        border-left: 4px solid #667eea;
        transition: all 0.2s ease;
    }
    
    .employee-card:hover {
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.15);
        transform: translateX(2px);
    }
    
    .employee-info {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 0.75rem;
    }
    
    .employee-avatar {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 0.9rem;
        flex-shrink: 0;
    }
    
    .employee-details h4 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: #2d3748;
    }
    
    .employee-details p {
        margin: 0;
        font-size: 0.875rem;
        color: #718096;
        line-height: 1.2;
    }
    
    /* Status Indicators */
    .status-present {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
        display: inline-block;
    }
    
    .status-absent {
        background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
        display: inline-block;
    }
    
    /* Metrics Cards */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
        border-top: 4px solid #667eea;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #2d3748;
        margin: 0;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #718096;
        font-weight: 500;
        margin-top: 0.5rem;
    }
    
    .metric-present .metric-value {
        color: #38a169;
    }
    
    .metric-absent .metric-value {
        color: #e53e3e;
    }
    
    /* Button Styles */
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Radio Button Styles */
    .stRadio > label {
        font-weight: 500 !important;
        color: #4a5568 !important;
    }
    
    .stRadio > div[role="radiogroup"] > label {
        background: #f7fafc;
        border: 2px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        margin: 0.25rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .stRadio > div[role="radiogroup"] > label:hover {
        border-color: #667eea;
        background: #edf2f7;
    }
    
    /* Mobile Responsiveness */
    @media (max-width: 768px) {
        .attendance-title {
            font-size: 2rem;
        }
        
        .attendance-header {
            padding: 1.5rem 1rem;
            margin-bottom: 1rem;
        }
        
        .attendance-card {
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        .employee-card {
            padding: 0.75rem;
        }
        
        .employee-info {
            flex-direction: column;
            align-items: flex-start;
            gap: 0.5rem;
        }
        
        .employee-avatar {
            width: 40px;
            height: 40px;
            font-size: 0.8rem;
        }
        
        .metric-value {
            font-size: 2rem;
        }
    }
    
    /* Loading Animation */
    .loading-spinner {
        border: 3px solid #f3f3f3;
        border-top: 3px solid #667eea;
        border-radius: 50%;
        width: 30px;
        height: 30px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Success/Error Messages */
    .stSuccess {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        font-weight: 500;
    }
    
    .stError {
        background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        font-weight: 500;
    }
    
    .stInfo {
        background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
        color: white;
        border-radius: 10px;
        padding: 1rem;
        font-weight: 500;
    }
    
    /* Download Buttons */
    .download-section {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
    }
    
    /* Tab Styles */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: white;
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        border: 2px solid #e2e8f0;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-color: #667eea;
    }
    </style>
    """, unsafe_allow_html=True)

def mark_attendance():
    """Professional mobile-responsive attendance marking interface"""
    
    # Inject custom CSS
    inject_custom_css()
    
    # Header Section
    st.markdown("""
    <div class="attendance-header">
        <h1 class="attendance-title">📋 Daily Attendance</h1>
        <p class="attendance-subtitle">Mark employee attendance with ease</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Date selection in a card
    with st.container():
        st.markdown('<div class="attendance-card">', unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📅 Select Date")
            attendance_date = st.date_input(
                "Choose attendance date", 
                value=datetime.now().date(), 
                key="mark_attendance_date",
                help="Select the date for marking attendance"
            )
        
        with col2:
            st.markdown("### ⏰ Current Time")
            current_time = datetime.now().strftime("%I:%M %p")
            st.markdown(f"<h3 style='color: #667eea; margin-top: 1rem;'>{current_time}</h3>", unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    if attendance_date > datetime.now().date():
        st.error("❌ Cannot mark attendance for future dates!")
        return
    
    db = get_database()
    
    # Convert date to datetime range for MongoDB query
    date_start = datetime.combine(attendance_date, datetime.min.time())
    date_end = datetime.combine(attendance_date, datetime.max.time())
    
    # Check if attendance has been submitted for this date
    attendance_submitted = st.session_state.get(f'attendance_submitted_{attendance_date}', False)
    
    if attendance_submitted:
        show_attendance_summary(db, date_start, date_end, attendance_date)
        
        # Reset button
        st.markdown('<div class="attendance-card">', unsafe_allow_html=True)
        if st.button("✏️ Edit Attendance", use_container_width=True, type="primary"):
            st.session_state[f'attendance_submitted_{attendance_date}'] = False
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Check existing attendance
    existing_attendance = list(db.attendance.find({
        "date": {"$gte": date_start, "$lte": date_end}
    }))
    existing_dict = {record['employee_id']: record for record in existing_attendance}
    
    # Get employees who haven't been marked as present yet
    marked_present_employee_ids = [
        record['employee_id'] for record in existing_attendance 
        if record['status'] == 'present'
    ]
    
    # Get all active employees sorted by employee_id
    all_employees = list(db.employees.find({
        "is_active": True
    }).sort("employee_id", 1))
    
    # Filter employees based on existing attendance
    if existing_attendance:
        employees = [emp for emp in all_employees if emp['employee_id'] not in marked_present_employee_ids]
    else:
        employees = all_employees
    
    if not employees and not existing_attendance:
        st.info("ℹ️ No active employees found.")
        return
    
    if not employees and existing_attendance:
        st.success("✅ All active employees have been marked as present for this date!")
        show_attendance_summary(db, date_start, date_end, attendance_date)
        return
    
    # Statistics Section
    total_employees = len(all_employees)
    already_marked = len(marked_present_employee_ids)
    remaining = len(employees)
    
    st.markdown('<div class="attendance-card">', unsafe_allow_html=True)
    st.markdown("### 📊 Quick Stats")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_employees}</div>
            <div class="metric-label">Total Employees</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card metric-present">
            <div class="metric-value">{already_marked}</div>
            <div class="metric-label">Already Marked</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{remaining}</div>
            <div class="metric-label">Remaining</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Search and Filter Section
    st.markdown('<div class="attendance-card">', unsafe_allow_html=True)
    st.markdown("### 🔍 Search & Filter")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input("🔍 Search employees...", placeholder="Search by name or employee ID")
    with col2:
        filter_dept = st.selectbox("🏢 Filter by Department", 
                                  options=["All"] + list(set([emp.get('department', 'N/A') for emp in employees])))
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Filter employees based on search and filter
    filtered_employees = employees
    if search_term:
        filtered_employees = [emp for emp in filtered_employees 
                            if search_term.lower() in emp['full_name'].lower() or 
                               search_term.lower() in emp['employee_id'].lower()]
    
    if filter_dept != "All":
        filtered_employees = [emp for emp in filtered_employees 
                            if emp.get('department', 'N/A') == filter_dept]
    
    st.markdown(f"### 👥 Mark Attendance ({len(filtered_employees)} employees)")
    
    if existing_attendance:
        st.info(f"ℹ️ Showing remaining employees. {len(marked_present_employee_ids)} employees already marked as present.")
    
    # Attendance Form
    with st.form("attendance_form"):
        attendance_data = {}
        
        # Bulk actions
        st.markdown("#### ⚡ Quick Actions")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("✅ Mark All Present", use_container_width=True):
                for emp in filtered_employees:
                    attendance_data[emp['employee_id']] = 'present'
        with col2:
            if st.form_submit_button("❌ Mark All Absent", use_container_width=True):
                for emp in filtered_employees:
                    attendance_data[emp['employee_id']] = 'absent'
        with col3:
            if st.form_submit_button("🔄 Reset All", use_container_width=True):
                attendance_data = {}
        
        st.markdown("---")
        st.markdown("#### 👤 Individual Attendance")
        
        # Employee attendance marking
        for i, employee in enumerate(filtered_employees):
            # Generate initials for avatar
            name_parts = employee['full_name'].split()
            initials = ''.join([part[0].upper() for part in name_parts[:2]])
            
            st.markdown(f"""
            <div class="employee-card">
                <div class="employee-info">
                    <div class="employee-avatar">{initials}</div>
                    <div class="employee-details">
                        <h4>{employee['full_name']}</h4>
                        <p><strong>ID:</strong> {employee['employee_id']} | <strong>Dept:</strong> {employee.get('department', 'N/A')}</p>
                        <p><strong>Designation:</strong> {employee.get('designation', 'N/A')}</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Status selection
            current_status = existing_dict.get(employee['employee_id'], {}).get('status', 'present')
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.radio(f"Status for {employee['employee_id']}", 
                           ['✅ Present', '❌ Absent'],
                           index=0 if current_status == 'present' else 1,
                           key=f"status_{employee['employee_id']}",
                           horizontal=True) == '✅ Present':
                    attendance_data[employee['employee_id']] = 'present'
                else:
                    attendance_data[employee['employee_id']] = 'absent'
            
            with col2:
                if employee['employee_id'] in existing_dict:
                    if existing_dict[employee['employee_id']]['status'] == 'absent':
                        st.markdown('<span class="status-absent">Previously Absent</span>', unsafe_allow_html=True)
            
            if i < len(filtered_employees) - 1:
                st.markdown("---")
        
        # Submit button
        st.markdown("### 💾 Save Attendance")
        submitted = st.form_submit_button(
            "💾 Save All Attendance Records", 
            use_container_width=True, 
            type="primary"
        )
        
        if submitted:
            # Show loading spinner
            with st.spinner('Saving attendance records...'):
                records_updated = 0
                records_inserted = 0
                
                for emp_id, status in attendance_data.items():
                    record_data = {
                        "employee_id": emp_id,
                        "date": datetime.combine(attendance_date, datetime.min.time()),
                        "status": status,
                        "marked_by": st.session_state.user_data['username'],
                        "created_at": datetime.now()
                    }
                    
                    try:
                        if emp_id in existing_dict:
                            db.attendance.update_one(
                                {"employee_id": emp_id, "date": {"$gte": date_start, "$lte": date_end}},
                                {"$set": {**record_data, "updated_at": datetime.now()}}
                            )
                            records_updated += 1
                        else:
                            db.attendance.insert_one(record_data)
                            records_inserted += 1
                    
                    except Exception as e:
                        st.error(f"❌ Error saving attendance for {emp_id}: {e}")
                
                st.success(f"✅ Attendance saved successfully! {records_inserted} new records, {records_updated} updated.")
                
                # Set flag to show summary
                st.session_state[f'attendance_submitted_{attendance_date}'] = True
                st.rerun()


def show_attendance_summary(db, date_start, date_end, attendance_date):
    """Professional attendance summary with mobile-responsive design"""
    
    st.markdown("""
    <div class="attendance-card">
        <h2 style="color: #667eea; margin-bottom: 1rem;">📊 Attendance Summary</h2>
        <p style="color: #718096; font-size: 1.1rem;"><strong>Date:</strong> {}</p>
    </div>
    """.format(format_date_for_display(attendance_date)), unsafe_allow_html=True)
    
    # Get attendance records
    attendance_records = list(db.attendance.find({
        "date": {"$gte": date_start, "$lte": date_end}
    }))
    
    if not attendance_records:
        st.info("ℹ️ No attendance records found for this date.")
        return
    
    # Get employee details
    employee_ids = [record['employee_id'] for record in attendance_records]
    employees = list(db.employees.find({
        "employee_id": {"$in": employee_ids}
    }))
    employee_dict = {emp['employee_id']: emp for emp in employees}
    
    # Prepare data
    present_employees = []
    absent_employees = []
    
    for record in attendance_records:
        emp_id = record['employee_id']
        employee = employee_dict.get(emp_id, {})
        
        emp_data = {
            'Employee ID': emp_id,
            'Name': employee.get('full_name', 'Unknown'),
            'Department': employee.get('department', 'N/A'),
            'Designation': employee.get('designation', 'N/A'),
            'Status': record['status'].title(),
            'Marked By': record.get('marked_by', 'N/A'),
            'Time': record.get('created_at', datetime.now()).strftime('%I:%M %p')
        }
        
        if record['status'] == 'present':
            present_employees.append(emp_data)
        else:
            absent_employees.append(emp_data)
    
    # Sort by Employee ID
    present_employees.sort(key=lambda x: x['Employee ID'])
    absent_employees.sort(key=lambda x: x['Employee ID'])
    
    # Summary metrics
    st.markdown('<div class="attendance-card">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(attendance_records)}</div>
            <div class="metric-label">Total</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card metric-present">
            <div class="metric-value">{len(present_employees)}</div>
            <div class="metric-label">Present</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card metric-absent">
            <div class="metric-value">{len(absent_employees)}</div>
            <div class="metric-label">Absent</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        attendance_rate = (len(present_employees) / len(attendance_records) * 100) if attendance_records else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{attendance_rate:.1f}%</div>
            <div class="metric-label">Attendance Rate</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Tabbed view for present/absent employees
    tab1, tab2 = st.tabs([f"✅ Present ({len(present_employees)})", f"❌ Absent ({len(absent_employees)})"])
    
    with tab1:
        if present_employees:
            present_df = pd.DataFrame(present_employees)
            st.dataframe(
                present_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Status": st.column_config.TextColumn(
                        "Status",
                        help="Attendance Status"
                    )
                }
            )
        else:
            st.info("ℹ️ No employees marked as present.")
    
    with tab2:
        if absent_employees:
            absent_df = pd.DataFrame(absent_employees)
            st.dataframe(
                absent_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Status": st.column_config.TextColumn(
                        "Status",
                        help="Attendance Status"
                    )
                }
            )
        else:
            st.success("✅ No employees marked as absent.")
    
    # Download section
    st.markdown('<div class="download-section">', unsafe_allow_html=True)
    st.markdown("### 📥 Download Reports")
    
    # Prepare combined data
    all_employees_data = present_employees + absent_employees
    all_employees_data.sort(key=lambda x: x['Employee ID'])
    
    if all_employees_data:
        combined_df = pd.DataFrame(all_employees_data)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # CSV download
            csv_buffer = BytesIO()
            combined_df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=f"attendance_{attendance_date.strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Excel download
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                combined_df.to_excel(writer, sheet_name='Attendance', index=False)
                if present_employees:
                    pd.DataFrame(present_employees).to_excel(writer, sheet_name='Present', index=False)
                if absent_employees:
                    pd.DataFrame(absent_employees).to_excel(writer, sheet_name='Absent', index=False)
            
            excel_data = excel_buffer.getvalue()
            
            st.download_button(
                label="📊 Download Excel",
                data=excel_data,
                file_name=f"attendance_{attendance_date.strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col3:
            # JSON download
            json_data = combined_df.to_json(orient='records', indent=2)
            
            st.download_button(
                label="📱 Download JSON",
                data=json_data,
                file_name=f"attendance_{attendance_date.strftime('%Y-%m-%d')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick summary for sharing
    st.markdown('<div class="attendance-card">', unsafe_allow_html=True)
    st.markdown("### 📱 Quick Summary")
    summary_text = f"""
📋 Attendance Summary - {format_date_for_display(attendance_date)}
{'='*50}
📊 Total Employees: {len(attendance_records)}
✅ Present: {len(present_employees)}
❌ Absent: {len(absent_employees)}
📈 Attendance Rate: {attendance_rate:.1f}%

✅ Present Employees:
{chr(10).join([f"• {emp['Name']} ({emp['Employee ID']})" for emp in present_employees]) if present_employees else "None"}

❌ Absent Employees:
{chr(10).join([f"• {emp['Name']} ({emp['Employee ID']})" for emp in absent_employees]) if absent_employees else "None"}
"""
    
    st.text_area("📋 Copy this summary:", summary_text, height=200)
    st.markdown('</div>', unsafe_allow_html=True)

# Helper function for date formatting
def format_date_for_display(date):
    """Format date for display"""
    return date.strftime("%B %d, %Y")


def edit_attendance():
    """Edit previously marked attendance"""
    st.subheader("📝 Edit Attendance")
    
    db = get_database()
    
    # Date and employee selection
    col1, col2 = st.columns(2)
    
    with col1:
        edit_date = st.date_input("Select Date", value=datetime.now().date(), key="edit_attendance_date")
    
    with col2:
        employees = list(db.employees.find({"is_active": True}).sort("full_name", 1))
        employee_options = {f"{emp['full_name']} ({emp['employee_id']})": emp['employee_id'] for emp in employees}
        selected_employee = st.selectbox("Select Employee", list(employee_options.keys()))
    
    if selected_employee and edit_date:
        employee_id = employee_options[selected_employee]
        
        # Convert date to datetime range for MongoDB query
        date_start = datetime.combine(edit_date, datetime.min.time())
        date_end = datetime.combine(edit_date, datetime.max.time())
        
        # Get current attendance record
        current_record = db.attendance.find_one({
            "employee_id": employee_id,
            "date": {"$gte": date_start, "$lte": date_end}
        })
        
        if not current_record:
            st.info("No attendance record found for this employee on the selected date.")
            return
        
        st.write(f"### Current Status: **{current_record['status'].title()}**")
        
        # Edit form
        with st.form("edit_attendance_form"):
            new_status = st.radio(
                "New Status",
                ['present', 'absent'],
                index=0 if current_record['status'] == 'present' else 1,
                horizontal=True
            )
            
            edit_reason = st.text_area("Reason for Edit*", placeholder="Mandatory: Explain why you're editing this attendance record...")
            
            submitted = st.form_submit_button("Update Attendance")
            
            if submitted:
                if not edit_reason.strip():
                    st.error("Please provide a reason for editing!")
                    return
                
                if new_status == current_record['status']:
                    st.warning("No changes made to attendance status.")
                    return
                
                try:
                    # Update attendance record
                    db.attendance.update_one(
                        {"employee_id": employee_id, "date": {"$gte": date_start, "$lte": date_end}},
                        {
                            "$set": {
                                "status": new_status,
                                "updated_at": datetime.now(),
                                "updated_by": st.session_state.user_data['username']
                            }
                        }
                    )
                    
                    # Log the edit
                    edit_log = {
                        "employee_id": employee_id,
                        "date": datetime.combine(edit_date, datetime.min.time()),
                        "old_status": current_record['status'],
                        "new_status": new_status,
                        "reason": edit_reason,
                        "edited_by": st.session_state.user_data['username'],
                        "edited_at": datetime.now()
                    }
                    
                    db.edit_logs.insert_one(edit_log)
                    
                    st.success("Attendance updated successfully!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error updating attendance: {e}")

def view_attendance():
    """View attendance records"""
    st.subheader("📅 View Attendance")
    
    db = get_database()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        view_type = st.selectbox("View Type", ["By Employee", "By Date", "Calendar View"])
    
    if view_type == "By Employee":
        with col2:
            employees = list(db.employees.find({"is_active": True}).sort("full_name", 1))
            employee_options = {f"{emp['full_name']} ({emp['employee_id']})": emp['employee_id'] for emp in employees}
            selected_employee = st.selectbox("Select Employee", list(employee_options.keys()))
        
        with col3:
            date_range_option = st.selectbox("Date Range", list(get_date_range_options().keys()))
            start_date, end_date = get_date_range_options()[date_range_option]
        
        if selected_employee:
            employee_id = employee_options[selected_employee]
            show_employee_attendance(employee_id, start_date, end_date)
    
    elif view_type == "By Date":
        with col2:
            selected_date = st.date_input("Select Date", value=datetime.now().date(), key="view_attendance_date")
        
        show_date_attendance(selected_date)
    
    elif view_type == "Calendar View":
        with col2:
            cal_year = st.selectbox("Year", range(datetime.now().year - 2, datetime.now().year + 1))
        with col3:
            cal_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1)
        
        show_calendar_view(cal_year, cal_month)

def show_employee_attendance(employee_id, start_date, end_date):
    """Show attendance for specific employee"""
    db = get_database()
    
    # Get employee details
    employee = db.employees.find_one({"employee_id": employee_id})
    if not employee:
        st.error("Employee not found!")
        return
    
    st.write(f"### Attendance for {employee['full_name']}")
    
    # Convert dates to datetime range for MongoDB query
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get attendance records
    attendance_records = list(db.attendance.find({
        "employee_id": employee_id,
        "date": {"$gte": start_datetime, "$lte": end_datetime}
    }).sort("date", -1))
    
    if attendance_records:
        # Calculate stats
        stats = calculate_attendance_stats(attendance_records)
        
        # Display stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Days", stats['total_days'])
        with col2:
            st.metric("Present", stats['present_days'])
        with col3:
            st.metric("Absent", stats['absent_days'])
        with col4:
            st.metric("Attendance %", f"{stats['attendance_percentage']}%")
        
        # Display records table
        df = pd.DataFrame(attendance_records)
        # Handle datetime conversion for display
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df = df[['date', 'status', 'marked_by']].rename(columns={
            'date': 'Date',
            'status': 'Status',
            'marked_by': 'Marked By'
        })
        
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No attendance records found for the selected period.")

def show_date_attendance(selected_date):
    """Show attendance for specific date"""
    db = get_database()
    
    st.write(f"### Attendance for {format_date_for_display(selected_date)}")
    
    # Convert date to datetime range for MongoDB query
    date_start = datetime.combine(selected_date, datetime.min.time())
    date_end = datetime.combine(selected_date, datetime.max.time())
    
    # Get attendance records for the date
    attendance_records = list(db.attendance.find({
        "date": {"$gte": date_start, "$lte": date_end}
    }))
    
    if attendance_records:
        # Get employee details
        employee_ids = [record['employee_id'] for record in attendance_records]
        employees = {emp['employee_id']: emp for emp in db.employees.find({"employee_id": {"$in": employee_ids}})}
        
        # Create display data
        display_data = []
        for record in attendance_records:
            employee = employees.get(record['employee_id'], {})
            display_data.append({
                'Employee ID': record['employee_id'],
                'Name': employee.get('full_name', 'Unknown'),
                'Department': employee.get('department', 'Unknown'),
                'Status': record['status'].title(),
                'Marked By': record.get('marked_by', 'Unknown')
            })
        
        df = pd.DataFrame(display_data)
        
        # Summary
        total_marked = len(display_data)
        present_count = sum(1 for d in display_data if d['Status'] == 'Present')
        absent_count = total_marked - present_count
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Marked", total_marked)
        with col2:
            st.metric("Present", present_count)
        with col3:
            st.metric("Absent", absent_count)
        
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No attendance records found for this date.")

def show_calendar_view(year, month):
    """Show calendar view of attendance"""
    db = get_database()
    
    st.write(f"### Calendar View - {calendar.month_name[month]} {year}")
    
    # Get all attendance records for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
    
    attendance_records = list(db.attendance.find({
        "date": {"$gte": start_date, "$lte": end_date}
    }))
    
    # Group by date
    daily_stats = {}
    for record in attendance_records:
        # Handle both date and datetime objects
        record_date = record['date']
        if isinstance(record_date, datetime):
            date_str = record_date.strftime('%Y-%m-%d')
        else:
            date_str = record_date.strftime('%Y-%m-%d')
            
        if date_str not in daily_stats:
            daily_stats[date_str] = {'present': 0, 'absent': 0}
        daily_stats[date_str][record['status']] += 1
    
    # Display calendar with statistics
    if daily_stats:
        for date_str, stats in daily_stats.items():
            total = stats['present'] + stats['absent']
            attendance_rate = (stats['present'] / total * 100) if total > 0 else 0
            st.write(f"**{date_str}**: {stats['present']} Present, {stats['absent']} Absent ({attendance_rate:.1f}% attendance)")
    else:
        st.info("No attendance records found for this month.")

def manage_tbt_images():
    """Manage TBT (Toolbox Talk) images"""
    st.subheader("📸 Manage TBT Images")
    
    tab1, tab2, tab3 = st.tabs(["📤 Upload Images", "👁️ View Images", "🗑️ Delete Images"])
    
    with tab1:
        upload_tbt_images()
    
    with tab2:
        view_tbt_images()
    
    with tab3:
        delete_tbt_images()

def upload_tbt_images():
    """Upload TBT images - Fixed version"""
    st.write("### Upload TBT Images")
    
    db = get_database()
    
    # Date selection
    upload_date = st.date_input("Select Date", value=datetime.now().date(), key="upload_tbt_date")
    
    # Convert date to datetime range for MongoDB query
    date_start = datetime.combine(upload_date, datetime.min.time())
    date_end = datetime.combine(upload_date, datetime.max.time())
    
    # Check existing images for the date
    existing_images = list(db.attendance_images.find({
        "date": {"$gte": date_start, "$lte": date_end}
    }))
    
    if len(existing_images) >= 2:
        st.warning("Maximum 2 images per day already uploaded!")
        st.write("### Current Images:")
        for i, img in enumerate(existing_images, 1):
            st.write(f"**Image {i}:** {img['filename']} (uploaded by {img['uploaded_by']})")
        return
    
    remaining_slots = 2 - len(existing_images)
    st.info(f"You can upload {remaining_slots} more image(s) for this date.")
    
    # Show existing images if any
    if existing_images:
        st.write("### Already Uploaded:")
        for i, img in enumerate(existing_images, 1):
            st.write(f"**Image {i}:** {img['filename']} (uploaded by {img['uploaded_by']})")
    
    # Image upload
    uploaded_files = st.file_uploader(
        "Choose TBT Images",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        key="tbt_upload",
        help="Supported formats: PNG, JPG, JPEG. Images will be automatically optimized."
    )
    
    if uploaded_files:
        if len(uploaded_files) > remaining_slots:
            st.error(f"You can only upload {remaining_slots} more image(s) for this date!")
            return
        
        # Preview images before upload
        st.write("### Preview:")
        cols = st.columns(min(len(uploaded_files), 3))
        for i, uploaded_file in enumerate(uploaded_files):
            with cols[i % 3]:
                st.image(uploaded_file, caption=uploaded_file.name, width=200)
        
        if st.button("Upload Images", type="primary"):
            uploaded_count = 0
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    # Update progress
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing {uploaded_file.name}...")
                    
                    # Convert to base64
                    image_base64 = convert_image_to_base64(uploaded_file)
                    
                    if image_base64:
                        # Save to database - store as datetime
                        image_data = {
                            "date": datetime.combine(upload_date, datetime.min.time()),
                            "filename": uploaded_file.name,
                            "original_format": uploaded_file.name.lower().split('.')[-1],
                            "file_size": len(image_base64),  # Store base64 size for reference
                            "image_data": image_base64,
                            "uploaded_by": st.session_state.user_data['username'],
                            "uploaded_at": datetime.now()
                        }
                        
                        db.attendance_images.insert_one(image_data)
                        uploaded_count += 1
                        st.success(f"✅ {uploaded_file.name} uploaded successfully!")
                    else:
                        st.error(f"❌ Failed to process {uploaded_file.name}")
                    
                except Exception as e:
                    st.error(f"❌ Error uploading {uploaded_file.name}: {str(e)}")
            
            progress_bar.empty()
            status_text.empty()
            
            if uploaded_count > 0:
                st.success(f"🎉 Successfully uploaded {uploaded_count} out of {len(uploaded_files)} image(s)!")
                st.balloons()  # Fun celebration effect
                time.sleep(2)  # Brief pause before rerun
                st.rerun()
            else:
                st.error("No images were uploaded successfully. Please try again.")

def view_tbt_images():
    """View TBT images"""
    st.write("### View TBT Images")
    
    db = get_database()
    
    # Date selection
    view_date = st.date_input("Select Date", value=datetime.now().date(), key="view_tbt_date")
    
    # Convert date to datetime range for MongoDB query
    date_start = datetime.combine(view_date, datetime.min.time())
    date_end = datetime.combine(view_date, datetime.max.time())
    
    # Get images for the date
    images = list(db.attendance_images.find({
        "date": {"$gte": date_start, "$lte": date_end}
    }).sort("uploaded_at", 1))
    
    if images:
        st.write(f"**Images for {format_date_for_display(view_date)}**")
        
        for i, img_record in enumerate(images, 1):
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Display image
                    try:
                        image = base64_to_image(img_record['image_data'])
                        if image:
                            st.image(image, caption=f"TBT Image {i} - {img_record['filename']}", width=500)
                        else:
                            st.error(f"Could not display image: {img_record['filename']}")
                    except Exception as e:
                        st.error(f"Error displaying image {img_record['filename']}: {str(e)}")
                
                with col2:
                    st.write(f"**Filename:** {img_record['filename']}")
                    st.write(f"**Uploaded by:** {img_record['uploaded_by']}")
                    st.write(f"**Upload time:** {img_record['uploaded_at'].strftime('%H:%M:%S')}")
                    st.write(f"**Format:** {img_record.get('original_format', 'Unknown').upper()}")
                    
                    # Delete button
                    if st.button(f"🗑️ Delete", key=f"delete_img_{img_record['_id']}", type="secondary"):
                        if st.session_state.get(f"confirm_delete_{img_record['_id']}", False):
                            try:
                                db.attendance_images.delete_one({"_id": img_record['_id']})
                                st.success("Image deleted!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting image: {e}")
                        else:
                            st.session_state[f"confirm_delete_{img_record['_id']}"] = True
                            st.warning("Click delete again to confirm!")
                
                st.markdown("---")
    else:
        st.info("No images found for the selected date.")

def delete_tbt_images():
    """Delete TBT images"""
    st.write("### Delete TBT Images")
    
    db = get_database()
    
    # Date selection
    delete_date = st.date_input("Select Date", value=datetime.now().date(), key="delete_tbt_date")
    
    # Convert date to datetime range for MongoDB query
    date_start = datetime.combine(delete_date, datetime.min.time())
    date_end = datetime.combine(delete_date, datetime.max.time())
    
    # Get images for the date
    images = list(db.attendance_images.find({
        "date": {"$gte": date_start, "$lte": date_end}
    }).sort("uploaded_at", 1))
    
    if images:
        st.write(f"**Images for {format_date_for_display(delete_date)}**")
        
        # Bulk delete option
        if len(images) > 1:
            if st.button("🗑️ Delete All Images for This Date", type="secondary"):
                if st.session_state.get("confirm_bulk_delete", False):
                    try:
                        result = db.attendance_images.delete_many({
                            "date": {"$gte": date_start, "$lte": date_end}
                        })
                        st.success(f"Deleted {result.deleted_count} images!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting images: {e}")
                else:
                    st.session_state["confirm_bulk_delete"] = True
                    st.warning("Click again to confirm bulk delete!")
            
            st.markdown("---")
        
        # Individual images
        for i, img_record in enumerate(images, 1):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                # Display thumbnail
                try:
                    image = base64_to_image(img_record['image_data'])
                    if image:
                        st.image(image, width=200)
                    else:
                        st.error("Could not display image")
                except Exception as e:
                    st.error(f"Error displaying image: {str(e)}")
            
            with col2:
                st.write(f"**Filename:** {img_record['filename']}")
                st.write(f"**Uploaded by:** {img_record['uploaded_by']}")
                st.write(f"**Upload time:** {img_record['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            
            with col3:
                if st.button(f"🗑️ Delete", key=f"delete_individual_{img_record['_id']}", type="secondary"):
                    if st.session_state.get(f"confirm_individual_delete_{img_record['_id']}", False):
                        try:
                            db.attendance_images.delete_one({"_id": img_record['_id']})
                            st.success("Image deleted!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting image: {e}")
                    else:
                        st.session_state[f"confirm_individual_delete_{img_record['_id']}"] = True
                        st.warning("Click again to confirm!")
        
    else:
        st.info("No images found for the selected date.")

def attendance_requests():
    """Handle attendance requests from employees"""
    st.subheader("📋 Attendance Requests")
    
    db = get_database()
    
    # Get pending requests
    pending_requests = list(db.attendance_requests.find({"status": "pending"}).sort("created_at", -1))
    
    if pending_requests:
        st.write("### Pending Requests")
        
        for req in pending_requests:
            # Get employee details
            employee = db.employees.find_one({"employee_id": req['employee_id']})
            employee_name = employee['full_name'] if employee else "Unknown"
            
            # Handle date conversion for display
            req_date = req['date']
            if isinstance(req_date, datetime):
                req_date = req_date.date()
            
            with st.expander(f"Request from {employee_name} - {format_date_for_display(req_date)}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Employee:** {employee_name} ({req['employee_id']})")
                    st.write(f"**Date:** {format_date_for_display(req_date)}")
                    st.write(f"**Request:** {req['message']}")
                    st.write(f"**Submitted:** {req['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col2:
                    col_approve, col_reject = st.columns(2)
                    
                    with col_approve:
                        if st.button("✅ Approve", key=f"approve_{req['_id']}", type="primary"):
                            handle_request_action(req, "approved")
                    
                    with col_reject:
                        if st.button("❌ Reject", key=f"reject_{req['_id']}", type="secondary"):
                            handle_request_action(req, "rejected")
    else:
        st.info("No pending requests.")
    
    # Show recent resolved requests
    st.write("### Recent Resolved Requests")
    resolved_requests = list(db.attendance_requests.find({
        "status": {"$in": ["approved", "rejected"]}
    }).sort("updated_at", -1).limit(10))
    
    if resolved_requests:
        for req in resolved_requests:
            employee = db.employees.find_one({"employee_id": req['employee_id']})
            employee_name = employee['full_name'] if employee else "Unknown"
            
            # Handle date conversion for display
            req_date = req['date']
            if isinstance(req_date, datetime):
                req_date = req_date.date()
            
            status_color = "🟢" if req['status'] == "approved" else "🔴"
            resolved_time = req.get('updated_at', req['created_at']).strftime('%Y-%m-%d %H:%M')
            st.write(f"{status_color} **{employee_name}** - {req['status'].title()} - {format_date_for_display(req_date)} - {resolved_time}")
    else:
        st.info("No resolved requests found.")

def handle_request_action(request, action):
    """Handle approval/rejection of attendance request"""
    db = get_database()
    
    try:
        # Update request status
        db.attendance_requests.update_one(
            {"_id": request['_id']},
            {
                "$set": {
                    "status": action,
                    "resolved_by": st.session_state.user_data['username'],
                    "updated_at": datetime.now()
                }
            }
        )
        
        # If approved, update attendance record
        if action == "approved":
            # Handle date conversion
            req_date = request['date']
            if isinstance(req_date, datetime):
                req_date = req_date.date()
            
            # Convert to datetime range for MongoDB query
            date_start = datetime.combine(req_date, datetime.min.time())
            date_end = datetime.combine(req_date, datetime.max.time())
            
            # Check if attendance record exists
            existing_attendance = db.attendance.find_one({
                "employee_id": request['employee_id'],
                "date": {"$gte": date_start, "$lte": date_end}
            })
            
            if existing_attendance:
                # Update existing record
                db.attendance.update_one(
                    {"employee_id": request['employee_id'], "date": {"$gte": date_start, "$lte": date_end}},
                    {
                        "$set": {
                            "status": "present",
                            "updated_at": datetime.now(),
                            "updated_by": st.session_state.user_data['username']
                        }
                    }
                )
            else:
                # Create new attendance record
                attendance_data = {
                    "employee_id": request['employee_id'],
                    "date": datetime.combine(req_date, datetime.min.time()),
                    "status": "present",
                    "marked_by": st.session_state.user_data['username'],
                    "created_at": datetime.now(),
                    "note": "Approved from employee request"
                }
                db.attendance.insert_one(attendance_data)
        
        st.success(f"Request {action}!")
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"Error processing request: {e}")

def reports_analytics():
    """Generate reports and analytics"""
    st.subheader("📈 Reports & Analytics")
    
    tab1, tab2, tab3 = st.tabs(["📊 Department Analytics", "📅 Monthly Reports", "📋 Export Data"])
    
    with tab1:
        department_analytics()
    
    with tab2:
        monthly_reports()
    
    with tab3:
        export_data()

def department_analytics():
    """Show department-wise analytics"""
    st.write("### Department-wise Attendance Analytics")
    
    db = get_database()
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=30), key="dept_analytics_start_date")
    with col2:
        end_date = st.date_input("End Date", value=datetime.now().date(), key="dept_analytics_end_date")
    
    if start_date > end_date:
        st.error("Start date cannot be after end date!")
        return
    
    # Convert dates to datetime range for MongoDB query
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get attendance data
    attendance_records = list(db.attendance.find({
        "date": {"$gte": start_datetime, "$lte": end_datetime}
    }))
    
    if not attendance_records:
        st.info("No attendance data found for the selected period.")
        return
    
    # Get employee data
    employee_ids = list(set(record['employee_id'] for record in attendance_records))
    employees = {emp['employee_id']: emp for emp in db.employees.find({"employee_id": {"$in": employee_ids}})}
    
    # Calculate department-wise stats
    dept_stats = {}
    for record in attendance_records:
        employee = employees.get(record['employee_id'])
        if employee:
            dept = employee.get('department', 'Unknown')
            if dept not in dept_stats:
                dept_stats[dept] = {'total': 0, 'present': 0, 'absent': 0}
            
            dept_stats[dept]['total'] += 1
            if record['status'] == 'present':
                dept_stats[dept]['present'] += 1
            else:
                dept_stats[dept]['absent'] += 1
    
    # Display results
    dept_data = []
    for dept, stats in dept_stats.items():
        attendance_rate = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
        dept_data.append({
            'Department': dept,
            'Total Records': stats['total'],
            'Present': stats['present'],
            'Absent': stats['absent'],
            'Attendance Rate (%)': round(attendance_rate, 2)
        })
    
    if dept_data:
        df = pd.DataFrame(dept_data)
        st.dataframe(df, use_container_width=True)
        
        # Simple visualization using Streamlit's built-in charts
        chart_df = df.set_index('Department')['Attendance Rate (%)']
        st.bar_chart(chart_df)
    else:
        st.info("No department data found.")

def monthly_reports():
    """Generate monthly reports"""
    st.write("### Monthly Attendance Reports")
    
    db = get_database()
    
    # Month/Year selection
    col1, col2 = st.columns(2)
    with col1:
        report_year = st.selectbox("Year", range(datetime.now().year - 2, datetime.now().year + 1), key="monthly_report_year")
    with col2:
        report_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1, key="monthly_report_month")
    
    # Generate report
    start_date = datetime(report_year, report_month, 1)
    if report_month == 12:
        end_date = datetime(report_year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(report_year, report_month + 1, 1) - timedelta(seconds=1)
    
    # Get data
    attendance_records = list(db.attendance.find({
        "date": {"$gte": start_date, "$lte": end_date}
    }))
    
    if attendance_records:
        # Calculate employee-wise stats
        employee_stats = {}
        for record in attendance_records:
            emp_id = record['employee_id']
            if emp_id not in employee_stats:
                employee_stats[emp_id] = {'present': 0, 'absent': 0, 'total': 0}
            
            employee_stats[emp_id]['total'] += 1
            if record['status'] == 'present':
                employee_stats[emp_id]['present'] += 1
            else:
                employee_stats[emp_id]['absent'] += 1
        
        # Get employee details
        employees = {emp['employee_id']: emp for emp in db.employees.find()}
        
        # Create report data
        report_data = []
        for emp_id, stats in employee_stats.items():
            employee = employees.get(emp_id, {})
            attendance_rate = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            report_data.append({
                'Employee ID': emp_id,
                'Name': employee.get('full_name', 'Unknown'),
                'Department': employee.get('department', 'Unknown'),
                'Total Days': stats['total'],
                'Present': stats['present'],
                'Absent': stats['absent'],
                'Attendance Rate (%)': round(attendance_rate, 2)
            })
        
        df = pd.DataFrame(report_data)
        st.dataframe(df, use_container_width=True)
        
        # Summary stats
        total_records = sum(stats['total'] for stats in employee_stats.values())
        total_present = sum(stats['present'] for stats in employee_stats.values())
        overall_rate = (total_present / total_records * 100) if total_records > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", total_records)
        with col2:
            st.metric("Total Present", total_present)
        with col3:
            st.metric("Overall Rate", f"{overall_rate:.2f}%")
        
    else:
        st.info("No attendance data found for the selected month.")

def export_data():
    """Export attendance data"""
    st.write("### Export Attendance Data")
    
    db = get_database()
    
    # Export options
    export_type = st.selectbox("Export Type", ["All Attendance Records", "Employee List", "Monthly Summary"])
    
    if export_type == "All Attendance Records":
        # Date range
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=30), key="export_start_date")
        with col2:
            end_date = st.date_input("End Date", value=datetime.now().date(), key="export_end_date")
        
        if st.button("Generate Export", type="primary"):
            # Convert dates to datetime range for MongoDB query
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            # Get data
            attendance_records = list(db.attendance.find({
                "date": {"$gte": start_datetime, "$lte": end_datetime}
            }).sort("date", -1))
            
            if attendance_records:
                # Get employee details
                employee_ids = list(set(record['employee_id'] for record in attendance_records))
                employees = {emp['employee_id']: emp for emp in db.employees.find({"employee_id": {"$in": employee_ids}})}
                
                # Create export data
                export_data = []
                for record in attendance_records:
                    employee = employees.get(record['employee_id'], {})
                    # Handle datetime conversion for export
                    record_date = record['date']
                    if isinstance(record_date, datetime):
                        date_str = record_date.strftime('%Y-%m-%d')
                    else:
                        date_str = record_date.strftime('%Y-%m-%d')
                    
                    export_data.append({
                        'Date': date_str,
                        'Employee ID': record['employee_id'],
                        'Employee Name': employee.get('full_name', 'Unknown'),
                        'Department': employee.get('department', 'Unknown'),
                        'Status': record['status'].title(),
                        'Marked By': record.get('marked_by', 'Unknown')
                    })
                
                df = pd.DataFrame(export_data)
                
                # Convert to CSV
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"attendance_records_{start_date}_to_{end_date}.csv",
                    mime="text/csv"
                )
                
                st.success(f"Export ready! {len(export_data)} records found.")
            else:
                st.info("No records found for the selected period.")
    
    elif export_type == "Employee List":
        if st.button("Generate Employee Export", type="primary"):
            employees = list(db.employees.find({}, {"password": 0}))
            
            if employees:
                df = pd.DataFrame(employees)
                # Remove MongoDB _id field and format dates
                if '_id' in df.columns:
                    df = df.drop('_id', axis=1)
                
                # Format datetime fields for CSV export
                for col in df.columns:
                    if df[col].dtype == 'datetime64[ns]' or col in ['join_date', 'created_at', 'updated_at']:
                        df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Employee List",
                    data=csv,
                    file_name="employee_list.csv",
                    mime="text/csv"
                )
                
                st.success(f"Employee list ready! {len(employees)} employees found.")
            else:
                st.info("No employees found.")
    
    elif export_type == "Monthly Summary":
        col1, col2 = st.columns(2)
        with col1:
            summary_year = st.selectbox("Year", range(datetime.now().year - 2, datetime.now().year + 1), key="export_summary_year")
        with col2:
            summary_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1, key="export_summary_month")
        
        if st.button("Generate Monthly Summary", type="primary"):
            # Similar to monthly_reports but for export
            start_date = datetime(summary_year, summary_month, 1)
            if summary_month == 12:
                end_date = datetime(summary_year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(summary_year, summary_month + 1, 1) - timedelta(seconds=1)
            
            attendance_records = list(db.attendance.find({
                "date": {"$gte": start_date, "$lte": end_date}
            }))
            
            if attendance_records:
                # Calculate stats (similar to monthly_reports)
                employee_stats = {}
                for record in attendance_records:
                    emp_id = record['employee_id']
                    if emp_id not in employee_stats:
                        employee_stats[emp_id] = {'present': 0, 'absent': 0, 'total': 0}
                    
                    employee_stats[emp_id]['total'] += 1
                    if record['status'] == 'present':
                        employee_stats[emp_id]['present'] += 1
                    else:
                        employee_stats[emp_id]['absent'] += 1
                
                employees = {emp['employee_id']: emp for emp in db.employees.find()}
                
                summary_data = []
                for emp_id, stats in employee_stats.items():
                    employee = employees.get(emp_id, {})
                    attendance_rate = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
                    
                    summary_data.append({
                        'Employee ID': emp_id,
                        'Name': employee.get('full_name', 'Unknown'),
                        'Department': employee.get('department', 'Unknown'),
                        'Total Days': stats['total'],
                        'Present': stats['present'],
                        'Absent': stats['absent'],
                        'Attendance Rate (%)': round(attendance_rate, 2)
                    })
                
                df = pd.DataFrame(summary_data)
                csv = df.to_csv(index=False)
                
                month_name = calendar.month_name[summary_month]
                st.download_button(
                    label="📥 Download Monthly Summary",
                    data=csv,
                    file_name=f"monthly_summary_{month_name}_{summary_year}.csv",
                    mime="text/csv"
                )
                
                st.success(f"Monthly summary ready! {len(summary_data)} records found.")
            else:
                st.info("No attendance data found for the selected month.")