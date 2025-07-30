import base64
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
from db import get_database
from utils import (
    format_date_for_display, get_date_range_options,
    calculate_attendance_stats, create_attendance_charts,
    create_attendance_calendar, base64_to_image
)

# Cache database connection
@st.cache_resource
def get_cached_database():
    """Cached database connection"""
    return get_database()

def employee_dashboard():
    """Main employee dashboard"""
    st.title("👤 Employee Dashboard")
    st.markdown("---")
    
    # Welcome message
    employee_name = st.session_state.user_data.get('full_name', 'Employee')
    st.write(f"Welcome, **{employee_name}**!")
    
    # Sidebar navigation
    with st.sidebar:
        st.header("📋 Employee Menu")
        menu_option = st.selectbox(
            "Select Action",
            [
                "📊 Dashboard Overview",
                "📅 My Attendance", 
                "📸 View TBT Images",
                "📝 Request Attendance",
                "📈 My Analytics"
            ],
            key="employee_menu"
        )
    
    # Route to appropriate function
    if menu_option == "📊 Dashboard Overview":
        employee_overview()
    elif menu_option == "📅 My Attendance":
        my_attendance()
    elif menu_option == "📸 View TBT Images":
        view_tbt_images()
    elif menu_option == "📝 Request Attendance":
        request_attendance()
    elif menu_option == "📈 My Analytics":
        my_analytics()

def employee_overview():
    """Employee dashboard overview"""
    st.subheader("📊 Dashboard Overview")
    
    # Initialize session state for caching
    if 'overview_data' not in st.session_state:
        st.session_state.overview_data = None
        st.session_state.overview_last_update = None
    
    db = get_cached_database()
    employee_id = st.session_state.user_data['employee_id']
    
    # Check if we need to refresh data (cache for 5 minutes)
    current_time = datetime.now()
    should_refresh = (
        st.session_state.overview_last_update is None or
        (current_time - st.session_state.overview_last_update).total_seconds() > 300
    )
    
    if should_refresh:
        # Get current month stats
        today = datetime.now()
        first_day_month = today.replace(day=1)
        
        # Convert to datetime objects for MongoDB query
        start_datetime = datetime.combine(first_day_month.date(), datetime.min.time())
        end_datetime = datetime.combine(today.date(), datetime.max.time())
        
        # Monthly attendance stats
        monthly_records = list(db.attendance.find({
            "employee_id": employee_id,
            "date": {"$gte": start_datetime, "$lte": end_datetime}
        }))
        
        # Recent attendance
        recent_attendance = list(db.attendance.find({
            "employee_id": employee_id
        }).sort("date", -1).limit(7))
        
        # Pending requests
        pending_requests = db.attendance_requests.count_documents({
            "employee_id": employee_id,
            "status": "pending"
        })
        
        # Cache the data
        st.session_state.overview_data = {
            'monthly_records': monthly_records,
            'recent_attendance': recent_attendance,
            'pending_requests': pending_requests
        }
        st.session_state.overview_last_update = current_time
    
    # Use cached data
    data = st.session_state.overview_data
    stats = calculate_attendance_stats(data['monthly_records'])
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("This Month - Present", stats['present_days'])
    
    with col2:
        st.metric("This Month - Absent", stats['absent_days'])
    
    with col3:
        st.metric("Total Working Days", stats['total_days'])
    
    with col4:
        st.metric("Attendance Rate", f"{stats['attendance_percentage']}%")
    
    st.markdown("---")
    
    # Recent attendance
    st.subheader("📋 Recent Attendance")
    
    if data['recent_attendance']:
        for record in data['recent_attendance']:
            status_color = "🟢" if record["status"] == "present" else "🔴"
            # Handle both date and datetime objects for display
            if isinstance(record['date'], datetime):
                display_date = record['date'].date()
            else:
                display_date = record['date']
            st.write(f"{status_color} **{format_date_for_display(display_date)}** - {record['status'].title()}")
    else:
        st.info("No recent attendance records found.")
    
    # Pending requests
    st.subheader("📋 My Requests")
    
    if data['pending_requests'] > 0:
        st.warning(f"You have {data['pending_requests']} pending attendance request(s).")
    else:
        st.success("No pending requests.")

def my_attendance():
    """View personal attendance records"""
    st.subheader("📅 My Attendance")
    
    employee_id = st.session_state.user_data['employee_id']
    
    # View options
    tab1, tab2, tab3 = st.tabs(["📋 List View", "📅 Calendar View", "📊 Summary"])
    
    with tab1:
        show_attendance_list(employee_id)
    
    with tab2:
        show_attendance_calendar(employee_id)
    
    with tab3:
        show_attendance_summary(employee_id)

def show_attendance_list(employee_id):
    """Show attendance in list format"""
    st.write("### Attendance Records")
    
    # Initialize session state for this function
    if 'attendance_list_data' not in st.session_state:
        st.session_state.attendance_list_data = None
        st.session_state.attendance_list_params = None
    
    db = get_cached_database()
    
    # Date range selection
    date_range_option = st.selectbox(
        "Select Date Range", 
        list(get_date_range_options().keys()),
        key="attendance_date_range"
    )
    start_date, end_date = get_date_range_options()[date_range_option]
    
    # Custom date range option
    custom_range = st.checkbox("Custom Date Range", key="custom_range_attendance")
    if custom_range:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=start_date, key="start_date_attendance")
        with col2:
            end_date = st.date_input("End Date", value=end_date, key="end_date_attendance")
    
    # Create current parameters for comparison
    current_params = {
        'employee_id': employee_id,
        'start_date': start_date,
        'end_date': end_date,
        'custom_range': custom_range
    }
    
    # Only fetch data if parameters changed
    if st.session_state.attendance_list_params != current_params:
        # Convert date objects to datetime objects for MongoDB query
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Get attendance records
        attendance_records = list(db.attendance.find({
            "employee_id": employee_id,
            "date": {"$gte": start_datetime, "$lte": end_datetime}
        }).sort("date", -1))
        
        # Cache the data
        st.session_state.attendance_list_data = attendance_records
        st.session_state.attendance_list_params = current_params
    else:
        # Use cached data
        attendance_records = st.session_state.attendance_list_data
    
    if attendance_records:
        # Create DataFrame for display
        display_data = []
        for record in attendance_records:
            # Handle both date and datetime objects for display
            if isinstance(record['date'], datetime):
                display_date = record['date'].date()
            else:
                display_date = record['date']
            
            display_data.append({
                'Date': format_date_for_display(display_date),
                'Status': record['status'].title(),
                'Marked By': record.get('marked_by', 'System'),
                'Notes': record.get('note', '-')
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True)
        
        # Show statistics
        stats = calculate_attendance_stats(attendance_records)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Days", stats['total_days'])
        with col2:
            st.metric("Present", stats['present_days'])
        with col3:
            st.metric("Absent", stats['absent_days'])
        with col4:
            st.metric("Attendance %", f"{stats['attendance_percentage']}%")
    else:
        st.info("No attendance records found for the selected period.")


def show_attendance_calendar(employee_id):
    """Show attendance in calendar format"""
    st.write("### Calendar View")
    
    # Initialize session state for calendar
    if 'calendar_data' not in st.session_state:
        st.session_state.calendar_data = None
        st.session_state.calendar_params = None
    
    db = get_cached_database()
    
    # Month/Year selection
    col1, col2 = st.columns(2)
    with col1:
        cal_year = st.selectbox("Year", range(datetime.now().year - 2, datetime.now().year + 1), key="cal_year")
    with col2:
        cal_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1, key="cal_month")
    
    # Create current parameters
    current_params = {
        'employee_id': employee_id,
        'year': cal_year,
        'month': cal_month
    }
    
    # Only fetch data if parameters changed
    if st.session_state.calendar_params != current_params:
        # Get attendance data for the month
        start_date = datetime(cal_year, cal_month, 1)
        if cal_month == 12:
            end_date = datetime(cal_year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(cal_year, cal_month + 1, 1) - timedelta(seconds=1)
        
        # Debug: Print date range
        # st.write(f"**Debug:** Searching for attendance between {start_date} and {end_date}")
        
        attendance_records = list(db.attendance.find({
            "employee_id": employee_id,
            "date": {"$gte": start_date, "$lte": end_date}
        }))
        
        # Debug: Show raw attendance records
        # st.write(f"**Debug:** Found {len(attendance_records)} attendance records")
        # if attendance_records:
        #     st.write("**Sample records:**")
        #     for i, record in enumerate(attendance_records[:3]):  # Show first 3 records
        #         st.write(f"Record {i+1}: Date={record.get('date')}, Status={record.get('status')}, Type={type(record.get('date'))}")
        
        # Cache the data
        st.session_state.calendar_data = attendance_records
        st.session_state.calendar_params = current_params
    else:
        # Use cached data
        attendance_records = st.session_state.calendar_data
    
    # Create attendance dictionary for quick lookup
    attendance_dict = {}
    for record in attendance_records:
        try:
            # Handle both date and datetime objects
            if isinstance(record['date'], datetime):
                record_date = record['date'].date()
            elif isinstance(record['date'], str):
                # Handle string dates (parse them)
                try:
                    parsed_date = datetime.strptime(record['date'], '%Y-%m-%d').date()
                    record_date = parsed_date
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(record['date'], '%Y-%m-%d %H:%M:%S').date()
                        record_date = parsed_date
                    except ValueError:
                        st.error(f"Unable to parse date: {record['date']}")
                        continue
            else:
                record_date = record['date']
            
            # Ensure the date belongs to the selected month/year
            if record_date.year == cal_year and record_date.month == cal_month:
                day = record_date.day
                attendance_dict[day] = record['status']
                
        except Exception as e:
            st.error(f"Error processing record: {record} - Error: {str(e)}")
    
    # Debug: Show processed attendance dictionary
    # st.write(f"**Debug:** Processed attendance dictionary: {attendance_dict}")
    
    # Create and display calendar
    calendar_html = create_attendance_calendar_fixed(attendance_dict, cal_year, cal_month)
    st.components.v1.html(calendar_html, height=500)
    
    # Legend
    st.markdown("""
    **Legend:**
    - 🟢 Green: Present
    - 🔴 Red: Absent  
    - 🟡 Yellow: Not Marked
    """)


def create_attendance_calendar_fixed(attendance_dict, year, month):
    """Create HTML calendar with color-coded attendance"""
    import calendar
    
    # Get calendar for the month
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    # Define colors
    colors = {
        'present': '#4CAF50',    # Green
        'absent': '#F44336',     # Red
        'not_marked': '#FFC107'  # Yellow/Amber
    }
    
    # Start building HTML
    html = f"""
    <style>
        .calendar-container {{
            max-width: 800px;
            margin: 0 auto;
            font-family: Arial, sans-serif;
        }}
        .calendar-header {{
            text-align: center;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #333;
        }}
        .calendar-table {{
            width: 100%;
            border-collapse: collapse;
            border: 2px solid #ddd;
        }}
        .calendar-table th {{
            background-color: #f5f5f5;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border: 1px solid #ddd;
        }}
        .calendar-table td {{
            width: 14.28%;
            height: 60px;
            text-align: center;
            vertical-align: middle;
            border: 1px solid #ddd;
            position: relative;
            font-size: 16px;
            font-weight: bold;
        }}
        .day-present {{
            background-color: {colors['present']};
            color: white;
        }}
        .day-absent {{
            background-color: {colors['absent']};
            color: white;
        }}
        .day-not-marked {{
            background-color: {colors['not_marked']};
            color: black;
        }}
        .day-empty {{
            background-color: #f9f9f9;
            color: #ccc;
        }}
    </style>
    
    <div class="calendar-container">
        <div class="calendar-header">{month_name} {year}</div>
        <table class="calendar-table">
            <tr>
                <th>Mon</th>
                <th>Tue</th>
                <th>Wed</th>
                <th>Thu</th>
                <th>Fri</th>
                <th>Sat</th>
                <th>Sun</th>
            </tr>
    """
    
    # Add calendar rows
    for week in cal:
        html += "<tr>"
        for day in week:
            if day == 0:
                # Empty cell for days not in this month
                html += '<td class="day-empty"></td>'
            else:
                # Determine the class based on attendance status
                if day in attendance_dict:
                    status = attendance_dict[day]
                    if status == 'present':
                        css_class = 'day-present'
                    elif status == 'absent':
                        css_class = 'day-absent'
                    else:
                        css_class = 'day-not-marked'
                else:
                    css_class = 'day-not-marked'
                
                html += f'<td class="{css_class}">{day}</td>'
        html += "</tr>"
    
    html += """
        </table>
    </div>
    """
    
    return html

def show_attendance_summary(employee_id):
    """Show attendance summary and analytics"""
    st.write("### Attendance Summary")
    
    # Initialize session state for summary
    if 'summary_data' not in st.session_state:
        st.session_state.summary_data = None
        st.session_state.summary_params = None
    
    db = get_cached_database()
    
    # Time period selection
    period = st.selectbox("Select Period", ["Last 30 Days", "Last 3 Months", "Last 6 Months", "This Year"], key="summary_period")
    
    # Create current parameters
    current_params = {
        'employee_id': employee_id,
        'period': period
    }
    
    # Only fetch data if parameters changed
    if st.session_state.summary_params != current_params:
        today = datetime.now()
        if period == "Last 30 Days":
            start_date = today - timedelta(days=30)
        elif period == "Last 3 Months":
            start_date = today - timedelta(days=90)
        elif period == "Last 6 Months":
            start_date = today - timedelta(days=180)
        else:  # This Year
            start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Ensure end date is datetime
        end_date = datetime.combine(today.date(), datetime.max.time())
        
        # Get attendance records
        attendance_records = list(db.attendance.find({
            "employee_id": employee_id,
            "date": {"$gte": start_date, "$lte": end_date}
        }))
        
        # Cache the data
        st.session_state.summary_data = attendance_records
        st.session_state.summary_params = current_params
    else:
        # Use cached data
        attendance_records = st.session_state.summary_data
    
    if attendance_records:
        # Calculate stats
        stats = calculate_attendance_stats(attendance_records)
        
        # Display summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Working Days", stats['total_days'])
        with col2:
            st.metric("Days Present", stats['present_days'])
        with col3:
            st.metric("Attendance Rate", f"{stats['attendance_percentage']}%")
        
        # Monthly breakdown
        st.subheader("Monthly Breakdown")
        
        monthly_stats = {}
        for record in attendance_records:
            # Handle both date and datetime objects
            if isinstance(record['date'], datetime):
                record_date = record['date'].date()
            else:
                record_date = record['date']
            
            month_key = record_date.strftime('%Y-%m')
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {'present': 0, 'absent': 0, 'total': 0}
            
            monthly_stats[month_key]['total'] += 1
            if record['status'] == 'present':
                monthly_stats[month_key]['present'] += 1
            else:
                monthly_stats[month_key]['absent'] += 1
        
        # Display monthly stats
        for month, stats in sorted(monthly_stats.items()):
            attendance_rate = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
            st.write(f"**{month}**: {stats['present']}/{stats['total']} days ({attendance_rate:.1f}% attendance)")
    else:
        st.info("No attendance data found for the selected period.")

def view_tbt_images():
    """View Toolbox Talk images - Mobile Optimized"""
    st.subheader("📸 Toolbox Talk Images")
    
    # Initialize session state for TBT images
    if 'tbt_data' not in st.session_state:
        st.session_state.tbt_data = None
        st.session_state.tbt_params = None
    
    db = get_cached_database()
    
    # Mobile-friendly date selection with better layout
    col1, col2 = st.columns([3, 1])
    with col1:
        view_date = st.date_input("📅 Select Date", value=datetime.now().date(), key="tbt_date")
    with col2:
        if st.button("🔄 Refresh", help="Refresh images for selected date"):
            # Force refresh by clearing cache
            st.session_state.tbt_params = None
            st.rerun()
    
    # Create current parameters
    current_params = {
        'view_date': view_date
    }
    
    # Only fetch data if parameters changed
    if st.session_state.tbt_params != current_params:
        # Convert date to datetime for MongoDB query
        start_datetime = datetime.combine(view_date, datetime.min.time())
        end_datetime = datetime.combine(view_date, datetime.max.time())
        
        # Get images for the date
        images = list(db.attendance_images.find({
            "date": {"$gte": start_datetime, "$lte": end_datetime}
        }).sort("uploaded_at", 1))
        
        # Cache the data
        st.session_state.tbt_data = images
        st.session_state.tbt_params = current_params
    else:
        # Use cached data
        images = st.session_state.tbt_data
    
    # Helper function to create download link for mobile
    def create_download_link(image_data, filename, button_text, key):
        """Create a proper download link that works on mobile"""
        try:
            # Decode base64 image data
            image_bytes = base64.b64decode(image_data)
            
            # Create download button with proper MIME type
            st.download_button(
                label=button_text,
                data=image_bytes,
                file_name=filename,
                mime="image/jpeg",  # Adjust based on your image format
                key=key,
                help="Download image to your device"
            )
        except Exception as e:
            st.error(f"Error creating download link: {str(e)}")
    

    
    if images:
        st.success(f"📊 **{len(images)} TBT Image(s) found for {format_date_for_display(view_date)}**")
        
        # Mobile-optimized image grid
        for i, img_record in enumerate(images, 1):
            # Create unique identifier for each image
            unique_id = str(img_record.get('_id', f"img_{i}_{int(datetime.now().timestamp())}"))[:-6]
            
            with st.container():
                # Mobile layout with image, info, and download
                col1, col2, col3 = st.columns([2, 3, 2])
                
                with col1:
                    # Image thumbnail
                    image = base64_to_image(img_record['image_data'])
                    if image:
                        st.image(image, width=120, caption=f"TBT {i}")
                
                with col2:
                    # User and time info
                    st.write(f"**👤 {img_record['uploaded_by']}**")
                    st.write(f"**⏰ {img_record['uploaded_at'].strftime('%H:%M:%S')}**")
                    st.write(f"📁 {img_record['filename'][:25]}{'...' if len(img_record['filename']) > 25 else ''}")
                
                with col3:
                    # Download button
                    create_download_link(
                        img_record['image_data'],
                        img_record['filename'],
                        "📥 Download",
                        f"download_{unique_id}"
                    )
                
                st.divider()
    else:
        st.info("📭 No TBT images found for the selected date.")
        st.write("💡 **Tip:** Try selecting a different date or check if images were uploaded correctly.")
    
    # # Recent images section - Mobile optimized
    # st.subheader("📋 Recent TBT Images")
    
    # current_time = datetime.now()
    # should_refresh_recent = (
    #     st.session_state.recent_tbt_last_update is None or
    #     (current_time - st.session_state.recent_tbt_last_update).total_seconds() > 300
    # )
    
    # if should_refresh_recent:
    #     recent_images = list(db.attendance_images.find().sort("date", -1).limit(5))
    #     st.session_state.recent_tbt_data = recent_images
    #     st.session_state.recent_tbt_last_update = current_time
    # else:
    #     recent_images = st.session_state.recent_tbt_data
    
    # if recent_images:
    #     # Mobile-friendly recent images layout
    #     for idx, img_record in enumerate(recent_images):
    #         # Create unique identifier for recent images
    #         recent_unique_id = f"recent_{str(img_record.get('_id', f'rec_{idx}'))[-8:]}"
            
    #         with st.container():
    #             col1, col2, col3 = st.columns([2, 3, 2])
                
    #             with col1:
    #                 # Small thumbnail
    #                 image = base64_to_image(img_record['image_data'])
    #                 if image:
    #                     st.image(image, width=80)
                
    #             with col2:
    #                 # Handle both date and datetime objects for display
    #                 if isinstance(img_record['date'], datetime):
    #                     display_date = img_record['date'].date()
    #                 else:
    #                     display_date = img_record['date']
                    
    #                 st.write(f"**📅 {format_date_for_display(display_date)}**")
    #                 st.write(f"**👤 {img_record['uploaded_by']}**")
    #                 st.write(f"**⏰ {img_record['uploaded_at'].strftime('%H:%M:%S')}**")
                
    #             with col3:
    #                 # Download button
    #                 create_download_link(
    #                     img_record['image_data'],
    #                     img_record['filename'],
    #                     "📥 Download",
    #                     f"quick_download_{recent_unique_id}"
    #                 )
                
    #             st.divider()
    # else:
        st.info("📭 No recent TBT images found.")
    


def request_attendance():
    """Request attendance correction"""
    st.subheader("📝 Request Attendance Correction")
    
    employee_id = st.session_state.user_data['employee_id']
    
    tab1, tab2 = st.tabs(["✉️ New Request", "📋 My Requests"])
    
    with tab1:
        submit_new_request(employee_id)
    
    with tab2:
        view_my_requests(employee_id)

def submit_new_request(employee_id):
    """Submit new attendance request"""
    st.write("### Submit New Request")
    
    db = get_cached_database()
    
    st.info("Use this form to request attendance correction for days you were present but marked absent.")
    
    with st.form("attendance_request_form"):
        request_date = st.date_input(
            "Select Date*", 
            value=datetime.now().date() - timedelta(days=1),
            max_value=datetime.now().date() - timedelta(days=1)
        )
        
        # Convert date to datetime range for MongoDB query
        start_datetime = datetime.combine(request_date, datetime.min.time())
        end_datetime = datetime.combine(request_date, datetime.max.time())
        
        # Check current status for the date
        current_record = db.attendance.find_one({
            "employee_id": employee_id,
            "date": {"$gte": start_datetime, "$lte": end_datetime}
        })
        
        if current_record:
            st.write(f"**Current Status:** {current_record['status'].title()}")
            if current_record['status'] == 'present':
                st.warning("You are already marked present for this date!")
        else:
            st.write("**Current Status:** Not marked")
        
        # Check if request already exists
        existing_request = db.attendance_requests.find_one({
            "employee_id": employee_id,
            "date": {"$gte": start_datetime, "$lte": end_datetime},
            "status": {"$in": ["pending", "approved"]}
        })
        
        if existing_request:
            st.error(f"You already have a {existing_request['status']} request for this date!")
            
        reason = st.text_area(
            "Reason for Request*",
            placeholder="Please explain why you should be marked present for this date...",
            height=100
        )
        
        submitted = st.form_submit_button("Submit Request")
        
        if submitted:
            if not reason.strip():
                st.error("Please provide a reason for your request!")
            elif existing_request:
                st.error("Request already exists for this date!")
            elif current_record and current_record['status'] == 'present':
                st.error("You are already marked present for this date!")
            else:
                try:
                    # Create request
                    request_data = {
                        "employee_id": employee_id,
                        "date": datetime.combine(request_date, datetime.min.time()),
                        "message": reason.strip(),
                        "status": "pending",
                        "created_at": datetime.now()
                    }
                    
                    db.attendance_requests.insert_one(request_data)
                    st.success("Request submitted successfully! Admin will review it shortly.")
                    # Clear cache to refresh data
                    if 'my_requests_data' in st.session_state:
                        del st.session_state.my_requests_data
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error submitting request: {e}")

def view_my_requests(employee_id):
    """View personal attendance requests"""
    st.write("### My Attendance Requests")
    
    # Initialize session state for requests
    if 'my_requests_data' not in st.session_state:
        st.session_state.my_requests_data = None
        st.session_state.my_requests_last_update = None
    
    db = get_cached_database()
    
    # Check if we need to refresh (cache for 2 minutes)
    current_time = datetime.now()
    should_refresh = (
        st.session_state.my_requests_last_update is None or
        (current_time - st.session_state.my_requests_last_update).total_seconds() > 120
    )
    
    if should_refresh:
        # Get all requests
        all_requests = list(db.attendance_requests.find({
            "employee_id": employee_id
        }).sort("created_at", -1))
        
        st.session_state.my_requests_data = all_requests
        st.session_state.my_requests_last_update = current_time
    else:
        all_requests = st.session_state.my_requests_data
    
    if all_requests:
        for req in all_requests:
            status_color = {
                'pending': '🟡',
                'approved': '🟢', 
                'rejected': '🔴'
            }.get(req['status'], '⚪')
            
            # Handle both date and datetime objects for display
            if isinstance(req['date'], datetime):
                display_date = req['date'].date()
            else:
                display_date = req['date']
            
            with st.expander(f"{status_color} {format_date_for_display(display_date)} - {req['status'].title()}"):
                st.write(f"**Date:** {format_date_for_display(display_date)}")
                st.write(f"**Status:** {req['status'].title()}")
                st.write(f"**Request:** {req['message']}")
                st.write(f"**Submitted:** {req['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                if req['status'] != 'pending':
                    st.write(f"**Resolved by:** {req.get('resolved_by', 'Admin')}")
                    if 'updated_at' in req:
                        st.write(f"**Resolved on:** {req['updated_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Show current attendance status
                if isinstance(req['date'], datetime):
                    query_date = req['date']
                    start_datetime = query_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_datetime = query_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                else:
                    start_datetime = datetime.combine(req['date'], datetime.min.time())
                    end_datetime = datetime.combine(req['date'], datetime.max.time())
                
                current_record = db.attendance.find_one({
                    "employee_id": employee_id,
                    "date": {"$gte": start_datetime, "$lte": end_datetime}
                })
                
                if current_record:
                    st.write(f"**Current Attendance:** {current_record['status'].title()}")
                else:
                    st.write("**Current Attendance:** Not marked")
    else:
        st.info("No attendance requests found.")

def my_analytics():
    """Show personal analytics"""
    st.subheader("📈 My Analytics")
    
    # Initialize session state for analytics
    if 'analytics_data' not in st.session_state:
        st.session_state.analytics_data = None
        st.session_state.analytics_params = None
    
    db = get_cached_database()
    employee_id = st.session_state.user_data['employee_id']
    
    # Time period selection
    period = st.selectbox("Select Period", ["Last 3 Months", "Last 6 Months", "This Year", "All Time"], key="analytics_period")
    
    # Create current parameters
    current_params = {
        'employee_id': employee_id,
        'period': period
    }
    
    # Only fetch data if parameters changed
    if st.session_state.analytics_params != current_params:
        today = datetime.now()
        if period == "Last 3 Months":
            start_date = today - timedelta(days=90)
        elif period == "Last 6 Months":
            start_date = today - timedelta(days=180)
        elif period == "This Year":
            start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # All Time
            start_date = datetime(2020, 1, 1)
        
        # Ensure end date is datetime
        end_date = datetime.combine(today.date(), datetime.max.time())
        
        # Get attendance records
        attendance_records = list(db.attendance.find({
            "employee_id": employee_id,
            "date": {"$gte": start_date, "$lte": end_date}
        }))
        
        # Cache the data
        st.session_state.analytics_data = attendance_records
        st.session_state.analytics_params = current_params
    else:
        # Use cached data
        attendance_records = st.session_state.analytics_data
    
    if attendance_records:
        # Create charts
        try:
            pie_fig, bar_fig, line_fig = create_attendance_charts(attendance_records)
            
            if pie_fig and bar_fig and line_fig:
                # Display charts
                col1, col2 = st.columns(2)
                
                with col1:
                    st.plotly_chart(pie_fig, use_container_width=True)
                
                with col2:
                    # Show attendance trends
                    stats = calculate_attendance_stats(attendance_records)
                    
                    st.metric("Total Working Days", stats['total_days'])
                    st.metric("Days Present", stats['present_days'])
                    st.metric("Days Absent", stats['absent_days'])
                    st.metric("Overall Attendance Rate", f"{stats['attendance_percentage']}%")
                
                # Monthly trend
                st.plotly_chart(bar_fig, use_container_width=True)
                
                # Daily trend (for recent data)
                if period in ["Last 3 Months", "Last 6 Months"]:
                    st.plotly_chart(line_fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error generating charts: {e}")
            # Show basic stats without charts
            stats = calculate_attendance_stats(attendance_records)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Working Days", stats['total_days'])
            with col2:
                st.metric("Days Present", stats['present_days'])
            with col3:
                st.metric("Days Absent", stats['absent_days'])
            with col4:
                st.metric("Overall Attendance Rate", f"{stats['attendance_percentage']}%")
        
        # Attendance patterns
        st.subheader("📊 Attendance Patterns")
        
        # Day of week analysis
        try:
            df = pd.DataFrame(attendance_records)
            # Handle both date and datetime objects in the date column
            if 'date' in df.columns and not df.empty:
                # Convert all dates to datetime for consistent processing
                df['date'] = pd.to_datetime(df['date'])
                df['day_of_week'] = df['date'].dt.day_name()
                
                day_stats = df.groupby(['day_of_week', 'status']).size().unstack(fill_value=0)
                
                if not day_stats.empty:
                    st.write("**Attendance by Day of Week:**")
                    
                    # Calculate attendance rate by day
                    day_rates = {}
                    for day in day_stats.index:
                        total = day_stats.loc[day].sum()
                        present = day_stats.loc[day].get('present', 0)
                        rate = (present / total * 100) if total > 0 else 0
                        day_rates[day] = rate
                    
                    # Display day-wise rates
                    for day, rate in day_rates.items():
                        st.write(f"**{day}:** {rate:.1f}% attendance")
                # Monthly comparison
                st.subheader("📅 Monthly Comparison")
                
                monthly_stats = df.groupby([df['date'].dt.to_period('M'), 'status']).size().unstack(fill_value=0)
                
                if not monthly_stats.empty:
                    for month in monthly_stats.index:
                        total = monthly_stats.loc[month].sum()
                        present = monthly_stats.loc[month].get('present', 0)
                        rate = (present / total * 100) if total > 0 else 0
                        st.write(f"**{month}:** {present}/{total} days ({rate:.1f}% attendance)")
        except Exception as e:
            st.error(f"Error analyzing attendance patterns: {e}")
    else:
        st.info("No attendance data found for the selected period.")
        st.write("Once you have attendance records, you'll see detailed analytics here including:")
        st.write("- 📊 Attendance distribution charts")
        st.write("- 📈 Monthly trends")
        st.write("- 📅 Day-wise patterns")
        st.write("- 🎯 Performance metrics")

# Additional helper function to clear all cache
def clear_employee_cache():
    """Clear all cached employee data"""
    cache_keys = [
        'overview_data', 'overview_last_update',
        'attendance_list_data', 'attendance_list_params',
        'calendar_data', 'calendar_params',
        'summary_data', 'summary_params',
        'tbt_data', 'tbt_params', 'recent_tbt_data', 'recent_tbt_last_update',
        'my_requests_data', 'my_requests_last_update',
        'analytics_data', 'analytics_params'
    ]
    
    for key in cache_keys:
        if key in st.session_state:
            del st.session_state[key]