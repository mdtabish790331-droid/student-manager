import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import plotly.express as px
import base64
import io
import requests
from PIL import Image
import hashlib
import os

# ========== ROBUST DATABASE SETUP & REPAIR ==========
def get_db_connection():
    """Get database connection"""
    return sqlite3.connect('student_data.db', check_same_thread=False)

def init_database():
    """Initialize database with all required tables and repair existing ones"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Users table - always create fresh as it's the base
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Define all tables with their schemas
    tables_schema = {
        'students': '''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                photo TEXT,
                email TEXT,
                phone TEXT,
                target_study_hours INTEGER DEFAULT 6,
                wakeup_time TEXT DEFAULT '07:00',
                bedtime TEXT DEFAULT '23:00',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
        'subjects': '''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject_name TEXT NOT NULL,
                weightage FLOAT DEFAULT 1.0,
                target_total_hours FLOAT DEFAULT 100.0,
                daily_lecture_hours FLOAT DEFAULT 2.0,
                daily_question_hours FLOAT DEFAULT 1.0,
                difficulty TEXT DEFAULT 'Medium',
                target_completion_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
        'exercises': '''
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exercise_type TEXT NOT NULL,
                day_of_week TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 30,
                intensity TEXT DEFAULT 'Moderate',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
        'daily_progress': '''
            CREATE TABLE IF NOT EXISTS daily_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject_id INTEGER,
                date DATE NOT NULL,
                lecture_hours_actual FLOAT DEFAULT 0.0,
                question_hours_actual FLOAT DEFAULT 0.0,
                questions_solved INTEGER DEFAULT 0,
                exercise_done BOOLEAN DEFAULT 0,
                exercise_minutes INTEGER DEFAULT 0,
                mood TEXT DEFAULT '🙂 Good',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, subject_id, date)
            )
        ''',
        'study_schedule': '''
            CREATE TABLE IF NOT EXISTS study_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                day_of_week TEXT NOT NULL,
                subject_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                session_type TEXT,
                priority INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
    }
    
    # Create all tables
    for table_name, create_sql in tables_schema.items():
        c.execute(create_sql)
    
    conn.commit()
    conn.close()

def repair_database():
    """Repair missing columns in existing tables"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # List of tables and their required columns with SQL type
    tables_to_repair = {
        'students': [
            ('user_id', 'INTEGER DEFAULT 1'),
            ('target_study_hours', 'INTEGER DEFAULT 6'),
            ('wakeup_time', 'TEXT DEFAULT "07:00"'),
            ('bedtime', 'TEXT DEFAULT "23:00"'),
            ('photo', 'TEXT'),
            ('email', 'TEXT'),
            ('phone', 'TEXT')
        ],
        'subjects': [
            ('user_id', 'INTEGER DEFAULT 1'),
            ('weightage', 'FLOAT DEFAULT 1.0'),
            ('target_total_hours', 'FLOAT DEFAULT 100.0'),
            ('daily_lecture_hours', 'FLOAT DEFAULT 2.0'),
            ('daily_question_hours', 'FLOAT DEFAULT 1.0'),
            ('difficulty', 'TEXT DEFAULT "Medium"'),
            ('target_completion_date', 'DATE'),
            ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ],
        'exercises': [
            ('user_id', 'INTEGER DEFAULT 1'),
            ('duration_minutes', 'INTEGER DEFAULT 30'),
            ('intensity', 'TEXT DEFAULT "Moderate"'),
            ('notes', 'TEXT'),
            ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ],
        'daily_progress': [
            ('user_id', 'INTEGER DEFAULT 1'),
            ('mood', 'TEXT DEFAULT "🙂 Good"'),
            ('notes', 'TEXT'),
            ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ],
        'study_schedule': [
            ('user_id', 'INTEGER DEFAULT 1'),
            ('priority', 'INTEGER DEFAULT 1'),
            ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ]
    }
    
    repairs_made = []
    
    for table_name, columns in tables_to_repair.items():
        # Check if table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not c.fetchone():
            continue  # Table doesn't exist, will be created by init_database
            
        # Get existing columns
        c.execute(f"PRAGMA table_info({table_name})")
        existing_columns = [col[1] for col in c.fetchall()]
        
        # Add missing columns
        for column_name, column_type in columns:
            if column_name not in existing_columns:
                try:
                    c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    repairs_made.append(f"Added {column_name} to {table_name}")
                except sqlite3.OperationalError as e:
                    # Column might already exist or other error
                    pass
    
    conn.commit()
    conn.close()
    
    if repairs_made:
        st.sidebar.info(f"Database repairs made: {len(repairs_made)} fixes applied")
        for repair in repairs_made:
            st.sidebar.text(f"• {repair}")

# Initialize and repair database
if 'db_initialized' not in st.session_state:
    init_database()
    repair_database()
    st.session_state.db_initialized = True

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="AI Student Manager Pro",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== CSS STYLING ==========
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #374151;
        border-bottom: 2px solid #E5E7EB;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
    }
    .profile-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
    }
    .subject-card {
        background: #F3F4F6;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #3B82F6;
    }
    .exercise-card {
        background: #ECFDF5;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #10B981;
    }
    .progress-card {
        background: #FEF3C7;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #F59E0B;
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: bold;
        margin: 0.25rem;
    }
    .day-header {
        background: #DBEAFE;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        font-weight: bold;
        color: #1E3A8A;
    }
    .schedule-card {
        background: #F0F9FF;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 5px solid #0EA5E9;
    }
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# ========== SESSION STATE ==========
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'current_user_id' not in st.session_state:
    st.session_state.current_user_id = None
if 'current_student_id' not in st.session_state:
    st.session_state.current_student_id = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Login"
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = date.today()
if 'form_submitted' not in st.session_state:
    st.session_state.form_submitted = False
if 'daily_entry_date' not in st.session_state:
    st.session_state.daily_entry_date = date.today()
if 'report_date' not in st.session_state:
    st.session_state.report_date = date.today()
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'need_clear_form' not in st.session_state:
    st.session_state.need_clear_form = False
if 'show_success_message' not in st.session_state:
    st.session_state.show_success_message = False
if 'success_message' not in st.session_state:
    st.session_state.success_message = ""
if 'form_reset_key' not in st.session_state:
    st.session_state.form_reset_key = 0

# ========== HELPER FUNCTIONS ==========
def hash_password(password):
    """Hash a password for storing."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    return stored_password == hash_password(provided_password)

def image_to_base64(image_file):
    """Convert image to base64 string"""
    if image_file:
        try:
            image_bytes = image_file.read()
            return base64.b64encode(image_bytes).decode('utf-8')
        except Exception as e:
            st.error(f"Error converting image: {e}")
            return None
    return None

def get_student_photo(user_id):
    """Get student photo from database"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT photo FROM students WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        return result[0]
    return None

def calculate_subject_progress(user_id, subject_id):
    """Calculate progress for a subject"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT target_total_hours, daily_lecture_hours, daily_question_hours 
        FROM subjects WHERE id = ? AND user_id = ?
    ''', (subject_id, user_id))
    subject = c.fetchone()
    
    if not subject:
        return 0, 0, 0
    
    target_total_hours, target_lecture_daily, target_question_daily = subject
    
    c.execute('''
        SELECT SUM(lecture_hours_actual), SUM(question_hours_actual), SUM(questions_solved)
        FROM daily_progress 
        WHERE user_id = ? AND subject_id = ?
    ''', (user_id, subject_id))
    
    actual = c.fetchone()
    conn.close()
    
    total_lecture_hours = actual[0] or 0
    total_question_hours = actual[1] or 0
    total_questions = actual[2] or 0
    
    lecture_progress = (total_lecture_hours / target_total_hours * 100) if target_total_hours > 0 else 0
    question_progress = (total_question_hours / target_total_hours * 100) if target_total_hours > 0 else 0
    
    return min(lecture_progress, 100), min(question_progress, 100), total_questions

def get_daily_report(user_id, report_date):
    """Get daily report for a student"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT id, subject_name, daily_lecture_hours, daily_question_hours
        FROM subjects 
        WHERE user_id = ?
        ORDER BY weightage DESC, subject_name
    ''', (user_id,))
    
    subjects = c.fetchall()
    
    if not subjects:
        conn.close()
        return {
            'subjects': [],
            'exercises': [],
            'totals': {
                'lecture_target': 0,
                'question_target': 0,
                'lecture_actual': 0,
                'question_actual': 0,
                'questions': 0
            }
        }
    
    subjects_progress = []
    for subject in subjects:
        sub_id, sub_name, daily_lecture, daily_question = subject
        
        c.execute('''
            SELECT lecture_hours_actual, question_hours_actual, questions_solved,
                   exercise_done, exercise_minutes, mood, notes
            FROM daily_progress 
            WHERE user_id = ? AND subject_id = ? AND date = ?
        ''', (user_id, sub_id, report_date))
        
        progress = c.fetchone()
        
        if progress:
            lecture_actual, question_actual, questions_solved, exercise_done, exercise_minutes, mood, notes = progress
        else:
            lecture_actual = question_actual = questions_solved = exercise_done = exercise_minutes = mood = notes = None
        
        subjects_progress.append((
            sub_id, sub_name, daily_lecture, daily_question,
            lecture_actual, question_actual, questions_solved,
            exercise_done, exercise_minutes, mood, notes
        ))
    
    day_name = report_date.strftime('%A')
    c.execute('''
        SELECT exercise_type, duration_minutes, intensity, notes
        FROM exercises 
        WHERE user_id = ? AND day_of_week = ?
    ''', (user_id, day_name))
    
    exercises = c.fetchall()
    
    total_lecture_target = sum([s[2] for s in subjects_progress])
    total_question_target = sum([s[3] for s in subjects_progress])
    total_lecture_actual = sum([s[4] or 0 for s in subjects_progress if s[4] is not None])
    total_question_actual = sum([s[5] or 0 for s in subjects_progress if s[5] is not None])
    total_questions = sum([s[6] or 0 for s in subjects_progress if s[6] is not None])
    
    conn.close()
    
    return {
        'subjects': subjects_progress,
        'exercises': exercises,
        'totals': {
            'lecture_target': total_lecture_target,
            'question_target': total_question_target,
            'lecture_actual': total_lecture_actual,
            'question_actual': total_question_actual,
            'questions': total_questions
        }
    }

def get_weekly_analysis(user_id, start_date, end_date):
    """Get weekly analysis data"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT date, 
               SUM(COALESCE(lecture_hours_actual, 0)) as total_lecture,
               SUM(COALESCE(question_hours_actual, 0)) as total_question,
               SUM(COALESCE(questions_solved, 0)) as total_questions,
               COUNT(DISTINCT subject_id) as subjects_studied
        FROM daily_progress 
        WHERE user_id = ? AND date BETWEEN ? AND ?
        GROUP BY date
        ORDER BY date
    ''', (user_id, start_date, end_date))
    
    daily_data = c.fetchall()
    
    exercise_data = []
    current_date = start_date
    while current_date <= end_date:
        c.execute('''
            SELECT COUNT(*), SUM(COALESCE(exercise_minutes, 0))
            FROM daily_progress 
            WHERE user_id = ? AND date = ? AND exercise_done = 1
        ''', (user_id, current_date))
        ex_result = c.fetchone()
        exercise_count = ex_result[0] or 0
        exercise_minutes = ex_result[1] or 0
        exercise_data.append((exercise_count > 0, exercise_minutes))
        current_date += timedelta(days=1)
    
    c.execute('''
        SELECT s.subject_name,
               COALESCE(SUM(dp.lecture_hours_actual), 0) as total_lecture,
               COALESCE(SUM(dp.question_hours_actual), 0) as total_question,
               COALESCE(SUM(dp.questions_solved), 0) as total_questions,
               COUNT(DISTINCT dp.date) as days_studied
        FROM subjects s
        LEFT JOIN daily_progress dp ON s.id = dp.subject_id 
            AND dp.date BETWEEN ? AND ? AND dp.user_id = ?
        WHERE s.user_id = ?
        GROUP BY s.id, s.subject_name
        ORDER BY total_lecture + total_question DESC
    ''', (start_date, end_date, user_id, user_id))
    
    subject_data = c.fetchall()
    
    conn.close()
    
    daily_data_with_exercise = []
    for i, day in enumerate(daily_data):
        if i < len(exercise_data):
            exercise_rate = 1.0 if exercise_data[i][0] else 0.0
            daily_data_with_exercise.append(day + (exercise_rate,))
        else:
            daily_data_with_exercise.append(day + (0.0,))
    
    return daily_data_with_exercise, subject_data

def get_gemini_response(prompt, user_subjects):
    """Get response from Gemini API"""
    try:
        api_key = "AIzaSyBi73WCQ80No8qy-sLSj_qfvztEtchoUM8"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        
        context = f"""
        You are an AI Study Assistant for a student learning the following subjects: {', '.join(user_subjects)}.
        
        Student's question: {prompt}
        
        Please provide helpful, practical study advice. Keep the response concise but informative.
        """
        
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{
                "parts": [{
                    "text": context
                }]
            }]
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                return "Sorry, I couldn't generate a response. Please try again."
        else:
            return f"Error: {response.status_code}. Please check your API key or try again later."
            
    except Exception as e:
        return f"Error connecting to Gemini API: {str(e)}"

def get_study_schedule(user_id):
    """Get study schedule for the student"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT ss.day_of_week, s.subject_name, ss.start_time, ss.end_time, ss.session_type, ss.priority
        FROM study_schedule ss
        JOIN subjects s ON ss.subject_id = s.id
        WHERE ss.user_id = ?
        ORDER BY 
            CASE ss.day_of_week 
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            ss.priority,
            ss.start_time
    ''', (user_id,))
    
    schedule = c.fetchall()
    conn.close()
    
    return schedule

def get_existing_progress_data(user_id, subject_id, entry_date):
    """Get existing progress data for a specific date"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT lecture_hours_actual, question_hours_actual, questions_solved,
               exercise_done, exercise_minutes, mood, notes
        FROM daily_progress 
        WHERE user_id = ? AND subject_id = ? AND date = ?
    ''', (user_id, subject_id, entry_date))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'lecture_hours': result[0] or 0,
            'question_hours': result[1] or 0,
            'questions_solved': result[2] or 0,
            'exercise_done': result[3] or False,
            'exercise_minutes': result[4] or 0,
            'mood': result[5] or "🙂 Good",
            'notes': result[6] or ""
        }
    return None

def check_user_profile_exists(user_id):
    """Check if user has created a profile"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM students WHERE user_id = ?", (user_id,))
    exists = c.fetchone()[0] > 0
    conn.close()
    return exists

def check_user_subjects_exist(user_id):
    """Check if user has added subjects"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM subjects WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def check_user_exercises_exist(user_id):
    """Check if user has added exercises"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM exercises WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def get_user_profile(user_id):
    """Get user profile data"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, name, photo, email, phone, target_study_hours, 
               wakeup_time, bedtime
        FROM students WHERE user_id = ?
    ''', (user_id,))
    
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'student_id': result[0],
            'name': result[1],
            'photo': result[2],
            'email': result[3],
            'phone': result[4],
            'target_study_hours': result[5],
            'wakeup_time': result[6],
            'bedtime': result[7]
        }
    return None

# ========== AUTHENTICATION FUNCTIONS ==========
def register_user(username, password, name, email, phone):
    """Register a new user"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if username already exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone():
            conn.close()
            return False, "Username already exists"
        
        # Hash password and insert user
        hashed_password = hash_password(password)
        c.execute('''
            INSERT INTO users (username, password, name, email, phone)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, hashed_password, name, email, phone))
        
        user_id = c.lastrowid
        
        # Create student profile with all required columns
        c.execute('''
            INSERT INTO students (user_id, name, email, phone, target_study_hours, wakeup_time, bedtime)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, email, phone, 6, '07:00', '23:00'))
        
        conn.commit()
        conn.close()
        
        return True, "Registration successful"
    except Exception as e:
        return False, f"Registration failed: {str(e)}"

def login_user(username, password):
    """Login existing user"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("SELECT id, password, name FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return False, "Invalid username or password"
        
        user_id, stored_password, name = user
        
        if verify_password(stored_password, password):
            # Get student ID
            c.execute("SELECT id FROM students WHERE user_id = ?", (user_id,))
            student_result = c.fetchone()
            student_id = student_result[0] if student_result else None
            
            conn.close()
            
            return True, {
                'user_id': user_id,
                'student_id': student_id,
                'username': username,
                'name': name
            }
        else:
            conn.close()
            return False, "Invalid username or password"
            
    except Exception as e:
        return False, f"Login failed: {str(e)}"

# ========== MAIN APP ==========
if not st.session_state.logged_in:
    # ========== LOGIN PAGE ==========
    st.markdown('<h1 class="main-header">🎓 AI Student Manager Pro</h1>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    with tab1:
        with st.form("login_form", clear_on_submit=True):
            st.write("### Login to Your Account")
            
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            login_submitted = st.form_submit_button("Login")
            
            if login_submitted:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    success, result = login_user(username, password)
                    
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.current_user = result['username']
                        st.session_state.current_user_id = result['user_id']
                        st.session_state.current_student_id = result['student_id']
                        st.session_state.current_page = "🏠 Dashboard"
                        
                        # Check if user has completed setup
                        if not check_user_profile_exists(result['user_id']):
                            st.session_state.current_page = "👤 Complete Profile"
                        
                        st.success(f"Welcome back, {result['name']}!")
                        st.rerun()
                    else:
                        st.error(result)
    
    with tab2:
        # Use a unique key for the form that changes when we want to reset
        form_key = f"register_form_{st.session_state.form_reset_key}"
        
        with st.form(form_key, clear_on_submit=True):
            st.write("### Create New Account")
            
            col1, col2 = st.columns(2)
            
            with col1:
                reg_username = st.text_input("Username*", placeholder="Choose a username", key="reg_username")
                reg_name = st.text_input("Full Name*", placeholder="Your full name", key="reg_name")
            
            with col2:
                reg_password = st.text_input("Password*", type="password", placeholder="Create a password", key="reg_password")
                confirm_password = st.text_input("Confirm Password*", type="password", placeholder="Confirm password", key="confirm_password")
            
            reg_email = st.text_input("Email Address", placeholder="your.email@example.com", key="reg_email")
            reg_phone = st.text_input("Phone Number", placeholder="+91 9876543210", key="reg_phone")
            
            register_submitted = st.form_submit_button("Register")
            
            if register_submitted:
                if not reg_username or not reg_password or not reg_name:
                    st.error("Please fill all required fields (*)")
                elif reg_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters long")
                else:
                    success, message = register_user(reg_username, reg_password, reg_name, reg_email, reg_phone)
                    
                    if success:
                        st.success("Registration successful! Please login.")
                        # Increment the form reset key to force a new form instance
                        st.session_state.form_reset_key += 1
                        st.rerun()
                    else:
                        st.error(message)
    
    st.stop()

# ========== LOGGED IN USER INTERFACE ==========
st.markdown('<h1 class="main-header">🎓 AI Student Manager Pro</h1>', unsafe_allow_html=True)

# ========== SIDEBAR ==========
with st.sidebar:
    if st.session_state.current_user_id:
        photo_data = get_student_photo(st.session_state.current_user_id)
        if photo_data:
            try:
                photo_bytes = base64.b64decode(photo_data)
                image = Image.open(io.BytesIO(photo_bytes))
                st.image(image, width=120, caption=st.session_state.current_user)
            except Exception as e:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=120, caption=st.session_state.current_user)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=120, caption=st.session_state.current_user)
        
        st.markdown(f"**Welcome, {st.session_state.current_user}**")
        st.markdown("---")
        
        # Date selector for reports
        selected_date = st.date_input(
            "📅 Select Date for Report",
            value=st.session_state.selected_date,
            max_value=date.today(),
            min_value=date.today() - timedelta(days=30)
        )
        
        if selected_date != st.session_state.selected_date:
            st.session_state.selected_date = selected_date
            if st.session_state.current_page == "📈 Daily Report":
                st.rerun()
        
        if st.button("📊 View Selected Date Report"):
            st.session_state.current_page = "📈 Daily Report"
            st.rerun()
        
        st.markdown("---")
    
    # Navigation - Only show pages after profile is complete
    profile_exists = check_user_profile_exists(st.session_state.current_user_id)
    
    if profile_exists:
        menu_options = ["🏠 Dashboard", "📚 Manage Subjects", "💪 Exercise Routine", 
                       "📝 Daily Entry", "📈 Daily Report", "📊 Weekly Analysis", 
                       "⏰ Study Planner", "🧠 AI Assistant", "👤 Edit Profile"]
    else:
        menu_options = ["👤 Complete Profile"]
    
    menu = st.selectbox(
        "📌 **Navigate**",
        menu_options,
        index=menu_options.index(st.session_state.current_page) if st.session_state.current_page in menu_options else 0
    )
    
    st.session_state.current_page = menu
    
    st.markdown("---")
    
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.current_user_id = None
        st.session_state.current_student_id = None
        st.session_state.current_page = "Login"
        st.session_state.messages = []
        st.session_state.need_clear_form = False
        st.session_state.show_success_message = False
        st.session_state.form_reset_key = 0
        st.rerun()

# ========== COMPLETE PROFILE PAGE ==========
if menu == "👤 Complete Profile":
    st.markdown('<h2 class="sub-header">👤 Complete Student Profile</h2>', unsafe_allow_html=True)
    
    # Check if profile already exists
    existing_profile = get_user_profile(st.session_state.current_user_id)
    
    if existing_profile:
        st.info(f"You already have a profile. You can edit it below.")
    
    # Use form_reset_key to create unique form key
    profile_form_key = f"profile_form_{st.session_state.form_reset_key}"
    
    with st.form(profile_form_key, clear_on_submit=True):
        st.write("### 📝 Personal Information")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            name = st.text_input("Full Name*", 
                                value=existing_profile['name'] if existing_profile else "", 
                                placeholder="Enter your full name",
                                key="profile_name")
            email = st.text_input("Email Address", 
                                 value=existing_profile['email'] if existing_profile else "", 
                                 placeholder="your.email@example.com",
                                 key="profile_email")
            phone = st.text_input("Phone Number", 
                                 value=existing_profile['phone'] if existing_profile else "", 
                                 placeholder="+91 9876543210",
                                 key="profile_phone")
        
        with col2:
            st.write("### 📸 Profile Photo")
            photo_file = st.file_uploader("Upload photo (jpg, png)", type=['jpg', 'jpeg', 'png'], key="photo_upload")
            
            if photo_file is not None:
                st.image(photo_file, width=150)
                photo_base64 = image_to_base64(photo_file)
            elif existing_profile and existing_profile['photo']:
                try:
                    photo_bytes = base64.b64decode(existing_profile['photo'])
                    image = Image.open(io.BytesIO(photo_bytes))
                    st.image(image, width=150, caption="Current Photo")
                    photo_base64 = existing_profile['photo']
                except:
                    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=150)
                    photo_base64 = None
            else:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=150)
                photo_base64 = None
        
        st.markdown("---")
        st.write("### 🎯 Academic Goals")
        
        col1, col2 = st.columns(2)
        
        with col1:
            target_study_hours = st.slider(
                "Target Daily Study Hours",
                min_value=1,
                max_value=12,
                value=existing_profile['target_study_hours'] if existing_profile else 6,
                help="How many hours do you want to study daily?",
                key="target_hours"
            )
        
        with col2:
            wakeup_time_default = existing_profile['wakeup_time'] if existing_profile else "07:00"
            bedtime_default = existing_profile['bedtime'] if existing_profile else "23:00"
            
            wakeup_time = st.time_input("Preferred Wake-up Time", 
                                       value=datetime.strptime(wakeup_time_default, "%H:%M").time() if ':' in wakeup_time_default else datetime.strptime("07:00", "%H:%M").time(),
                                       key="wakeup_time")
            bedtime = st.time_input("Preferred Bedtime", 
                                   value=datetime.strptime(bedtime_default, "%H:%M").time() if ':' in bedtime_default else datetime.strptime("23:00", "%H:%M").time(),
                                   key="bedtime")
        
        submitted = st.form_submit_button("💾 Save Profile")
        
        if submitted:
            if not name:
                st.error("Name is required!")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                
                if existing_profile:
                    # Update existing profile
                    c.execute('''
                        UPDATE students 
                        SET name = ?, photo = ?, email = ?, phone = ?,
                            target_study_hours = ?, wakeup_time = ?, bedtime = ?
                        WHERE user_id = ?
                    ''', (name, photo_base64, email, phone, target_study_hours, 
                          wakeup_time.strftime("%H:%M"), bedtime.strftime("%H:%M"), 
                          st.session_state.current_user_id))
                else:
                    # Insert new profile
                    c.execute('''
                        INSERT INTO students 
                        (user_id, name, photo, email, phone, target_study_hours, wakeup_time, bedtime)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (st.session_state.current_user_id, name, photo_base64, email, phone,
                          target_study_hours, wakeup_time.strftime("%H:%M"), bedtime.strftime("%H:%M")))
                
                # Get student ID
                c.execute("SELECT id FROM students WHERE user_id = ?", (st.session_state.current_user_id,))
                student_id = c.fetchone()[0]
                
                conn.commit()
                conn.close()
                
                st.session_state.current_student_id = student_id
                
                st.success(f"✅ Profile saved successfully!")
                st.balloons()
                
                # Increment form reset key to clear form for next use
                st.session_state.form_reset_key += 1
                
                # Redirect to dashboard after profile completion
                st.session_state.current_page = "🏠 Dashboard"
                st.rerun()

# ========== DASHBOARD PAGE ==========
elif menu == "🏠 Dashboard":
    # Get user profile data
    user_profile = get_user_profile(st.session_state.current_user_id)
    
    if not user_profile:
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f'<div class="profile-card"><h2>Welcome back, {user_profile["name"]}!</h2><p>📅 {date.today().strftime("%A, %d %B %Y")}</p></div>', unsafe_allow_html=True)
    
    with col2:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM subjects WHERE user_id = ?", (st.session_state.current_user_id,))
        total_subjects = c.fetchone()[0]
        
        c.execute('''
            SELECT COUNT(DISTINCT date) FROM daily_progress 
            WHERE user_id = ? AND date = date('now')
        ''', (st.session_state.current_user_id,))
        today_entry = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM exercises WHERE user_id = ?", (st.session_state.current_user_id,))
        total_exercises = c.fetchone()[0]
        
        conn.close()
        
        st.metric("📚 Subjects", total_subjects)
        st.metric("✅ Today's Entry", "Done" if today_entry else "Pending")
        st.metric("💪 Exercises", total_exercises)
    
    st.markdown("---")
    
    # Check if user has completed initial setup
    has_subjects = check_user_subjects_exist(st.session_state.current_user_id)
    has_exercises = check_user_exercises_exist(st.session_state.current_user_id)
    
    if not has_subjects:
        st.warning("You haven't added any subjects yet. Add subjects to start tracking your studies!")
        if st.button("➕ Add Your First Subject"):
            st.session_state.current_page = "📚 Manage Subjects"
            st.rerun()
    elif not has_exercises:
        st.info("Add exercise routine to maintain your wellness!")
        if st.button("💪 Add Exercise Routine"):
            st.session_state.current_page = "💪 Exercise Routine"
            st.rerun()
    else:
        st.subheader("⚡ Quick Actions")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("➕ Add Subject"):
                st.session_state.current_page = "📚 Manage Subjects"
                st.rerun()
        
        with col2:
            if st.button("📝 Today's Entry"):
                st.session_state.current_page = "📝 Daily Entry"
                st.rerun()
        
        with col3:
            if st.button("📊 View Report"):
                st.session_state.current_page = "📈 Daily Report"
                st.rerun()
        
        with col4:
            if st.button("⏰ Study Plan"):
                st.session_state.current_page = "⏰ Study Planner"
                st.rerun()

# ========== MANAGE SUBJECTS PAGE ==========
elif menu == "📚 Manage Subjects":
    st.markdown('<h2 class="sub-header">📚 Manage Your Subjects</h2>', unsafe_allow_html=True)
    
    # Check if user has profile
    if not check_user_profile_exists(st.session_state.current_user_id):
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    # Get existing subjects
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, subject_name, weightage, target_total_hours, 
              daily_lecture_hours, daily_question_hours, difficulty, target_completion_date
        FROM subjects 
        WHERE user_id = ?
        ORDER BY weightage DESC, subject_name
    ''', (st.session_state.current_user_id,))
    
    existing_subjects = c.fetchall()
    conn.close()
    
    if existing_subjects:
        # User has subjects - show edit options
        st.info(f"You have {len(existing_subjects)} subjects. You can edit them below.")
        
        for subject in existing_subjects:
            sub_id, sub_name, weight, total_hours, lecture_hours, question_hours, diff, comp_date = subject
            
            with st.expander(f"📚 {sub_name} | Weight: {weight}x | Difficulty: {diff}", expanded=False):
                edit_form_key = f"edit_subject_{sub_id}_{st.session_state.form_reset_key}"
                
                with st.form(edit_form_key, clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_name = st.text_input("Subject Name", value=sub_name, key=f"name_{sub_id}")
                        new_weight = st.slider("Weightage", 0.5, 3.0, float(weight), 0.1, key=f"weight_{sub_id}")
                        new_diff = st.selectbox("Difficulty", ["Easy", "Medium", "Hard", "Very Hard"], 
                                              index=["Easy", "Medium", "Hard", "Very Hard"].index(diff) if diff in ["Easy", "Medium", "Hard", "Very Hard"] else 1, 
                                              key=f"diff_{sub_id}")
                    
                    with col2:
                        new_total = st.number_input("Target Hours", value=float(total_hours), 
                                                  min_value=10.0, step=5.0, key=f"total_{sub_id}")
                        new_lecture = st.number_input("Daily Lecture Hours", value=float(lecture_hours), 
                                                    min_value=0.5, step=0.5, key=f"lecture_{sub_id}")
                        new_question = st.number_input("Daily Question Hours", value=float(question_hours), 
                                                     min_value=0.5, step=0.5, key=f"question_{sub_id}")
                    
                    new_date = st.date_input("Completion Date", 
                                            value=datetime.strptime(comp_date, '%Y-%m-%d').date() if comp_date and isinstance(comp_date, str) else date.today() + timedelta(days=30), 
                                            key=f"date_{sub_id}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        save_changes = st.form_submit_button("💾 Save Changes")
                    
                    with col2:
                        delete_subject = st.form_submit_button("🗑️ Delete Subject", type="secondary")
                    
                    if save_changes:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute('''
                            UPDATE subjects 
                            SET subject_name = ?, weightage = ?, target_total_hours = ?,
                                daily_lecture_hours = ?, daily_question_hours = ?,
                                difficulty = ?, target_completion_date = ?
                            WHERE id = ? AND user_id = ?
                        ''', (new_name, new_weight, new_total, new_lecture, 
                              new_question, new_diff, new_date, sub_id, st.session_state.current_user_id))
                        conn.commit()
                        conn.close()
                        st.success("✅ Subject updated successfully!")
                        # Increment form reset key to clear form
                        st.session_state.form_reset_key += 1
                        st.rerun()
                    
                    if delete_subject:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("DELETE FROM subjects WHERE id = ? AND user_id = ?", 
                                 (sub_id, st.session_state.current_user_id))
                        conn.commit()
                        conn.close()
                        st.success("✅ Subject deleted successfully!")
                        # Increment form reset key to clear form
                        st.session_state.form_reset_key += 1
                        st.rerun()
        
        # Option to add new subject
        st.markdown("---")
        st.write("### ➕ Add New Subject")
        
        add_subject_form_key = f"add_subject_form_{st.session_state.form_reset_key}"
        
        with st.form(add_subject_form_key, clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                subject_name = st.text_input("Subject Name*", placeholder="Mathematics", key="new_subject_name")
                weightage = st.slider("Weightage (Importance)", 0.5, 3.0, 1.0, 0.1, key="new_weightage")
                difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard", "Very Hard"], key="new_difficulty")
            
            with col2:
                target_total_hours = st.number_input(
                    "Target Total Hours",
                    min_value=10.0,
                    max_value=500.0,
                    value=100.0,
                    step=5.0,
                    help="Total hours you want to dedicate to this subject",
                    key="new_target_hours"
                )
                
                daily_lecture_hours = st.number_input(
                    "Daily Lecture Hours",
                    min_value=0.5,
                    max_value=8.0,
                    value=2.0,
                    step=0.5,
                    help="Hours per day for watching/attending lectures",
                    key="new_lecture_hours"
                )
                
                daily_question_hours = st.number_input(
                    "Daily Question Hours",
                    min_value=0.5,
                    max_value=8.0,
                    value=1.0,
                    step=0.5,
                    help="Hours per day for solving questions",
                    key="new_question_hours"
                )
            
            target_date = st.date_input(
                "Target Completion Date",
                value=date.today() + timedelta(days=30),
                key="new_target_date"
            )
            
            submitted = st.form_submit_button("➕ Add New Subject")
            
            if submitted and subject_name:
                conn = get_db_connection()
                c = conn.cursor()
                
                c.execute('''
                    SELECT COUNT(*) FROM subjects 
                    WHERE user_id = ? AND subject_name = ?
                ''', (st.session_state.current_user_id, subject_name))
                
                if c.fetchone()[0] > 0:
                    st.error(f"❌ Subject '{subject_name}' already exists!")
                else:
                    c.execute('''
                        INSERT INTO subjects 
                        (user_id, subject_name, weightage, target_total_hours, 
                         daily_lecture_hours, daily_question_hours, difficulty, target_completion_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (st.session_state.current_user_id, subject_name, weightage, 
                          target_total_hours, daily_lecture_hours, daily_question_hours, 
                          difficulty, target_date))
                    
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Subject '{subject_name}' added successfully!")
                    # Increment form reset key to clear form
                    st.session_state.form_reset_key += 1
                    st.rerun()
    
    else:
        # User has no subjects - show initial setup form
        st.info("Add your first subject to get started!")
        
        initial_subject_form_key = f"initial_subject_form_{st.session_state.form_reset_key}"
        
        with st.form(initial_subject_form_key, clear_on_submit=True):
            st.write("### Add Your First Subject")
            
            col1, col2 = st.columns(2)
            
            with col1:
                subject_name = st.text_input("Subject Name*", placeholder="Mathematics", key="first_subject_name")
                weightage = st.slider("Weightage (Importance)", 0.5, 3.0, 1.0, 0.1, key="first_weightage")
                difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard", "Very Hard"], key="first_difficulty")
            
            with col2:
                target_total_hours = st.number_input(
                    "Target Total Hours",
                    min_value=10.0,
                    max_value=500.0,
                    value=100.0,
                    step=5.0,
                    help="Total hours you want to dedicate to this subject",
                    key="first_target_hours"
                )
                
                daily_lecture_hours = st.number_input(
                    "Daily Lecture Hours",
                    min_value=0.5,
                    max_value=8.0,
                    value=2.0,
                    step=0.5,
                    help="Hours per day for watching/attending lectures",
                    key="first_lecture_hours"
                )
                
                daily_question_hours = st.number_input(
                    "Daily Question Hours",
                    min_value=0.5,
                    max_value=8.0,
                    value=1.0,
                    step=0.5,
                    help="Hours per day for solving questions",
                    key="first_question_hours"
                )
            
            target_date = st.date_input(
                "Target Completion Date",
                value=date.today() + timedelta(days=30),
                key="first_target_date"
            )
            
            submitted = st.form_submit_button("➕ Add First Subject")
            
            if submitted and subject_name:
                conn = get_db_connection()
                c = conn.cursor()
                
                c.execute('''
                    INSERT INTO subjects 
                    (user_id, subject_name, weightage, target_total_hours, 
                     daily_lecture_hours, daily_question_hours, difficulty, target_completion_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (st.session_state.current_user_id, subject_name, weightage, 
                      target_total_hours, daily_lecture_hours, daily_question_hours, 
                      difficulty, target_date))
                
                conn.commit()
                conn.close()
                st.success(f"✅ Subject '{subject_name}' added successfully!")
                st.balloons()
                # Increment form reset key to clear form
                st.session_state.form_reset_key += 1
                st.rerun()

# ========== EXERCISE ROUTINE PAGE ==========
elif menu == "💪 Exercise Routine":
    st.markdown('<h2 class="sub-header">💪 Exercise & Wellness Routine</h2>', unsafe_allow_html=True)
    
    # Check if user has profile
    if not check_user_profile_exists(st.session_state.current_user_id):
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    # Get existing exercises
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, exercise_type, day_of_week, duration_minutes, intensity, notes
        FROM exercises 
        WHERE user_id = ?
        ORDER BY 
            CASE day_of_week 
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    ''', (st.session_state.current_user_id,))
    
    existing_exercises = c.fetchall()
    conn.close()
    
    if existing_exercises:
        # User has exercises - show edit options
        st.info(f"You have {len(existing_exercises)} exercise routines. You can edit them below.")
        
        for exercise in existing_exercises:
            ex_id, ex_type, day, duration, intensity, notes = exercise
            
            with st.expander(f"💪 {ex_type} on {day}", expanded=False):
                edit_exercise_key = f"edit_exercise_{ex_id}_{st.session_state.form_reset_key}"
                
                with st.form(edit_exercise_key, clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_type = st.selectbox(
                            "Exercise Type",
                            ["Gym", "Running", "Walking", "Cycling", "Swimming", "Yoga", 
                             "Meditation", "Sports", "Dancing", "Other"],
                            index=["Gym", "Running", "Walking", "Cycling", "Swimming", "Yoga", 
                                  "Meditation", "Sports", "Dancing", "Other"].index(ex_type) if ex_type in ["Gym", "Running", "Walking", "Cycling", "Swimming", "Yoga", "Meditation", "Sports", "Dancing", "Other"] else 0,
                            key=f"type_{ex_id}"
                        )
                        
                        if new_type == "Other":
                            new_type = st.text_input("Specify Exercise Type", value=ex_type, key=f"other_type_{ex_id}")
                        
                        new_day = st.selectbox(
                            "Day of Week",
                            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                            index=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(day),
                            key=f"day_{ex_id}"
                        )
                    
                    with col2:
                        new_duration = st.slider("Duration (minutes)", 10, 120, duration, 5, key=f"duration_{ex_id}")
                        new_intensity = st.selectbox(
                            "Intensity Level",
                            ["Light", "Moderate", "Hard", "Very Hard"],
                            index=["Light", "Moderate", "Hard", "Very Hard"].index(intensity) if intensity in ["Light", "Moderate", "Hard", "Very Hard"] else 1,
                            key=f"intensity_{ex_id}"
                        )
                    
                    new_notes = st.text_area("Notes", value=notes or "", placeholder="Any specific details...", key=f"notes_{ex_id}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        save_changes = st.form_submit_button("💾 Save Changes")
                    
                    with col2:
                        delete_exercise = st.form_submit_button("🗑️ Delete Exercise", type="secondary")
                    
                    if save_changes:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute('''
                            UPDATE exercises 
                            SET exercise_type = ?, day_of_week = ?, duration_minutes = ?, 
                                intensity = ?, notes = ?
                            WHERE id = ? AND user_id = ?
                        ''', (new_type, new_day, new_duration, new_intensity, new_notes, ex_id, st.session_state.current_user_id))
                        conn.commit()
                        conn.close()
                        st.success("✅ Exercise updated successfully!")
                        # Increment form reset key to clear form
                        st.session_state.form_reset_key += 1
                        st.rerun()
                    
                    if delete_exercise:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("DELETE FROM exercises WHERE id = ? AND user_id = ?", 
                                 (ex_id, st.session_state.current_user_id))
                        conn.commit()
                        conn.close()
                        st.success("✅ Exercise deleted successfully!")
                        # Increment form reset key to clear form
                        st.session_state.form_reset_key += 1
                        st.rerun()
        
        # Option to add new exercise
        st.markdown("---")
        st.write("### ➕ Add New Exercise")
        
        add_exercise_key = f"add_exercise_form_{st.session_state.form_reset_key}"
        
        with st.form(add_exercise_key, clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                exercise_type = st.selectbox(
                    "Exercise Type*",
                    ["Gym", "Running", "Walking", "Cycling", "Swimming", "Yoga", 
                     "Meditation", "Sports", "Dancing", "Other"],
                    key="new_exercise_type"
                )
                
                if exercise_type == "Other":
                    exercise_type = st.text_input("Specify Exercise Type", key="new_exercise_other")
                
                day_of_week = st.selectbox(
                    "Day of Week*",
                    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    key="new_exercise_day"
                )
            
            with col2:
                duration = st.slider("Duration (minutes)", 10, 120, 30, 5, key="new_exercise_duration")
                intensity = st.selectbox(
                    "Intensity Level",
                    ["Light", "Moderate", "Hard", "Very Hard"],
                    key="new_exercise_intensity"
                )
            
            notes = st.text_area("Notes (Optional)", placeholder="Any specific details about this exercise...", key="new_exercise_notes")
            
            submitted = st.form_submit_button("➕ Add New Exercise")
            
            if submitted and exercise_type:
                conn = get_db_connection()
                c = conn.cursor()
                
                c.execute('''
                    INSERT INTO exercises (user_id, exercise_type, day_of_week, duration_minutes, intensity, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (st.session_state.current_user_id, exercise_type, day_of_week, duration, intensity, notes))
                
                conn.commit()
                conn.close()
                
                st.success(f"✅ {exercise_type} added for {day_of_week}!")
                # Increment form reset key to clear form
                st.session_state.form_reset_key += 1
                st.rerun()
    
    else:
        # User has no exercises - show initial setup form
        st.info("Add your first exercise routine to maintain your wellness!")
        
        initial_exercise_key = f"initial_exercise_form_{st.session_state.form_reset_key}"
        
        with st.form(initial_exercise_key, clear_on_submit=True):
            st.write("### Add Your First Exercise Routine")
            
            col1, col2 = st.columns(2)
            
            with col1:
                exercise_type = st.selectbox(
                    "Exercise Type*",
                    ["Gym", "Running", "Walking", "Cycling", "Swimming", "Yoga", 
                     "Meditation", "Sports", "Dancing", "Other"],
                    key="first_exercise_type"
                )
                
                if exercise_type == "Other":
                    exercise_type = st.text_input("Specify Exercise Type", key="first_exercise_other")
                
                day_of_week = st.selectbox(
                    "Day of Week*",
                    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    key="first_exercise_day"
                )
            
            with col2:
                duration = st.slider("Duration (minutes)", 10, 120, 30, 5, key="first_exercise_duration")
                intensity = st.selectbox(
                    "Intensity Level",
                    ["Light", "Moderate", "Hard", "Very Hard"],
                    key="first_exercise_intensity"
                )
            
            notes = st.text_area("Notes (Optional)", placeholder="Any specific details about this exercise...", key="first_exercise_notes")
            
            submitted = st.form_submit_button("➕ Add First Exercise")
            
            if submitted and exercise_type:
                conn = get_db_connection()
                c = conn.cursor()
                
                c.execute('''
                    INSERT INTO exercises (user_id, exercise_type, day_of_week, duration_minutes, intensity, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (st.session_state.current_user_id, exercise_type, day_of_week, duration, intensity, notes))
                
                conn.commit()
                conn.close()
                
                st.success(f"✅ {exercise_type} added for {day_of_week}!")
                st.balloons()
                # Increment form reset key to clear form
                st.session_state.form_reset_key += 1
                st.rerun()

# ========== DAILY ENTRY PAGE ==========
elif menu == "📝 Daily Entry":
    st.markdown('<h2 class="sub-header">📝 Daily Progress Entry</h2>', unsafe_allow_html=True)
    
    # Check if user has profile and subjects
    if not check_user_profile_exists(st.session_state.current_user_id):
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    if not check_user_subjects_exist(st.session_state.current_user_id):
        st.warning("Please add subjects first!")
        st.session_state.current_page = "📚 Manage Subjects"
        st.rerun()
    
    # Date selection - can go back 30 days
    col1, col2 = st.columns([2, 1])
    
    with col1:
        entry_date = st.date_input(
            "Select Date for Entry",
            value=st.session_state.daily_entry_date,
            max_value=date.today(),
            min_value=date.today() - timedelta(days=30),
            key="daily_entry_date_selector"
        )
        
        if entry_date != st.session_state.daily_entry_date:
            st.session_state.daily_entry_date = entry_date
            st.session_state.form_submitted = False
            st.session_state.need_clear_form = True
            st.rerun()
    
    with col2:
        if st.button("🔄 Reset Form", key="reset_form_btn"):
            st.session_state.form_submitted = False
            st.session_state.need_clear_form = True
            st.rerun()
    
    st.info(f"Entering data for: **{entry_date.strftime('%A, %d %B %Y')}**")
    
    # Show success message if data was just saved
    if st.session_state.show_success_message:
        st.success(st.session_state.success_message)
        st.session_state.show_success_message = False
        st.session_state.success_message = ""
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT id, subject_name, daily_lecture_hours, daily_question_hours
        FROM subjects 
        WHERE user_id = ?
        ORDER BY weightage DESC, subject_name
    ''', (st.session_state.current_user_id,))
    
    subjects = c.fetchall()
    conn.close()
    
    if not subjects:
        st.warning("No subjects found. Please add subjects first.")
        st.session_state.current_page = "📚 Manage Subjects"
        st.rerun()
    
    # Check if entry already exists for this date
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM daily_progress 
        WHERE user_id = ? AND date = ?
    ''', (st.session_state.current_user_id, entry_date))
    
    entry_exists = c.fetchone()[0] > 0
    conn.close()
    
    if entry_exists:
        st.success(f"✅ Entry already exists for {entry_date.strftime('%d %B %Y')}. You can edit it below.")
    else:
        st.info(f"📝 No entry found for {entry_date.strftime('%d %B %Y')}. Fill the form below.")
    
    # Create form with unique key based on date and reset key
    form_key = f"daily_entry_form_{entry_date}_{st.session_state.form_reset_key}"
    
    with st.form(form_key, clear_on_submit=True):
        st.write(f"### 📚 Study Progress for {entry_date.strftime('%A, %d %B %Y')}")
        
        daily_data = []
        
        for subject in subjects:
            sub_id, sub_name, target_lecture, target_question = subject
            
            # Get existing values if they exist
            existing_data = get_existing_progress_data(st.session_state.current_user_id, sub_id, entry_date)
            
            if existing_data and not st.session_state.need_clear_form:
                default_lecture = existing_data['lecture_hours']
                default_question = existing_data['question_hours']
                default_solved = existing_data['questions_solved']
            else:
                # Use target values for new entries or when clearing
                default_lecture = target_lecture
                default_question = target_question
                default_solved = 10
            
            st.write(f"**{sub_name}** (Target: {target_lecture}L + {target_question}Q hrs)")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                lecture_hours = st.number_input(
                    f"Lecture Hours",
                    min_value=0.0,
                    max_value=12.0,
                    value=default_lecture,
                    step=0.5,
                    key=f"lecture_{sub_id}_{entry_date}_{st.session_state.form_reset_key}"
                )
            
            with col2:
                question_hours = st.number_input(
                    f"Question Hours",
                    min_value=0.0,
                    max_value=12.0,
                    value=default_question,
                    step=0.5,
                    key=f"question_{sub_id}_{entry_date}_{st.session_state.form_reset_key}"
                )
            
            with col3:
                questions_solved = st.number_input(
                    f"Questions Solved",
                    min_value=0,
                    value=default_solved,
                    key=f"solved_{sub_id}_{entry_date}_{st.session_state.form_reset_key}"
                )
            
            daily_data.append({
                'subject_id': sub_id,
                'lecture_hours': lecture_hours,
                'question_hours': question_hours,
                'questions_solved': questions_solved
            })
            
            st.markdown("---")
        
        # Exercise section - COMMON FOR ALL SUBJECTS
        st.write("### 💪 Exercise & Wellness")
        
        day_name = entry_date.strftime('%A')
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            SELECT exercise_type FROM exercises 
            WHERE user_id = ? AND day_of_week = ?
        ''', (st.session_state.current_user_id, day_name))
        
        planned_exercises = [ex[0] for ex in c.fetchall()]
        conn.close()
        
        # Get existing exercise data from database (common for all subjects)
        existing_exercise_data = None
        if subjects and not st.session_state.need_clear_form:
            # Get exercise data from any subject (all share same exercise data)
            first_subject_id = subjects[0][0]
            existing_exercise_data = get_existing_progress_data(st.session_state.current_user_id, first_subject_id, entry_date)
        
        if existing_exercise_data and not st.session_state.need_clear_form:
            existing_exercise_done = existing_exercise_data['exercise_done']
            existing_exercise_minutes = existing_exercise_data['exercise_minutes']
            existing_mood = existing_exercise_data['mood']
            existing_notes = existing_exercise_data['notes']
        else:
            existing_exercise_done = bool(planned_exercises)
            existing_exercise_minutes = 30
            existing_mood = "🙂 Good"
            existing_notes = ""
        
        exercise_done = st.checkbox("Completed exercise today?", 
                                   value=existing_exercise_done, 
                                   key=f"exercise_done_{entry_date}_{st.session_state.form_reset_key}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if exercise_done:
                exercise_minutes = st.number_input("Exercise Duration (minutes)", 
                                                  min_value=1, 
                                                  value=existing_exercise_minutes,
                                                  key=f"exercise_minutes_{entry_date}_{st.session_state.form_reset_key}")
                exercise_type = st.selectbox(
                    "Exercise Type",
                    options=planned_exercises + ["Custom"] if planned_exercises else ["Custom"],
                    index=0 if planned_exercises else 0,
                    key=f"exercise_type_{entry_date}_{st.session_state.form_reset_key}"
                )
            else:
                exercise_minutes = 0
                exercise_type = None
        
        with col2:
            mood = st.select_slider(
                "Today's Mood",
                options=["😢 Very Sad", "😞 Sad", "😐 Neutral", "🙂 Good", "😊 Very Good", "😄 Excellent"],
                value=existing_mood,
                key=f"mood_{entry_date}_{st.session_state.form_reset_key}"
            )
        
        notes = st.text_area("Daily Notes (Optional)", 
                            value=existing_notes,
                            placeholder="How was your day? Any challenges or achievements?",
                            key=f"notes_{entry_date}_{st.session_state.form_reset_key}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            submitted = st.form_submit_button("💾 Save Daily Entry")
        
        with col2:
            clear_form = st.form_submit_button("🗑️ Clear Form", type="secondary")
            if clear_form:
                st.session_state.need_clear_form = True
                st.session_state.form_reset_key += 1
                st.rerun()
        
        if submitted:
            conn = get_db_connection()
            c = conn.cursor()
            
            success_count = 0
            for data in daily_data:
                # Use INSERT OR REPLACE to handle both new and existing entries
                c.execute('''
                    INSERT OR REPLACE INTO daily_progress 
                    (user_id, subject_id, date, lecture_hours_actual, question_hours_actual,
                     questions_solved, exercise_done, exercise_minutes, mood, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (st.session_state.current_user_id, data['subject_id'], entry_date,
                      data['lecture_hours'], data['question_hours'], data['questions_solved'],
                      exercise_done, exercise_minutes, mood, notes))
                success_count += 1
            
            conn.commit()
            conn.close()
            
            # Set success message
            st.session_state.success_message = f"✅ Daily entry saved successfully for {entry_date.strftime('%d %B %Y')}!"
            st.session_state.show_success_message = True
            
            # Reset the clear form flag and increment reset key
            st.session_state.need_clear_form = True
            st.session_state.form_reset_key += 1
            
            # Show success message
            st.success(st.session_state.success_message)
            st.balloons()
            
            # Refresh to show cleared form
            st.rerun()

# ========== DAILY REPORT PAGE ==========
elif menu == "📈 Daily Report":
    st.markdown('<h2 class="sub-header">📈 Daily Progress Report</h2>', unsafe_allow_html=True)
    
    # Check if user has profile and subjects
    if not check_user_profile_exists(st.session_state.current_user_id):
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    if not check_user_subjects_exist(st.session_state.current_user_id):
        st.warning("Please add subjects first!")
        st.session_state.current_page = "📚 Manage Subjects"
        st.rerun()
    
    # Date selector for report
    col1, col2 = st.columns([2, 1])
    
    with col1:
        report_date = st.date_input(
            "📅 Select Date for Report",
            value=st.session_state.selected_date,
            max_value=date.today(),
            min_value=date.today() - timedelta(days=30),
            key="report_date_selector"
        )
        
        if report_date != st.session_state.selected_date:
            st.session_state.selected_date = report_date
            st.rerun()
    
    with col2:
        st.write("")
        st.write("")
        if st.button("🔄 Refresh Report", key="refresh_report_btn"):
            st.rerun()
    
    report = get_daily_report(st.session_state.current_user_id, report_date)
    
    st.write(f"### 📊 Report for {report_date.strftime('%A, %d %B %Y')}")
    
    if not report['subjects']:
        st.warning(f"No data available for {report_date.strftime('%d %B %Y')}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button(f"📝 Add Entry", key="add_entry_from_report"):
                st.session_state.daily_entry_date = report_date
                st.session_state.current_page = "📝 Daily Entry"
                st.rerun()
        
        with col2:
            # Show previous date navigation
            prev_date = report_date - timedelta(days=1)
            if prev_date >= date.today() - timedelta(days=30):
                if st.button(f"⬅️ Previous", key="prev_day_from_empty"):
                    st.session_state.selected_date = prev_date
                    st.rerun()
        
        with col3:
            # Show next date navigation
            next_date = report_date + timedelta(days=1)
            if next_date <= date.today():
                if st.button(f"Next ➡️", key="next_day_from_empty"):
                    st.session_state.selected_date = next_date
                    st.rerun()
        
        with col4:
            if st.button("📅 Today", key="today_from_empty"):
                st.session_state.selected_date = date.today()
                st.rerun()
        
        # Show recent dates with data
        st.write("### 📅 Recent Entries")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            SELECT DISTINCT date FROM daily_progress 
            WHERE user_id = ? 
            ORDER BY date DESC 
            LIMIT 5
        ''', (st.session_state.current_user_id,))
        
        recent_dates = c.fetchall()
        conn.close()
        
        if recent_dates:
            st.write("Available reports:")
            for d in recent_dates:
                date_str = d[0]
                if isinstance(date_str, str):
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    date_obj = date_str
                
                if st.button(f"📊 {date_obj.strftime('%A, %d %B %Y')}", key=f"report_{date_obj}"):
                    st.session_state.selected_date = date_obj
                    st.rerun()
        st.stop()
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        lecture_target = report['totals']['lecture_target']
        lecture_actual = report['totals']['lecture_actual']
        lecture_achievement = (lecture_actual / lecture_target * 100) if lecture_target > 0 else 0
        st.metric("📖 Lectures", f"{lecture_actual:.1f}/{lecture_target:.1f} hrs", 
                 f"{lecture_achievement:.1f}%")
    
    with col2:
        question_target = report['totals']['question_target']
        question_actual = report['totals']['question_actual']
        question_achievement = (question_actual / question_target * 100) if question_target > 0 else 0
        st.metric("❓ Questions", f"{question_actual:.1f}/{question_target:.1f} hrs", 
                 f"{question_achievement:.1f}%")
    
    with col3:
        st.metric("✅ Solved", f"{report['totals']['questions']} questions")
    
    with col4:
        exercise_done = any([s[7] for s in report['subjects'] if s[7] is not None])
        exercise_minutes = next((s[8] for s in report['subjects'] if s[8] is not None), 0)
        st.metric("💪 Exercise", f"{'✅ Done' if exercise_done else '❌ Missed'}", 
                 f"{exercise_minutes} mins" if exercise_done else "")
    
    # Navigation buttons for previous/next day - FIXED WITH CALLBACKS
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        prev_date = report_date - timedelta(days=1)
        if prev_date >= date.today() - timedelta(days=30):
            if st.button(f"⬅️ Previous Day", key="prev_day_btn"):
                st.session_state.selected_date = prev_date
                st.rerun()
        else:
            st.button(f"⬅️ Previous Day", disabled=True, key="prev_day_disabled")
    
    with col2:
        next_date = report_date + timedelta(days=1)
        if next_date <= date.today():
            if st.button(f"Next Day ➡️", key="next_day_btn"):
                st.session_state.selected_date = next_date
                st.rerun()
        else:
            st.button(f"Next Day ➡️", disabled=True, key="next_day_disabled")
    
    with col3:
        if st.button("📝 Edit This Entry", key="edit_entry_btn"):
            st.session_state.daily_entry_date = report_date
            st.session_state.current_page = "📝 Daily Entry"
            st.rerun()
    
    with col4:
        if st.button("📅 Today's Report", key="today_report_btn"):
            st.session_state.selected_date = date.today()
            st.rerun()
    
    st.markdown("---")
    
    # Detailed subject-wise report
    st.write("### 📚 Subject-wise Performance")
    
    for i, subject in enumerate(report['subjects']):
        sub_id, sub_name, target_lecture, target_question, actual_lecture, actual_question, questions, exercise_done, exercise_mins, mood, notes = subject
        
        actual_lecture_val = actual_lecture if actual_lecture is not None else 0
        actual_question_val = actual_question if actual_question is not None else 0
        questions_val = questions if questions is not None else 0
        
        with st.container():
            st.markdown(f'<div class="progress-card">', unsafe_allow_html=True)
            
            st.write(f"**{sub_name}**")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                lecture_percent = (actual_lecture_val / target_lecture * 100) if target_lecture > 0 else 0
                st.write(f"**Lectures:** {actual_lecture_val:.1f}/{target_lecture:.1f} hrs")
                st.progress(min(lecture_percent/100, 1.0))
                st.caption(f"{lecture_percent:.1f}% achievement")
            
            with col2:
                question_percent = (actual_question_val / target_question * 100) if target_question > 0 else 0
                st.write(f"**Practice:** {actual_question_val:.1f}/{target_question:.1f} hrs")
                st.progress(min(question_percent/100, 1.0))
                st.caption(f"{question_percent:.1f}% achievement")
            
            with col3:
                st.write(f"**Questions Solved:** {questions_val}")
                efficiency = (questions_val / actual_question_val) if actual_question_val > 0 else 0
                st.caption(f"{efficiency:.1f} questions/hour")
            
            with col4:
                if i == 0:  # Only show exercise info once (common for all subjects)
                    if exercise_done:
                        st.success("✅ Exercise Done")
                        st.caption(f"{exercise_mins or 0} minutes")
                    else:
                        st.error("❌ Exercise Missed")
                    
                    if mood:
                        st.write(f"**Mood:** {mood}")
            
            st.markdown('</div>', unsafe_allow_html=True)

# ========== WEEKLY ANALYSIS PAGE ==========
elif menu == "📊 Weekly Analysis":
    st.markdown('<h2 class="sub-header">📊 Weekly Performance Analysis</h2>', unsafe_allow_html=True)
    
    # Check if user has profile and subjects
    if not check_user_profile_exists(st.session_state.current_user_id):
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    if not check_user_subjects_exist(st.session_state.current_user_id):
        st.warning("Please add subjects first!")
        st.session_state.current_page = "📚 Manage Subjects"
        st.rerun()
    
    # Date range selection - can go back 30 days
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input("Start Date", 
                                  value=date.today() - timedelta(days=7),
                                  max_value=date.today(),
                                  min_value=date.today() - timedelta(days=30))
    
    with col2:
        end_date = st.date_input("End Date", 
                                value=date.today(),
                                max_value=date.today(),
                                min_value=start_date)
    
    if start_date > end_date:
        st.error("Start date must be before end date!")
        st.stop()
    
    daily_data, subject_data = get_weekly_analysis(st.session_state.current_user_id, start_date, end_date)
    
    if daily_data:
        daily_df = pd.DataFrame(daily_data, columns=['Date', 'Lecture Hours', 'Question Hours', 'Questions Solved', 'Subjects Studied', 'Exercise Rate'])
        subject_df = pd.DataFrame(subject_data, columns=['Subject', 'Lecture Hours', 'Question Hours', 'Questions Solved', 'Days Studied'])
        
        st.write("### 📈 Weekly Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_lecture = daily_df['Lecture Hours'].sum()
            avg_lecture = daily_df['Lecture Hours'].mean()
            st.metric("📖 Total Lecture Hours", f"{total_lecture:.1f}", f"Avg: {avg_lecture:.1f}/day")
        
        with col2:
            total_question = daily_df['Question Hours'].sum()
            avg_question = daily_df['Question Hours'].mean()
            st.metric("❓ Total Question Hours", f"{total_question:.1f}", f"Avg: {avg_question:.1f}/day")
        
        with col3:
            total_questions = daily_df['Questions Solved'].sum()
            avg_questions = daily_df['Questions Solved'].mean()
            st.metric("✅ Total Questions Solved", f"{total_questions}", f"Avg: {avg_questions:.0f}/day")
        
        with col4:
            exercise_rate = daily_df['Exercise Rate'].mean() * 100
            st.metric("💪 Exercise Rate", f"{exercise_rate:.1f}%")
        
        st.markdown("---")
        
        st.write("### 📅 Daily Trends")
        
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=daily_df['Date'], y=daily_df['Lecture Hours'], 
                                mode='lines+markers', name='Lecture Hours', line=dict(color='#3B82F6')))
        fig1.add_trace(go.Scatter(x=daily_df['Date'], y=daily_df['Question Hours'], 
                                mode='lines+markers', name='Question Hours', line=dict(color='#10B981')))
        fig1.update_layout(title='Daily Study Hours Trend', height=400, xaxis_title='Date', yaxis_title='Hours')
        st.plotly_chart(fig1, use_container_width=True)
        
        st.write("### 📚 Subject-wise Analysis")
        
        subject_df['Total Hours'] = subject_df['Lecture Hours'] + subject_df['Question Hours']
        subject_df['Hours per Day'] = subject_df['Total Hours'] / subject_df['Days Studied'].replace(0, 1)
        subject_df['Questions per Hour'] = subject_df['Questions Solved'] / subject_df['Total Hours'].replace(0, 1)
        
        st.dataframe(subject_df, use_container_width=True)
        
        if not subject_df.empty and subject_df['Total Hours'].sum() > 0:
            fig2 = px.pie(subject_df, values='Total Hours', names='Subject', 
                         title='Study Hours Distribution by Subject',
                         color_discrete_sequence=px.colors.qualitative.Set3)
            fig2.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No data available for the selected period. Start by making daily entries!")

# ========== STUDY PLANNER PAGE ==========
elif menu == "⏰ Study Planner":
    st.markdown('<h2 class="sub-header">⏰ Smart Study Planner</h2>', unsafe_allow_html=True)
    
    # Check if user has profile and subjects
    if not check_user_profile_exists(st.session_state.current_user_id):
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    if not check_user_subjects_exist(st.session_state.current_user_id):
        st.warning("Please add subjects first!")
        st.session_state.current_page = "📚 Manage Subjects"
        st.rerun()
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, subject_name, daily_lecture_hours, daily_question_hours, weightage
        FROM subjects 
        WHERE user_id = ?
        ORDER BY weightage DESC
    ''', (st.session_state.current_user_id,))
    
    subjects = c.fetchall()
    conn.close()
    
    if not subjects:
        st.warning("No subjects found. Please add subjects first.")
        st.session_state.current_page = "📚 Manage Subjects"
        st.rerun()
    
    tab1, tab2 = st.tabs(["📅 Create Study Schedule", "🗓️ View Weekly Schedule"])
    
    with tab1:
        st.write("### 📅 Create Your Weekly Study Schedule")
        
        schedule_form_key = f"study_schedule_form_{st.session_state.form_reset_key}"
        
        with st.form(schedule_form_key, clear_on_submit=True):
            st.write("Select subjects and time slots for each day:")
            
            days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            schedule_data = []
            
            for day in days_of_week:
                st.markdown(f"#### {day}")
                
                # Create columns for time slots
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    subject_1 = st.selectbox(
                        f"Morning Subject ({day})",
                        options=[""] + [s[1] for s in subjects],
                        key=f"morning_{day}_{st.session_state.form_reset_key}"
                    )
                    if subject_1:
                        start_time_1 = st.time_input(f"Start Time", value=datetime.strptime("09:00", "%H:%M").time(), key=f"start_morning_{day}_{st.session_state.form_reset_key}")
                        end_time_1 = st.time_input(f"End Time", value=datetime.strptime("11:00", "%H:%M").time(), key=f"end_morning_{day}_{st.session_state.form_reset_key}")
                        schedule_data.append({
                            'day': day,
                            'subject': subject_1,
                            'start_time': start_time_1.strftime("%H:%M"),
                            'end_time': end_time_1.strftime("%H:%M"),
                            'session_type': 'Morning'
                        })
                
                with col2:
                    subject_2 = st.selectbox(
                        f"Afternoon Subject ({day})",
                        options=[""] + [s[1] for s in subjects],
                        key=f"afternoon_{day}_{st.session_state.form_reset_key}"
                    )
                    if subject_2:
                        start_time_2 = st.time_input(f"Start Time", value=datetime.strptime("14:00", "%H:%M").time(), key=f"start_afternoon_{day}_{st.session_state.form_reset_key}")
                        end_time_2 = st.time_input(f"End Time", value=datetime.strptime("16:00", "%H:%M").time(), key=f"end_afternoon_{day}_{st.session_state.form_reset_key}")
                        schedule_data.append({
                            'day': day,
                            'subject': subject_2,
                            'start_time': start_time_2.strftime("%H:%M"),
                            'end_time': end_time_2.strftime("%H:%M"),
                            'session_type': 'Afternoon'
                        })
                
                with col3:
                    subject_3 = st.selectbox(
                        f"Evening Subject ({day})",
                        options=[""] + [s[1] for s in subjects],
                        key=f"evening_{day}_{st.session_state.form_reset_key}"
                    )
                    if subject_3:
                        start_time_3 = st.time_input(f"Start Time", value=datetime.strptime("18:00", "%H:%M").time(), key=f"start_evening_{day}_{st.session_state.form_reset_key}")
                        end_time_3 = st.time_input(f"End Time", value=datetime.strptime("20:00", "%H:%M").time(), key=f"end_evening_{day}_{st.session_state.form_reset_key}")
                        schedule_data.append({
                            'day': day,
                            'subject': subject_3,
                            'start_time': start_time_3.strftime("%H:%M"),
                            'end_time': end_time_3.strftime("%H:%M"),
                            'session_type': 'Evening'
                        })
                
                st.markdown("---")
            
            submitted = st.form_submit_button("💾 Save Study Schedule")
            
            if submitted:
                conn = get_db_connection()
                c = conn.cursor()
                
                # Clear existing schedule
                c.execute("DELETE FROM study_schedule WHERE user_id = ?", (st.session_state.current_user_id,))
                
                # Save new schedule
                for item in schedule_data:
                    if item['subject']:  # Only save if subject is selected
                        # Get subject ID
                        c.execute("SELECT id FROM subjects WHERE subject_name = ? AND user_id = ?", 
                                 (item['subject'], st.session_state.current_user_id))
                        subject_result = c.fetchone()
                        
                        if subject_result:
                            subject_id = subject_result[0]
                            priority = 1 if item['session_type'] == 'Morning' else 2 if item['session_type'] == 'Afternoon' else 3
                            
                            c.execute('''
                                INSERT INTO study_schedule 
                                (user_id, day_of_week, subject_id, start_time, end_time, session_type, priority)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (st.session_state.current_user_id, item['day'], subject_id, 
                                  item['start_time'], item['end_time'], item['session_type'], priority))
                
                conn.commit()
                conn.close()
                
                st.success("✅ Study schedule saved successfully!")
                st.balloons()
                # Increment form reset key to clear form
                st.session_state.form_reset_key += 1
                st.rerun()
    
    with tab2:
        st.write("### 🗓️ Your Weekly Study Schedule")
        
        schedule = get_study_schedule(st.session_state.current_user_id)
        
        if schedule:
            # Group by day
            schedule_by_day = {}
            for item in schedule:
                day = item[0]
                if day not in schedule_by_day:
                    schedule_by_day[day] = []
                schedule_by_day[day].append(item)
            
            # Display schedule
            days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for day in days_order:
                if day in schedule_by_day:
                    st.markdown(f'<div class="day-header">{day}</div>', unsafe_allow_html=True)
                    
                    for item in schedule_by_day[day]:
                        _, subject_name, start_time, end_time, session_type, priority = item
                        
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.write(f"**{subject_name}**")
                            st.caption(f"{session_type} Session")
                        
                        with col2:
                            st.write(f"🕐 {start_time} - {end_time}")
                        
                        with col3:
                            if priority == 1:
                                st.success("High Priority")
                            elif priority == 2:
                                st.warning("Medium Priority")
                            else:
                                st.info("Low Priority")
                        
                        st.markdown("---")
                else:
                    st.markdown(f'<div class="day-header" style="opacity:0.5;">{day} - No study sessions scheduled</div>', unsafe_allow_html=True)
        else:
            st.info("No study schedule created yet. Go to 'Create Study Schedule' tab to create your schedule.")

# ========== AI ASSISTANT PAGE ==========
elif menu == "🧠 AI Assistant":
    st.markdown('<h2 class="sub-header">🧠 AI Study Assistant (Powered by Gemini)</h2>', unsafe_allow_html=True)
    
    # Check if user has profile and subjects
    if not check_user_profile_exists(st.session_state.current_user_id):
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Get user's subjects for context
    user_subjects = []
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT subject_name FROM subjects 
        WHERE user_id = ?
    ''', (st.session_state.current_user_id,))
    user_subjects = [s[0] for s in c.fetchall()]
    conn.close()
    
    if not user_subjects:
        user_subjects = ["General Studies"]
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about your studies..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant response with streaming
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                # Get response from Gemini API
                response = get_gemini_response(prompt, user_subjects)
                st.markdown(response)
        
        # Add AI response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Quick question buttons
    st.markdown("---")
    st.subheader("💡 Quick Questions")
    
    col1, col2 = st.columns(2)
    
    quick_questions = [
        ("📚 Study techniques", "What are the most effective study techniques for long-term retention?"),
        ("⏰ Time management", "How can I better manage my time between multiple subjects?"),
        ("📝 Exam preparation", "What's the best way to prepare for exams one week before?"),
        ("🧠 Memory improvement", "How can I improve my memory for studying complex concepts?"),
        ("📖 Focus techniques", "How do I stay focused while studying for long hours?"),
        ("📊 Study schedule", "How should I create an effective study schedule?"),
        ("💪 Motivation", "How do I stay motivated when studying gets difficult?"),
        ("😴 Sleep & studies", "How does sleep affect learning and how much sleep do I need?")
    ]
    
    # Display quick question buttons
    for i, (btn_text, question) in enumerate(quick_questions):
        if i % 2 == 0:
            with col1:
                if st.button(btn_text, key=f"q_{i}_{st.session_state.form_reset_key}"):
                    # Add to chat
                    st.session_state.messages.append({"role": "user", "content": question})
                    st.rerun()
        else:
            with col2:
                if st.button(btn_text, key=f"q_{i}_{st.session_state.form_reset_key}"):
                    st.session_state.messages.append({"role": "user", "content": question})
                    st.rerun()
    
    # Clear chat button
    if st.button("🗑️ Clear Chat History", type="secondary"):
        st.session_state.messages = []
        st.rerun()

# ========== EDIT PROFILE PAGE ==========
elif menu == "👤 Edit Profile":
    st.markdown('<h2 class="sub-header">👤 Edit Your Profile</h2>', unsafe_allow_html=True)
    
    # Get existing profile data
    existing_profile = get_user_profile(st.session_state.current_user_id)
    
    if not existing_profile:
        st.warning("Please complete your profile first!")
        st.session_state.current_page = "👤 Complete Profile"
        st.rerun()
    
    edit_profile_key = f"edit_profile_form_{st.session_state.form_reset_key}"
    
    with st.form(edit_profile_key, clear_on_submit=True):
        st.write("### 📝 Personal Information")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            name = st.text_input("Full Name*", 
                                value=existing_profile['name'], 
                                placeholder="Enter your full name",
                                key="edit_name")
            email = st.text_input("Email Address", 
                                 value=existing_profile['email'], 
                                 placeholder="your.email@example.com",
                                 key="edit_email")
            phone = st.text_input("Phone Number", 
                                 value=existing_profile['phone'], 
                                 placeholder="+91 9876543210",
                                 key="edit_phone")
        
        with col2:
            st.write("### 📸 Profile Photo")
            photo_file = st.file_uploader("Upload photo (jpg, png)", type=['jpg', 'jpeg', 'png'], key="edit_photo_upload")
            
            if photo_file is not None:
                st.image(photo_file, width=150)
                photo_base64 = image_to_base64(photo_file)
            elif existing_profile['photo']:
                try:
                    photo_bytes = base64.b64decode(existing_profile['photo'])
                    image = Image.open(io.BytesIO(photo_bytes))
                    st.image(image, width=150, caption="Current Photo")
                    photo_base64 = existing_profile['photo']
                except:
                    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=150)
                    photo_base64 = None
            else:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=150)
                photo_base64 = None
        
        st.markdown("---")
        st.write("### 🎯 Academic Goals")
        
        col1, col2 = st.columns(2)
        
        with col1:
            target_study_hours = st.slider(
                "Target Daily Study Hours",
                min_value=1,
                max_value=12,
                value=existing_profile['target_study_hours'],
                help="How many hours do you want to study daily?",
                key="edit_target_hours"
            )
        
        with col2:
            wakeup_time = st.time_input("Preferred Wake-up Time", 
                                       value=datetime.strptime(existing_profile['wakeup_time'], "%H:%M").time() if ':' in existing_profile['wakeup_time'] else datetime.strptime("07:00", "%H:%M").time(),
                                       key="edit_wakeup_time")
            bedtime = st.time_input("Preferred Bedtime", 
                                   value=datetime.strptime(existing_profile['bedtime'], "%H:%M").time() if ':' in existing_profile['bedtime'] else datetime.strptime("23:00", "%H:%M").time(),
                                   key="edit_bedtime")
        
        submitted = st.form_submit_button("💾 Update Profile")
        
        if submitted:
            if not name:
                st.error("Name is required!")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                
                # Update profile
                c.execute('''
                    UPDATE students 
                    SET name = ?, photo = ?, email = ?, phone = ?,
                        target_study_hours = ?, wakeup_time = ?, bedtime = ?
                    WHERE user_id = ?
                ''', (name, photo_base64, email, phone, target_study_hours, 
                      wakeup_time.strftime("%H:%M"), bedtime.strftime("%H:%M"), 
                      st.session_state.current_user_id))
                
                conn.commit()
                conn.close()
                
                st.success(f"✅ Profile updated successfully!")
                st.balloons()
                # Increment form reset key to clear form
                st.session_state.form_reset_key += 1
                st.rerun()

# ========== FOOTER ==========
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns(3)

with footer_col1:
    st.caption("🎓 AI Student Manager Pro")
    st.caption("Version 5.0")

with footer_col2:
    st.caption(f"👤 User: {st.session_state.current_user}")

with footer_col3:
    st.caption(f"📅 {datetime.now().strftime('%d %B %Y')}")
