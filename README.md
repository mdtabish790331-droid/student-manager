🎓 AI Student Manager Pro
A comprehensive student study management system built with Streamlit that helps students track their studies, exercises, and progress with AI-powered assistance.

🌟 Features
📊 Dashboard
Real-time progress tracking

Quick access to daily entries

Study hour monitoring

📚 Subjects Management
Add, edit, and delete subjects

Set weightage and difficulty levels

Track target completion dates

💪 Exercise & Wellness
Create weekly exercise routines

Track exercise completion

Set intensity and duration

📝 Daily Progress Entry
Log lecture and question hours

Track questions solved

Mood tracking and daily notes

📈 Reports & Analytics
Daily performance reports

Weekly analysis with charts

Subject-wise progress tracking

⏰ Study Planner
Create weekly study schedules

Time slot management

Priority-based planning

🧠 AI Assistant
Gemini AI-powered study assistant

Quick study tips and techniques

Personalized recommendations

🚀 Quick Start
Prerequisites
Python 3.8 or higher

Git

Streamlit account (for deployment)

Installation
Clone the repository

bash
git clone https://github.com/yourusername/student-manager.git
cd student-manager
Create virtual environment

bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
Install dependencies

bash
pip install -r requirements.txt
Run the application

bash
streamlit run app.py
📁 Project Structure
text
student-manager/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── runtime.txt           # Python version specification
├── Procfile             # Deployment configuration
├── .gitignore           # Git ignore file
├── README.md            # This file
└── student_data.db      # SQLite database (auto-generated)
🔧 Configuration
Environment Variables
Create a .env file for local development:
