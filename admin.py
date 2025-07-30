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


def mark_attendance():
    """Mark daily attendance"""
    st.subheader("✅ Mark Attendance")
    
    # Date selection
    attendance_date = st.date_input("Select Date", value=datetime.now().date(), key="mark_attendance_date")
    
    if attendance_date > datetime.now().date():
        st.error("Cannot mark attendance for future dates!")
        return
    
    db = get_database()
    
    # Convert date to datetime range for MongoDB query
    date_start = datetime.combine(attendance_date, datetime.min.time())
    date_end = datetime.combine(attendance_date, datetime.max.time())
    
    # Check if attendance already marked for this date (sorted by employee_id)
    existing_attendance = list(db.attendance.find({
        "date": {"$gte": date_start, "$lte": date_end}
    }).sort("employee_id", 1))
    existing_dict = {record['employee_id']: record for record in existing_attendance}
    
    # Get employees who haven't been marked at all (neither present nor absent)
    marked_employee_ids = [record['employee_id'] for record in existing_attendance]
    
    # Get all active employees excluding those already marked (present or absent) - sorted by employee_id
    employees = list(db.employees.find({
        "is_active": True,
        "employee_id": {"$nin": marked_employee_ids}
    }).sort("employee_id", 1))
    
    # Display attendance summary table if there are existing records
    if existing_attendance:
        st.write(f"### Attendance Summary for {format_date_for_display(attendance_date)}")
        
        # Create summary table (sorted by employee_id)
        summary_data = []
        present_count = 0
        absent_count = 0
        
        # Sort existing_attendance by employee_id for consistent display
        sorted_attendance = sorted(existing_attendance, key=lambda x: x['employee_id'])
        
        for record in sorted_attendance:
            # Get employee details
            employee = db.employees.find_one({"employee_id": record['employee_id']})
            employee_name = employee['full_name'] if employee else "Unknown"
            
            summary_data.append({
                "Employee ID": record['employee_id'],
                "Employee Name": employee_name,
                "Status": record['status'].title(),
                "Marked By": record.get('marked_by', 'N/A'),
                "Time": record.get('created_at', record.get('updated_at', 'N/A'))
            })
            
            if record['status'] == 'present':
                present_count += 1
            else:
                absent_count += 1
        
        # Display summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Present", present_count, delta=None)
        with col2:
            st.metric("Absent", absent_count, delta=None)
        with col3:
            st.metric("Total Marked", len(existing_attendance), delta=None)
        
        # Display attendance table
        if summary_data:
            df = pd.DataFrame(summary_data)
            st.dataframe(df, use_container_width=True)
    
    # Show remaining employees to mark
    if not employees:
        if existing_attendance:
            st.success(f"✅ All active employees have been marked for {format_date_for_display(attendance_date)}!")
        else:
            st.info("No active employees found.")
        return
    
    st.write(f"### Mark Remaining Employees for {format_date_for_display(attendance_date)}")
    st.info(f"📝 {len(employees)} employees remaining to mark attendance")
    
    # Attendance form
    with st.form("attendance_form"):
        attendance_data = {}
        
        # Display employees in a more organized way
        st.write("**Select attendance status for each employee:**")
        
        for i, employee in enumerate(employees):
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.write(f"**{employee['full_name']}** ({employee['employee_id']})")
            
            with col2:
                status = st.radio(
                    f"Status", 
                    ['present', 'absent'],
                    index=0,  # Default to present
                    key=f"status_{employee['employee_id']}",
                    horizontal=True
                )
                attendance_data[employee['employee_id']] = status
            
            # Add separator line except for last employee
            if i < len(employees) - 1:
                st.divider()
        
        col1, col2 = st.columns([1, 4])
        with col1:
            submitted = st.form_submit_button("💾 Save Attendance", type="primary")
        with col2:
            if st.form_submit_button("🔄 Refresh List"):
                st.rerun()
        
        if submitted:
            if not attendance_data:
                st.error("No attendance data to save!")
                return
                
            records_inserted = 0
            errors = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, (emp_id, status) in enumerate(attendance_data.items()):
                try:
                    # Store as datetime for MongoDB compatibility  
                    record_data = {
                        "employee_id": emp_id,
                        "date": datetime.combine(attendance_date, datetime.min.time()),
                        "status": status,
                        "marked_by": st.session_state.user_data['username'],
                        "created_at": datetime.now()
                    }
                    
                    # Insert new record (since we're only showing unmarked employees)
                    db.attendance.insert_one(record_data)
                    records_inserted += 1
                    
                    # Update progress
                    progress = (i + 1) / len(attendance_data)
                    progress_bar.progress(progress)
                    status_text.text(f"Saving... {i + 1}/{len(attendance_data)}")
                    
                except Exception as e:
                    errors.append(f"Error saving attendance for {emp_id}: {str(e)}")
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Show results
            if errors:
                st.error("Some errors occurred:")
                for error in errors:
                    st.error(error)
            
            if records_inserted > 0:
                st.success(f"✅ Attendance saved successfully! {records_inserted} records added.")
                st.balloons()  # Celebration effect
                
                # Auto-refresh after successful save
                time.sleep(1)
                st.rerun()

# Helper function to format date for display
def format_date_for_display(date_obj):
    """Format date for better display"""
    return date_obj.strftime("%B %d, %Y (%A)")


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