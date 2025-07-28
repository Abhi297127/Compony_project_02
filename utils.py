import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import calendar
import base64
from io import BytesIO
from PIL import Image
import bcrypt

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def generate_employee_id():
    """Generate unique employee ID"""
    from db import get_database
    db = get_database()
    
    # Find the highest employee ID
    last_employee = db.employees.find().sort("employee_id", -1).limit(1)
    last_employee = list(last_employee)
    
    if last_employee:
        last_id = int(last_employee[0]['employee_id'].replace('EMP', ''))
        new_id = f"EMP{last_id + 1:04d}"
    else:
        new_id = "EMP0001"
    
    return new_id

def convert_image_to_base64(image):
    """Convert uploaded image to base64 string"""
    if image is not None:
        # Convert to PIL Image
        pil_image = Image.open(image)
        
        # Resize if too large (max 800x600)
        if pil_image.size[0] > 800 or pil_image.size[1] > 600:
            pil_image.thumbnail((800, 600), Image.Resampling.LANCZOS)
        
        # Convert to bytes
        buffer = BytesIO()
        pil_image.save(buffer, format='JPEG', quality=85)
        img_bytes = buffer.getvalue()
        
        # Convert to base64
        img_base64 = base64.b64encode(img_bytes).decode()
        return img_base64
    return None

def base64_to_image(base64_string):
    """Convert base64 string back to image"""
    if base64_string:
        img_bytes = base64.b64decode(base64_string)
        return Image.open(BytesIO(img_bytes))
    return None

def create_attendance_calendar(attendance_data, year, month):
    """Create calendar view for attendance"""
    # Get calendar matrix
    cal = calendar.monthcalendar(year, month)
    
    # Create DataFrame for calendar
    calendar_df = pd.DataFrame(cal)
    calendar_df = calendar_df.replace(0, '')
    
    # Create attendance status mapping
    attendance_dict = {}
    for record in attendance_data:
        day = record['date'].day
        attendance_dict[day] = record['status']
    
    # Create HTML calendar
    html_calendar = "<table class='calendar-table'>"
    html_calendar += "<tr><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th>Sat</th><th>Sun</th></tr>"
    
    for week in cal:
        html_calendar += "<tr>"
        for day in week:
            if day == 0:
                html_calendar += "<td></td>"
            else:
                status = attendance_dict.get(day, 'not_marked')
                css_class = {
                    'present': 'present-day',
                    'absent': 'absent-day',
                    'not_marked': 'not-marked-day'
                }.get(status, 'not-marked-day')
                
                html_calendar += f"<td class='{css_class}'>{day}</td>"
        html_calendar += "</tr>"
    
    html_calendar += "</table>"
    
    # Add CSS styles
    css = """
    <style>
    .calendar-table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }
    .calendar-table th, .calendar-table td {
        border: 1px solid #ddd;
        padding: 10px;
        text-align: center;
        width: 14.28%;
        height: 40px;
    }
    .calendar-table th {
        background-color: #f2f2f2;
        font-weight: bold;
    }
    .present-day {
        background-color: #d4edda !important;
        color: #155724;
        font-weight: bold;
    }
    .absent-day {
        background-color: #f8d7da !important;
        color: #721c24;
        font-weight: bold;
    }
    .not-marked-day {
        background-color: #fff3cd !important;
        color: #856404;
    }
    </style>
    """
    
    return css + html_calendar

def create_attendance_charts(attendance_data):
    """Create attendance visualization charts"""
    if not attendance_data:
        return None, None, None
    
    # Convert to DataFrame
    df = pd.DataFrame(attendance_data)
    df['date'] = pd.to_datetime(df['date'])
    
    # 1. Pie chart for overall attendance
    status_counts = df['status'].value_counts()
    pie_fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Overall Attendance Distribution",
        color_discrete_map={'present': '#28a745', 'absent': '#dc3545'}
    )
    
    # 2. Bar chart for monthly attendance
    df['month_year'] = df['date'].dt.to_period('M')
    monthly_stats = df.groupby(['month_year', 'status']).size().unstack(fill_value=0)
    
    bar_fig = go.Figure()
    if 'present' in monthly_stats.columns:
        bar_fig.add_trace(go.Bar(
            name='Present',
            x=monthly_stats.index.astype(str),
            y=monthly_stats['present'],
            marker_color='#28a745'
        ))
    if 'absent' in monthly_stats.columns:
        bar_fig.add_trace(go.Bar(
            name='Absent',
            x=monthly_stats.index.astype(str),
            y=monthly_stats['absent'],
            marker_color='#dc3545'
        ))
    
    bar_fig.update_layout(
        title='Monthly Attendance Comparison',
        xaxis_title='Month',
        yaxis_title='Days',
        barmode='group'
    )
    
    # 3. Line chart for attendance trend
    daily_stats = df.set_index('date').resample('D')['status'].apply(
        lambda x: 1 if 'present' in x.values else 0 if 'absent' in x.values else None
    ).dropna()
    
    line_fig = px.line(
        x=daily_stats.index,
        y=daily_stats.values,
        title="Daily Attendance Trend",
        labels={'x': 'Date', 'y': 'Present (1) / Absent (0)'}
    )
    line_fig.update_traces(line_color='#007bff', line_width=3)
    
    return pie_fig, bar_fig, line_fig

def validate_date_range(start_date, end_date):
    """Validate date range for queries"""
    if start_date > end_date:
        return False, "Start date cannot be after end date"
    
    if end_date > datetime.now().date():
        return False, "End date cannot be in the future"
    
    # Check if range is within 3 years
    three_years_ago = datetime.now().date() - timedelta(days=3*365)
    if start_date < three_years_ago:
        return False, "Date range cannot exceed 3 years from today"
    
    return True, "Valid date range"

def calculate_attendance_stats(attendance_data):
    """Calculate attendance statistics"""
    if not attendance_data:
        return {
            'total_days': 0,
            'present_days': 0,
            'absent_days': 0,
            'attendance_percentage': 0
        }
    
    total_days = len(attendance_data)
    present_days = sum(1 for record in attendance_data if record['status'] == 'present')
    absent_days = total_days - present_days
    
    attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
    
    return {
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'attendance_percentage': round(attendance_percentage, 2)
    }

def format_date_for_display(date_obj):
    """Format date for display"""
    if isinstance(date_obj, datetime):
        return date_obj.strftime("%B %d, %Y")
    elif isinstance(date_obj, str):
        try:
            parsed_date = datetime.strptime(date_obj, "%Y-%m-%d")
            return parsed_date.strftime("%B %d, %Y")
        except:
            return date_obj
    return str(date_obj)

def get_date_range_options():
    """Get predefined date range options"""
    today = datetime.now().date()
    
    return {
        "Today": (today, today),
        "This Week": (today - timedelta(days=today.weekday()), today),
        "This Month": (today.replace(day=1), today),
        "Last 30 Days": (today - timedelta(days=30), today),
        "Last 3 Months": (today - timedelta(days=90), today),
        "This Year": (today.replace(month=1, day=1), today)
    }