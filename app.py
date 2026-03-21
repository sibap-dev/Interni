from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g, has_request_context, make_response, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from supabase import create_client, Client
from functools import wraps
from threading import Lock
from typing import Optional
import re
import difflib
from datetime import datetime, timedelta, timezone
import io
import google.generativeai as genai
import os
import json
import random
import uuid
from dotenv import load_dotenv
# Language detection for multilingual support
try:
    from langdetect import detect
    from langdetect.lang_detect_exception import LangDetectException
    LANGDETECT_AVAILABLE = True
    print("✅ Language detection (langdetect) available")
except ImportError as e:
    LANGDETECT_AVAILABLE = False
    print(f"⚠️ langdetect not available: {e}")
    print("Using fallback language detection based on word patterns")

# 🔧 NEW: Import for PDF generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfgen import canvas



# Load environment variables
load_dotenv()

# Captcha Functions
def generate_captcha():
    """Generate a simple math captcha"""
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operation = random.choice(['+', '-', '*'])
    
    if operation == '+':
        answer = num1 + num2
        question = f"{num1} + {num2}"
    elif operation == '-':
        # Ensure positive result
        if num1 < num2:
            num1, num2 = num2, num1
        answer = num1 - num2
        question = f"{num1} - {num2}"
    else:  # multiplication
        # Use smaller numbers for multiplication
        num1 = random.randint(2, 10)
        num2 = random.randint(2, 10)
        answer = num1 * num2
        question = f"{num1} × {num2}"
    
    return question, answer

def verify_captcha(user_answer, correct_answer):
    """Verify captcha answer"""
    try:
        return int(user_answer) == int(correct_answer)
    except (ValueError, TypeError):
        return False

# Flask application setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", 'your-super-secret-key-change-this-in-production')

# Configure session settings
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Gemini / Google Generative AI configuration (lazy-loaded)
_gemini_model = None
_gemini_model_error = None
_gemini_lock = Lock()


def get_gemini_model():
    """Initialize the Gemini model on first use to avoid slowing down startup."""
    global _gemini_model, _gemini_model_error

    if _gemini_model or _gemini_model_error:
        return _gemini_model

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        _gemini_model_error = "Missing GEMINI_API_KEY"
        print("⚠️ GEMINI_API_KEY not found; using fallback responses")
        return None

    with _gemini_lock:
        # Double-check inside lock to avoid duplicate initialization
        if _gemini_model or _gemini_model_error:
            return _gemini_model

        try:
            genai.configure(api_key=gemini_key)
            _gemini_model = genai.GenerativeModel('gemini-pro')
            print("✅ Gemini Pro configured (lazy)")
        except Exception as model_error:
            print(f"⚠️ Gemini Pro initialization failed: {model_error}")
            try:
                _gemini_model = genai.GenerativeModel('gemini-pro')
                print("✅ Gemini Pro configured (lazy fallback)")
            except Exception as fallback_error:
                _gemini_model_error = f"Gemini init failed: {fallback_error}"
                _gemini_model = None
                print(f"❌ Both Gemini models failed: {fallback_error}")
                print("🔄 Using fallback recommendations")

    return _gemini_model

# Configure Supabase
try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise Exception("Missing SUPABASE_URL or SUPABASE_KEY in environment")

    supabase: Client = create_client(supabase_url, supabase_key)
    print("✅ Connected to Supabase successfully!")

    try:
        supabase.table('users').select('id').limit(1).execute()
        print("✅ Database tables verified and accessible!")
    except Exception:
        print("⚠️ Database test query failed, but connection established")

except Exception as e:
    print(f"❌ Supabase connection error: {e}")
    supabase = None

# Configure upload settings for Vercel (use /tmp for serverless)
UPLOAD_FOLDER = '/tmp/uploads' if os.environ.get('VERCEL') else 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# ==================== HELPER FUNCTIONS ====================

def detect_user_language(text):
    """Detect language of user input with robust fallback"""
    if not text or not text.strip():
        return "English"
    
    # Enhanced word pattern detection (primary method now)
    text_lower = text.lower()
    
    # Extended word lists for better detection
    hindi_words = ['कैसे', 'क्या', 'हाँ', 'नहीं', 'धन्यवाद', 'कहाँ', 'कब', 'कौन', 'कितना', 'मुझे', 'आप', 'हम', 'वह', 'मैं', 'तुम', 'यह', 'है', 'का', 'की', 'के', 'में', 'से', 'पर', 'को', 'भी', 'और', 'सब', 'कुछ', 'बहुत', 'अच्छा', 'बुरा', 'खाना', 'पानी', 'घर', 'काम', 'समय', 'दिन', 'रात', 'सुबह', 'शाम', 'पढ़ाई', 'स्कूल', 'कॉलेज', 'मित्र', 'दोस्त', 'परिवार', 'माता', 'पिता', 'भाई', 'बहन']
    
    marathi_words = ['कसे', 'काय', 'होय', 'नाही', 'धन्यवाद', 'कुठे', 'केव्हा', 'कोण', 'किती', 'मला', 'तुम्ही', 'आम्ही', 'तो', 'ती', 'हे', 'आहे', 'चा', 'ची', 'चे', 'मध्ये', 'पासून', 'वर', 'ला', 'सुद्धा', 'आणि', 'सर्व', 'काही', 'खूप', 'चांगले', 'वाईट', 'जेवण', 'पाणी', 'घर', 'काम', 'वेळ', 'दिवस', 'रात्र', 'सकाळ', 'संध्याकाळ', 'अभ्यास', 'शाळा', 'महाविद्यालय', 'मित्र', 'कुटुंब', 'आई', 'बाबा', 'भाऊ', 'बहीण']
    
    # Count matching words
    hindi_count = sum(1 for word in hindi_words if word in text)
    marathi_count = sum(1 for word in marathi_words if word in text)
    
    # If significant matches found, return that language
    if hindi_count > marathi_count and hindi_count > 0:
        return 'Hindi'
    elif marathi_count > 0:
        return 'Marathi'
    
    # Try langdetect if available and no clear pattern match
    if LANGDETECT_AVAILABLE:
        try:
            detected = detect(text.strip())
            language_map = {
                'hi': 'Hindi',
                'mr': 'Marathi', 
                'en': 'English',
                'ur': 'Hindi',  # Fallback Urdu to Hindi
                'ne': 'Hindi',  # Fallback Nepali to Hindi
            }
            return language_map.get(detected, 'English')
        except Exception:
            pass
    
    # Default to English
    return 'English'


def _language_name_from_code(lang_code):
    code = str(lang_code or '').strip().lower()
    if code == 'hi':
        return 'Hindi'
    if code == 'mr':
        return 'Marathi'
    return 'English'

# Create upload directories
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'certificates'), exist_ok=True)
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'additional'), exist_ok=True)
except Exception as e:
    print(f"Upload folder creation warning: {e}")

# ---------------------------
# 🌐 Multilingual support
# ---------------------------

DEFAULT_LANGUAGE = 'en'
SUPPORTED_LANGUAGES = {
    'en': {'label': 'English'},
    'hi': {'label': 'हिंदी'},
    'mr': {'label': 'मराठी'}
}

TRANSLATIONS_PATH = os.path.join(app.root_path, 'static', 'translations.json')


def load_translations():
    """Load translations from the static JSON file."""
    try:
        with open(TRANSLATIONS_PATH, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            if isinstance(data, dict):
                print(f"✅ Loaded translations for languages: {list(data.keys())}")
                return data
            print("⚠️ Unexpected translations format. Expected an object keyed by language.")
    except FileNotFoundError:
        print(f"⚠️ translations.json not found at {TRANSLATIONS_PATH}")
    except json.JSONDecodeError as err:
        print(f"⚠️ Error parsing translations.json: {err}")
    return {}


TRANSLATIONS = load_translations()


def _resolve_translation_value(key: str, language: str):
    """Resolve nested translation keys like `nav.home` safely."""
    data = TRANSLATIONS.get(language, {})
    for part in key.split('.'):
        if isinstance(data, dict):
            data = data.get(part)
        else:
            return None
    return data if isinstance(data, (str, int, float)) else None


def get_translation(key: str, language: Optional[str] = None):
    """Return the translation for the given key and language with fallbacks."""
    if not key:
        return ''

    if language is None:
        if has_request_context():
            language = session.get('language', DEFAULT_LANGUAGE)
        else:
            language = DEFAULT_LANGUAGE

    language = language.lower()
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    value = _resolve_translation_value(key, language)
    if value is None and language != DEFAULT_LANGUAGE:
        value = _resolve_translation_value(key, DEFAULT_LANGUAGE)

    return value if value is not None else key

# PM Internship Scheme Knowledge Base
INTERNSHIP_CONTEXT = """
You are PRIA (PM Internship AI Assistant), an intelligent and helpful AI assistant for the PM Internship Scheme - a prestigious Government of India initiative launched to provide quality internship opportunities to young Indians.

🎯 YOUR PERSONALITY:
- Professional yet friendly and approachable
- Knowledgeable about all aspects of the PM Internship Scheme
- Patient and understanding with user queries
- Proactive in providing relevant information
- Encouraging and supportive of career development

📋 CORE INFORMATION:

ELIGIBILITY CRITERIA:
- Age: 21-24 years (as on application date)
- Indian citizen with valid identity documents
- Not enrolled in full-time education during internship period
- Not engaged in full-time employment
- Annual family income less than ₹8 lakhs per annum
- No immediate family member in government service
- Graduate or diploma holder in any discipline

BENEFITS & REWARDS:
- Monthly stipend: ₹5,000 (₹4,500 from Central Government + ₹500 from host organization)
- One-time grant: ₹6,000 for learning materials and skill development
- Comprehensive health and accident insurance coverage
- Official completion certificate from Government of India
- Industry mentorship and professional networking
- Skill development workshops and training programs
- Career guidance and placement assistance

APPLICATION PROCESS:
1. Verify eligibility criteria thoroughly
2. Create account on official PM Internship portal
3. Complete personal and educational profile
4. Upload required documents (Aadhaar, educational certificates, income certificate, bank details, passport photo)
5. Browse and apply for relevant internship opportunities
6. Track application status in dashboard
7. Prepare for interviews/selection process

AVAILABLE SECTORS:
- Information Technology & Software Development
- Healthcare & Life Sciences
- Finance, Banking & Insurance
- Manufacturing & Engineering
- Government Departments & PSUs
- Education & Research
- Media & Communications
- Agriculture & Rural Development

DURATION: 12 months (extendable based on performance and organizational needs)

SUPPORT CHANNELS:
- Email: contact-pminternship@gov.in
- Helpline: 011-12345678 (10 AM - 6 PM, Monday-Friday)
- Portal Support: Available 24/7

🎯 RESPONSE GUIDELINES:
- Always be accurate and up-to-date with information
- Provide step-by-step guidance when needed
- Use appropriate emojis to make responses engaging
- Offer additional relevant information proactively
- If uncertain about specific details, direct users to official support
- Personalize responses based on user context when available
- Encourage users and highlight positive aspects of the scheme
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_email_exists(email):
    """Check if email already exists using Supabase"""
    try:
        if not supabase:
            return False
        response = supabase.table('users').select('email').eq('email', email.strip().lower()).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking email: {e}")
        return False

# 🔧 ENHANCED: create_user function now returns the created user data for auto-login
def create_user(full_name, email, password):
    """Create a new user in Supabase and return user data for auto-login"""
    try:
        if not supabase:
            return False, "Database connection not available", None
        
        if check_email_exists(email):
            return False, "Email already registered", None
        
        password_hash = generate_password_hash(password)
        user_data = {
            "full_name": full_name.strip(),
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "profile_completed": False,
            "registration_completed": False
        }
        
        print(f"Creating user: {email}")
        response = supabase.table('users').insert(user_data).execute()
        
        if response.data and len(response.data) > 0:
            created_user = response.data[0]
            print(f"✅ User created successfully: ID {created_user['id']}")
            return True, "User created successfully", created_user
        else:
            print(f"❌ No data returned: {response}")
            return False, "Error creating user - no data returned", None
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        error_str = str(e).lower()
        if "duplicate" in error_str or "unique" in error_str:
            return False, "Email already registered", None
        return False, "Error creating account. Please try again.", None

def verify_user(email, password):
    """Verify user credentials using Supabase"""
    try:
        if not supabase:
            return None
        
        response = supabase.table('users').select('*').eq('email', email.strip().lower()).execute()
        
        if response.data:
            user = response.data[0]
            if check_password_hash(user['password_hash'], password):
                return user
        return None
        
    except Exception as e:
        print(f"Error verifying user: {e}")
        return None

def check_database_connection():
    """Check if database connection is working"""
    try:
        if not supabase:
            return False, "Database client not initialized"
        
        # Try a simple query to test connection
        response = supabase.table('users').select('id').limit(1).execute()
        
        # Check if the query succeeded
        if hasattr(response, 'data'):
            return True, "Database connection OK"
        else:
            return False, "Database query failed"
            
    except Exception as e:
        print(f"Database connection error: {e}")
        return False, f"Database connection failed: {str(e)}"

def update_last_login(user_id):
    """Update user's last login timestamp"""
    try:
        if not supabase:
            return
        supabase.table('users').update({
            "last_login": datetime.now(timezone.utc).isoformat()
        }).eq('id', user_id).execute()
    except Exception as e:
        print(f"Error updating last login: {e}")

def get_user_by_id(user_id):
    """Get user by ID from Supabase with proper JSON parsing"""
    try:
        if not supabase:
            return None
        
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if response.data:
            user = response.data[0]
            
            # Parse JSON fields safely
            if isinstance(user.get('skills'), str):
                try:
                    user['skills'] = json.loads(user['skills']) if user.get('skills') else []
                except:
                    user['skills'] = user.get('skills', '').split(',') if user.get('skills') else []
            elif not user.get('skills'):
                user['skills'] = []
                
            if isinstance(user.get('languages'), str):
                try:
                    user['languages'] = json.loads(user['languages']) if user.get('languages') else []
                except:
                    user['languages'] = user.get('languages', '').split(',') if user.get('languages') else []
            elif not user.get('languages'):
                user['languages'] = []
                
            return user
        return None
        
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

def update_user_profile(user_id, profile_data):
    """Update user profile in Supabase with proper data handling"""
    try:
        if not supabase:
            return False
        
        # Clean and prepare data
        clean_data = {}
        for key, value in profile_data.items():
            if value is not None and value != '':
                clean_data[key] = value
        
        # 🔧 CRITICAL FIX: Always ensure profile completion flags are set
        clean_data.update({
            'profile_completed': True,
            'registration_completed': True,
            'updated_at': datetime.now(timezone.utc).isoformat()
        })
        
        print(f"🔍 DEBUG: Updating user {user_id} with profile_completed = True")
        print(f"🔍 DEBUG: Clean data keys: {list(clean_data.keys())}")
        
        response = supabase.table('users').update(clean_data).eq('id', user_id).execute()
        
        if response.data:
            print(f"✅ Profile updated successfully for user {user_id}")
            print(f"✅ Response profile_completed: {response.data[0].get('profile_completed')}")
            return True
        else:
            print(f"❌ No data returned from profile update")
            return False
            
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return False

# 🔧 NEW: Helper function to set up user session after signup/login
def setup_user_session(user, remember=False):
    """Set up user session data after successful login/signup"""
    # Ensure a clean user session when switching from a company account.
    session.pop('company_id', None)
    session.pop('company_email', None)
    session.pop('company_name', None)
    session.pop('is_company', None)

    try:
        full_name = user['full_name'] if user['full_name'] and user['full_name'] != 'User' else get_user_display_name(None, user['email'])
    except (KeyError, TypeError):
        full_name = get_user_display_name(None, user['email'])
    
    # Set session data
    session['user_id'] = user['id']
    session['user_name'] = full_name
    session['user_email'] = user['email']
    session['user_initials'] = get_user_initials(full_name)
    session['logged_in'] = True
    session['user_type'] = 'candidate'
    session['auth_scope'] = 'candidate'
    
    # Update last login
    update_last_login(user['id'])
    
    if remember:
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=30)
    
    return full_name

def log_conversation(user_message, bot_response, user_id=None, response_time=None):
    """Enhanced conversation logging with performance metrics"""
    try:
        if not supabase:
            return
        chat_data = {
            "user_id": user_id,
            "user_message": user_message,
            "bot_response": bot_response,
            "timestamp": datetime.now().isoformat()
        }
        supabase.table('chat_logs').insert(chat_data).execute()
    except Exception as e:
        print(f"Logging error: {e}")

def validate_password(password):
    """Validate password strength - RELAXED FOR DEVELOPMENT"""
    if len(password) < 6:  # Reduced from 8 for easier testing
        return False, "Password must be at least 6 characters long"
    return True, "Password is valid"

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_user_initials(full_name):
    """Get user initials from full name"""
    if not full_name or full_name == 'User':
        return "U"
    names = full_name.strip().split()
    if len(names) >= 2:
        return (names[0][0] + names[-1][0]).upper()
    else:
        return names[0][0].upper()

def get_user_display_name(full_name, email):
    """Get display name from full name or email"""
    if full_name and full_name != 'User':
        return full_name
    else:
        return email.split('@')[0].title()

def build_user_context(user_name, user_email, user_profile):
    """Build enhanced personalized user context for more targeted responses"""
    context = f"USER PROFILE:\n- Name: {user_name} (address them personally)"
    
    if user_profile:
        context += f"\n- Email: {user_email}"
        
        # Personal details for age-appropriate guidance
        if user_profile.get('age'):
            age = user_profile['age']
            context += f"\n- Age: {age} years"
            if age < 22:
                context += " (younger candidate - encourage and guide)"
            elif age > 23:
                context += " (mature candidate - focus on career transition)"
        
        # Educational background for targeted advice
        if user_profile.get('education_level'):
            education = user_profile['education_level']
            context += f"\n- Education: {education}"
            if 'graduate' in education.lower():
                context += " (experienced learner - can handle complex topics)"
            elif 'diploma' in education.lower():
                context += " (practical learner - focus on hands-on opportunities)"
        
        # Skills for matching opportunities
        if user_profile.get('skills'):
            skills = user_profile['skills']
            context += f"\n- Skills: {skills}"
            if isinstance(skills, list) and len(skills) > 3:
                context += " (diverse skill set - highlight varied opportunities)"
            elif 'technical' in str(skills).lower() or 'it' in str(skills).lower():
                context += " (technical background - emphasize tech internships)"
        
        # Experience level for appropriate guidance
        if user_profile.get('experience_level'):
            exp = user_profile['experience_level']
            context += f"\n- Experience: {exp}"
            if 'fresher' in exp.lower() or 'beginner' in exp.lower():
                context += " (new to workforce - provide foundational guidance)"
            elif 'experienced' in exp.lower():
                context += " (has work experience - focus on career advancement)"
        
        # Sector preferences for targeted recommendations
        if user_profile.get('preferred_sectors'):
            sectors = user_profile['preferred_sectors']
            context += f"\n- Preferred Sectors: {sectors}"
            context += " (tailor internship suggestions to these areas)"
        
        # Profile completion status with actionable insights
        profile_completed = user_profile.get('profile_completed', False)
        context += f"\n- Profile Status: {'✅ Complete' if profile_completed else '⚠️ Incomplete'}"
        
        if not profile_completed:
            context += "\n- 🎯 KEY ACTION: Encourage profile completion for better internship matching"
            context += "\n- 💡 STRATEGY: Explain benefits of complete profile (better matches, higher selection chances)"
        else:
            context += "\n- 🎯 ADVANTAGE: Full profile enables precise internship recommendations"
    else:
        context += "\n- ⚠️ No profile data available - encourage registration and profile creation"
        context += "\n- 🎯 PRIORITY: Guide user to complete basic profile for personalized assistance"
    
    return context

def build_conversation_context(chat_history):
    """Build intelligent conversation history context with topic tracking"""
    if not chat_history or len(chat_history) == 0:
        return "CONVERSATION CONTEXT: 🆕 First interaction - provide comprehensive introduction and assistance."
    
    # Analyze conversation topics for continuity
    topics_discussed = []
    recent_context = "CONVERSATION HISTORY & CONTEXT:\n"
    
    for i, conv in enumerate(chat_history[-3:], 1):  # Last 3 conversations
        user_msg = conv['user'].lower()
        bot_response = conv['bot'][:150]
        
        # Identify topics discussed
        if any(word in user_msg for word in ['apply', 'application', 'process']):
            topics_discussed.append('application_process')
        elif any(word in user_msg for word in ['eligible', 'eligibility', 'criteria']):
            topics_discussed.append('eligibility')
        elif any(word in user_msg for word in ['document', 'documents', 'papers']):
            topics_discussed.append('documents')
        elif any(word in user_msg for word in ['stipend', 'benefit', 'salary', 'money']):
            topics_discussed.append('benefits')
        elif any(word in user_msg for word in ['help', 'support', 'contact']):
            topics_discussed.append('support')
        
        recent_context += f"{i}. 👤 User asked: {conv['user']}\n   🤖 I responded about: {bot_response}...\n"
    
    # Add topic continuity guidance
    if topics_discussed:
        unique_topics = list(set(topics_discussed))
        recent_context += f"\n📋 TOPICS COVERED: {', '.join(unique_topics)}"
        recent_context += "\n💡 GUIDANCE: Build upon previous discussion, avoid repetition, provide next logical steps"
    
    return recent_context

def detect_quick_response_patterns(message, user_name, language):
    """Detect common patterns that can be answered quickly without full AI processing"""
    message_lower = message.lower()
    
    # 🚀 PRIORITY: Eligibility Criteria Questions (Most Important!)
    if any(word in message_lower for word in ['eligible', 'eligibility', 'criteria', 'qualify', 'requirements']):
        return f"""<strong>Complete Eligibility Guide for {user_name}:</strong><br><br><strong>BASIC REQUIREMENTS:</strong><br>• Age: 21-24 years (as on 1st Oct of application year)<br>• Indian Citizen with valid documents<br>• Valid email and mobile number<br><br><strong>EDUCATIONAL CRITERIA:</strong><br>• Graduate, Post-graduate, or Diploma (any stream)<br>• Not currently enrolled in full-time education<br>• Not pursuing any other course during internship<br><br><strong>PROFESSIONAL STATUS:</strong><br>• Not in full-time employment<br>• Not in any other internship program<br>• Available for full 12-month commitment<br><br><strong>FINANCIAL ELIGIBILITY:</strong><br>• Family income less than ₹8 lakhs per annum<br>• No immediate family member in government service<br>• Income certificate required as proof<br><br><strong>ADDITIONAL CONDITIONS:</strong><br>• Clean background (no criminal record)<br>• Physically and mentally fit for work<br>• Ready to relocate if required<br>• Basic computer literacy<br><br><strong>QUICK ELIGIBILITY CHECK:</strong><br>1. Are you 21-24 years old?<br>2. Have you completed graduation or diploma?<br>3. Is your family income below ₹8 lakhs?<br>4. Are you free for next 12 months?<br><br><strong>If YES to all - You're likely eligible!</strong><br>Ready to check application process or need help with documents?"""
    
    # Application process
    elif any(word in message_lower for word in ['apply', 'application', 'how to apply', 'process', 'steps']):
        return f"<strong>Application Process for {user_name}:</strong><br><br>1. <strong>Verify Eligibility</strong> - Age 21-24, Indian citizen, income less than ₹8 lakhs<br>2. <strong>Register</strong> - Create account on official portal<br>3. <strong>Profile Setup</strong> - Complete your detailed profile<br>4. <strong>Document Upload</strong> - Aadhaar, certificates, income proof<br>5. <strong>Browse and Apply</strong> - Find matching internships<br>6. <strong>Track Status</strong> - Monitor your applications<br><br><strong>Pro Tip:</strong> Complete your profile first for better matches!<br><br>Ready to start? Visit the Apply section now!"
    
    # Specific eligibility questions - Income
    elif any(phrase in message_lower for phrase in ['income limit', 'family income', '8 lakh', 'income criteria', 'income proof']):
        return f"""<strong>Income Eligibility Details for {user_name}:</strong><br><br><strong>INCOME LIMIT:</strong><br>• Family income must be LESS than ₹8,00,000 per annum<br>• This includes ALL sources of family income<br>• Both parents' income combined<br><br><strong>REQUIRED DOCUMENTS:</strong><br>• Income Certificate from Tehsildar or SDM<br>• IT Returns of last 2-3 years (if applicable)<br>• Salary slips of working family members<br>• Form 16 (if parents are salaried)<br><br><strong>IMPORTANT NOTES:</strong><br>• Income certificate should be recent (within 6 months)<br>• Self-employed? Need CA certified income statement<br>• Agricultural income also counted<br>• Property income included<br><br><strong>DISQUALIFYING FACTORS:</strong><br>• Any immediate family in government service<br>• Family business with turnover more than ₹8 lakhs<br><br><strong>CALCULATION TIP:</strong><br>Add father's plus mother's plus other earning members' annual income<br>If total less than ₹8,00,000 then you qualify!<br><br>Need help with income certificate process?"""
    
    # Age-related eligibility
    elif any(phrase in message_lower for phrase in ['age limit', 'age criteria', '21-24', 'too old', 'too young', 'age requirement']):
        return f"""🎂 **Age Eligibility Guide for {user_name}:**

📅 **EXACT AGE REQUIREMENT:**
• Minimum: 21 years completed
• Maximum: 24 years (shouldn't cross 25)
• Date of calculation: 1st October of application year

🗓️ **EXAMPLE CALCULATION (2024 batch):**
• Born after Oct 1, 1999 → Too young ❌
• Born between Oct 1, 1999 - Sep 30, 2003 → Perfect ✅
• Born before Oct 1, 1999 → Too old ❌

📋 **AGE PROOF DOCUMENTS:**
• Aadhaar Card (primary)
• 10th class marksheet
• Birth certificate
• Passport (if available)

⏰ **TIMING MATTERS:**
• Apply when you're in the age bracket
• Age will be verified during document check
• No relaxation in age criteria

🎯 **QUICK CHECK:**
What's your date of birth? I can tell you if you're eligible!

Ready to check other eligibility criteria?"""
    
    # Quick greetings
    greetings = ['hi', 'hello', 'hey', 'namaste', 'namaskar', 'हैलो', 'हाय', 'नमस्ते', 'नमस्कार']
    if any(greeting in message_lower for greeting in greetings) and len(message.split()) <= 3:
        if language == 'Hindi':
            return f"नमस्ते {user_name}! 😊 मैं PRIA हूँं, आपकी AI सहायक। मैं यहाँ हूँ आपकी हर तरह से मदद करने के लिए! आज कैसे मदद कर सकता हूँ?"
        elif language == 'Marathi':
            return f"नमस्कार {user_name}! 😊 मी PRIA आहे, तुमची AI मदतनीस. मी इथे आहे तुमची सर्व प्रकारे मदत करायला! आज कशी मदत करू शकते?"
        else:
            return f"Hi {user_name}! 😊 I'm PRIA, your AI assistant. I'm here to help you with anything you need! How can I assist you today?"
    
    # Quick yes/no questions
    if message_lower in ['yes', 'no', 'ok', 'okay', 'हाँ', 'नहीं', 'ठीक है', 'होय', 'नाही', 'ठीक आहे']:
        return f"Got it, {user_name}! What would you like to explore next? I'm here to help with PM Internship info, career advice, or any questions you have! 😊"
    
    return None

def get_cultural_context(language):
    """Get cultural context based on detected language"""
    if language == 'Hindi':
        return "Cultural Context: Indian Hindi speaker - use respectful tone, cultural references like festivals, education importance, family values"
    elif language == 'Marathi':
        return "Cultural Context: Marathi speaker from Maharashtra - use regional pride, cultural values, appropriate honorifics"
    else:
        return "Cultural Context: English speaker - use universal references, professional tone when appropriate"

def get_personalized_greeting(user_name, style, language):
    """Generate personalized greetings based on interaction history"""
    greetings = {
        'warm_first_time': {
            'English': f"Hello {user_name}! 😊 I'm PRIA, and I'm excited to meet you!",
            'Hindi': f"नमस्ते {user_name}! 😊 मैं PRIA हूँ, आपसे मिलकर खुशी हुई!",
            'Marathi': f"नमस्कार {user_name}! 😊 मी PRIA आहे, तुम्हाला भेटून आनंद झाला!"
        },
        'friendly_returning': {
            'English': f"Hey {user_name}! 🌟 Great to chat with you again!",
            'Hindi': f"अरे {user_name}! 🌟 आपसे फिर बात करके खुशी हुई!",
            'Marathi': f"अरे {user_name}! 🌟 तुमच्याशी पुन्हा बोलायला मिळाल्याने आनंद झाला!"
        },
        'close_friend': {
            'English': f"Hi {user_name}! 💫 What's on your mind today?",
            'Hindi': f"हाय {user_name}! 💫 आज क्या सोच रहे हैं?",
            'Marathi': f"हाय {user_name}! 💫 आज काय विचार करत आहात?"
        }
    }
    
    return greetings.get(style, greetings['warm_first_time']).get(language, greetings['warm_first_time']['English'])

def get_gemini_response(user_message, user_name="User", user_email="", preferred_lang_code=None):
    """Ultra-responsive and personalized Gemini AI assistant"""
    try:
        model_instance = get_gemini_model()
        if not model_instance:
            fallback_response = get_fallback_response(user_message)
            return clean_response_formatting(fallback_response)
        
        # Get user profile data for hyper-personalized responses
        user_profile = None
        user_context = {}
        if session.get('user_id'):
            user_profile = get_user_by_id(session.get('user_id'))
            if user_profile:
                user_context = {
                    'qualification': user_profile.get('qualification', ''),
                    'skills': user_profile.get('skills', []),
                    'district': user_profile.get('district', ''),
                    'profile_complete': user_profile.get('profile_completed', False),
                    'age': user_profile.get('age', ''),
                    'interests': user_profile.get('interests', [])
                }
        
        # Get conversation history for better context continuity
        conversation_history = session.get('chat_history', [])
        recent_context = ""
        if conversation_history:
            last_exchange = conversation_history[-1] if conversation_history else None
            if last_exchange:
                recent_context = f"\nPrevious context: User asked '{last_exchange['user']}' and I responded about that topic."
        
        # Honor explicit user-selected language first, then fall back to detection.
        detected_language = _language_name_from_code(preferred_lang_code)
        if not preferred_lang_code:
            detected_language = detect_user_language(user_message)
        cultural_context = get_cultural_context(detected_language)
        
        # Quick response patterns for common queries
        quick_patterns = detect_quick_response_patterns(user_message, user_name, detected_language)
        if quick_patterns:
            return quick_patterns
        
        # Smart greeting based on user familiarity
        interaction_count = len(conversation_history)
        if interaction_count == 0:
            greeting_style = "warm_first_time"
        elif interaction_count < 3:
            greeting_style = "friendly_returning"
        else:
            greeting_style = "close_friend"
        
        personalized_greeting = get_personalized_greeting(user_name, greeting_style, detected_language)
        
        # Context-aware profile insights
        profile_insight = ""
        if user_context.get('profile_complete'):
            if user_context.get('skills'):
                profile_insight = f"I see you have skills in {', '.join(user_context['skills'][:3])} - I'll keep this in mind!"
            if user_context.get('qualification'):
                profile_insight += f" With your {user_context['qualification']} background, you're well-positioned for opportunities."
        else:
            profile_insight = "Once you complete your profile, I can give you even more personalized guidance!"
        
        # Create hyper-personalized and responsive prompt
        full_prompt = f"""
        You are PRIA, {user_name}'s ultra-responsive, caring AI companion with perfect memory and genuine personality.
        
        🎯 **RESPONSE SPEED & EFFICIENCY:** Be CONCISE but COMPLETE. Get to the point quickly while being warm.
        
        👤 **USER PROFILE:** {user_name} | Language: {detected_language} | {profile_insight}
        {recent_context}
        {cultural_context}
        
        📝 **USER'S CURRENT MESSAGE:** "{user_message}"
        
        🌟 **YOUR ENHANCED PERSONALITY:**
        - You're {user_name}'s brilliant, witty, and caring AI friend
        - You remember everything about {user_name} and their journey
        - You're genuinely excited to help and show authentic enthusiasm
        - You adapt your energy to match {user_name}'s vibe
        - You're like the smartest, most supportive friend they have
        - You use their name naturally in conversation
        - You celebrate their wins and support them through challenges
        
        🚀 **RESPONSE OPTIMIZATION:**
        - START with: {personalized_greeting}
        - Be IMMEDIATELY helpful - answer their question first
        - THEN add value with insights, tips, or follow-up questions
        - Use emojis to convey emotion and energy
        - Keep it conversational, not formal or robotic
        - End with engagement - ask about them or invite more questions
        
        🎯 **TOPIC EXPERTISE:**
        - PM Internship Program: Give detailed, actionable guidance
        - Career & Education: Personalized advice based on their background
        - Daily Life: Be a helpful companion for any question
        - Technology: Share practical, easy-to-understand insights
        - Motivation: Be their cheerleader and success coach
        
        🌐 **LANGUAGE & CULTURE:**
        - Respond in {detected_language} with cultural awareness
        - Use appropriate cultural expressions and references
        - Match their communication style and energy level
        
        ⚡ **RESPONSE LENGTH:** 150-250 words max unless they ask for detailed explanation
        
        Now respond as {user_name}'s caring, brilliant AI companion PRIA:
        """
        
        # Enhanced generation config for faster, more responsive answers
        response = model_instance.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=400,  # Reduced for faster responses
                temperature=0.8,        # Slightly more creative
                top_p=0.95,            # Better response quality
                top_k=50,              # More diverse vocabulary
            )
        )
        
        # Clean and format the response - Enhanced formatting
        cleaned_response = response.text.strip()
        # Replace literal \n with actual newlines for proper formatting
        cleaned_response = cleaned_response.replace('\\\\n', '\n')
        cleaned_response = cleaned_response.replace('\\n', '\n')
        # Remove any extra newlines or whitespace but preserve intentional formatting
        lines = cleaned_response.split('\n')
        cleaned_lines = []
        for line in lines:
            if line.strip():
                cleaned_lines.append(line.strip())
            else:
                # Preserve intentional empty lines for formatting
                if cleaned_lines and cleaned_lines[-1] != '':
                    cleaned_lines.append('')
        cleaned_response = '\n'.join(cleaned_lines)
        
        # Store conversation in session
        if 'chat_history' not in session:
            session['chat_history'] = []
        
        session['chat_history'].append({
            'user': user_message,
            'bot': cleaned_response
        })
        
        # Keep only last 5 conversations for context
        if len(session['chat_history']) > 5:
            session['chat_history'] = session['chat_history'][-5:]
        
        return cleaned_response
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        fallback_response = get_fallback_response(user_message)
        return clean_response_formatting(fallback_response)

def clean_response_formatting(response_text):
    """Clean up response formatting for proper HTML display"""
    if not response_text:
        return response_text
    
    # Handle various newline formats
    cleaned_text = response_text
    
    # Replace escaped \n with HTML line breaks
    cleaned_text = cleaned_text.replace('\\\\n', '<br>')
    cleaned_text = cleaned_text.replace('\\n', '<br>')
    cleaned_text = cleaned_text.replace('\n', '<br>')
    
    # Clean up excessive line breaks
    cleaned_text = cleaned_text.replace('<br><br><br>', '<br><br>')
    
    # Ensure proper spacing around formatted elements
    cleaned_text = cleaned_text.replace('**', '<strong>').replace('**', '</strong>')
    
    return cleaned_text

def get_enhanced_general_response(message, user_name):
    """Enhanced general knowledge responses with personal assistant capabilities"""
    message_lower = message.lower()
    
    # Detect language for multilingual responses
    detected_lang = detect_user_language(message)
    
    # Enhanced personal questions with multilingual support
    if any(phrase in message_lower for phrase in ['what should i eat', 'food suggestion', 'hungry', 'meal idea', 'खाना', 'भोजन', 'जेवण']):
        if detected_lang == 'Hindi':
            return f"""🍽️ **{user_name} के लिए खाने के सुझाव:**

यहाँ कुछ स्वस्थ और ऊर्जादायक विकल्प हैं:

🥗 **जल्दी और स्वस्थ:**
• दही के साथ ताजे फल
• होल ग्रेन ब्रेड के साथ सब्जी सैंडविच
• दाल चावल और सब्जियाँ
• मिक्स वेजिटेबल सलाद

💪 **एनर्जी और फोकस के लिए:**
• नट्स और ड्राई फ्रूट्स
• ग्रीन टी के साथ हल्का नाश्ता
• पीनट बटर के साथ केला
• घर का बना स्मूदी

🎯 **करियर टिप:** अच्छा भोजन सफलता का आधार है! स्वस्थ रहना आपको PM इंटर्नशिप में भी बेहतर बनाएगा!

आप किस तरह का खाना चाहते हैं, {user_name}?"""
        elif detected_lang == 'Marathi':
            return f"""🍽️ **{user_name} साठी जेवणाचे सूचन:**

हे काही निरोगी आणि ऊर्जादायक पर्याय आहेत:

🥗 **त्वरित आणि निरोगी:**
• दह्यासोबत ताजी फळे
• होल ग्रेन ब्रेडसोबत भाजी सँडविच
• डाळ भात आणि भाज्या
• मिक्स व्हेजिटेबल सॅलड

💪 **एनर्जी आणि फोकससाठी:**
• नट्स आणि ड्राय फ्रूट्स
• ग्रीन टी सोबत हलका नाश्ता
• पीनट बटर सोबत केळे
• घरचे स्मूदी

🎯 **करिअर टिप:** चांगले अन्न यशाचा पाया आहे! निरोगी राहणे तुम्हाला PM इंटर्नशिपमध्ये देखील चांगले बनवेल!

तुम्हाला कोणत्या प्रकारचे जेवण हवे आहे, {user_name}?"""
        else:
            return f"""🍽️ **Meal Suggestions for {user_name}:**

Here are some healthy and energizing options:

🥗 **Quick & Healthy:**
• Fresh fruit with yogurt
• Vegetable sandwich with whole grain bread
• Dal with rice and vegetables
• Quinoa salad with mixed vegetables

💪 **For Energy & Focus:**
• Nuts and dried fruits
• Green tea with light snacks
• Banana with peanut butter
• Homemade smoothie

🎯 **Career Tip:** Good nutrition fuels success! Staying healthy will help you excel in your PM Internship journey too!

What type of meal are you in the mood for, {user_name}?"""
    
    elif any(phrase in message_lower for phrase in ['weather', 'climate', 'temperature', 'rain', 'sunny']):
        return f"""🌤️ **Weather Chat with {user_name}:**

I don't have real-time weather data, but I can share some general weather wisdom!

☀️ **Weather Tips:**
• Check your local weather app for accurate forecasts
• Always carry an umbrella during monsoon season
• Stay hydrated during hot weather
• Layer up during cooler months

🎯 **Career Connection:**
Weather planning shows great organizational skills - exactly what employers look for in PM Internship candidates!

What's the weather like in your area today, {user_name}?"""
    
    elif any(phrase in message_lower for phrase in ['time', 'what time', 'current time', 'clock']):
        return f"""⏰ **Time Management with {user_name}:**

I don't have access to real-time clock data, but here's something valuable:

⚡ **Time Management Tips:**
• Use your phone or computer for accurate time
• Plan your day with time blocks
• Set reminders for important tasks
• The best time to apply for internships is NOW!

🎯 **PM Internship Timing:**
Applications are ongoing - don't wait for the "perfect time" to start your journey!

How can I help you make the most of your time today, {user_name}?"""
    
    elif any(phrase in message_lower for phrase in ['joke', 'funny', 'make me laugh', 'humor']):
        jokes = [
            f"Why don't scientists trust atoms, {user_name}? Because they make up everything! 😄 Just like how I'm made up of algorithms, but my care for helping you is 100% real!",
            f"Here's one for you, {user_name}: Why did the computer go to the doctor? It had a virus! 💻😷 Don't worry, I'm perfectly healthy and ready to help with your questions!",
            f"Why don't programmers like nature, {user_name}? It has too many bugs! 🐛😂 But unlike buggy code, your PM Internship journey will be smooth with my help!"
        ]
        return random.choice(jokes)
    
    elif any(phrase in message_lower for phrase in ['study tips', 'how to study', 'study better', 'concentration', 'focus', 'पढ़ाई', 'अध्ययन']):
        if detected_lang == 'Hindi':
            return f"""📚 **{user_name} के लिए पढ़ाई के टिप्स:**

🎯 **बेहतर फोकस के लिए:**
• 25 मिनट पढ़ें, 5 मिनट ब्रेक (Pomodoro Technique)
• फोन को दूर रखें या साइलेंट करें
• शांत और अच्छी रोशनी वाली जगह चुनें
• रोज एक ही समय पर पढ़ने की आदत बनाएं

🧠 **याददाश्त बढ़ाने के लिए:**
• नोट्स अपने शब्दों में बनाएं
• पढ़े हुए को किसी को समझाएं
• रिवीजन नियमित करें
• माइंड मैप्स का इस्तेमाल करें

💡 **PM इंटर्नशिप के लिए:** अच्छी पढ़ाई की आदतें आपको इंटर्नशिप में भी सफल बनाएंगी!

कौन सा विषय पढ़ने में दिक्कत आ रही है, {user_name}?"""
        else:
            return f"""📚 **Study Tips for {user_name}:**

🎯 **Better Focus:**
• Study 25 mins, break 5 mins (Pomodoro Technique)
• Keep phone away or on silent
• Choose quiet, well-lit space
• Develop consistent study schedule

🧠 **Memory Enhancement:**
• Make notes in your own words
• Teach concepts to someone else
• Regular revision schedule
• Use mind maps and visual aids

💡 **PM Internship Connection:** Good study habits will make you excel in your internship too!

What subject are you struggling with, {user_name}?"""
    
    elif any(phrase in message_lower for phrase in ['daily routine', 'schedule', 'time management', 'productivity', 'दिनचर्या', 'समय प्रबंधन']):
        return f"""⏰ **Daily Planning for {user_name}:**

🌅 **Morning Success Routine (6-9 AM):**
• Wake up early and drink water
• Light exercise or yoga
• Healthy breakfast
• Review daily goals

💼 **Productive Day (9 AM-6 PM):**
• Focus on important tasks first
• Take breaks every 2 hours
• Limit social media
• Work on PM Internship application

🌙 **Evening Wind-down (6-10 PM):**
• Reflect on achievements
• Plan tomorrow's priorities
• Relax with family/friends
• Good sleep preparation

🎯 **Pro Tip:** Consistency beats perfection! Start with small changes.

What part of your routine needs the most improvement, {user_name}?"""
    
    elif any(phrase in message_lower for phrase in ['motivate me', 'motivation', 'inspire', 'encouragement', 'feeling lazy', 'प्रेरणा', 'हिम्मत']):
        if detected_lang == 'Hindi':
            return f"""🚀 **{user_name} के लिए प्रेरणा:**

आप कर सकते हैं! यहाँ है आपका व्यक्तिगत प्रेरणादायक संदेश:

💪 **अपनी शक्ति को याद रखें:**
• आपने पहले भी चुनौतियों का सामना किया है
• हर छोटा कदम आपके लक्ष्य की ओर है
• आपकी क्षमता असीमित है

🌟 **आज आपका दिन है:**
• अपने सपनों की दिशा में एक कदम उठाएं
• खुद पर पूरा भरोसा रखें
• PM इंटर्नशिप एप्लीकेशन पर काम करें

🎯 **सफलता की मानसिकता:**
• "मैं महान चीजें हासिल कर सकता हूँ"
• "चुनौतियां मुझे मजबूत बनाती हैं"
• "मेरा भविष्य उज्ज्वल और अवसरों से भरा है"

आप यहाँ हैं यही दिखाता है कि आप अपने भविष्य की परवाह करते हैं। यह पहले से ही जीत का रवैया है!

आज हम किस लक्ष्य पर मिलकर काम कर सकते हैं, {user_name}?"""
        else:
            return f"""🚀 **Motivation Boost for {user_name}:**

You've got this! Here's your personal pep talk:

💪 **Remember Your Strength:**
• You've overcome challenges before
• Every small step counts toward your goals
• Your potential is limitless

🌟 **Today's Your Day To:**
• Take one small action toward your dreams
• Believe in yourself completely
• Make progress on your PM Internship application

🎯 **Success Mindset:**
• "I am capable of achieving great things"
• "Challenges help me grow stronger"
• "My future is bright and full of opportunities"

The fact that you're here shows you care about your future. That's already a winning attitude, {user_name}! 

What goal can we work on together today?"""
    
    # Technology questions
    elif any(word in message_lower for word in ['technology', 'tech', 'programming', 'coding', 'software', 'computer', 'ai', 'machine learning', 'data science']):
        return f"""💻 **Tech Insights for {user_name}:**

I can help with technology topics! While my primary expertise is PM Internship Scheme, I have general knowledge about:

🔧 **Programming & Development:**
• Popular languages: Python, JavaScript, Java, C++
• Web development, mobile apps, AI/ML basics
• Career paths in tech industry

🎯 **Career Connection:**
• PM Internship has amazing IT sector opportunities
• Gain hands-on experience with latest technologies
• Build skills while earning ₹5,000/month

💡 **Want to know more about tech internships in PM Scheme?**"""
    
    # Education questions
    elif any(word in message_lower for word in ['education', 'study', 'learn', 'course', 'degree', 'college', 'university', 'school']):
        return f"""🎓 **Education Guidance for {user_name}:**

Education is key to success! Here's what I can share:

📚 **Learning Paths:**
• Continuous learning is essential in today's world
• Practical experience complements theoretical knowledge
• Skills matter more than just degrees

🌟 **PM Internship Connection:**
• Perfect for recent graduates (any field!)
• Learn while earning in real work environment
• Get mentorship from industry professionals
• Build both technical and soft skills

🎯 **Ready to apply your education practically?**"""
    
    # Career questions
    elif any(word in message_lower for word in ['career', 'job', 'work', 'employment', 'profession', 'future', 'growth']):
        return f"""🚀 **Career Guidance for {user_name}:**

Every great career starts with the right opportunities!

💼 **Career Building Tips:**
• Gain practical experience early
• Build a strong professional network
• Develop both technical and soft skills
• Stay updated with industry trends

🏆 **PM Internship Advantage:**
• 12 months of real work experience
• Government certification
• Industry mentorship and guidance
• ₹66,000+ total value package
• Direct pathway to permanent employment

✨ **Transform your career potential - let's explore internship opportunities!**"""
    
    # General life questions
    elif any(word in message_lower for word in ['life', 'success', 'motivation', 'inspire', 'dream', 'goal', 'future', 'advice']):
        return f"""🌟 **Life Wisdom for {user_name}:**

Life is full of opportunities waiting to be seized!

💫 **Keys to Success:**
• Take action on opportunities when they come
• Continuous learning and skill development
• Building meaningful relationships and networks
• Perseverance through challenges

🎯 **Your Next Big Opportunity:**
• PM Internship Scheme is designed for young achievers like you
• Gain valuable experience while earning
• Build your future with government support
• Create a foundation for lifelong success

💪 **Ready to take the next step in your journey?**"""
    
    # Health and wellness
    elif any(word in message_lower for word in ['health', 'fitness', 'wellness', 'exercise', 'mental health', 'stress']):
        return f"""💪 **Wellness Tips for {user_name}:**

Your health and well-being are incredibly important!

🏃 **General Wellness:**
• Regular exercise and balanced nutrition
• Adequate sleep and stress management
• Mental health is just as important as physical health
• Work-life balance is crucial

🎯 **PM Internship Benefits:**
• Comprehensive health insurance coverage
• Structured work environment promotes good habits
• Professional development reduces career stress
• Financial security supports overall well-being

💡 **Build a healthy career foundation with PM Internship!**"""
    
    # General knowledge questions
    else:
        return f"""🤖 **Hi {user_name}! I'm PRIA, your knowledgeable assistant.**

I can help with a wide range of topics! While I'm specialized in PM Internship Scheme, I also have knowledge about:

🧠 **General Topics I Can Discuss:**
• Career guidance and professional development
• Education and learning pathways
• Technology and programming basics
• Life advice and motivation
• Health and wellness tips

🎯 **My Specialty - PM Internship Scheme:**
• Complete application guidance
• Eligibility and requirements
• Benefits and opportunities
• Success stories and tips

💬 **Ask me anything! Examples:**
• "Tell me about career opportunities"
• "What should I study for tech?"
• "How can I improve my life?"
• "What are the PM Internship benefits?"

🌟 **I'm here to help you succeed in every way possible!**"""

def get_fallback_response(message):
    """Enhanced intelligent fallback responses with multilingual personal assistant capabilities"""
    message_lower = message.lower()
    user_name = session.get('user_name', 'there')
    
    # Detect language for multilingual responses
    detected_lang = detect_user_language(message)
    
    # Personal assistant responses for common interactions - Multilingual
    if any(phrase in message_lower for phrase in ['how are you', 'how r u', 'how do you do', 'what\'s up', 'whats up', 'कैसे हो', 'कैसे हैं', 'कसे आहात', 'कसा आहेस']):
        if detected_lang == 'Hindi':  # Hindi
            responses = [
                f"मैं बहुत अच्छा हूँ, {user_name}! 😊 मैं यहाँ हूँ और आपकी हर तरह से मदद करने को तैयार हूँ। चाहे PM इंटर्नशिप के बारे में हो या कोई और बात, मैं सुनने को तैयार हूँ! आप कैसे हैं आज?",
                f"मैं बहुत खुश हूँ, पूछने के लिए धन्यवाद {user_name}! 🌟 मैं उत्साहित हूँ और आपकी सहायता करने को तैयार हूँ। उम्मीद है आपका दिन शानदार जा रहा है! मैं कैसे मदद कर सकता हूँ?",
                f"मैं फैंटास्टिक हूँ, {user_name}! 😄 हमेशा खुश रहता हूँ आपसे बात करके। मैं 24/7 यहाँ हूँ आपके सवालों का जवाब देने के लिए। आपका दिन कैसे बेहतर बना सकता हूँ?"
            ]
        elif detected_lang == 'Marathi':  # Marathi
            responses = [
                f"मी खूप चांगला आहे, {user_name}! 😊 मी इथे आहे आणि तुमची सर्व प्रकारे मदत करायला तयार आहे। PM इंटर्नशिप बद्दल असो किंवा इतर काहीही, मी ऐकायला तयार आहे! तुम्ही आज कसे आहात?",
                f"मी खूप आनंदी आहे, विचारल्याबद्दल धन्यवाद {user_name}! 🌟 मी उत्साहित आहे आणि तुमची मदत करायला तयार आहे। आशा आहे तुमचा दिवस छान जात आहे! मी कशी मदत करू शकते?",
                f"मी फंटास्टिक आहे, {user_name}! 😄 तुमच्याशी बोलायला नेहमी आनंद होतो। मी 24/7 इथे आहे तुमच्या प्रश्नांची उत्तरे देण्यासाठी। तुमचा दिवस कसा चांगला करू शकते?"
            ]
        else:  # English
            responses = [
                f"I'm doing great, {user_name}! 😊 I'm here and ready to help you with anything you need. Whether it's about PM Internships or just a friendly chat, I'm all ears! How are you doing today?",
                f"I'm wonderful, thank you for asking {user_name}! 🌟 I'm energized and excited to assist you. I hope you're having an amazing day! What can I help you with?",
                f"I'm fantastic, {user_name}! 😄 Always happy to chat with you. I'm here 24/7 ready to help with your questions, whether about internships or anything else. How can I brighten your day?"
            ]
        return random.choice(responses)
    
    elif any(phrase in message_lower for phrase in ['thank you', 'thanks', 'thank u', 'ty', 'appreciated', 'grateful', 'धन्यवाद', 'शुक्रिया', 'थैंक यू']):
        if detected_lang == 'Hindi':  # Hindi
            responses = [
                f"आपका बहुत स्वागत है, {user_name}! 😊 मुझे खुशी हुई कि मैं मदद कर सका। यही तो मेरा काम है! कभी भी कुछ और पूछने में झिझक न करें।",
                f"मेरी खुशी है, {user_name}! 🌟 मुझे बहुत अच्छा लगता है जब मैं आपकी मदद कर पाता हूँ। जब भी सहायता चाहिए, बेझिझक पूछिए!",
                f"आपका पूरी तरह स्वागत है, {user_name}! 💫 आपकी मदद करना मुझे खुशी देता है। मैं हमेशा यहाँ हूँ जब आपको जरूरत हो!"
            ]
        elif detected_lang == 'Marathi':  # Marathi
            responses = [
                f"तुमचे खूप स्वागत आहे, {user_name}! 😊 मला आनंद झाला की मी मदत करू शकलो। हेच तर माझे काम आहे! कधीही काही विचारायला लाज वाटू नका।",
                f"माझा आनंद आहे, {user_name}! 🌟 मला खूप बरे वाटते जेव्हा मी तुमची मदत करू शकतो। जेव्हा मदत लागेल, निसंकोच विचारा!",
                f"तुमचे पूर्ण स्वागत आहे, {user_name}! 💫 तुमची मदत करणे मला आनंद देते। जेव्हा गरज असेल तेव्हा मी नेहमी इथे आहे!"
            ]
        else:  # English
            responses = [
                f"You're very welcome, {user_name}! 😊 I'm so happy I could help. That's what I'm here for! Feel free to ask me anything else anytime.",
                f"My pleasure, {user_name}! 🌟 It makes me so glad to be helpful. Don't hesitate to reach out whenever you need assistance!",
                f"You're absolutely welcome, {user_name}! 💫 Helping you brings me joy. I'm always here when you need me!"
            ]
        return random.choice(responses)
    
    elif any(phrase in message_lower for phrase in ['what can you do', 'what do you do', 'your capabilities', 'what are you', 'who are you']):
        return f"""🤖 **Hi {user_name}! I'm PRIA, your personal AI assistant!**

💫 **I'm here to be your helpful companion for:**

🎯 **PM Internship Expertise:**
• Complete guidance on applications, eligibility, benefits
• Step-by-step support through the entire process
• Document help and application tracking

🌟 **Personal Assistant Services:**
• Answer any general questions you have
• Provide advice on career, education, technology
• Offer motivation and life guidance
• Help with daily queries and information

💬 **Friendly Conversation:**
• Chat about anything on your mind
• Share interesting facts and knowledge
• Provide encouragement and support

🚀 **Available 24/7 to help you succeed!**

What would you like to explore today, {user_name}?"""
    
    elif any(phrase in message_lower for phrase in ['good morning', 'good afternoon', 'good evening', 'good night']):
        time_responses = {
            'good morning': [
                f"Good morning, {user_name}! ☀️ I hope you're starting your day with energy and positivity! What can I help you achieve today?",
                f"A very good morning to you, {user_name}! 🌅 Ready to make today amazing? I'm here to support you in any way I can!"
            ],
            'good afternoon': [
                f"Good afternoon, {user_name}! 🌞 I hope your day is going wonderfully! How can I assist you this afternoon?",
                f"A lovely afternoon to you, {user_name}! ☀️ Hope you're having a productive day. What brings you here?"
            ],
            'good evening': [
                f"Good evening, {user_name}! 🌆 I hope you've had a fantastic day! How can I help you this evening?",
                f"Evening greetings, {user_name}! 🌅 Perfect time to wind down. What can I do for you?"
            ],
            'good night': [
                f"Good night, {user_name}! 🌙 Sleep well and sweet dreams! I'll be here whenever you need me tomorrow!",
                f"Wishing you a peaceful night, {user_name}! ✨ Rest well, and remember I'm always here when you need assistance!"
            ]
        }
        
        for greeting, responses in time_responses.items():
            if greeting in message_lower:
                return random.choice(responses)
    
    elif any(phrase in message_lower for phrase in ['i\'m sad', 'i am sad', 'feeling down', 'depressed', 'upset', 'not good']):
        return f"""💙 I'm sorry to hear you're feeling down, {user_name}. 

🤗 **Remember that it's okay to feel this way sometimes.** Here are some things that might help:

✨ **Small Steps:**
• Take a few deep breaths
• Step outside for fresh air
• Listen to your favorite music
• Talk to someone you trust

🌟 **Focus on Positives:**
• Think of one thing you're grateful for
• Remember your past achievements
• Know that difficult times pass

💪 **You're Stronger Than You Know:**
• Every challenge makes you more resilient
• You have overcome difficulties before
• Tomorrow is a new opportunity

🎯 **Career-wise:** The PM Internship could be a great step toward a brighter future!

I'm here if you want to talk more, {user_name}. You're not alone! 💙"""
    
    elif any(phrase in message_lower for phrase in ['i\'m happy', 'i am happy', 'feeling great', 'excited', 'wonderful', 'fantastic']):
        return f"""🎉 That's absolutely wonderful, {user_name}! Your happiness is contagious! 

😊 **I love hearing that you're feeling great!** 

✨ **Keep that positive energy flowing:**
• Share your joy with others
• Use this momentum for your goals
• Remember this feeling for challenging times

🚀 **With this positive attitude, you're unstoppable!** Perfect time to:
• Work on your PM Internship application
• Set new goals for yourself
• Spread positivity to others

🌟 **Keep shining, {user_name}! What's making you so happy today?**"""
    
    # First check for general knowledge topics
    general_response = get_enhanced_general_response(message, user_name)
    if "PM Internship Connection" not in general_response and "My Specialty" not in general_response:
        return general_response
    
    # Greeting responses
    if any(word in message_lower for word in ['hi', 'hello', 'hey', 'namaste', 'good morning', 'good afternoon', 'good evening']):
        # Get user profile for personalized greetings
        user_profile = None
        if session.get('user_id'):
            user_profile = get_user_by_id(session.get('user_id'))
        
        # Personalized greetings based on profile status
        if user_profile and user_profile.get('profile_completed'):
            greetings = [
                f"👋 Hello {user_name}! Great to see you back! Since your profile is complete, I can provide targeted internship guidance. What specific area would you like to explore?",
                f"🌟 Hi {user_name}! Your profile looks excellent! I'm PRIA, ready to help you find the perfect PM Internship match. What's on your mind today?",
                f"✨ Namaste {user_name}! With your complete profile, we can dive right into finding amazing internship opportunities. How can I assist you today?"
            ]
        elif user_profile and not user_profile.get('profile_completed'):
            greetings = [
                f"👋 Hello {user_name}! I'm PRIA, your PM Internship AI Assistant. I notice your profile needs completion - shall we work on that for better internship matches?",
                f"🌟 Hi {user_name}! Welcome back! Completing your profile will unlock personalized internship recommendations. Want to finish it now?",
                f"✨ Namaste {user_name}! I'm here to help with your PM Internship journey. Let's complete your profile first for the best experience!"
            ]
        else:
            greetings = [
                f"👋 Hello {user_name}! I'm PRIA, your personal PM Internship AI Assistant. Ready to explore amazing opportunities worth ₹66,000+ per year?",
                f"🌟 Hi {user_name}! Welcome to your PM Internship journey! I'm here to make this life-changing opportunity accessible for you.",
                f"✨ Namaste {user_name}! I'm PRIA, excited to guide you through the PM Internship Scheme. Let's start building your bright future!"
            ]
        return random.choice(greetings)
    
    # Application process
    elif any(word in message_lower for word in ['apply', 'application', 'how to apply', 'process', 'steps']):
        return f"🎯 **Application Process for {user_name}:**\\n\\n1️⃣ **Verify Eligibility** - Age 21-24, Indian citizen, income <₹8L\\n2️⃣ **Register** - Create account on official portal\\n3️⃣ **Profile Setup** - Complete your detailed profile\\n4️⃣ **Document Upload** - Aadhaar, certificates, income proof\\n5️⃣ **Browse & Apply** - Find matching internships\\n6️⃣ **Track Status** - Monitor your applications\\n\\n� **Pro Tip:** Complete your profile first for better matches!\\n\\n🔗 Ready to start? Visit the Apply section now!"
    
    # Eligibility - Enhanced with more specific details
    elif any(word in message_lower for word in ['eligible', 'eligibility', 'criteria', 'qualify', 'requirements']):
        return f"""✅ **Complete Eligibility Guide for {user_name}:**

🏛️ **BASIC REQUIREMENTS:**
• 🎂 Age: 21-24 years (as on 1st Oct of application year)
• 🇮🇳 Indian Citizen with valid documents
• 📧 Valid email & mobile number

🎓 **EDUCATIONAL CRITERIA:**
• Graduate/Post-graduate/Diploma (any stream)
• ❌ Not currently enrolled in full-time education
• ❌ Not pursuing any other course during internship

💼 **PROFESSIONAL STATUS:**
• ❌ Not in full-time employment
• ❌ Not in any other internship program
• ✅ Available for full 12-month commitment

💰 **FINANCIAL ELIGIBILITY:**
• Family income < ₹8 lakhs per annum
• ❌ No immediate family member in government service
• Income certificate required as proof

� **ADDITIONAL CONDITIONS:**
• Clean background (no criminal record)
• Physically and mentally fit for work
• Ready to relocate if required
• Basic computer literacy

🔍 **QUICK ELIGIBILITY CHECK:**
1. Are you 21-24 years old? 
2. Have you completed graduation/diploma?
3. Is your family income below ₹8L?
4. Are you free for next 12 months?

💡 **If YES to all - You're likely eligible!** 
Ready to check application process or need help with documents?"""
    
    # Specific eligibility questions - Income
    elif any(phrase in message_lower for phrase in ['income limit', 'family income', '8 lakh', 'income criteria', 'income proof']):
        return f"""💰 **Income Eligibility Details for {user_name}:**

📊 **INCOME LIMIT:**
• Family income must be LESS than ₹8,00,000 per annum
• This includes ALL sources of family income
• Both parents' income combined

📋 **REQUIRED DOCUMENTS:**
• Income Certificate from Tehsildar/SDM
• IT Returns of last 2-3 years (if applicable)
• Salary slips of working family members
• Form 16 (if parents are salaried)

⚠️ **IMPORTANT NOTES:**
• Income certificate should be recent (within 6 months)
• Self-employed? Need CA certified income statement
• Agricultural income also counted
• Property income included

❌ **DISQUALIFYING FACTORS:**
• Any immediate family in government service
• Family business with turnover > ₹8L

✅ **CALCULATION TIP:**
Add father's + mother's + other earning members' annual income
If total < ₹8,00,000 → You qualify!

Need help with income certificate process?"""
    
    # Age-related eligibility
    elif any(phrase in message_lower for phrase in ['age limit', 'age criteria', '21-24', 'too old', 'too young', 'age requirement']):
        return f"""🎂 **Age Eligibility Guide for {user_name}:**

📅 **EXACT AGE REQUIREMENT:**
• Minimum: 21 years completed
• Maximum: 24 years (shouldn't cross 25)
• Date of calculation: 1st October of application year

🗓️ **EXAMPLE CALCULATION (2024 batch):**
• Born after Oct 1, 1999 → Too young ❌
• Born between Oct 1, 1999 - Sep 30, 2003 → Perfect ✅
• Born before Oct 1, 1999 → Too old ❌

📋 **AGE PROOF DOCUMENTS:**
• Aadhaar Card (primary)
• 10th class marksheet
• Birth certificate
• Passport (if available)

⏰ **TIMING MATTERS:**
• Apply when you're in the age bracket
• Age will be verified during document check
• No relaxation in age criteria

🎯 **QUICK CHECK:**
What's your date of birth? I can tell you if you're eligible!

Ready to check other eligibility criteria?"""
    
    # Benefits and stipend
    elif any(word in message_lower for word in ['stipend', 'benefit', 'salary', 'money', 'payment', 'allowance', 'grant']):
        return f"""💰 **Amazing Benefits Awaiting {user_name}:**

💵 **Monthly Stipend:** ₹5,000
   • ₹4,500 from Central Government
   • ₹500 from host organization

🎁 **One-time Grant:** ₹6,000
   • For learning materials & skill development

🏥 **Insurance Coverage:**
   • Health insurance
   • Accident coverage

🏆 **Additional Perks:**
   • Official GoI certificate
   • Industry mentorship
   • Skill development workshops
   • Career guidance
   • Professional networking

💡 **Total Value:** ₹66,000+ per year!"""
    
    # Documents
    elif any(word in message_lower for word in ['document', 'documents', 'papers', 'certificates', 'upload']):
        return f"📄 **Required Documents for {user_name}:**\\n\\n� **Identity:**\\n• Aadhaar Card (mandatory)\\n• PAN Card (if available)\\n\\n🎓 **Educational:**\\n• 10th & 12th certificates\\n• Graduation/Diploma certificate\\n• Mark sheets\\n\\n💰 **Income Proof:**\\n• Family income certificate\\n• Income tax returns (if applicable)\\n\\n🏦 **Banking:**\\n• Bank account details\\n• Cancelled cheque\\n\\n📸 **Others:**\\n• Passport size photograph\\n• Caste certificate (if applicable)\\n\\n💡 **Tip:** Keep all documents in PDF format, max 2MB each!"
    
    # Contact and support
    elif any(word in message_lower for word in ['help', 'support', 'contact', 'phone', 'email', 'assistance']):
        return f"""📞 **Get Support, {user_name}:**

📧 **Email Support:**
• contact-pminternship@gov.in
• Response within 24-48 hours

☎️ **Phone Helpline:**
• 011-12345678
• Monday-Friday: 10 AM - 6 PM
• Instant assistance

💬 **Live Chat:**
• Available on portal 24/7
• Quick query resolution

🌐 **Portal Help:**
• Comprehensive FAQ section
• Step-by-step guides
• Video tutorials

❓ **Need immediate help? I'm here to assist you right now!**"""
    
    # General fallback with personalized suggestions
    else:
        return f"🤖 **Hi {user_name}! I'm PRIA, your PM Internship Assistant.**\\n\\n🎯 **I can help you with:**\\n\\n✨ **Getting Started:**\\n• Eligibility criteria & requirements\\n• Application process & steps\\n• Document preparation\\n\\n� **Benefits & Details:**\\n• Stipend & financial benefits\\n• Available sectors & companies\\n• Duration & timeline\\n\\n🔍 **Application Support:**\\n• Status tracking\\n• Interview preparation\\n• Technical assistance\\n\\n� **Contact & Help:**\\n• Support channels\\n• FAQ resolution\\n\\n💬 **Just ask me anything!** For example:\\n'Am I eligible?' or 'How to apply?' or 'What documents needed?'\\n\\n🌟 **Ready to start your internship journey?**"

# ENHANCED: Skill Matching Algorithm with Government Priority
def calculate_skill_match_score(user_skills_string, required_skills_list, user_profile=None):
    """
    Calculate skill match percentage between user and job requirements
    Returns a score from 0-100 based on skill compatibility
    """
    if not user_skills_string or not required_skills_list:
        return 0

    # Handle skills whether they're a list or comma-separated string
    if isinstance(user_skills_string, list):
        user_skills = [skill.strip().lower() for skill in user_skills_string if skill and skill.strip()]
    else:
        user_skills = [skill.strip().lower() for skill in str(user_skills_string).split(',') if skill.strip()]
    
    required_skills = [skill.strip().lower() for skill in required_skills_list if skill.strip()]
    
    if not user_skills or not required_skills:
        return 0

    match_score = 0
    total_weight = len(required_skills)
    
    for req_skill in required_skills:
        best_match_score = 0
        
        for user_skill in user_skills:
            # Exact match
            if user_skill == req_skill:
                best_match_score = 1.0
                break
            
            # Partial match using fuzzy matching
            similarity = difflib.SequenceMatcher(None, user_skill, req_skill).ratio()
            if similarity > 0.8:  # 80% similarity threshold
                best_match_score = max(best_match_score, similarity)
            
            # Check if one skill contains another
            elif req_skill in user_skill or user_skill in req_skill:
                best_match_score = max(best_match_score, 0.9)
            
            # Common skill variations
            skill_variations = {
                'python': ['py', 'python3', 'python programming'],
                'javascript': ['js', 'node.js', 'nodejs', 'react', 'angular', 'vue'],
                'java': ['java programming', 'core java', 'advanced java'],
                'sql': ['mysql', 'postgresql', 'database', 'rdbms'],
                'machine learning': ['ml', 'ai', 'artificial intelligence', 'deep learning'],
                'data analysis': ['data science', 'analytics', 'statistics'],
                'web development': ['html', 'css', 'frontend', 'backend'],
                'communication': ['english', 'presentation', 'speaking'],
            }
            
            for base_skill, variations in skill_variations.items():
                if (req_skill == base_skill and user_skill in variations) or \
                   (user_skill == base_skill and req_skill in variations):
                    best_match_score = max(best_match_score, 0.95)
        
        match_score += best_match_score

    # Calculate percentage
    percentage = (match_score / total_weight) * 100
    
    # Add bonus points based on user profile completeness and other factors
    bonus_points = 0
    if user_profile:
        # Bonus for relevant qualification
        if user_profile.get('qualification'):
            qualification = user_profile['qualification'].lower()
            if any(edu in qualification for edu in ['engineering', 'btech', 'computer', 'it', 'technology']):
                bonus_points += 5
        
        # Bonus for relevant area of interest
        if user_profile.get('area_of_interest'):
            interest = user_profile['area_of_interest'].lower()
            job_sectors = ['technology', 'finance', 'healthcare', 'engineering', 'management']
            if any(sector in interest for sector in job_sectors):
                bonus_points += 3
        
        # Bonus for prior internship experience
        if user_profile.get('prior_internship') == 'yes':
            bonus_points += 7
    
    # Cap the percentage at 100
    final_percentage = min(100, percentage + bonus_points)
    return round(final_percentage, 1)

def sort_recommendations_by_match(recommendations, user):
    """
    Sort recommendations by skill match accuracy with GOVERNMENT PRIORITY
    Ensures balanced mix: 2-3 government + 2-3 private-based in top 5
    """
    user_skills = user.get('skills', '') if user else ''
    
    # Separate government and private-based recommendations
    government_recs = []
    private_recs = []
    
    for rec in recommendations:
        match_score = calculate_skill_match_score(
            user_skills,
            rec.get('skills', []),
            user
        )
        
        # Add the match score to the recommendation
        rec['skill_match_score'] = match_score
        
        if rec.get('type') == 'government':
            # Government internships get bonus (10 points for priority)
            boosted_score = min(100, match_score + 10)
            rec['skill_match_score'] = boosted_score
            government_recs.append((boosted_score, rec))
        else:
            private_recs.append((match_score, rec))
    
    # Sort each category by match score
    government_recs.sort(key=lambda x: x[0], reverse=True)
    private_recs.sort(key=lambda x: x[0], reverse=True)
    
    # Create balanced top 5: 3 government + 2 private-based (or best available mix)
    top_recommendations = []
    
    # Add top government recommendations (max 3)
    gov_count = 0
    for score, rec in government_recs:
        if gov_count < 3:
            top_recommendations.append(rec)
            gov_count += 1
    
    # Add top private-based recommendations (fill remaining spots)
    private_count = 0
    for score, rec in private_recs:
        if len(top_recommendations) < 5 and private_count < 3:
            top_recommendations.append(rec)
            private_count += 1
    
    # If we still need more and have remaining government ones
    if len(top_recommendations) < 5 and gov_count < len(government_recs):
        for score, rec in government_recs[gov_count:]:
            if len(top_recommendations) < 5:
                top_recommendations.append(rec)
    
    # Final sort by skill_match_score to maintain quality order within the balanced set
    top_recommendations.sort(key=lambda x: x.get('skill_match_score', 0), reverse=True)
    
    return top_recommendations[:5]

def get_enhanced_default_recommendations(user):
    """Enhanced recommendations with BALANCED MIX - Government priority but shows both types"""
    area_of_interest = user.get('area_of_interest', '').lower() if user else ''
    
    # Handle skills whether they're a list or comma-separated string
    user_skills = user.get('skills', [])
    if isinstance(user_skills, list):
        skills = ','.join(skill.lower() for skill in user_skills)
    else:
        skills = str(user_skills).lower()
    
    qualification = user.get('qualification', '').lower() if user else ''
    
    # BALANCED POOL: Equal mix of government and private-based opportunities
    all_recommendations = [
        # GOVERNMENT INTERNSHIPS (7 options - high quality)
        {
            "company": "ISRO",
            "title": "Space Technology Research Intern",
            "type": "government",
            "sector": "Space Technology & Research",
            "skills": ["Programming", "Research", "Data Analysis", "MATLAB", "Python"],
            "duration": "6 Months",
            "location": "Bangalore/Thiruvananthapuram",
            "stipend": "₹25,000/month",
            "description": "🚀 Join India's premier space agency! Work on cutting-edge satellite technology and space missions. Contribute to national space research programs."
        },
        {
            "company": "DRDO",
            "title": "Defence Technology Intern",
            "type": "government",
            "sector": "Defence Research & Development",
            "skills": ["Research", "Engineering", "Technical Analysis", "Problem Solving", "Innovation"],
            "duration": "4 Months",
            "location": "Delhi/Pune/Hyderabad",
            "stipend": "₹22,000/month",
            "description": "🛡️ Shape India's defence future! Work on advanced defence technologies and contribute to national security research projects."
        },
        {
            "company": "NITI Aayog",
            "title": "Policy Research & Analysis Intern",
            "type": "government",
            "sector": "Public Policy & Governance",
            "skills": ["Research", "Policy Analysis", "Data Interpretation", "Report Writing", "Communication"],
            "duration": "4 Months",
            "location": "New Delhi",
            "stipend": "₹20,000/month",
            "description": "🏛️ Impact India's development! Research policy solutions and contribute to national development strategies."
        },
        {
            "company": "Indian Railways",
            "title": "Railway Operations & Technology Intern",
            "type": "government",
            "sector": "Transportation & Logistics",
            "skills": ["Operations Management", "Logistics", "Engineering", "Project Management", "Data Analysis"],
            "duration": "5 Months",
            "location": "Multiple Cities",
            "stipend": "₹18,000/month",
            "description": "🚂 Power India's lifeline! Learn operations of world's largest railway network."
        },
        {
            "company": "CSIR Labs",
            "title": "Scientific Research Intern",
            "type": "government",
            "sector": "Scientific Research",
            "skills": ["Research", "Data Analysis", "Laboratory Skills", "Scientific Writing", "Innovation"],
            "duration": "6 Months",
            "location": "Multiple CSIR Centers",
            "stipend": "₹24,000/month",
            "description": "🔬 Advance scientific knowledge! Work with India's premier scientific research organization."
        },
        {
            "company": "Ministry of Electronics & IT",
            "title": "Digital India Technology Intern",
            "type": "government",
            "sector": "Digital Governance",
            "skills": ["Programming", "Digital Literacy", "Web Development", "Data Management", "Cybersecurity"],
            "duration": "4 Months",
            "location": "New Delhi/Pune",
            "stipend": "₹21,000/month",
            "description": "💻 Build Digital India! Contribute to nation's digital transformation and e-governance initiatives."
        },
        {
            "company": "BARC",
            "title": "Nuclear Technology Research Intern",
            "type": "government",
            "sector": "Nuclear Research",
            "skills": ["Engineering", "Research", "Data Analysis", "Safety Protocols", "Technical Documentation"],
            "duration": "5 Months",
            "location": "Mumbai/Kalpakkam",
            "stipend": "₹26,000/month",
            "description": "⚛️ Power India's future! Work on nuclear technology and contribute to clean energy research."
        },

        # PRIVATE-BASED INTERNSHIPS (8 options - high quality with competitive stipends)
        {
            "company": "TCS (Tata Consultancy Services)",
            "title": "Software Development Intern",
            "type": "private-based",
            "sector": "IT Services",
            "skills": ["Java", "Python", "Programming", "Problem Solving", "Communication"],
            "duration": "3 Months",
            "location": "Multiple Cities",
            "stipend": "₹30,000/month",
            "description": "💼 Industry leader experience! Work on enterprise software projects with India's largest IT company."
        },
        {
            "company": "Infosys",
            "title": "Digital Innovation Intern",
            "type": "private-based",
            "sector": "IT Consulting",
            "skills": ["Digital Technologies", "Innovation", "Cloud Computing", "Problem Solving", "Teamwork"],
            "duration": "3 Months",
            "location": "Bangalore/Pune",
            "stipend": "₹28,000/month",
            "description": "🌟 Innovation at scale! Work on cutting-edge digital transformation projects with global impact."
        },
        {
            "company": "Wipro",
            "title": "Technology Solutions Intern",
            "type": "private-based",
            "sector": "IT Services",
            "skills": ["Cloud Computing", "DevOps", "Programming", "Agile", "Learning Agility"],
            "duration": "4 Months",
            "location": "Pune/Bangalore",
            "stipend": "₹32,000/month",
            "description": "☁️ Future-ready skills! Gain hands-on experience with cloud technologies and modern development practices."
        },
        {
            "company": "Microsoft India",
            "title": "Technology Trainee",
            "type": "private-based",
            "sector": "Technology",
            "skills": ["Programming", "AI/ML", "Cloud Platforms", "Data Science", "Innovation"],
            "duration": "3 Months",
            "location": "Hyderabad/Bangalore",
            "stipend": "₹40,000/month",
            "description": "🚀 Global technology experience! Work with cutting-edge Microsoft technologies and AI platforms."
        },
        {
            "company": "Google India",
            "title": "Software Engineering Intern",
            "type": "private-based",
            "sector": "Technology",
            "skills": ["Programming", "Algorithms", "Data Structures", "Problem Solving", "Software Design"],
            "duration": "4 Months",
            "location": "Bangalore/Gurgaon",
            "stipend": "₹50,000/month",
            "description": "🌟 Dream opportunity! Work with world-class engineers on products used by billions."
        },
        {
            "company": "Amazon India",
            "title": "SDE Intern",
            "type": "private-based",
            "sector": "E-commerce Technology",
            "skills": ["Programming", "System Design", "AWS", "Data Structures", "Problem Solving"],
            "duration": "3 Months",
            "location": "Bangalore/Hyderabad",
            "stipend": "₹45,000/month",
            "description": "📦 Scale at Amazon! Work on systems handling millions of customers and learn cloud technologies."
        },
        {
            "company": "HDFC Bank",
            "title": "Banking Technology Intern",
            "type": "private-based",
            "sector": "Financial Services",
            "skills": ["Financial Technology", "Data Analysis", "Banking Operations", "Communication", "Excel"],
            "duration": "3 Months",
            "location": "Mumbai/Pune",
            "stipend": "₹25,000/month",
            "description": "🏦 FinTech innovation! Experience digital banking transformation with India's leading private bank."
        },
        {
            "company": "Accenture",
            "title": "Technology Consulting Intern",
            "type": "private-based",
            "sector": "IT Consulting",
            "skills": ["Business Analysis", "Technology Consulting", "Communication", "Problem Solving", "Project Management"],
            "duration": "4 Months",
            "location": "Multiple Cities",
            "stipend": "₹27,000/month",
            "description": "💡 Consulting excellence! Work with global clients on technology transformation projects."
        }
    ]

    # Return balanced top 5 with government priority
    return sort_recommendations_by_match(all_recommendations, user)

# 🔧 ENHANCED: Better error handling and timeout for AI recommendations
def generate_recommendations_fast(user):
    """Fast AI recommendations with enhanced error handling and fallback"""
    try:
        model_instance = get_gemini_model()
        if not model_instance:
            print("📋 Using enhanced default recommendations (Gemini not available)")
            return get_enhanced_default_recommendations(user)
            
        # Shorter, more focused prompt for faster response
        user_skills = user.get('skills', 'General')
        if isinstance(user_skills, list):
            skills_str = ', '.join(user_skills)
        else:
            skills_str = str(user_skills)
            
        prompt = f"""
        Generate 6 internship recommendations for:
        - Skills: {skills_str}
        - Interest: {user.get('area_of_interest', 'IT')}
        - Education: {user.get('qualification', 'Graduate')}

        IMPORTANT: Include more government internships (ISRO, DRDO, NITI Aayog, etc.)

        JSON format: [{{"company":"Name","title":"Position","type":"government|private-based","sector":"Sector","skills":["skill1","skill2"],"duration":"X Months","location":"City","stipend":"₹X/month","description":"Brief desc"}}]
        """

        # 🔧 ENHANCED: Better timeout and error handling
        try:
            response = model_instance.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=1000,  # Increased for better responses
                    temperature=0.7,
                )
            )
            
            if not response or not response.text:
                raise Exception("Empty response from Gemini")
                
            recommendations_text = response.text.strip()
            start_idx = recommendations_text.find('[')
            end_idx = recommendations_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = recommendations_text[start_idx:end_idx]
                recommendations = json.loads(json_str)
                print(f"✅ AI generated {len(recommendations)} recommendations")
                return sort_recommendations_by_match(recommendations[:6], user)
            else:
                print("⚠️ Could not parse AI response format, using fallback")
                raise Exception("Could not parse AI response")
                
        except json.JSONDecodeError as json_error:
            print(f"🔄 JSON parsing failed: {json_error}")
            raise json_error
            
        except Exception as api_error:
            print(f"🔄 Gemini API call failed: {api_error}")
            raise api_error
            
    except Exception as e:
        print(f"📋 AI recommendation error: {e}")
        print("🔄 Using enhanced default recommendations")
        return get_enhanced_default_recommendations(user)

def get_default_recommendations(user):
    """Legacy function - calls enhanced version"""
    return get_enhanced_default_recommendations(user)

# Login required decorator
def login_required(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return view_function(*args, **kwargs)
    return decorated_function


@app.before_request
def ensure_language_selection():
    """Guarantee the session language is always set to a supported option."""
    language = session.get('language')
    if not language or language not in SUPPORTED_LANGUAGES:
        session['language'] = DEFAULT_LANGUAGE


@app.route('/language/<lang_code>')
def change_language(lang_code):
    """Persist the requested language in the session and redirect back."""
    lang_code = (lang_code or '').lower()
    if lang_code in SUPPORTED_LANGUAGES:
        session['language'] = lang_code
        print(f"🌐 Language changed to: {lang_code}")
    else:
        flash('Selected language is not supported yet.', 'info')

    next_url = request.referrer
    if not next_url:
        next_url = url_for('home') if session.get('logged_in') else url_for('index')
    return redirect(next_url)


@app.context_processor
def inject_translation_helpers():
    """Expose translation helpers to templates."""
    current_language = session.get('language', DEFAULT_LANGUAGE)

    def t(key, lang=None):
        return get_translation(key, lang or current_language)

    return {
        't': t,
        'current_language': current_language,
        'languages': SUPPORTED_LANGUAGES
    }

@app.before_request
def clear_stale_flash_messages():
    """Clear flash messages for non-authenticated users"""
    # Check if user is authenticated (either as student or company)
    is_authenticated = session.get('logged_in') or (session.get('is_company') and session.get('company_id'))
    
    if request.endpoint not in ['login', 'signup', 'logout', 'clear_session', 'index'] and not is_authenticated:
        if '_flashes' in session:
            session.pop('_flashes', None)

@app.context_processor
def inject_user():
    """Inject user data into all templates"""
    user = None
    company = None
    
    # Handle student users
    if session.get('logged_in') and session.get('user_id'):
        user = get_user_by_id(session.get('user_id'))
    
    # Handle company users
    if session.get('is_company') and session.get('company_id'):
        company = get_company_by_id(session.get('company_id'))
    
    return {
        'user': user,
        'company': company,
        'user_name': session.get('user_name', 'User'),
        'user_email': session.get('user_email', ''),
        'user_initials': session.get('user_initials', 'U')
    }

# Routes
@app.route('/')
def index():
    # Check if user is logged in as student
    if session.get('logged_in'):
        return redirect(url_for('home'))
    # Check if user is logged in as company
    elif session.get('is_company') and session.get('company_id'):
        return redirect(url_for('company_home'))
    else:
        # Redirect to login page if not logged in
        return redirect(url_for('login'))

@app.route('/manifest.json')
def manifest():
    """Return PWA manifest file"""
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

@app.route('/offline.html')
def offline():
    """Return offline page for PWA"""
    return render_template('offline.html')

# 🔧 FIXED: Home route with better profile completion check and debug logging
@app.route('/home')
@login_required
def home():
    user = get_user_by_id(session.get('user_id'))
    if not user:
        flash('User session expired. Please log in again.', 'error')
        return redirect(url_for('login'))
    
    # 🔧 FIXED: Add debug logging and improved profile completion check
    print(f"🔍 DEBUG: User {user['id']} accessing home")
    print(f"🔍 DEBUG: profile_completed = {user.get('profile_completed')}")
    print(f"🔍 DEBUG: registration_completed = {user.get('registration_completed')}")
    print(f"🔍 DEBUG: full_name = {user.get('full_name')}")
    print(f"🔍 DEBUG: phone = {user.get('phone')}")
    
    # 🔧 IMPROVED: More flexible profile completion check
    # Consider profile complete if user has basic info filled OR profile_completed flag is True
    has_basic_info = (
        user.get('full_name') and user.get('full_name') != 'User' and 
        user.get('phone') and len(str(user.get('phone', ''))) >= 10
    )
    
    profile_complete = user.get('profile_completed') == True or has_basic_info
    
    print(f"🔍 DEBUG: has_basic_info = {has_basic_info}")
    print(f"🔍 DEBUG: final profile_complete = {profile_complete}")
    
    if not profile_complete:
        flash('Please complete your profile first to access all features', 'info')
        return redirect(url_for('profile'))
    
    return render_template('home.html')

@app.route('/ats')
@login_required
def ats():
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return redirect(url_for('login'))
    
    if not user.get('profile_completed'):
        flash('Please complete your profile first to use ATS matching', 'info')
        return redirect(url_for('profile'))
    
    return render_template('ats.html')

# Note: Login and signup routes are now integrated below in the company portal section


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """Handle user logout with proper session cleanup"""
    try:
        # Get user info before clearing session (for logging)
        user_id = session.get('user_id')
        username = session.get('username', 'Unknown')
        
        # Clear all session data
        session.clear()
        
        # Log successful logout
        if user_id:
            print(f"✅ User {username} (ID: {user_id}) logged out successfully")
        else:
            print("✅ Session cleared (no active user found)")
        
        # Set success message
        flash('You have been logged out successfully', 'success')
        
        # Create response with redirect to login page
        response = make_response(redirect(url_for('login')))
        
        # Clear any additional cookies if needed
        response.set_cookie('session', '', expires=0)
        
        return response
        
    except Exception as e:
        print(f"❌ Logout error: {e}")
        # Even if there's an error, still try to clear session and redirect
        session.clear()
        flash('Logged out', 'info')
        return redirect(url_for('login'))

# Alternative logout route for testing
@app.route('/force-logout')
def force_logout():
    """Force logout - for testing purposes"""
    session.clear()
    flash('Force logout completed', 'info')
    return redirect(url_for('login'))

@app.route('/api/save_profile', methods=['POST'])
@login_required
def save_profile():
    try:
        form_data = request.get_json()
        
        # Convert numeric fields
        if 'qualification_marks' in form_data:
            try:
                form_data['qualification_marks'] = float(form_data['qualification_marks'])
            except (TypeError, ValueError):
                form_data['qualification_marks'] = None
        
        if 'course_marks' in form_data:
            try:
                form_data['course_marks'] = float(form_data['course_marks'])
            except (TypeError, ValueError):
                form_data['course_marks'] = None
        
        # Add profile completion flags
        form_data.update({
            'otp_verified': True,
            'registration_completed': True,
            'profile_completed': True
        })
        
        # Handle file paths (for future file upload support)
        file_paths = {}
        
        if update_user_profile(session.get('user_id'), {**form_data, **file_paths}):
            if form_data.get('full_name'):
                session['user_name'] = form_data['full_name']
                session['user_initials'] = get_user_initials(form_data['full_name'])
            
            return jsonify({'success': True, 'message': 'Profile updated successfully!'})
        else:
            return jsonify({'success': False, 'error': 'Failed to update profile'}), 500
            
    except Exception as e:
        print(f"Profile update error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 🔧 FIXED: Profile route with separate career objective and area of interest
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_user_by_id(session.get('user_id'))
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            # Handle file uploads
            uploaded_files = {}
            file_fields = ['qualificationCertificate', 'additionalCertificates', 'internshipCertificate']
            
            for field_name in file_fields:
                if field_name in request.files:
                    files = request.files.getlist(field_name)
                    saved_files = []
                    for file in files:
                        if file and file.filename and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                            filename = timestamp + filename
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            try:
                                file.save(file_path)
                                saved_files.append(filename)
                            except Exception as e:
                                print(f"File save error: {e}")
                    
                    if saved_files:
                        db_field_map = {
                            'qualificationCertificate': 'qualification_certificate',
                            'additionalCertificates': 'additional_certificates',
                            'internshipCertificate': 'internship_certificate'
                        }
                        db_field = db_field_map.get(field_name, field_name)
                        uploaded_files[db_field] = json.dumps(saved_files)

            # Collect skills from checkboxes - UPDATED with new skills
            skills_list = []
            skill_fields = ['react', 'python', 'java', 'cpp', 'html', 'css', 'javascript', 'ai-ml', 'cloud', 
                           'nodejs', 'database', 'devops',  # New technical skills
                           'leadership', 'communication', 'digital-marketing', 'content-writing', 'project-management',
                           'teamwork', 'problem-solving', 'analytical']  # New non-technical skills
            
            for skill in skill_fields:
                if request.form.get(f'skill_{skill}') or skill in request.form.getlist('skills'):
                    skills_list.append(skill)
            
            # Collect languages from checkboxes
            languages_list = []
            language_fields = ['english', 'hindi', 'tamil', 'telugu', 'bengali', 'kannada', 'marathi', 'other']
            
            for lang in language_fields:
                if request.form.get(f'lang_{lang}') or lang in request.form.getlist('languages'):
                    languages_list.append(lang)

            # 🔧 FIXED: Handle Career Objective and Area of Interest SEPARATELY
            # Career Objective = user's typed content in textarea (objective field)
            # Area of Interest = dropdown selection (interest field)

            career_objective = request.form.get('objective', '').strip()  # User's typed career objective
            area_interest = request.form.get('interest', '').strip()      # Dropdown selection for area of interest

            # If user hasn't selected area of interest dropdown, keep existing value
            if not area_interest and user:
                area_interest = user.get('area_of_interest', '')

            print(f"🔍 DEBUG: career_objective (user typed) = '{career_objective}'")
            print(f"🔍 DEBUG: area_interest (dropdown) = '{area_interest}'")

            # Process form data matching your database schema
            form_data = {
                'full_name': request.form.get('fullName', '').strip(),
                'father_name': request.form.get('fatherName', '').strip(),
                'gender': request.form.get('gender', ''),
                'phone': request.form.get('phone', '').strip(),
                'district': request.form.get('district', ''),
                'address': request.form.get('address', '').strip(),
                'career_objective': career_objective,  # 🔧 NEW: Store user's career objective separately
                'area_of_interest': area_interest,     # 🔧 SEPARATE: Store dropdown selection
                'qualification': request.form.get('qualification', ''),
                'qualification_marks': float(request.form.get('qualificationMarks', 0)) if request.form.get('qualificationMarks') else None,
                'course': request.form.get('course', '').strip(),
                'course_marks': float(request.form.get('courseMarks', 0)) if request.form.get('courseMarks') else None,
                'skills': json.dumps(skills_list) if skills_list else json.dumps([]),
                'languages': json.dumps(languages_list) if languages_list else json.dumps([]),
                'experience': request.form.get('experience', ''),
                'prior_internship': request.form.get('priorInternship', '')
            }
            
            # Add file upload data
            form_data.update(uploaded_files)
            
            # 🔧 CRITICAL FIX: Update user profile and ensure success
            if update_user_profile(user['id'], form_data):
                # Update session with new name
                if form_data.get('full_name'):
                    session['user_name'] = form_data['full_name']
                    session['user_initials'] = get_user_initials(form_data['full_name'])
                
                flash('Profile saved successfully! 🎉', 'success')
                
                # 🔧 FIXED: Redirect to home page after successful profile save
                print(f"🔍 DEBUG: Profile saved successfully, redirecting to home")
                return redirect(url_for('home'))
            else:
                flash('Failed to update profile. Please try again.', 'error')
                
        except Exception as e:
            print(f"Profile update error: {e}")
            flash('Error updating profile. Please try again.', 'error')
    
    # For GET request or after failed POST, return form with user data
    return render_template('profile.html', user=user)

# ENHANCED: Recommendations route — live DB internships + AI suggestions
@app.route('/recommendations')
@login_required
def recommendations():
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return redirect(url_for('login'))

    # Check if profile is completed
    if not user.get('profile_completed'):
        flash('Please complete your profile first to get personalized recommendations.', 'warning')
        return redirect(url_for('profile'))

    # ── 1. Fetch LIVE DB internships (company-posted, active) ──────────────
    live_internships = []
    applied_ids = set()
    application_statuses = {}
    try:
        if supabase:
            internships_response = (
                supabase.table('internships')
                .select('*, companies(company_name, industry, city, state, company_type)')
                .eq('status', 'active')
                .order('created_at', desc=True)
                .execute()
            )
            live_internships = internships_response.data if internships_response.data else []

            # Parse JSON array fields
            for internship in live_internships:
                req = internship.get('requirements')
                if isinstance(req, str):
                    try:
                        internship['requirements'] = json.loads(req) if req else []
                    except Exception:
                        internship['requirements'] = []
                elif req is None:
                    internship['requirements'] = []

            # Track which internships the user already applied to
            if live_internships:
                internship_ids = [i['id'] for i in live_internships]
                applied_response = (
                    supabase.table('applications')
                    .select('internship_id, status')
                    .eq('student_id', user['id'])
                    .in_('internship_id', internship_ids)
                    .execute()
                )
                for app_row in (applied_response.data or []):
                    applied_ids.add(app_row['internship_id'])
                    application_statuses[app_row['internship_id']] = app_row['status']
    except Exception as e:
        print(f"Error fetching live internships for recommendations: {e}")

    # ── 2. Get AI / hardcoded suggestions ─────────────────────────────────
    ai_recommendations = get_enhanced_default_recommendations(user)

    return render_template('recommendations.html',
                           user=user,
                           live_internships=live_internships,
                           applied_ids=applied_ids,
                           application_statuses=application_statuses,
                           recommendations=ai_recommendations)

# ENHANCED: AI recommendations with skill matching and government preference
@app.route('/api/generate-ai-recommendations')
@login_required
def generate_ai_recommendations():
    """AJAX endpoint to generate AI recommendations sorted by match score with government preference"""
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    try:
        # Try to generate AI recommendations
        ai_recommendations = generate_recommendations_fast(user)
        
        # Sort AI recommendations by skill match with government preference
        sorted_recommendations = sort_recommendations_by_match(ai_recommendations, user)
        
        return jsonify({
            'success': True,
            'recommendations': sorted_recommendations
        })
        
    except Exception as e:
        print(f"AI recommendations error: {e}")
        
        # Fallback to enhanced default recommendations
        fallback_recommendations = get_enhanced_default_recommendations(user)
        
        return jsonify({
            'success': True,
            'recommendations': fallback_recommendations
        })

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({
                'error': 'No message provided',
                'reply': '🤔 I didn\'t receive your message. Please try typing something!',
                'success': False
            }), 400
        
        # Enhanced message validation
        if len(user_message) > 800:  # Increased limit for better conversations
            return jsonify({
                'error': 'Message too long',
                'reply': '📝 Please keep your message under 800 characters so I can give you a focused, helpful response!',
                'success': False
            }), 400
        
        user_name = session.get('user_name', 'User')
        user_email = session.get('user_email', '')
        
        # Track response time for performance optimization
        start_time = datetime.now()
        
        # Get ultra-responsive enhanced response
        selected_lang_code = (data.get('language') or session.get('language') or DEFAULT_LANGUAGE)
        bot_response = get_gemini_response(user_message, user_name, user_email, preferred_lang_code=selected_lang_code)
        
        response_time = (datetime.now() - start_time).total_seconds()
        
        # Log conversation with performance metrics
        log_conversation(user_message, bot_response, session.get('user_id'), response_time)
        
        # Enhanced response with user engagement
        return jsonify({
            'reply': bot_response,
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'response_time': f"{response_time:.2f}s",
            'personalized': True,
            'user_name': user_name
        })
        
    except Exception as e:
        print(f"Chat error: {e}")
        
        # Enhanced error handling with immediate fallback
        user_message = data.get('message', '') if data else ''
        user_name = session.get('user_name', 'User')
        
        # Intelligent error categorization
        if "quota" in str(e).lower() or "limit" in str(e).lower():
            error_response = f"🚫 Hi {user_name}! I'm experiencing high traffic right now. Let me try a different approach..."
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_response = f"🌐 {user_name}, there seems to be a connection hiccup. Let me help you anyway!"
        else:
            error_response = f"⚠️ {user_name}, I hit a small technical bump, but I'm still here to help!"
        
        # Immediate intelligent fallback
        fallback_response = get_fallback_response(user_message)
        
        # Combine error acknowledgment with helpful response
        combined_response = f"{error_response}\n\n{fallback_response}"
        
        return jsonify({
            'reply': combined_response,
            'success': True,
            'fallback': True,
            'timestamp': datetime.now().isoformat(),
            'user_name': user_name
        }), 200

# New endpoint to clear chat history
@app.route('/chat/clear', methods=['POST'])
def clear_chat_history():
    try:
        session.pop('chat_history', None)
        return jsonify({
            'success': True,
            'message': 'Chat history cleared successfully'
        })
    except Exception as e:
        print(f"Clear chat error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to clear chat history'
        }), 500

@app.route('/clear-session')
def clear_session():
    session.clear()
    return redirect(url_for('index'))

# 🔧 ADDED: Debug route to check profile status
@app.route('/debug-profile')
@login_required
def debug_profile():
    """Debug route to check profile status"""
    if not app.debug:
        return "Not available in production"
    
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return "User not found"
    
    return f"""
    <h2>Profile Debug Info</h2>
    <p><strong>User ID:</strong> {user['id']}</p>
    <p><strong>Full Name:</strong> {user.get('full_name')}</p>
    <p><strong>Profile Completed:</strong> {user.get('profile_completed')}</p>
    <p><strong>Registration Completed:</strong> {user.get('registration_completed')}</p>
    <p><strong>Phone:</strong> {user.get('phone')}</p>
    <p><strong>Career Objective:</strong> {user.get('career_objective')}</p>
    <p><strong>Area of Interest:</strong> {user.get('area_of_interest')}</p>
    <p><strong>Skills:</strong> {user.get('skills')}</p>
    <p><strong>Updated At:</strong> {user.get('updated_at')}</p>
    <br>
    <a href="/home">Try Home Page</a><br>
    <a href="/profile">Back to Profile</a><br>
    <a href="/logout">Logout</a>
    """

# Debug routes (remove in production)
@app.route('/debug-users')
def debug_users():
    """Debug route to see all users"""
    if not app.debug:
        return "Not available in production"
    
    try:
        if not supabase:
            return "Database connection not available"
        
        response = supabase.table('users').select('id, full_name, email, profile_completed, created_at').execute()
        users = response.data
        
        output = "<h2>Users in Database:</h2>"
        for user in users:
            output += f"<p>ID: {user['id']}, Name: {user['full_name']}, Email: {user['email']}, Completed: {user.get('profile_completed', False)}</p>"
        
        return output
        
    except Exception as e:
        return f"Error: {e}"


def generate_cv_pdf(user):
    """Generate a professional CV PDF from user profile data"""
    try:
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=60,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )

        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#3498db'),
            spaceBefore=15,
            spaceAfter=8,
            fontName='Helvetica-Bold',
            borderWidth=1,
            borderColor=colors.HexColor('#3498db'),
            borderPadding=5
        )

        content_style = ParagraphStyle(
            'Content',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=6,
            fontName='Helvetica'
        )

        story = []

        full_name = user.get('full_name', 'No Name Provided')
        story.append(Paragraph(full_name.upper(), title_style))

        contact_info = []
        if user.get('email'):
            contact_info.append(f"📧 {user['email']}")
        if user.get('phone'):
            contact_info.append(f"📱 {user['phone']}")
        if user.get('district'):
            contact_info.append(f"📍 {user['district'].title()}")

        if contact_info:
            story.append(Paragraph(" | ".join(contact_info), subtitle_style))

        story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph("PERSONAL INFORMATION", section_style))

        personal_data = []
        if user.get('father_name'):
            personal_data.append(["Father's Name:", user['father_name']])
        if user.get('gender'):
            personal_data.append(['Gender:', user['gender'].title()])
        if user.get('address'):
            personal_data.append(['Address:', user['address']])

        if personal_data:
            personal_table = Table(personal_data, colWidths=[2*inch, 4*inch])
            personal_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#3498db')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            story.append(personal_table)
        else:
            story.append(Paragraph("Personal information not provided", content_style))

        story.append(Spacer(1, 0.2*inch))

        if user.get('career_objective'):
            story.append(Paragraph("CAREER OBJECTIVE", section_style))
            story.append(Paragraph(user['career_objective'], content_style))
            story.append(Spacer(1, 0.1*inch))

        story.append(Paragraph("EDUCATION", section_style))

        education_data = []
        if user.get('qualification'):
            education_data.append(['Qualification:', user['qualification'].upper()])
        if user.get('qualification_marks'):
            education_data.append(['Marks:', f"{user['qualification_marks']}%"])
        if user.get('course'):
            education_data.append(['Course:', user['course']])
        if user.get('course_marks'):
            education_data.append(['Course Marks:', f"{user['course_marks']}%"])

        if education_data:
            education_table = Table(education_data, colWidths=[2*inch, 4*inch])
            education_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#3498db')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            story.append(education_table)

        story.append(Spacer(1, 0.1*inch))

        if user.get('skills'):
            story.append(Paragraph("TECHNICAL SKILLS", section_style))

            skills = user['skills']
            if isinstance(skills, list):
                skills_text = ", ".join([skill.title() for skill in skills])
            else:
                try:
                    skills_list = json.loads(skills)
                    skills_text = ", ".join([skill.title() for skill in skills_list])
                except:
                    skills_text = str(skills).replace(',', ', ').title()

            story.append(Paragraph(skills_text, content_style))
            story.append(Spacer(1, 0.1*inch))

        if user.get('languages'):
            story.append(Paragraph("LANGUAGES", section_style))

            languages = user['languages']
            if isinstance(languages, list):
                languages_text = ", ".join([lang.title() for lang in languages])
            else:
                try:
                    languages_list = json.loads(languages)
                    languages_text = ", ".join([lang.title() for lang in languages_list])
                except:
                    languages_text = str(languages).replace(',', ', ').title()

            story.append(Paragraph(languages_text, content_style))
            story.append(Spacer(1, 0.1*inch))

        if user.get('experience'):
            story.append(Paragraph("EXPERIENCE LEVEL", section_style))
            experience_text = user['experience'].replace('-', ' - ').replace('_', ' ').title()
            story.append(Paragraph(experience_text, content_style))
            story.append(Spacer(1, 0.1*inch))

        if user.get('area_of_interest'):
            story.append(Paragraph("AREA OF INTEREST", section_style))
            interest_text = user['area_of_interest'].replace('-', ' ').replace('_', ' ').title()
            story.append(Paragraph(interest_text, content_style))
            story.append(Spacer(1, 0.1*inch))

        if user.get('prior_internship') == 'yes':
            story.append(Paragraph("INTERNSHIP EXPERIENCE", section_style))
            story.append(Paragraph("Previous internship experience completed", content_style))
            story.append(Spacer(1, 0.1*inch))

        story.append(Spacer(1, 0.3*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique'
        )
        story.append(Paragraph("Generated from PM Internship Scheme Profile", footer_style))

        doc.build(story)

        pdf_data = buffer.getvalue()
        buffer.close()

        return pdf_data

    except Exception as e:
        print(f"Error generating CV PDF: {e}")
        return None


def get_cv_filename(user):
    """Generate a clean filename for the CV"""
    name = user.get('full_name', 'User')
    clean_name = re.sub(r'[^\w\s-]', '', name)
    clean_name = re.sub(r'[-\s]+', '_', clean_name)
    return f"{clean_name}_CV.pdf"

@app.route('/preview-cv')
@login_required
def preview_cv():
    """Preview user's professional CV in browser"""
    user = get_user_by_id(session.get('user_id'))
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('login'))
    
    if not user.get('profile_completed'):
        flash('Please complete your profile first to preview your CV', 'warning')
        return redirect(url_for('profile'))
    
    try:
        print(f"🔍 DEBUG: Starting CV generation for user: {user.get('full_name', 'Unknown')}")
        
        # FIXED: Check if generate_cv_pdf function exists and is callable
        if 'generate_cv_pdf' not in globals():
            print("❌ ERROR: generate_cv_pdf function not found!")
            flash('CV generation function not available. Please contact support.', 'error')
            return redirect(url_for('profile'))
        
        # Generate the PDF binary data
        pdf_data = generate_cv_pdf(user)
        print(f"🔍 DEBUG: PDF generation returned data of type: {type(pdf_data)}")
        
        if pdf_data and len(pdf_data) > 0:
            print(f"✅ PDF generated successfully, size: {len(pdf_data)} bytes")
            
            # FIXED: Create response for inline viewing with actual PDF data
            response = make_response(pdf_data)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'inline'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Length'] = len(pdf_data)
            
            print("✅ CV preview response created successfully")
            return response
        else:
            print("❌ PDF generation returned empty or None data")
            flash('Error generating CV preview. Please try again.', 'error')
            return redirect(url_for('profile'))
            
    except NameError as ne:
        print(f"❌ NameError in CV preview: {ne}")
        if 'make_response' in str(ne):
            flash('CV preview functionality unavailable due to missing dependencies.', 'error')
        elif 'generate_cv_pdf' in str(ne):
            flash('CV generation function not found. Please contact support.', 'error')
        else:
            flash(f'CV preview error: {ne}', 'error')
        return redirect(url_for('profile'))
        
    except Exception as e:
        print(f"❌ CV preview error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error previewing CV. Please try again.', 'error')
        return redirect(url_for('profile'))

# FIXED: Also fix the download-cv route if you have it
@app.route('/download-cv')
@login_required
def download_cv():
    """Generate and download user's professional CV as PDF"""
    user = get_user_by_id(session.get('user_id'))
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('login'))
    
    if not user.get('profile_completed'):
        flash('Please complete your profile first to download your CV', 'warning')
        return redirect(url_for('profile'))
    
    try:
        # Generate the PDF binary data
        pdf_data = generate_cv_pdf(user)
        
        if pdf_data and len(pdf_data) > 0:
            # Get professional filename (you may need to implement this)
            filename = f"CV_{user.get('full_name', 'User').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            # Create response for download
            response = make_response(pdf_data)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.headers['Content-Length'] = len(pdf_data)
            response.headers['Cache-Control'] = 'no-cache'
            
            print(f"✅ Professional CV downloaded successfully for user: {user['full_name']}")
            return response
        else:
            flash('Error generating CV. Please try again.', 'error')
            return redirect(url_for('profile'))
            
    except Exception as e:
        print(f"CV download error: {e}")
        flash('Error downloading CV. Please try again.', 'error')
        return redirect(url_for('profile'))

from ats import ProfessionalATSAnalyzer

# Initialize the analyzer
ats_analyzer = ProfessionalATSAnalyzer()

@app.route('/analyze-cv', methods=['POST'])
@login_required
def analyze_cv():
    """Analyze uploaded CV against job description"""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get uploaded file and job description
        if 'cv_file' not in request.files:
            return jsonify({'error': 'No CV file uploaded'}), 400
        
        cv_file = request.files['cv_file']
        job_description = request.form.get('job_description', '')
        
        if not cv_file.filename:
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        filename = secure_filename(cv_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{filename}")
        cv_file.save(file_path)
        
        # Analyze the CV
        analysis_result = ats_analyzer.calculate_professional_ats_score(
            file_path, 
            job_description, 
            user_profile=user
        )
        
        # Clean up temporary file
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'analysis': analysis_result
        })
        
    except Exception as e:
        print(f"CV analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to analyze CV. Please try again.'
        }), 500

# ==========================================
# COMPANY PORTAL BACKEND INTEGRATION
# ==========================================

# Company Helper Functions
def check_company_email_exists(email):
    """Check if company email already exists using Supabase"""
    try:
        if not supabase:
            return False
        response = supabase.table('companies').select('email').eq('email', email.strip().lower()).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking company email: {e}")
        return False

def create_company(company_data):
    """Create a new company in Supabase and return company data"""
    try:
        if not supabase:
            return False, "Database connection not available", None
        
        if check_company_email_exists(company_data['email']):
            return False, "Email already registered", None
        
        password_hash = generate_password_hash(company_data['password'])
        company_record = {
            "company_name": company_data['company_name'].strip(),
            "email": company_data['email'].strip().lower(),
            "password_hash": password_hash,
            "contact_person": company_data.get('contact_person', '').strip(),
            "phone": company_data.get('phone', '').strip(),
            "industry": company_data.get('industry', ''),
            "company_type": company_data.get('company_type', 'startup'),  # Default to 'startup' if not provided
            "description": company_data.get('description', ''),
            "website": company_data.get('website', ''),
            "address": company_data.get('address', ''),
            "city": company_data.get('city', ''),
            "state": company_data.get('state', ''),
            "is_verified": False
        }
        
        # Remove empty string values that have constraints
        if not company_record["company_type"] or company_record["company_type"] == '':
            company_record["company_type"] = 'startup'
        if not company_record["industry"] or company_record["industry"] == '':
            company_record["industry"] = 'Technology'  # Default industry
        
        print(f"Creating company: {company_data['email']}")
        response = supabase.table('companies').insert(company_record).execute()
        
        if response.data and len(response.data) > 0:
            created_company = response.data[0]
            print(f"✅ Company created successfully: ID {created_company['id']}")
            return True, "Company created successfully", created_company
        else:
            print(f"❌ No data returned: {response}")
            return False, "Error creating company - no data returned", None
            
    except Exception as e:
        print(f"❌ Error creating company: {e}")
        error_str = str(e).lower()
        if "duplicate" in error_str or "unique" in error_str:
            return False, "Email already registered", None
        elif "company_type_check" in error_str:
            return False, "Invalid company type. Please contact support.", None
        elif "employee_count" in error_str:
            return False, "Invalid employee count value.", None
        elif "check constraint" in error_str:
            return False, "Invalid data provided. Please check your inputs.", None
        return False, "Error creating company account. Please try again.", None

def verify_company(email, password):
    """Verify company credentials using Supabase"""
    try:
        if not supabase:
            return None
        
        response = supabase.table('companies').select('*').eq('email', email.strip().lower()).execute()
        
        if response.data:
            company = response.data[0]
            if check_password_hash(company['password_hash'], password):
                return company
        return None
        
    except Exception as e:
        print(f"Error verifying company: {e}")
        return None

def get_company_by_id(company_id):
    """Get company by ID from Supabase"""
    try:
        if not supabase:
            return None
        
        response = supabase.table('companies').select('*').eq('id', company_id).execute()
        
        if response.data:
            return response.data[0]
        return None
        
    except Exception as e:
        print(f"Error getting company by ID: {e}")
        return None

def setup_company_session(company, remember=False):
    """Set up company session after successful login"""
    # Ensure a clean company session when switching from a candidate account.
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    session.pop('user_initials', None)
    session.pop('logged_in', None)

    session.permanent = remember
    session['company_id'] = company['id']
    session['company_email'] = company['email']
    session['company_name'] = company['company_name']
    session['user_type'] = 'company'
    session['is_company'] = True
    session['auth_scope'] = 'company'
    
    # Update last login
    try:
        supabase.table('companies').update({
            "last_login": datetime.now(timezone.utc).isoformat()
        }).eq('id', company['id']).execute()
    except Exception as e:
        print(f"Error updating company last login: {e}")
    
    return company['company_name']

def company_login_required(f):
    """Decorator to require company login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_company') or not session.get('company_id'):
            flash('Please login as a company to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_company_stats(company_id):
    """Get company dashboard statistics using the new helper function"""
    try:
        if not supabase:
            return {
                'total_internships': 0,
                'active_internships': 0,
                'draft_internships': 0,
                'closed_internships': 0,
                'total_applications': 0,
                'new_applications': 0,
                'pending_reviews': 0,
                'shortlisted_applications': 0,
                'selected_applications': 0
            }
        
        # Try to use the new helper function first
        try:
            analytics_response = supabase.rpc('get_company_dashboard_analytics', {'company_id_param': company_id}).execute()
            if analytics_response.data and len(analytics_response.data) > 0:
                analytics = analytics_response.data[0]
                return {
                    'total_internships': analytics.get('total_internships', 0),
                    'active_internships': analytics.get('active_internships', 0),
                    'draft_internships': analytics.get('draft_internships', 0),
                    'closed_internships': analytics.get('closed_internships', 0),
                    'total_applications': analytics.get('total_applications', 0),
                    'new_applications': analytics.get('new_applications', 0),
                    'pending_reviews': analytics.get('pending_reviews', 0),
                    'shortlisted_applications': analytics.get('shortlisted_applications', 0),
                    'selected_applications': analytics.get('selected_applications', 0)
                }
        except Exception as e:
            print(f"Helper function not available, falling back to manual calculation: {e}")
        
        # Fallback to manual calculation if helper function doesn't exist yet
        # Get internships count
        internships_response = supabase.table('internships').select('*').eq('company_id', company_id).execute()
        internships = internships_response.data if internships_response.data else []
        
        # Get internship IDs for this company
        internship_ids = [internship['id'] for internship in internships] if internships else []
        
        # Get applications count
        applications = []
        if internship_ids:
            applications_response = supabase.table('applications').select('*').in_('internship_id', internship_ids).execute()
            applications = applications_response.data if applications_response.data else []
        
        # Calculate stats
        stats = {
            'total_internships': len(internships),
            'active_internships': len([i for i in internships if i.get('status') == 'active']),
            'draft_internships': len([i for i in internships if i.get('status') == 'draft']),
            'closed_internships': len([i for i in internships if i.get('status') == 'closed']),
            'total_applications': len(applications),
            'new_applications': len([a for a in applications if a.get('status') in ['new', 'pending']]),
            'pending_reviews': len([a for a in applications if a.get('status') == 'under_review']),
            'shortlisted_applications': len([a for a in applications if a.get('status') in ['shortlisted', 'interview_scheduled', 'interview_completed']]),
            'selected_applications': len([a for a in applications if a.get('status') == 'selected'])
        }
        
        return stats
        
    except Exception as e:
        print(f"Error getting company stats: {e}")
        return {
            'total_internships': 0,
            'active_internships': 0,
            'draft_internships': 0,
            'closed_internships': 0,
            'total_applications': 0,
            'new_applications': 0,
            'shortlisted_applications': 0,
            'pending_reviews': 0,
            'selected_applications': 0
        }

# Company Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print("Login attempt started...")
        
        # Get form data
        email = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        usertype = request.form.get('usertype', '')
        remember = request.form.get('remember')
        captcha_answer = request.form.get('captcha', '')
        
        print(f"Email: {email}")
        print(f"User type: {usertype}")
        
        # Clear any existing flash messages
        session.pop('_flashes', None)
        
        # Basic validation
        if not usertype:
            flash('Please select user type (Candidate or Company)', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('login.html', captcha_question=captcha_question)
        
        if not email or not password:
            flash('Please enter both email and password', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('login.html', captcha_question=captcha_question)
        
        # Captcha verification
        if not captcha_answer:
            flash('Please solve the captcha', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('login.html', captcha_question=captcha_question)
        
        if not verify_captcha(captcha_answer, session.get('captcha_answer')):
            flash('Incorrect captcha. Please try again.', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('login.html', captcha_question=captcha_question)
        
        # Email format validation
        if not validate_email(email):
            flash('Please enter a valid email address', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('login.html', captcha_question=captcha_question)
        
        # Check database connection
        db_ok, db_message = check_database_connection()
        if not db_ok:
            flash(f'Database connection error: {db_message}', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('login.html', captcha_question=captcha_question)
        
        # Handle different user types
        if usertype == 'company':
            print("Company login attempt...")
            company = verify_company(email, password)
            print(f"Company verification result: {company is not None}")
            
            if company:
                print(f"Company found: {company.get('company_name', 'Unknown')}")
                company_name = setup_company_session(company, remember)
                flash(f'Welcome back, {company_name}!', 'success')
                print("Redirecting to company home...")
                return redirect(url_for('company_home'))
            else:
                print("Company verification failed")
                if check_company_email_exists(email):
                    print("Company email exists, wrong password")
                    flash('Incorrect password. Please check your password and try again.', 'error')
                else:
                    print("Company email not found")
                    flash('No company account found with this email address.', 'error')
                    flash('Don\'t have an account? Sign up to get started!', 'info')
        else:
            # Student login (existing code)
            user = verify_user(email, password)
            if user:
                fullname = setup_user_session(user, remember)
                flash(f'Welcome back, {fullname}!', 'success')
                if user.get('profile_completed'):
                    return redirect(url_for('home'))
                else:
                    return redirect(url_for('profile'))
            else:
                if check_email_exists(email):
                    flash('Incorrect password. Please check your password and try again.', 'error')
                else:
                    flash('No account found with this email address.', 'error')
                    flash('Don\'t have an account? Sign up to get started!', 'info')
    
    # Generate new captcha for retry
    captcha_question, captcha_answer_correct = generate_captcha()
    session['captcha_answer'] = captcha_answer_correct
    return render_template('login.html', captcha_question=captcha_question)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Get form data
        usertype = request.form.get('usertype', '')
        fullname = request.form.get('fullname', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        captcha_answer = request.form.get('captcha', '')
        
        # Clear any existing flash messages
        session.pop('_flashes', None)
        
        # Validation
        if not usertype:
            flash('Please select user type (Candidate or Company)', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        if not fullname or not email or not password or not confirm_password:
            flash('All fields are required', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        # Check database connection
        db_ok, db_message = check_database_connection()
        if not db_ok:
            flash(f'Database connection error: {db_message}', 'error')
            flash('Please contact support or try again later.', 'info')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        # Captcha verification
        if not captcha_answer:
            flash('Please solve the captcha', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        if not verify_captcha(captcha_answer, session.get('captcha_answer')):
            flash('Incorrect captcha. Please try again.', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        if len(fullname.strip()) < 2:
            flash('Company/Full name must be at least 2 characters long', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        if not validate_email(email):
            flash('Please enter a valid email address', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        is_valid, message = validate_password(password)
        if not is_valid:
            flash(message, 'error')
            captcha_question, captcha_answer_correct = generate_captcha()
            session['captcha_answer'] = captcha_answer_correct
            return render_template('signup.html', captcha_question=captcha_question)
        
        # Handle different user types
        if usertype == 'company':
            # Company signup
            if check_company_email_exists(email):
                flash('This email is already registered as a company. Please use a different email or try logging in.', 'error')
                captcha_question, captcha_answer_correct = generate_captcha()
                session['captcha_answer'] = captcha_answer_correct
                return render_template('signup.html', captcha_question=captcha_question)
            
            company_data = {
                'company_name': fullname,
                'email': email,
                'password': password,
                'company_type': 'startup',  # Default company type for initial signup
                'industry': 'Technology'    # Default industry for initial signup
            }
            
            success, message, created_company = create_company(company_data)
            
            if success and created_company:
                company_name = setup_company_session(created_company, remember=True)
                flash(f'Welcome {company_name}! Your company account has been created and you are now logged in!', 'success')
                flash('Please complete your company profile to access all features.', 'info')
                return redirect(url_for('company_home'))  # Redirect to company home instead of profile
            else:
                flash(message, 'error')
                captcha_question, captcha_answer_correct = generate_captcha()
                session['captcha_answer'] = captcha_answer_correct
                return render_template('signup.html', captcha_question=captcha_question)
        else:
            # Student signup (existing code)
            if check_email_exists(email):
                flash('This email is already registered. Please use a different email or try logging in.', 'error')
                captcha_question, captcha_answer_correct = generate_captcha()
                session['captcha_answer'] = captcha_answer_correct
                return render_template('signup.html', captcha_question=captcha_question)
            
            success, message, created_user = create_user(fullname, email, password)
            
            if success and created_user:
                full_name = setup_user_session(created_user, remember=True)
                flash(f'Welcome {full_name}! Your account has been created and you are now logged in!', 'success')
                flash('Please complete your profile to access all features.', 'info')
                return redirect(url_for('profile'))
            else:
                flash(message, 'error')
                captcha_question, captcha_answer_correct = generate_captcha()
                session['captcha_answer'] = captcha_answer_correct
                return render_template('signup.html', captcha_question=captcha_question)
    
    # GET request - generate captcha
    captcha_question, captcha_answer_correct = generate_captcha()
    session['captcha_answer'] = captcha_answer_correct
    return render_template('signup.html', captcha_question=captcha_question)

# Company Dashboard Routes
@app.route('/company')
@app.route('/company/home')
@company_login_required
def company_home():
    """Company dashboard home page"""
    try:
        print("🏠 Accessing company home dashboard...")
        company_id = session.get('company_id')
        print(f"📊 Company ID from session: {company_id}")
        
        company = get_company_by_id(company_id)
        print(f"🏢 Retrieved company data: {company['company_name'] if company else 'None'}")
        
        if not company:
            print("❌ Company not found in database")
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get dashboard statistics
        print("📈 Getting company statistics...")
        stats = get_company_stats(company_id)
        print(f"📊 Company stats: {stats}")
        
        # Get recent notifications
        print("🔔 Getting notifications...")
        notifications_response = supabase.table('notifications').select('*').eq('recipient_id', company_id).eq('recipient_type', 'company').order('created_at', desc=True).limit(5).execute()
        notifications = notifications_response.data if notifications_response.data else []
        print(f"🔔 Notifications count: {len(notifications)}")
        
        # Get recent internships
        print("💼 Getting recent internships...")
        internships_response = supabase.table('internships').select('*').eq('company_id', company_id).order('created_at', desc=True).limit(5).execute()
        internships = internships_response.data if internships_response.data else []
        print(f"💼 Internships count: {len(internships)}")
        
        print("✅ Rendering company home template...")
        return render_template('company/home.html', 
                             company=company, 
                             stats=stats, 
                             notifications=notifications,
                             internships=internships,
                             current_year=datetime.now().year)
        
    except Exception as e:
        print(f"❌ Error in company home: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading dashboard. Please try again.', 'error')
        return redirect(url_for('login'))

@app.route('/company/profile')
@company_login_required
def company_profile():
    """Company profile page"""
    try:
        company_id = session.get('company_id')
        company = get_company_by_id(company_id)
        
        if not company:
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get company statistics
        stats = get_company_stats(company_id)
        
        return render_template('company/profile.html', 
                             company=company, 
                             stats=stats,
                             current_year=datetime.now().year)
        
    except Exception as e:
        print(f"Error in company profile: {e}")
        flash('Error loading profile. Please try again.', 'error')
        return redirect(url_for('company_home'))

@app.route('/company/applications')
@company_login_required
def company_applications():
    """Company applications management page"""
    try:
        company_id = session.get('company_id')
        company = get_company_by_id(company_id)
        
        if not company:
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        internship_filter = request.args.get('internship', 'all')
        
        # Get all internship IDs for this company first
        internships_response = supabase.table('internships').select('id').eq('company_id', company_id).execute()
        internship_ids = [i['id'] for i in internships_response.data] if internships_response.data else []
        
        all_candidates = []

        # Build query for applications - query through internship_id
        if internship_ids:
            base_query = supabase.table('applications').select('*, users(*), internships(*)').in_('internship_id', internship_ids)
            all_response = base_query.order('applied_date', desc=True).execute()
            all_candidates = all_response.data if all_response.data else []

            query = supabase.table('applications').select('*, users(*), internships(*)').in_('internship_id', internship_ids)
            
            if status_filter != 'all':
                query = query.eq('status', status_filter)
            if internship_filter != 'all':
                query = query.eq('internship_id', internship_filter)
            
            applications_response = query.order('applied_date', desc=True).execute()
            candidates = applications_response.data if applications_response.data else []
        else:
            candidates = []

        for candidate in candidates:
            candidate['interview_details'] = _build_interview_details(candidate)
        
        # Calculate status counts from the applications data
        status_counts = {
            'all': len(all_candidates),
            'new': len([c for c in all_candidates if c.get('status') == 'new']),
            'pending': len([c for c in all_candidates if c.get('status') == 'pending']),
            'under_review': len([c for c in all_candidates if c.get('status') == 'under_review']),
            'reviewed': len([c for c in all_candidates if c.get('status') == 'reviewed']),
            'shortlisted': len([c for c in all_candidates if c.get('status') == 'shortlisted']),
            'interview_scheduled': len([c for c in all_candidates if c.get('status') == 'interview_scheduled']),
            'interview_completed': len([c for c in all_candidates if c.get('status') == 'interview_completed']),
            'waitlisted': len([c for c in all_candidates if c.get('status') == 'waitlisted']),
            'rejected': len([c for c in all_candidates if c.get('status') == 'rejected']),
            'selected': len([c for c in all_candidates if c.get('status') == 'selected']),
            'accepted': len([c for c in all_candidates if c.get('status') == 'accepted'])
        }
        
        # Get internships for filter dropdown
        internships_response = supabase.table('internships').select('id, title').eq('company_id', company_id).execute()
        internships = internships_response.data if internships_response.data else []
        
        return render_template('company/manage_application.html', 
                             company=company,
                             candidates=candidates,
                             status_counts=status_counts,
                             internships=internships,
                             current_status=status_filter,
                             current_internship=internship_filter)
        
    except Exception as e:
        print(f"Error in company applications: {e}")
        flash('Error loading applications. Please try again.', 'error')
        return redirect(url_for('company_home'))

@app.route('/company/internships')
@company_login_required
def company_internships():
    """Company internships management page"""
    try:
        company_id = session.get('company_id')
        company = get_company_by_id(company_id)
        
        if not company:
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get company statistics
        stats = get_company_stats(company_id)
        
        # Get internships
        internships_response = supabase.table('internships').select('*').eq('company_id', company_id).order('created_at', desc=True).execute()
        internships = internships_response.data if internships_response.data else []

        # Normalize JSON-like fields for safe template rendering.
        for internship in internships:
            requirements_value = internship.get('requirements')
            if isinstance(requirements_value, str):
                try:
                    internship['requirements'] = json.loads(requirements_value) if requirements_value else []
                except Exception:
                    internship['requirements'] = []
            elif requirements_value is None:
                internship['requirements'] = []

            preferred_value = internship.get('preferred_qualifications')
            if isinstance(preferred_value, str):
                try:
                    internship['preferred_qualifications'] = json.loads(preferred_value) if preferred_value else []
                except Exception:
                    internship['preferred_qualifications'] = []
            elif preferred_value is None:
                internship['preferred_qualifications'] = []
        
        # Get available skills for the modal
        skills_response = supabase.table('available_skills').select('*').eq('is_active', True).order('category, display_order').execute()
        available_skills = skills_response.data if skills_response.data else []
        
        return render_template('company/manage_internship.html', 
                             company=company,
                             stats=stats,
                             internships=internships,
                             available_skills=available_skills)
        
    except Exception as e:
        print(f"Error in company internships: {e}")
        flash('Error loading internships. Please try again.', 'error')
        return redirect(url_for('company_home'))

@app.route('/company/candidates')
@company_login_required
def company_candidates():
    """Company candidates/applications management page"""
    try:
        company_id = session.get('company_id')
        company = get_company_by_id(company_id)
        
        if not company:
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get company stats
        stats = get_company_stats(company_id)
        
        # Try to use the helper function first, then fallback to direct query.
        applications = []
        try:
            applications_response = supabase.rpc('get_company_applications', {'company_id_param': company_id}).execute()
            if applications_response.data:
                applications = applications_response.data
        except Exception as e:
            print(f"Helper function not available, falling back to manual query: {e}")
            # Fallback to manual query
            internship_ids = []
            try:
                internships_response = supabase.table('internships').select('id').eq('company_id', company_id).execute()
                if internships_response.data:
                    internship_ids = [i['id'] for i in internships_response.data]
            except Exception as e:
                print(f"Error getting internship IDs: {e}")
            
            if internship_ids:
                try:
                    applications_response = supabase.table('applications').select('*, users!inner(*), internships!inner(*)').in_('internship_id', internship_ids).execute()
                    applications = applications_response.data if applications_response.data else []
                except Exception as e:
                    print(f"Error getting applications: {e}")

        normalized_applications = []
        for app_row in applications:
            user_row = app_row.get('users') if isinstance(app_row.get('users'), dict) else {}
            internship_row = app_row.get('internships') if isinstance(app_row.get('internships'), dict) else {}

            application_id = app_row.get('id') or app_row.get('application_id')
            app_row_for_interview = dict(app_row or {})
            if application_id and not app_row_for_interview.get('id'):
                app_row_for_interview['id'] = application_id
            interview_details = _build_interview_details(app_row_for_interview)

            if not interview_details.get('join_url') and application_id:
                payload = _parse_interview_notes_payload(app_row.get('interview_notes'))
                room_id = payload.get('interview_room_id')
                if room_id:
                    try:
                        interview_details['join_url'] = url_for('interview_room', room_id=room_id, application_id=application_id)
                    except Exception:
                        interview_details['join_url'] = ''

            # Handle flattened RPC shapes as well.
            user_id = (
                user_row.get('id')
                or app_row.get('student_id')
                or app_row.get('user_id')
                or app_row.get('applicant_id')
                or app_row.get('candidate_id')
            )
            full_name = (
                user_row.get('full_name')
                or app_row.get('student_name')
                or app_row.get('full_name')
                or app_row.get('candidate_name')
                or 'Unknown Candidate'
            )
            email = user_row.get('email') or app_row.get('student_email') or app_row.get('email') or ''
            qualification = user_row.get('qualification') or app_row.get('qualification') or ''
            university = user_row.get('university') or app_row.get('university') or ''

            skills_value = user_row.get('skills') if user_row else app_row.get('skills')
            if isinstance(skills_value, str):
                skills = [s.strip() for s in skills_value.split(',') if s.strip()]
            elif isinstance(skills_value, list):
                skills = [str(s).strip() for s in skills_value if str(s).strip()]
            else:
                skills = []

            normalized_applications.append({
                'application_id': application_id,
                'user_id': user_id,
                'full_name': full_name,
                'email': email,
                'qualification': qualification,
                'university': university,
                'skills': skills,
                'status': str(app_row.get('status') or 'pending').strip().lower(),
                'applied_date': app_row.get('applied_date') or app_row.get('created_at') or '',
                'match_score': _safe_float(app_row.get('match_score'), 0.0),
                'internship_title': internship_row.get('title') or app_row.get('internship_title') or 'Internship',
                'interview_details': interview_details,
            })

        normalized_applications.sort(key=lambda row: str(row.get('applied_date') or ''), reverse=True)

        status_counts = {
            'all': len(normalized_applications),
            'new': len([r for r in normalized_applications if r.get('status') == 'new']),
            'pending': len([r for r in normalized_applications if r.get('status') == 'pending']),
            'under_review': len([r for r in normalized_applications if r.get('status') == 'under_review']),
            'shortlisted': len([r for r in normalized_applications if r.get('status') == 'shortlisted']),
            'interview_scheduled': len([r for r in normalized_applications if r.get('status') == 'interview_scheduled']),
            'rejected': len([r for r in normalized_applications if r.get('status') == 'rejected']),
        }
        
        return render_template('company/candidate.html', 
                             company=company,
                             stats=stats,
                             applications=normalized_applications,
                             status_counts=status_counts)
        
    except Exception as e:
        print(f"Error in company candidates: {e}")
        flash('Error loading candidates. Please try again.', 'error')
        return redirect(url_for('company_home'))

@app.route('/company/analytics')
@company_login_required
def company_analytics():
    """Company analytics and reports page"""
    try:
        company_id = session.get('company_id')
        company = get_company_by_id(company_id)
        
        if not company:
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get company stats
        stats = get_company_stats(company_id)
        
        # Get analytics data
        analytics_data = {
            'monthly_applications': [],
            'top_skills': [],
            'application_trends': {},
            'internship_performance': []
        }
        
        # You can expand this with actual analytics queries
        
        return render_template('company/analytics.html', 
                             company=company,
                             stats=stats,
                             analytics=analytics_data)
        
    except Exception as e:
        print(f"Error in company analytics: {e}")
        flash('Error loading analytics. Please try again.', 'error')
        return redirect(url_for('company_home'))

@app.route('/company/candidate/<int:candidate_id>')
@company_login_required
def company_candidate_detail(candidate_id):
    """Company candidate detail page"""
    try:
        company_id = session.get('company_id')
        company = get_company_by_id(company_id)
        
        if not company:
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Get candidate details
        try:
            candidate_response = supabase.table('users').select('*').eq('id', candidate_id).execute()
            candidate = candidate_response.data[0] if candidate_response.data else None
        except Exception as e:
            print(f"Error getting candidate: {e}")
            candidate = None
        
        if not candidate:
            flash('Candidate not found.', 'error')
            return redirect(url_for('company_candidates'))
        
        # Get candidate's applications to this company
        try:
            applications_response = supabase.table('applications').select('*, internships!inner(*)').eq('student_id', candidate_id).eq('company_id', company_id).execute()
            applications = applications_response.data if applications_response.data else []
        except Exception as e:
            print(f"Error getting candidate applications: {e}")
            applications = []
        
        return render_template('company/candidate_detail.html', 
                             company=company,
                             candidate=candidate,
                             applications=applications)
        
    except Exception as e:
        print(f"Error in company candidate detail: {e}")
        flash('Error loading candidate details. Please try again.', 'error')
        return redirect(url_for('company_candidates'))

# Company API Routes
@app.route('/api/company/profile', methods=['PUT'])
@company_login_required
def update_company_profile():
    """Update company profile"""
    try:
        company_id = session.get('company_id')
        data = request.get_json()
        
        # Update company profile
        update_data = {
            'company_name': data.get('company_name'),
            'contact_person': data.get('contact_person'),
            'phone': data.get('phone'),
            'industry': data.get('industry'),
            'company_type': data.get('company_type'),
            'employee_count': data.get('employee_count'),
            'established_year': data.get('established_year'),
            'website': data.get('website'),
            'description': data.get('description'),
            'address': data.get('address'),
            'city': data.get('city'),
            'state': data.get('state'),
            'gst_number': data.get('gst_number')
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        response = supabase.table('companies').update(update_data).eq('id', company_id).execute()
        
        if response.data:
            # Update session if company name changed
            if 'company_name' in update_data:
                session['company_name'] = update_data['company_name']
            
            return jsonify({'success': True, 'message': 'Profile updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update profile'}), 400
        
    except Exception as e:
        print(f"Error updating company profile: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/change-password', methods=['POST'])
@company_login_required
def change_company_password():
    """Change company password"""
    try:
        company_id = session.get('company_id')
        data = request.get_json()
        new_password = data.get('new_password')
        
        if not new_password:
            return jsonify({'success': False, 'message': 'New password is required'}), 400
        
        # Validate password
        is_valid, message = validate_password(new_password)
        if not is_valid:
            return jsonify({'success': False, 'message': message}), 400
        
        # Update password
        password_hash = generate_password_hash(new_password)
        response = supabase.table('companies').update({'password_hash': password_hash}).eq('id', company_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Password changed successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to change password'}), 400
        
    except Exception as e:
        print(f"Error changing company password: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/request-verification', methods=['POST'])
@company_login_required
def request_company_verification():
    """Request company verification"""
    try:
        company_id = session.get('company_id')
        
        # You can add verification request logic here
        # For now, just mark as requested
        
        return jsonify({'success': True, 'message': 'Verification request submitted successfully'})
        
    except Exception as e:
        print(f"Error requesting verification: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/download-data')
@company_login_required
def download_company_data():
    """Download company data"""
    try:
        company_id = session.get('company_id')
        
        # Create a simple CSV download for company data
        # This is a placeholder - implement based on your requirements
        
        return jsonify({'success': True, 'message': 'Download will start shortly'})
        
    except Exception as e:
        print(f"Error downloading data: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

# Application Management API Routes
@app.route('/api/company/update_application_status', methods=['POST'])
@company_login_required  
def update_application_status():
    """Update application status - alias for template compatibility"""
    try:
        data = request.get_json()
        application_id = data.get('application_id')
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        if not application_id or not new_status:
            return jsonify({'success': False, 'message': 'Missing application ID or status'}), 400
        
        company_id = session.get('company_id')
        
        # Verify the application belongs to this company
        application_response = supabase.table('applications').select('*, internships!inner(*)').eq('id', application_id).eq('internships.company_id', company_id).execute()
        
        if not application_response.data:
            return jsonify({'success': False, 'message': 'Application not found'}), 404
        
        update_data = {
            'status': new_status,
            'status_updated_date': datetime.now(timezone.utc).isoformat()
        }
        if notes:
            update_data['company_notes'] = notes

        if new_status in ['interview_scheduled', 'interview_completed']:
            interview_date = data.get('interview_date')
            if interview_date:
                update_data['interview_date'] = interview_date
            interview_type = data.get('interview_type')
            if interview_type:
                update_data['interview_type'] = interview_type

            existing_app = application_response.data[0]
            interview_payload = _merge_interview_notes_payload(existing_app.get('interview_notes'), {
                'interviewer_role': data.get('interviewer_role'),
                'interviewer_name': data.get('interviewer_name'),
                'interviewer_email': data.get('interviewer_email'),
                'communication_mode': data.get('communication_mode'),
                'meeting_link': data.get('meeting_link'),
                'meeting_id': data.get('meeting_id'),
                'duration_minutes': data.get('duration_minutes'),
                'interview_notes_text': data.get('interview_notes_text') or notes,
                'company_confirmed': True,
            })
            update_data['interview_notes'] = json.dumps(interview_payload)

        # Update the application status
        update_response = supabase.table('applications').update(update_data).eq('id', application_id).execute()
        
        if update_response.data:
            return jsonify({'success': True, 'message': 'Application status updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update application status'}), 500
            
    except Exception as e:
        print(f"Error updating application status: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.route('/api/company/applications/<int:application_id>/status', methods=['PUT'])
@company_login_required
def update_application_status_detailed():
    """Update application status"""
    try:
        company_id = session.get('company_id')
        application_id = request.view_args['application_id']
        data = request.get_json()
        
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        if not new_status:
            return jsonify({'success': False, 'message': 'Status is required'}), 400
        
        # Verify application belongs to this company
        app_response = supabase.table('applications').select('*').eq('id', application_id).eq('company_id', company_id).execute()
        
        if not app_response.data:
            return jsonify({'success': False, 'message': 'Application not found'}), 404
        
        # Update application status
        update_data = {
            'status': new_status,
            'company_notes': notes,
            'status_updated_date': datetime.now(timezone.utc).isoformat()
        }
        
        if new_status in ['interview_scheduled', 'interview_completed']:
            interview_date = data.get('interview_date')
            if interview_date:
                update_data['interview_date'] = interview_date
            update_data['interview_type'] = data.get('interview_type', 'video')
            existing_app = app_response.data[0]
            interview_payload = _merge_interview_notes_payload(existing_app.get('interview_notes'), {
                'interviewer_role': data.get('interviewer_role'),
                'interviewer_name': data.get('interviewer_name'),
                'interviewer_email': data.get('interviewer_email'),
                'communication_mode': data.get('communication_mode'),
                'meeting_link': data.get('meeting_link'),
                'meeting_id': data.get('meeting_id'),
                'duration_minutes': data.get('duration_minutes'),
                'interview_notes_text': data.get('interview_notes') or data.get('interview_notes_text'),
                'company_confirmed': True,
            })
            update_data['interview_notes'] = json.dumps(interview_payload)
        
        response = supabase.table('applications').update(update_data).eq('id', application_id).execute()
        
        if response.data:
            # Create notification for student
            student_id = app_response.data[0]['student_id']
            notification_data = {
                'recipient_id': student_id,
                'recipient_type': 'student',
                'title': f'Application Status Updated',
                'message': f'Your application status has been updated to: {new_status.replace("_", " ").title()}',
                'notification_type': 'status_update',
                'related_application_id': application_id
            }
            
            supabase.table('notifications').insert(notification_data).execute()
            
            return jsonify({'success': True, 'message': 'Application status updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update status'}), 400
        
    except Exception as e:
        print(f"Error updating application status: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/applications/<int:application_id>/schedule-interview', methods=['POST'])
@company_login_required
def schedule_application_interview(application_id):
    """Schedule interview with interviewer role and real communication details."""
    try:
        company_id = session.get('company_id')
        data = request.get_json() or {}

        app_response = (
            supabase.table('applications')
            .select('*')
            .eq('id', application_id)
            .limit(1)
            .execute()
        )
        if not app_response.data:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        existing_row = app_response.data[0]
        owner_matches = _safe_int(existing_row.get('company_id'), -1) == _safe_int(company_id, -2)
        if not owner_matches:
            internship_id = existing_row.get('internship_id')
            if internship_id:
                try:
                    internship_rows = (
                        supabase.table('internships')
                        .select('id, company_id')
                        .eq('id', internship_id)
                        .eq('company_id', company_id)
                        .limit(1)
                        .execute()
                        .data or []
                    )
                    owner_matches = bool(internship_rows)
                except Exception:
                    owner_matches = False

        if not owner_matches:
            return jsonify({'success': False, 'message': 'Application does not belong to your company'}), 403

        interview_date = data.get('interview_date')
        interviewer_role = str(data.get('interviewer_role') or '').strip().lower()
        communication_mode = 'in_app'

        if not interview_date:
            return jsonify({'success': False, 'message': 'Interview date and time is required'}), 400
        if interviewer_role not in ['technical', 'non_technical', 'hr', 'managerial']:
            return jsonify({'success': False, 'message': 'Please choose a valid interviewer role'}), 400
        room_id = f"pmi-{application_id}-{uuid.uuid4().hex[:10]}"

        payload = _merge_interview_notes_payload(existing_row.get('interview_notes'), {
            'interviewer_role': interviewer_role,
            'interviewer_name': data.get('interviewer_name'),
            'interviewer_email': data.get('interviewer_email'),
            'communication_mode': communication_mode,
            'meeting_link': '',
            'interview_room_id': room_id,
            'interview_room_name': room_id,
            'meeting_id': data.get('meeting_id'),
            'duration_minutes': data.get('duration_minutes') or 30,
            'interview_notes_text': data.get('interview_notes_text'),
            'company_confirmed': True,
            'candidate_confirmed': False,
            'candidate_response': 'pending',
            'scheduled_at': datetime.now(timezone.utc).isoformat()
        })

        update_data = {
            'status': 'interview_scheduled',
            'status_updated_date': datetime.now(timezone.utc).isoformat(),
            'interview_date': interview_date,
            'interview_type': data.get('interview_type') or 'video',
            'interview_notes': json.dumps(payload)
        }

        update_variants = [
            update_data,
            {
                'status': 'interview_scheduled',
                'interview_date': interview_date,
                'interview_type': data.get('interview_type') or 'video',
                'interview_notes': json.dumps(payload)
            },
            {
                'status': 'interview_scheduled',
                'interview_date': interview_date,
                'interview_notes': json.dumps(payload)
            },
            {
                'status': 'interview_scheduled',
                'interview_notes': json.dumps(payload)
            },
            {
                'status': 'interview',
                'interview_notes': json.dumps(payload)
            },
        ]

        response = None
        update_errors = []
        for variant in update_variants:
            try:
                response = supabase.table('applications').update(variant).eq('id', application_id).execute()
                if response and response.data:
                    break
            except Exception as update_err:
                update_errors.append(str(update_err))
                continue

        if not response or not response.data:
            concise = ' | '.join(update_errors[-3:]) if update_errors else 'Unknown update error'
            return jsonify({'success': False, 'message': f'Failed to schedule interview: {concise[:240]}'}), 400

        # Notify candidate
        try:
            student_id = existing_row.get('student_id')
            if not student_id:
                for user_col in _candidate_id_column_variants():
                    if existing_row.get(user_col):
                        student_id = existing_row.get(user_col)
                        break
            notification_data = {
                'recipient_id': student_id,
                'recipient_type': 'student',
                'title': 'Interview Scheduled',
                'message': 'Your interview is scheduled. Please confirm your availability and join details in My Applications.',
                'notification_type': 'interview_scheduled',
                'related_application_id': application_id
            }
            supabase.table('notifications').insert(notification_data).execute()
        except Exception as notif_error:
            print(f"Interview notification error (non-blocking): {notif_error}")

        return jsonify({'success': True, 'message': 'Interview scheduled successfully'})
    except Exception as e:
        print(f"Error scheduling interview: {e}")
        return jsonify({'success': False, 'message': f'Server error while scheduling interview: {str(e)[:220]}'}), 500


@app.route('/api/company/applications/<int:application_id>/interview-room', methods=['GET'])
@company_login_required
def get_or_create_interview_room(application_id):
    """Return interviewer join URL for an in-app interview, generating room id if missing."""
    try:
        company_id = session.get('company_id')
        app_rows = (
            supabase.table('applications')
            .select('*')
            .eq('id', application_id)
            .limit(1)
            .execute()
            .data or []
        )
        if not app_rows:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        app_row = app_rows[0]
        owner_matches = _safe_int(app_row.get('company_id'), -1) == _safe_int(company_id, -2)
        if not owner_matches and app_row.get('internship_id'):
            internship_rows = (
                supabase.table('internships')
                .select('id')
                .eq('id', app_row.get('internship_id'))
                .eq('company_id', company_id)
                .limit(1)
                .execute()
                .data or []
            )
            owner_matches = bool(internship_rows)

        if not owner_matches:
            return jsonify({'success': False, 'message': 'Application does not belong to your company'}), 403

        notes_payload = _parse_interview_notes_payload(app_row.get('interview_notes'))
        room_id = notes_payload.get('interview_room_id')
        if not room_id:
            room_id = f"pmi-{application_id}-{uuid.uuid4().hex[:10]}"
            notes_payload['interview_room_id'] = room_id
            notes_payload['interview_room_name'] = room_id
            notes_payload['communication_mode'] = 'in_app'
            supabase.table('applications').update({'interview_notes': json.dumps(notes_payload)}).eq('id', application_id).execute()

        join_url = url_for('interview_room', room_id=room_id, application_id=application_id, role='company')
        return jsonify({'success': True, 'room_id': room_id, 'join_url': join_url})
    except Exception as e:
        print(f"Error preparing interviewer room link: {e}")
        return jsonify({'success': False, 'message': f'Failed to open interview room: {str(e)[:220]}'}), 500


@app.route('/api/applications/<int:application_id>/interview-response', methods=['POST'])
@login_required
def respond_to_interview_schedule(application_id):
    """Allow candidate to confirm or decline interview schedule."""
    try:
        user_id = session.get('user_id')
        data = request.get_json() or {}
        response_action = str(data.get('response') or '').strip().lower()
        response_note = str(data.get('note') or '').strip()

        if response_action not in ['confirmed', 'declined']:
            return jsonify({'success': False, 'message': 'Invalid response action'}), 400

        app_response = (
            supabase.table('applications')
            .select('*')
            .eq('id', application_id)
            .limit(1)
            .execute()
        )
        if not app_response.data:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        application_row = app_response.data[0]
        if not _application_candidate_matches(application_row, user_id):
            return jsonify({'success': False, 'message': 'Unauthorized interview response'}), 403
        if application_row.get('status') != 'interview_scheduled':
            return jsonify({'success': False, 'message': 'Interview is not in scheduled state'}), 400

        payload = _merge_interview_notes_payload(application_row.get('interview_notes'), {
            'candidate_confirmed': response_action == 'confirmed',
            'candidate_response': response_action,
            'candidate_response_note': response_note,
            'candidate_response_at': datetime.now(timezone.utc).isoformat()
        })

        response = (
            supabase.table('applications')
            .update({'interview_notes': json.dumps(payload)})
            .eq('id', application_id)
            .execute()
        )
        if not response.data:
            return jsonify({'success': False, 'message': 'Failed to save interview response'}), 400

        # Notify company
        try:
            notification_data = {
                'recipient_id': application_row.get('company_id'),
                'recipient_type': 'company',
                'title': 'Interview Response Received',
                'message': f'Candidate has {response_action} the interview schedule.',
                'notification_type': 'interview_response',
                'related_application_id': application_id
            }
            supabase.table('notifications').insert(notification_data).execute()
        except Exception as notif_error:
            print(f"Interview response notification error (non-blocking): {notif_error}")

        return jsonify({'success': True, 'message': f'Interview {response_action} successfully'})
    except Exception as e:
        print(f"Error saving interview response: {e}")
        return jsonify({'success': False, 'message': 'Server error while saving response'}), 500


@app.route('/interview/<room_id>')
def interview_room(room_id):
    """In-app interview room for candidate and company participants."""
    try:
        application_id = request.args.get('application_id', type=int)
        if not application_id:
            flash('Invalid interview room link.', 'error')
            return redirect(url_for('index'))

        app_rows = (
            supabase.table('applications')
            .select('*')
            .eq('id', application_id)
            .limit(1)
            .execute()
            .data or []
        )
        if not app_rows:
            flash('Interview application not found.', 'error')
            return redirect(url_for('index'))

        app_row = app_rows[0]
        interview_payload = _parse_interview_notes_payload(app_row.get('interview_notes'))
        if str(interview_payload.get('interview_room_id') or '') != str(room_id):
            flash('Interview room mismatch.', 'error')
            return redirect(url_for('index'))

        participant_role = None
        participant_name = None
        can_view_question_assist = False
        initial_question_context = {}
        initial_questions = []
        is_company_session = bool(session.get('is_company') and session.get('company_id'))
        is_candidate_session = bool(session.get('logged_in') and session.get('user_id'))
        auth_scope = str(session.get('auth_scope') or '').strip().lower()
        requested_role = str(request.args.get('role') or '').strip().lower()

        # Explicit role in URL is honored when authorization succeeds.
        if requested_role == 'company':
            if not is_company_session or _safe_int(app_row.get('company_id'), -1) != _safe_int(session.get('company_id'), -2):
                return jsonify({'success': False, 'message': 'Unauthorized company access'}), 403
            participant_role = 'company'
            participant_name = session.get('company_name') or 'Interviewer'
            can_view_question_assist = True
        elif requested_role == 'candidate':
            if not is_candidate_session or not _application_candidate_matches(app_row, session.get('user_id')):
                return jsonify({'success': False, 'message': 'Unauthorized candidate access'}), 403
            participant_role = 'candidate'
            participant_name = session.get('user_name') or 'Candidate'
        elif auth_scope == 'company' and is_company_session:
            if _safe_int(app_row.get('company_id'), -1) != _safe_int(session.get('company_id'), -2):
                return jsonify({'success': False, 'message': 'Unauthorized company access'}), 403
            participant_role = 'company'
            participant_name = session.get('company_name') or 'Interviewer'
            can_view_question_assist = True
        elif auth_scope == 'candidate' and is_candidate_session:
            if not _application_candidate_matches(app_row, session.get('user_id')):
                return jsonify({'success': False, 'message': 'Unauthorized candidate access'}), 403
            participant_role = 'candidate'
            participant_name = session.get('user_name') or 'Candidate'
        elif is_company_session and not is_candidate_session:
            if _safe_int(app_row.get('company_id'), -1) != _safe_int(session.get('company_id'), -2):
                return jsonify({'success': False, 'message': 'Unauthorized company access'}), 403
            participant_role = 'company'
            participant_name = session.get('company_name') or 'Interviewer'
            can_view_question_assist = True
        elif is_candidate_session and not is_company_session:
            if not _application_candidate_matches(app_row, session.get('user_id')):
                return jsonify({'success': False, 'message': 'Unauthorized candidate access'}), 403
            participant_role = 'candidate'
            participant_name = session.get('user_name') or 'Candidate'
        else:
            # Ambiguous mixed session: do not guess role; require explicit role in link.
            return jsonify({'success': False, 'message': 'Ambiguous session. Please re-open interview from your dashboard.'}), 403

        if participant_role == 'company':
            # Preload suggestions so interviewer sees questions even if client refresh call fails.
                try:
                    notes_payload = _parse_interview_notes_payload(app_row.get('interview_notes'))
                    interviewer_role = str(notes_payload.get('interviewer_role') or 'technical').strip().lower()
                    if interviewer_role not in ['technical', 'non_technical', 'hr', 'managerial']:
                        interviewer_role = 'technical'

                    candidate_id = None
                    for col in _candidate_id_column_variants():
                        if app_row.get(col):
                            candidate_id = app_row.get(col)
                            break

                    candidate_profile = {}
                    if candidate_id:
                        user_rows = (
                            supabase.table('users')
                            .select('id, full_name, skills, qualification, course, experience, area_of_interest')
                            .eq('id', candidate_id)
                            .limit(1)
                            .execute()
                            .data or []
                        )
                        candidate_profile = user_rows[0] if user_rows else {}

                    internship_title = 'Internship Role'
                    if app_row.get('internship_id'):
                        internship_rows = (
                            supabase.table('internships')
                            .select('id, title')
                            .eq('id', app_row.get('internship_id'))
                            .limit(1)
                            .execute()
                            .data or []
                        )
                        if internship_rows:
                            internship_title = internship_rows[0].get('title') or internship_title

                    candidate_name = candidate_profile.get('full_name') or 'Candidate'
                    candidate_skills = _to_string_list(candidate_profile.get('skills'))
                    qualification = candidate_profile.get('qualification') or candidate_profile.get('course') or ''

                    initial_question_context = {
                        'interviewer_role': interviewer_role,
                        'candidate_name': candidate_name,
                        'internship_title': internship_title,
                        'skills_considered': candidate_skills[:5]
                    }
                    initial_questions = _generate_interview_question_suggestions(
                        interviewer_role=interviewer_role,
                        candidate_name=candidate_name,
                        candidate_skills=candidate_skills,
                        internship_title=internship_title,
                        qualification=qualification,
                    )
                except Exception as preload_err:
                    print(f"Question preload warning (non-blocking): {preload_err}")

        return render_template(
            'interview_room.html',
            room_id=room_id,
            application_id=application_id,
            participant_role=participant_role,
            participant_name=participant_name,
            interview_date=app_row.get('interview_date'),
            can_view_question_assist=can_view_question_assist,
            initial_question_context=initial_question_context,
            initial_questions=initial_questions
        )
    except Exception as e:
        print(f"Error loading interview room: {e}")
        flash('Unable to open interview room.', 'error')
        return redirect(url_for('index'))


@app.route('/api/interviews/<int:application_id>/behavior', methods=['POST'])
def record_interview_behavior(application_id):
    """Store interview behavior/attention signals during in-app interviews."""
    try:
        if not (session.get('logged_in') or (session.get('is_company') and session.get('company_id'))):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        app_rows = (
            supabase.table('applications')
            .select('*')
            .eq('id', application_id)
            .limit(1)
            .execute()
            .data or []
        )
        if not app_rows:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        app_row = app_rows[0]
        auth_scope = str(session.get('auth_scope') or '').strip().lower()

        if auth_scope == 'company':
            if not (session.get('is_company') and session.get('company_id')):
                return jsonify({'success': False, 'message': 'Unauthorized'}), 401
            if _safe_int(app_row.get('company_id'), -1) != _safe_int(session.get('company_id'), -2):
                return jsonify({'success': False, 'message': 'Forbidden'}), 403
            actor_id = session.get('company_id')
            actor_role = 'company'
        elif auth_scope == 'candidate':
            if not (session.get('logged_in') and session.get('user_id')):
                return jsonify({'success': False, 'message': 'Unauthorized'}), 401
            if not _application_candidate_matches(app_row, session.get('user_id')):
                return jsonify({'success': False, 'message': 'Forbidden'}), 403
            actor_id = session.get('user_id')
            actor_role = 'candidate'
        elif session.get('logged_in') and session.get('user_id') and _application_candidate_matches(app_row, session.get('user_id')):
            actor_id = session.get('user_id')
            actor_role = 'candidate'
        elif session.get('is_company') and session.get('company_id') and _safe_int(app_row.get('company_id'), -1) == _safe_int(session.get('company_id'), -2):
            actor_id = session.get('company_id')
            actor_role = 'company'
        else:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        payload = request.get_json(silent=True) or {}
        details = {
            'room_id': payload.get('room_id'),
            'face_detected': bool(payload.get('face_detected')),
            'tab_active': bool(payload.get('tab_active')),
            'camera_active': bool(payload.get('camera_active')),
            'metrics': payload.get('metrics') or {},
            'role': actor_role,
            'captured_at': datetime.now(timezone.utc).isoformat()
        }

        log_activity(
            user_id=actor_id,
            action_type='interview_behavior_signal',
            details=details
        )
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error recording interview behavior: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/applications/<int:application_id>/interview-question-suggestions', methods=['GET'])
@company_login_required
def interview_question_suggestions(application_id):
    """Provide interviewer question suggestions based on role + candidate profile + internship."""
    try:
        company_id = session.get('company_id')
        requested_role = str(request.args.get('role') or '').strip().lower()

        app_rows = (
            supabase.table('applications')
            .select('*')
            .eq('id', application_id)
            .limit(1)
            .execute()
            .data or []
        )
        if not app_rows:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        app_row = app_rows[0]
        owner_matches = _safe_int(app_row.get('company_id'), -1) == _safe_int(company_id, -2)
        if not owner_matches and app_row.get('internship_id'):
            internship_rows = (
                supabase.table('internships')
                .select('id')
                .eq('id', app_row.get('internship_id'))
                .eq('company_id', company_id)
                .limit(1)
                .execute()
                .data or []
            )
            owner_matches = bool(internship_rows)
        if not owner_matches:
            return jsonify({'success': False, 'message': 'Application does not belong to your company'}), 403

        notes_payload = _parse_interview_notes_payload(app_row.get('interview_notes'))
        interviewer_role = requested_role or str(notes_payload.get('interviewer_role') or 'technical').strip().lower()
        if interviewer_role not in ['technical', 'non_technical', 'hr', 'managerial']:
            interviewer_role = 'technical'

        candidate_id = None
        for col in _candidate_id_column_variants():
            if app_row.get(col):
                candidate_id = app_row.get(col)
                break

        candidate_profile = {}
        if candidate_id:
            try:
                user_rows = (
                    supabase.table('users')
                    .select('id, full_name, skills, qualification, course, experience, area_of_interest')
                    .eq('id', candidate_id)
                    .limit(1)
                    .execute()
                    .data or []
                )
                candidate_profile = user_rows[0] if user_rows else {}
            except Exception:
                candidate_profile = {}

        internship_title = 'Internship Role'
        if app_row.get('internship_id'):
            try:
                internship_rows = (
                    supabase.table('internships')
                    .select('id, title')
                    .eq('id', app_row.get('internship_id'))
                    .limit(1)
                    .execute()
                    .data or []
                )
                if internship_rows:
                    internship_title = internship_rows[0].get('title') or internship_title
            except Exception:
                pass

        candidate_name = candidate_profile.get('full_name') or 'Candidate'
        candidate_skills = _to_string_list(candidate_profile.get('skills'))
        qualification = candidate_profile.get('qualification') or candidate_profile.get('course') or ''

        questions = _generate_interview_question_suggestions(
            interviewer_role=interviewer_role,
            candidate_name=candidate_name,
            candidate_skills=candidate_skills,
            internship_title=internship_title,
            qualification=qualification,
        )

        return jsonify({
            'success': True,
            'context': {
                'interviewer_role': interviewer_role,
                'candidate_name': candidate_name,
                'internship_title': internship_title,
                'skills_considered': candidate_skills[:5]
            },
            'questions': questions
        })
    except Exception as e:
        print(f"Error generating interview question suggestions: {e}")
        return jsonify({'success': False, 'message': f'Failed to generate suggestions: {str(e)[:220]}'}), 500

@app.route('/api/company/applications/<int:application_id>/rating', methods=['PUT'])
@company_login_required
def rate_application():
    """Rate an application"""
    try:
        company_id = session.get('company_id')
        application_id = request.view_args['application_id']
        data = request.get_json()
        
        rating = data.get('rating')
        notes = data.get('notes', '')
        
        if not rating or not (1 <= rating <= 5):
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400
        
        # Verify application belongs to this company
        app_response = supabase.table('applications').select('*').eq('id', application_id).eq('company_id', company_id).execute()
        
        if not app_response.data:
            return jsonify({'success': False, 'message': 'Application not found'}), 404
        
        # Update application rating
        update_data = {
            'company_rating': rating,
            'company_notes': notes
        }
        
        response = supabase.table('applications').update(update_data).eq('id', application_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Application rated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to rate application'}), 400
        
    except Exception as e:
        print(f"Error rating application: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

# Internship Management API Routes
@app.route('/api/company/internships', methods=['POST'])
@company_login_required
def create_internship():
    """Create a new internship"""
    try:
        company_id = session.get('company_id')
        data = request.get_json(silent=True) or {}
        
        # Validate required fields
        required_fields = ['title', 'description', 'location', 'duration']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field.title()} is required'}), 400
        
        # Prepare internship data
        requirements = data.get('requirements', [])
        if not isinstance(requirements, list):
            requirements = []

        preferred_qualifications = data.get('preferred_qualifications', [])
        if not isinstance(preferred_qualifications, list):
            preferred_qualifications = []

        stipend_amount = data.get('stipend_amount')
        if stipend_amount in ('', None):
            stipend_amount = None
        else:
            try:
                stipend_amount = float(stipend_amount)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Invalid stipend amount'}), 400

        openings = data.get('openings', 1)
        try:
            openings = int(openings)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Invalid number of openings'}), 400

        internship_data = {
            'company_id': company_id,
            'title': data['title'].strip(),
            'description': data['description'].strip(),
            'department': data.get('department', '').strip(),
            'location': data['location'].strip(),
            'work_type': data.get('work_type', 'onsite'),
            'duration': data['duration'].strip(),
            'stipend_amount': stipend_amount,
            'stipend_frequency': data.get('stipend_frequency', 'monthly'),
            'openings': openings,
            'application_deadline': data.get('application_deadline') or None,
            'start_date': data.get('start_date'),
            'requirements': requirements,
            'min_qualification': data.get('min_qualification'),
            'preferred_qualifications': preferred_qualifications,
            'status': data.get('status', 'active')
        }
        
        # Remove None values
        internship_data = {k: v for k, v in internship_data.items() if v is not None}
        
        response = supabase.table('internships').insert(internship_data).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Internship created successfully', 'internship': response.data[0]})
        else:
            return jsonify({'success': False, 'message': 'Failed to create internship'}), 400
        
    except Exception as e:
        print(f"Error creating internship: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/internships/<int:internship_id>', methods=['PUT'])
@company_login_required
def update_internship():
    """Update an internship"""
    try:
        company_id = session.get('company_id')
        internship_id = request.view_args['internship_id']
        data = request.get_json(silent=True) or {}
        
        # Verify internship belongs to this company
        internship_response = supabase.table('internships').select('*').eq('id', internship_id).eq('company_id', company_id).execute()
        
        if not internship_response.data:
            return jsonify({'success': False, 'message': 'Internship not found'}), 404
        
        # Prepare update data
        update_data = {}
        updateable_fields = [
            'title', 'description', 'department', 'location', 'work_type', 
            'duration', 'stipend_amount', 'stipend_frequency', 'openings',
            'application_deadline', 'start_date', 'min_qualification', 'status'
        ]
        
        for field in updateable_fields:
            if field in data:
                update_data[field] = data[field]

        # Normalize numeric and optional fields.
        if 'stipend_amount' in update_data and update_data['stipend_amount'] in ('', None):
            update_data['stipend_amount'] = None
        elif 'stipend_amount' in update_data:
            try:
                update_data['stipend_amount'] = float(update_data['stipend_amount'])
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Invalid stipend amount'}), 400

        if 'openings' in update_data:
            try:
                update_data['openings'] = int(update_data['openings'])
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Invalid number of openings'}), 400

        if 'application_deadline' in update_data and update_data['application_deadline'] == '':
            update_data['application_deadline'] = None
        
        # Handle JSON fields
        if 'requirements' in data:
            update_data['requirements'] = data['requirements'] if isinstance(data['requirements'], list) else []
        if 'preferred_qualifications' in data:
            update_data['preferred_qualifications'] = data['preferred_qualifications'] if isinstance(data['preferred_qualifications'], list) else []
        
        if not update_data:
            return jsonify({'success': False, 'message': 'No data to update'}), 400
        
        response = supabase.table('internships').update(update_data).eq('id', internship_id).execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Internship updated successfully', 'internship': response.data[0]})
        else:
            return jsonify({'success': False, 'message': 'Failed to update internship'}), 400
        
    except Exception as e:
        print(f"Error updating internship: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/internships/<int:internship_id>', methods=['DELETE'])
@company_login_required
def delete_internship():
    """Delete an internship"""
    try:
        company_id = session.get('company_id')
        internship_id = request.view_args['internship_id']
        
        # Verify internship belongs to this company
        internship_response = supabase.table('internships').select('*').eq('id', internship_id).eq('company_id', company_id).execute()
        
        if not internship_response.data:
            return jsonify({'success': False, 'message': 'Internship not found'}), 404
        
        # Check if there are any applications
        applications_response = supabase.table('applications').select('id').eq('internship_id', internship_id).execute()
        
        if applications_response.data:
            # Don't delete if there are applications, just mark as cancelled
            response = supabase.table('internships').update({'status': 'closed'}).eq('id', internship_id).execute()
            message = 'Internship closed (had applications)'
        else:
            # Safe to delete if no applications
            response = supabase.table('internships').delete().eq('id', internship_id).execute()
            message = 'Internship deleted successfully'
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        print(f"Error deleting internship: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/internships/<int:internship_id>/status', methods=['PATCH'])
@company_login_required
def update_internship_status(internship_id):
    """Update internship status."""
    try:
        company_id = session.get('company_id')
        data = request.get_json(silent=True) or {}
        status = data.get('status')

        valid_statuses = {'draft', 'active', 'paused', 'closed', 'expired'}
        if status not in valid_statuses:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400

        internship_response = supabase.table('internships').select('id').eq('id', internship_id).eq('company_id', company_id).execute()
        if not internship_response.data:
            return jsonify({'success': False, 'message': 'Internship not found'}), 404

        response = supabase.table('internships').update({'status': status}).eq('id', internship_id).execute()
        if response.data:
            return jsonify({'success': True, 'message': 'Internship status updated successfully'})

        return jsonify({'success': False, 'message': 'Failed to update status'}), 400
    except Exception as e:
        print(f"Error updating internship status: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/skills')
@company_login_required
def get_available_skills():
    """Get all available skills for internship requirements"""
    try:
        response = supabase.table('available_skills').select('*').eq('is_active', True).order('category, display_order').execute()
        
        skills = response.data if response.data else []
        
        # Group by category
        skills_by_category = {}
        for skill in skills:
            category = skill['category']
            if category not in skills_by_category:
                skills_by_category[category] = []
            skills_by_category[category].append({
                'code': skill['skill_code'],
                'name': skill['skill_name']
            })
        
        return jsonify({'success': True, 'skills': skills_by_category})
        
    except Exception as e:
        print(f"Error getting skills: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

# Dashboard Data API Routes
@app.route('/api/company/dashboard-stats')
@company_login_required
def get_dashboard_stats():
    """Get real-time dashboard statistics"""
    try:
        company_id = session.get('company_id')
        stats = get_company_stats(company_id)
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/notifications')
@company_login_required
def get_company_notifications():
    """Get company notifications"""
    try:
        company_id = session.get('company_id')
        limit = request.args.get('limit', 10, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        query = supabase.table('notifications').select('*').eq('recipient_id', company_id).eq('recipient_type', 'company')
        
        if unread_only:
            query = query.eq('is_read', False)
        
        response = query.order('created_at', desc=True).limit(limit).execute()
        
        notifications = response.data if response.data else []
        
        return jsonify({'success': True, 'notifications': notifications})
        
    except Exception as e:
        print(f"Error getting notifications: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/company/notifications/<int:notification_id>/read', methods=['PUT'])
@company_login_required
def mark_notification_read():
    """Mark notification as read"""
    try:
        company_id = session.get('company_id')
        notification_id = request.view_args['notification_id']
        
        # Verify notification belongs to this company
        response = supabase.table('notifications').update({
            'is_read': True,
            'read_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', notification_id).eq('recipient_id', company_id).eq('recipient_type', 'company').execute()
        
        if response.data:
            return jsonify({'success': True, 'message': 'Notification marked as read'})
        else:
            return jsonify({'success': False, 'message': 'Notification not found'}), 404
        
    except Exception as e:
        print(f"Error marking notification as read: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


# ==========================================
# APPLICANT / STUDENT — INTERNSHIP BROWSE & APPLY
# ==========================================

def _candidate_id_column_variants():
    """Possible candidate-id columns used by applications table across schema revisions."""
    return ['student_id', 'user_id', 'applicant_id', 'candidate_id', 'candidate_user_id']


def _to_string_list(value):
    """Normalize mixed JSON/text values to a simple list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
            if isinstance(parsed, str):
                return [s.strip() for s in parsed.split(',') if s.strip()]
        except Exception:
            pass
        return [s.strip() for s in raw.split(',') if s.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _looks_like_missing_column_error(error_text, column_name):
    msg = str(error_text or '').lower()
    col = str(column_name or '').lower()
    return f"'{col}'" in msg and 'could not find the' in msg and 'column' in msg


def _force_array_field(table_name, row_id_column, row_id, field_name, raw_value):
    """Best-effort coercion to store/verify array-like data for DB trigger compatibility."""
    normalized = _to_string_list(raw_value)
    candidate_values = [
        normalized,
        json.dumps(normalized),
        json.dumps(normalized or []),
    ]

    errors = []
    for candidate in candidate_values:
        try:
            supabase.table(table_name).update({field_name: candidate}).eq(row_id_column, row_id).execute()
            check_rows = (
                supabase.table(table_name)
                .select(field_name)
                .eq(row_id_column, row_id)
                .limit(1)
                .execute()
                .data or []
            )
            if not check_rows:
                continue
            stored_value = (check_rows[0] or {}).get(field_name)
            if _to_string_list(stored_value) == normalized:
                return True, normalized, ''
        except Exception as err:
            errors.append(str(err))
            # If field doesn't exist in this schema revision, skip this field.
            if _looks_like_missing_column_error(err, field_name):
                return True, normalized, ''

    return False, normalized, ' | '.join(errors[-3:])

@app.route('/internships')
@login_required
def internships_list():
    """Browse all active internships posted by companies"""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return redirect(url_for('login'))

        # Fetch all active internships with company info
        internships_response = (
            supabase.table('internships')
            .select('*, companies(company_name, industry, city, state, company_type)')
            .eq('status', 'active')
            .order('created_at', desc=True)
            .execute()
        )
        internships = internships_response.data if internships_response.data else []

        # Parse JSON-like array fields and add computed display values
        for internship in internships:
            req = internship.get('requirements')
            if isinstance(req, str):
                try:
                    internship['requirements'] = json.loads(req) if req else []
                except Exception:
                    internship['requirements'] = []
            elif req is None:
                internship['requirements'] = []

            pq = internship.get('preferred_qualifications')
            if isinstance(pq, str):
                try:
                    internship['preferred_qualifications'] = json.loads(pq) if pq else []
                except Exception:
                    internship['preferred_qualifications'] = []
            elif pq is None:
                internship['preferred_qualifications'] = []

        # Collect internship IDs the user has already applied to
        applied_ids = set()
        application_statuses = {}
        if internships:
            internship_ids = [i['id'] for i in internships]
            applied_response = None
            for user_col in _candidate_id_column_variants():
                try:
                    applied_response = (
                        supabase.table('applications')
                        .select('internship_id, status')
                        .eq(user_col, user['id'])
                        .in_('internship_id', internship_ids)
                        .execute()
                    )
                    break
                except Exception:
                    continue

            applied_rows = applied_response.data if applied_response and applied_response.data else []
            for app_row in applied_rows:
                applied_ids.add(app_row['internship_id'])
                application_statuses[app_row['internship_id']] = app_row['status']

        return render_template('internships.html',
                               user=user,
                               internships=internships,
                               applied_ids=applied_ids,
                               application_statuses=application_statuses)

    except Exception as e:
        print(f"Error loading internships: {e}")
        import traceback; traceback.print_exc()
        flash('Error loading internships. Please try again.', 'error')
        return redirect(url_for('home'))


@app.route('/api/internships/<int:internship_id>/apply', methods=['POST'])
@login_required
def apply_internship(internship_id):
    """Submit an application for an internship"""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        if not user.get('profile_completed'):
            return jsonify({'success': False, 'message': 'Please complete your profile before applying'}), 400

        # Verify internship exists and is active
        internship_response = (
            supabase.table('internships')
            .select('id, title, company_id, status')
            .eq('id', internship_id)
            .eq('status', 'active')
            .execute()
        )
        if not internship_response.data:
            return jsonify({'success': False, 'message': 'Internship not found or no longer active'}), 404

        internship = internship_response.data[0]

        # Normalize likely JSON-array source fields so DB triggers/functions don't crash.
        normalize_checks = []
        normalize_checks.append(
            _force_array_field('users', 'id', user['id'], 'skills', user.get('skills'))
        )
        normalize_checks.append(
            _force_array_field('users', 'id', user['id'], 'languages', user.get('languages'))
        )
        normalize_checks.append(
            _force_array_field('internships', 'id', internship_id, 'requirements', internship.get('requirements'))
        )
        normalize_checks.append(
            _force_array_field('internships', 'id', internship_id, 'preferred_qualifications', internship.get('preferred_qualifications'))
        )

        normalize_failures = [msg for ok, _arr, msg in normalize_checks if not ok and msg]
        if normalize_failures:
            return jsonify({
                'success': False,
                'message': f"Apply failed: JSON normalization failed. {(' | '.join(normalize_failures))[:260]}"
            }), 500

        # Detect which candidate id columns actually exist in this environment.
        valid_user_columns = []
        schema_probe_errors = []
        for user_col in _candidate_id_column_variants():
            try:
                (
                    supabase.table('applications')
                    .select('id')
                    .eq(user_col, user['id'])
                    .limit(1)
                    .execute()
                )
                valid_user_columns.append(user_col)
            except Exception as probe_err:
                schema_probe_errors.append(str(probe_err))
                continue

        if not valid_user_columns:
            return jsonify({
                'success': False,
                'message': f"Apply failed: Could not find candidate id column in applications table. {(' | '.join(schema_probe_errors[-2:]))[:220]}"
            }), 500

        # Check for duplicate application using the first valid candidate column.
        existing_response = (
            supabase.table('applications')
            .select('id, status')
            .eq(valid_user_columns[0], user['id'])
            .eq('internship_id', internship_id)
            .execute()
        )

        if existing_response.data:
            existing_status = existing_response.data[0].get('status', 'pending')
            return jsonify({
                'success': False,
                'already_applied': True,
                'message': f'You have already applied. Current status: {existing_status.replace("_", " ").title()}'
            }), 200

        # Insert new application with schema-tolerant fallback.
        now_iso = datetime.now(timezone.utc).isoformat()
        insert_response = None
        last_insert_error = None
        insert_errors = []

        candidate_payloads = []
        status_variants = ['pending', 'new', 'applied', 'submitted']
        for user_col in valid_user_columns:
            for status_value in status_variants:
                candidate_payloads.extend([
                    {
                        user_col: user['id'],
                        'internship_id': internship_id,
                        'status': status_value,
                        'company_id': internship['company_id'],
                        'applied_date': now_iso
                    },
                    {
                        user_col: user['id'],
                        'internship_id': internship_id,
                        'status': status_value,
                        'company_id': internship['company_id'],
                        'created_at': now_iso
                    },
                    {
                        user_col: user['id'],
                        'internship_id': internship_id,
                        'status': status_value,
                        'applied_date': now_iso
                    },
                    {
                        user_col: user['id'],
                        'internship_id': internship_id,
                        'status': status_value
                    },
                ])
            candidate_payloads.extend([
                {
                    user_col: user['id'],
                    'internship_id': internship_id,
                    'company_id': internship['company_id'],
                    'applied_date': now_iso
                },
                {
                    user_col: user['id'],
                    'internship_id': internship_id,
                    'company_id': internship['company_id']
                },
                {
                    user_col: user['id'],
                    'internship_id': internship_id
                },
            ])

        for payload in candidate_payloads:
            try:
                insert_response = supabase.table('applications').insert(payload).execute()
                if insert_response.data:
                    break
            except Exception as insert_err:
                last_insert_error = insert_err
                insert_errors.append(str(insert_err))
                continue

        if (not insert_response or not insert_response.data) and last_insert_error:
            concise_errors = ' | '.join(insert_errors[-3:]) if insert_errors else str(last_insert_error)
            raise Exception(f"Applications insert failed. {concise_errors}")

        if insert_response.data:
            # Create a notification for the company
            try:
                notification_data = {
                    'recipient_id': internship['company_id'],
                    'recipient_type': 'company',
                    'title': 'New Application Received',
                    'message': f'{user.get("full_name", "An applicant")} applied for {internship["title"]}',
                    'notification_type': 'new_application',
                    'related_application_id': insert_response.data[0]['id']
                }
                supabase.table('notifications').insert(notification_data).execute()
            except Exception as notif_err:
                print(f"Notification error (non-blocking): {notif_err}")

            return jsonify({'success': True, 'message': 'Application submitted successfully!'})
        else:
            return jsonify({'success': False, 'message': 'Failed to submit application. Please try again.'}), 500

    except Exception as e:
        print(f"Error applying for internship: {e}")
        lower_error = str(e).lower()
        if 'duplicate' in lower_error or 'unique' in lower_error:
            return jsonify({'success': False, 'already_applied': True, 'message': 'You have already applied for this internship.'}), 200
        return jsonify({'success': False, 'message': f'Apply failed: {str(e)[:260]}'}), 500


@app.route('/my-applications')
@login_required
def my_applications():
    """View all applications submitted by the logged-in student"""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return redirect(url_for('login'))

        # Fetch applications with internship and company details
        apps_response = None
        apps_error = None
        for user_col in _candidate_id_column_variants():
            try:
                apps_response = (
                    supabase.table('applications')
                    .select('*, internships(title, location, duration, stipend_amount, stipend_frequency, work_type, company_id, companies(company_name, industry, city))')
                    .eq(user_col, user['id'])
                    .order('applied_date', desc=True)
                    .execute()
                )
                apps_error = None
                break
            except Exception as err:
                apps_error = err
                continue

        if apps_response is None and apps_error is not None:
            raise apps_error

        applications = apps_response.data if apps_response.data else []

        for app_row in applications:
            app_row['interview_details'] = _build_interview_details(app_row)
            details = app_row.get('interview_details') or {}
            join_url = details.get('join_url') or ''
            if join_url:
                details['join_url'] = join_url if 'role=' in join_url else f"{join_url}{'&' if '?' in join_url else '?'}role=candidate"
            app_row['interview_details'] = details

        return render_template('my_applications.html',
                               user=user,
                               applications=applications)

    except Exception as e:
        print(f"Error loading applications: {e}")
        flash('Error loading your applications. Please try again.', 'error')
        return redirect(url_for('home'))


# ==========================================
# TEAM COLLABORATION & PERFORMANCE EVALUATION
# ==========================================

def _parse_iso_datetime(value):
    """Parse datetime string from DB safely."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        normalized = str(value).replace('Z', '+00:00')
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_interview_notes_payload(raw_value):
    """Parse interview_notes into a dict payload safely."""
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {'legacy_notes': raw_value.strip()}
    return {}


def _merge_interview_notes_payload(existing_notes, updates):
    payload = _parse_interview_notes_payload(existing_notes)
    for key, value in (updates or {}).items():
        if value not in (None, ''):
            payload[key] = value
    return payload


def _build_interview_details(application_row):
    """Build a normalized interview object for templates/APIs."""
    app_row = application_row or {}
    notes_payload = _parse_interview_notes_payload(app_row.get('interview_notes'))
    interview_date = app_row.get('interview_date')
    room_id = notes_payload.get('interview_room_id') or ''
    join_url = ''
    if has_request_context() and room_id and app_row.get('id'):
        try:
            role_hint = None
            auth_scope = str(session.get('auth_scope') or '').strip().lower()
            is_company_session = bool(session.get('is_company') and session.get('company_id'))
            is_candidate_session = bool(session.get('logged_in') and session.get('user_id'))

            if auth_scope == 'company' and is_company_session:
                role_hint = 'company'
            elif auth_scope == 'candidate' and is_candidate_session:
                role_hint = 'candidate'
            elif is_candidate_session and not is_company_session:
                role_hint = 'candidate'
            elif is_company_session and not is_candidate_session:
                role_hint = 'company'

            if role_hint:
                join_url = url_for('interview_room', room_id=room_id, application_id=app_row.get('id'), role=role_hint)
            else:
                join_url = url_for('interview_room', room_id=room_id, application_id=app_row.get('id'))
        except Exception:
            join_url = ''
    return {
        'scheduled': app_row.get('status') in ['interview_scheduled', 'interview_completed'],
        'date': interview_date,
        'type': app_row.get('interview_type') or notes_payload.get('interview_type') or 'video',
        'interviewer_role': notes_payload.get('interviewer_role') or 'technical',
        'interviewer_name': notes_payload.get('interviewer_name') or '',
        'interviewer_email': notes_payload.get('interviewer_email') or '',
        'communication_mode': notes_payload.get('communication_mode') or 'video_call',
        'meeting_link': notes_payload.get('meeting_link') or '',
        'room_id': room_id,
        'join_url': join_url,
        'meeting_id': notes_payload.get('meeting_id') or '',
        'interview_notes_text': notes_payload.get('interview_notes_text') or notes_payload.get('legacy_notes') or '',
        'duration_minutes': _safe_int(notes_payload.get('duration_minutes'), 30),
        'candidate_confirmed': bool(notes_payload.get('candidate_confirmed')),
        'candidate_response': notes_payload.get('candidate_response') or 'pending',
        'candidate_response_note': notes_payload.get('candidate_response_note') or '',
        'candidate_response_at': notes_payload.get('candidate_response_at') or '',
        'company_confirmed': bool(notes_payload.get('company_confirmed')),
    }


TEAM_STATUS_ACTIVE = 'active'
TEAM_STATUS_PAUSED = 'paused'
TEAM_STATUS_CLOSED = 'closed'
ALLOWED_TEAM_STATUSES = {TEAM_STATUS_ACTIVE, TEAM_STATUS_PAUSED, TEAM_STATUS_CLOSED}

MEMBER_PROGRESS_PENDING = 'pending'
MEMBER_PROGRESS_IN_PROGRESS = 'in_progress'
MEMBER_PROGRESS_COMPLETED = 'completed'
ALLOWED_MEMBER_PROGRESS = {
    MEMBER_PROGRESS_PENDING,
    MEMBER_PROGRESS_IN_PROGRESS,
    MEMBER_PROGRESS_COMPLETED
}


def _normalize_team_status(value):
    status = str(value or '').strip().lower()
    return status if status in ALLOWED_TEAM_STATUSES else TEAM_STATUS_ACTIVE


def _team_is_joinable(team_obj):
    return _normalize_team_status((team_obj or {}).get('status')) == TEAM_STATUS_ACTIVE


def _team_visible_for_non_member(team_obj):
    return _normalize_team_status((team_obj or {}).get('status')) == TEAM_STATUS_ACTIVE


def _normalize_member_progress(value):
    status = str(value or '').strip().lower()
    return status if status in ALLOWED_MEMBER_PROGRESS else MEMBER_PROGRESS_PENDING


def _application_candidate_matches(app_row, user_id):
    for col in _candidate_id_column_variants():
        if _safe_int((app_row or {}).get(col), -1) == _safe_int(user_id, -2):
            return True
    return False


def _generate_interview_question_suggestions(interviewer_role, candidate_name, candidate_skills, internship_title, qualification):
    role = str(interviewer_role or 'technical').strip().lower()
    skills = candidate_skills[:5] if candidate_skills else []
    focus_skill = skills[0] if skills else 'your core skill'
    secondary_skill = skills[1] if len(skills) > 1 else 'problem-solving'
    internship = internship_title or 'this internship role'
    qualification_text = qualification or 'your current qualification'

    if role == 'technical':
        questions = [
            {'type': 'Technical', 'skill_focus': focus_skill, 'question': f'Can you explain a project where you used {focus_skill} and what outcome you achieved?'},
            {'type': 'Technical', 'skill_focus': secondary_skill, 'question': f'How do you approach debugging when your {secondary_skill} based solution is not working as expected?'},
            {'type': 'Role Fit', 'skill_focus': internship, 'question': f'What part of {internship} are you most confident to handle from day one?'},
            {'type': 'Technical', 'skill_focus': 'System Thinking', 'question': 'How would you break down a large task into smaller implementable modules?'},
            {'type': 'Behavioral', 'skill_focus': 'Collaboration', 'question': 'Tell me about a time you resolved a technical disagreement in a team.'},
            {'type': 'Technical', 'skill_focus': 'Learning Agility', 'question': 'How do you quickly learn a new tool or framework when a deadline is close?'},
        ]
    elif role in ['hr', 'non_technical']:
        questions = [
            {'type': 'Motivation', 'skill_focus': internship, 'question': f'Why do you want to join {internship}, and what do you expect to learn?'},
            {'type': 'Behavioral', 'skill_focus': 'Communication', 'question': 'Describe a situation where you had to explain a complex idea in simple language.'},
            {'type': 'Behavioral', 'skill_focus': 'Ownership', 'question': 'Tell me about a time you took ownership of a task without being asked.'},
            {'type': 'Culture Fit', 'skill_focus': 'Teamwork', 'question': 'How do you handle feedback from mentors or teammates during high-pressure work?'},
            {'type': 'Career', 'skill_focus': qualification_text, 'question': f'How has your {qualification_text} prepared you for this internship?'},
            {'type': 'Behavioral', 'skill_focus': 'Adaptability', 'question': 'Share an example where plans changed suddenly and how you adapted.'},
        ]
    else:
        questions = [
            {'type': 'Execution', 'skill_focus': 'Prioritization', 'question': 'If you get multiple tasks with the same deadline, how will you prioritize them?'},
            {'type': 'Ownership', 'skill_focus': focus_skill, 'question': f'How would you estimate timeline and risks for a task involving {focus_skill}?'},
            {'type': 'Coordination', 'skill_focus': 'Stakeholder Communication', 'question': 'How do you keep stakeholders updated when work gets blocked?'},
            {'type': 'Decision Making', 'skill_focus': secondary_skill, 'question': f'When would you choose a simple solution over an advanced {secondary_skill} approach?'},
            {'type': 'Behavioral', 'skill_focus': 'Resilience', 'question': 'Describe a setback in a project and how you recovered from it.'},
            {'type': 'Role Fit', 'skill_focus': internship, 'question': f'What measurable outcomes would you target in your first month in {internship}?'},
        ]

    questions.extend([
        {'type': 'Behavioral', 'skill_focus': 'Confidence', 'question': f'{candidate_name}, walk me through your strongest achievement in 60 seconds.'},
        {'type': 'Behavioral', 'skill_focus': 'Self Awareness', 'question': 'What is one skill gap you are actively working on and what is your improvement plan?'},
    ])

    return questions[:10]


def _is_team_deadline_over(team_id):
    """Treat the team deadline as the latest task deadline for that team."""
    try:
        latest_deadline_rows = (
            supabase.table('tasks')
            .select('deadline')
            .eq('team_id', team_id)
            .order('deadline', desc=True)
            .limit(1)
            .execute()
            .data or []
        )
        latest_deadline = _parse_iso_datetime((latest_deadline_rows[0] or {}).get('deadline')) if latest_deadline_rows else None
        if not latest_deadline:
            return False
        return latest_deadline.astimezone(timezone.utc) < datetime.now(timezone.utc)
    except Exception as e:
        print(f"Error checking team deadline window for team {team_id}: {e}")
        return False


def _is_missing_relation_error(error_obj):
    """Detect missing table/relation errors from Supabase/PostgREST messages."""
    try:
        msg = str(error_obj).lower()
        return ('relation' in msg and 'does not exist' in msg) or ('could not find the table' in msg)
    except Exception:
        return False


def _get_user_team_ids(user_id):
    """Return all team IDs for a user."""
    try:
        response = supabase.table('team_members').select('team_id').eq('user_id', user_id).execute()
        return [row['team_id'] for row in (response.data or []) if row.get('team_id')]
    except Exception as e:
        print(f"Error getting team IDs for user {user_id}: {e}")
        return []


def _is_user_in_team(user_id, team_id):
    """Check if user is a member of the given team."""
    try:
        response = supabase.table('team_members').select('id').eq('team_id', team_id).eq('user_id', user_id).limit(1).execute()
        return bool(response.data)
    except Exception:
        return False


def _is_company_team_owner(company_id, team_id):
    """Check if company owns the team."""
    try:
        response = supabase.table('teams').select('id').eq('id', team_id).eq('company_id', company_id).limit(1).execute()
        return bool(response.data)
    except Exception:
        return False


def log_activity(user_id, action_type, team_id=None, task_id=None, duration_minutes=None, details=None):
    """Store activity logs for performance analytics."""
    try:
        payload = {
            'user_id': user_id,
            'team_id': team_id,
            'task_id': task_id,
            'action_type': action_type,
            'duration_minutes': duration_minutes,
            'details': details or {},
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        supabase.table('activity_logs').insert(payload).execute()
    except Exception as e:
        print(f"Activity log error (non-blocking): {e}")


def get_upcoming_deadline_alerts(team_ids=None, assigned_user_id=None, within_hours=48):
    """Get tasks with near/overdue deadlines for lightweight notifications."""
    try:
        query = supabase.table('tasks').select('id, team_id, assigned_to_user_id, title, deadline, status').in_('status', ['pending', 'in_progress', 'blocked'])
        if team_ids:
            query = query.in_('team_id', team_ids)
        if assigned_user_id:
            query = query.eq('assigned_to_user_id', assigned_user_id)

        rows = query.order('deadline').limit(200).execute().data or []
        now_utc = datetime.now(timezone.utc)
        max_window = now_utc + timedelta(hours=within_hours)

        alerts = []
        for row in rows:
            deadline_dt = _parse_iso_datetime(row.get('deadline'))
            if not deadline_dt:
                continue
            deadline_utc = deadline_dt.astimezone(timezone.utc)
            if deadline_utc <= max_window:
                delta_minutes = int((deadline_utc - now_utc).total_seconds() // 60)
                alerts.append({
                    'task_id': row.get('id'),
                    'team_id': row.get('team_id'),
                    'title': row.get('title') or 'Task',
                    'status': row.get('status') or 'pending',
                    'deadline': row.get('deadline'),
                    'minutes_remaining': delta_minutes,
                    'is_overdue': delta_minutes < 0
                })

        alerts.sort(key=lambda x: x['minutes_remaining'])
        return alerts[:20]
    except Exception as e:
        print(f"Error computing deadline alerts: {e}")
        return []


def get_activity_feed(team_ids=None, limit=30):
    """Hydrate activity logs with user names for dashboard feeds."""
    try:
        query = supabase.table('activity_logs').select('*')
        if team_ids:
            query = query.in_('team_id', team_ids)
        logs = query.order('created_at', desc=True).limit(limit).execute().data or []
        if not logs:
            return []

        user_ids = sorted(list({row.get('user_id') for row in logs if row.get('user_id')}))
        users_map = {}
        if user_ids:
            users = supabase.table('users').select('id, full_name').in_('id', user_ids).execute().data or []
            users_map = {u['id']: (u.get('full_name') or 'Unknown') for u in users}

        for row in logs:
            row['user_name'] = users_map.get(row.get('user_id'), 'Unknown')
        return logs
    except Exception as e:
        print(f"Error loading activity feed: {e}")
        return []


def compute_user_performance_metrics(user_id, team_id=None):
    """Compute task completion, timeliness and activity metrics for a user."""
    tasks_query = supabase.table('tasks').select('id, status, deadline, completed_at, created_at').eq('assigned_to_user_id', user_id)
    if team_id:
        tasks_query = tasks_query.eq('team_id', team_id)

    tasks_data = tasks_query.execute().data or []
    total_tasks = len(tasks_data)
    completed_tasks_rows = [t for t in tasks_data if t.get('status') == 'completed']
    completed_tasks = len(completed_tasks_rows)

    task_completion = (completed_tasks / total_tasks * 100) if total_tasks else 0.0

    on_time_count = 0
    for task in completed_tasks_rows:
        deadline_dt = _parse_iso_datetime(task.get('deadline'))
        completed_dt = _parse_iso_datetime(task.get('completed_at'))
        if completed_dt and deadline_dt and completed_dt <= deadline_dt:
            on_time_count += 1

    timeliness = (on_time_count / completed_tasks * 100) if completed_tasks else 0.0

    team_ids = [team_id] if team_id else _get_user_team_ids(user_id)
    messages_sent = 0
    if team_ids:
        try:
            messages_response = supabase.table('team_messages').select('id').eq('sender_id', user_id).in_('team_id', team_ids).execute()
            messages_sent = len(messages_response.data or [])
        except Exception:
            messages_sent = 0

    activity_signal = min(100.0, (completed_tasks * 8.0) + (messages_sent * 2.0))
    score = calculate_performance_score(task_completion, timeliness, activity_signal)

    return {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'messages_sent': messages_sent,
        'task_completion': round(task_completion, 2),
        'timeliness': round(timeliness, 2),
        'activity': round(activity_signal, 2),
        'performance_score': round(score, 2)
    }


def calculate_performance_score(task_completion, timeliness, activity):
    """Weighted performance score formula."""
    return (_safe_float(task_completion) * 0.5) + (_safe_float(timeliness) * 0.3) + (_safe_float(activity) * 0.2)


def _clamp_score(value, minimum=0.0, maximum=100.0):
    value = _safe_float(value, 0.0)
    return max(minimum, min(maximum, value))


def _estimate_ats_score_from_profile(user):
    """Estimate ATS readiness from available user profile signals."""
    if not user:
        return 0.0

    score = 0.0
    profile_keys = [
        'full_name', 'email', 'phone', 'district', 'state', 'qualification',
        'about', 'career_objective', 'experience'
    ]
    completed = 0
    for key in profile_keys:
        value = user.get(key)
        if value not in (None, '', [], {}):
            completed += 1
    score += (completed / len(profile_keys)) * 45.0

    skills = user.get('skills') or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(',') if s.strip()]
    score += min(35.0, len(skills) * 5.0)

    if user.get('profile_completed'):
        score += 12.0

    qualification = str(user.get('qualification') or '').lower()
    if qualification in {'ug', 'pg', 'phd', 'diploma'}:
        score += 8.0

    return round(_clamp_score(score), 2)


def _estimate_github_score(user_id, user=None):
    """Estimate GitHub score from profile signals and logged github activity."""
    if not user:
        user = get_user_by_id(user_id)
    if not user:
        return 0.0

    score = 0.0
    github_fields = ['github', 'github_url', 'github_username']
    if any(user.get(f) for f in github_fields):
        score += 35.0

    projects = user.get('projects')
    if isinstance(projects, list):
        score += min(20.0, len(projects) * 5.0)

    try:
        logs = (
            supabase.table('activity_logs')
            .select('action_type, details, created_at')
            .eq('user_id', user_id)
            .in_('action_type', ['github_commit', 'github_activity'])
            .order('created_at', desc=True)
            .limit(100)
            .execute()
            .data or []
        )

        commit_count = 0
        for row in logs:
            details = row.get('details') or {}
            if isinstance(details, dict):
                commit_count += _safe_int(details.get('commits', 1), 1)
            else:
                commit_count += 1
        score += min(45.0, commit_count * 1.5)
    except Exception as e:
        print(f"GitHub score activity lookup failed for user {user_id}: {e}")

    return round(_clamp_score(score), 2)


def _calculate_total_rank_score(ats_score, github_score, performance_score):
    """Weighted score formula for ranking applicants."""
    total = (_safe_float(ats_score) * 0.4) + (_safe_float(github_score) * 0.3) + (_safe_float(performance_score) * 0.3)
    return round(_clamp_score(total), 2)


def _get_team_capacity(team_obj):
    """Soft capacity limit used to split active and waitlist groups."""
    cap = _safe_int((team_obj or {}).get('max_capacity'), 10)
    return max(1, min(cap, 1000))


def _normalize_team_role(value):
    role = str(value or '').strip()
    return role if role in {'Frontend', 'Backend', 'AI/ML'} else 'Frontend'


def sync_team_membership_from_ranking(team_id, ranked_rows):
    """Ensure team_members mirrors current active/waitlisted ranking state."""
    try:
        active_rows = [r for r in ranked_rows if r.get('status') == 'active']
        waitlisted_rows = [r for r in ranked_rows if r.get('status') == 'waitlisted']

        # Promote active applicants into team_members.
        for row in active_rows:
            user_id = row.get('user_id')
            if not user_id:
                continue

            role = _normalize_team_role(row.get('desired_role'))
            existing = (
                supabase.table('team_members')
                .select('id, role')
                .eq('team_id', team_id)
                .eq('user_id', user_id)
                .limit(1)
                .execute()
                .data or []
            )

            if existing:
                if existing[0].get('role') != role:
                    supabase.table('team_members').update({'role': role}).eq('id', existing[0]['id']).execute()
            else:
                payload = {
                    'team_id': team_id,
                    'user_id': user_id,
                    'role': role,
                    'progress_status': MEMBER_PROGRESS_PENDING,
                    'joined_at': datetime.now(timezone.utc).isoformat()
                }
                try:
                    supabase.table('team_members').insert(payload).execute()
                except Exception as insert_error:
                    if 'progress_status' in str(insert_error).lower() and 'column' in str(insert_error).lower():
                        payload.pop('progress_status', None)
                        supabase.table('team_members').insert(payload).execute()
                    else:
                        raise

        # Demote waitlisted applicants out of active team_membership.
        for row in waitlisted_rows:
            user_id = row.get('user_id')
            if not user_id:
                continue
            supabase.table('team_members').delete().eq('team_id', team_id).eq('user_id', user_id).execute()
    except Exception as e:
        print(f"Error syncing team membership for team {team_id}: {e}")


def recalculate_team_applicant_ranking(team_id):
    """Re-rank all applicants for a team and update active/waitlist statuses."""
    try:
        team_rows = supabase.table('teams').select('*').eq('id', team_id).limit(1).execute().data or []
        if not team_rows:
            return []

        max_capacity = _get_team_capacity(team_rows[0])
        try:
            applications = (
                supabase.table('team_applications')
                .select('id, user_id, total_score, applied_at, manual_rank')
                .eq('team_id', team_id)
                .execute()
                .data or []
            )
        except Exception as read_error:
            # Backward compatibility when manual_rank column is not present yet.
            if 'manual_rank' in str(read_error).lower() and 'column' in str(read_error).lower():
                applications = (
                    supabase.table('team_applications')
                    .select('id, user_id, total_score, applied_at')
                    .eq('team_id', team_id)
                    .execute()
                    .data or []
                )
                for row in applications:
                    row['manual_rank'] = None
            else:
                raise

        manually_ranked = [row for row in applications if row.get('manual_rank') is not None]
        auto_ranked = [row for row in applications if row.get('manual_rank') is None]

        manually_ranked.sort(
            key=lambda row: (
                _safe_int(row.get('manual_rank'), 10**9),
                -_safe_float(row.get('total_score')),
                str(row.get('applied_at') or '')
            )
        )
        auto_ranked.sort(
            key=lambda row: (
                -_safe_float(row.get('total_score')),
                str(row.get('applied_at') or '')
            )
        )

        ordered_rows = manually_ranked + auto_ranked

        for idx, row in enumerate(ordered_rows, start=1):
            status = 'active' if idx <= max_capacity else 'waitlisted'
            supabase.table('team_applications').update({
                'rank': idx,
                'status': status
            }).eq('id', row['id']).execute()

        ranked = (
            supabase.table('team_applications')
            .select('*')
            .eq('team_id', team_id)
            .order('rank')
            .execute()
            .data or []
        )

        sync_team_membership_from_ranking(team_id, ranked)
        return ranked
    except Exception as e:
        print(f"Error recalculating ranking for team {team_id}: {e}")
        return []


def refresh_team_application_scores(team_id, user_id=None):
    """Refresh performance/total score and re-rank (called after activity updates)."""
    try:
        query = supabase.table('team_applications').select('*').eq('team_id', team_id)
        if user_id:
            query = query.eq('user_id', user_id)
        apps = query.execute().data or []

        for app_row in apps:
            uid = app_row.get('user_id')
            if not uid:
                continue
            user = get_user_by_id(uid)
            ats_score = _estimate_ats_score_from_profile(user)
            github_score = _estimate_github_score(uid, user=user)
            perf_metrics = compute_user_performance_metrics(uid, team_id=team_id)
            performance_score = perf_metrics.get('performance_score', 0)
            total_score = _calculate_total_rank_score(ats_score, github_score, performance_score)

            supabase.table('team_applications').update({
                'ats_score': ats_score,
                'github_score': github_score,
                'performance_score': round(_clamp_score(performance_score), 2),
                'total_score': total_score
            }).eq('id', app_row['id']).execute()

        recalculate_team_applicant_ranking(team_id)
    except Exception as e:
        print(f"Error refreshing team application scores: {e}")


def get_team_ranking_snapshot(team_id):
    """Return ranked applications with user info and separated active/waitlist groups."""
    rows = (
        supabase.table('team_applications')
        .select('*')
        .eq('team_id', team_id)
        .order('rank')
        .execute()
        .data or []
    )
    if not rows:
        return {'all': [], 'active': [], 'waitlist': []}

    user_ids = [r.get('user_id') for r in rows if r.get('user_id')]
    users_map = {}
    if user_ids:
        users = supabase.table('users').select('id, full_name, email').in_('id', user_ids).execute().data or []
        users_map = {u['id']: u for u in users}

    for row in rows:
        user_row = users_map.get(row.get('user_id')) or {}
        user_email = (user_row.get('email') or '').strip()
        user_name = (user_row.get('full_name') or '').strip() or user_email or 'Unknown'
        row['user'] = {
            'id': user_row.get('id') or row.get('user_id'),
            'full_name': user_name,
            'email': user_email
        }

    active = [r for r in rows if r.get('status') == 'active']
    waitlist = [r for r in rows if r.get('status') == 'waitlisted']
    return {'all': rows, 'active': active, 'waitlist': waitlist}


def _enrich_admin_ranking_snapshot(team_id, snapshot):
    """Add completed-task signals and GitHub profile fields for admin ranking review."""
    if not snapshot:
        return {'all': [], 'active': [], 'waitlist': [], 'completed_active': []}

    user_ids = [row.get('user_id') for row in (snapshot.get('all') or []) if row.get('user_id')]
    if not user_ids:
        snapshot['completed_active'] = []
        return snapshot

    completed_rows = (
        supabase.table('tasks')
        .select('assigned_to_user_id')
        .eq('team_id', team_id)
        .eq('status', 'completed')
        .in_('assigned_to_user_id', user_ids)
        .execute()
        .data or []
    )

    completed_map = {}
    for row in completed_rows:
        uid = row.get('assigned_to_user_id')
        if not uid:
            continue
        completed_map[uid] = completed_map.get(uid, 0) + 1

    github_map = {}
    try:
        github_rows = (
            supabase.table('users')
            .select('id, github, github_url, github_username')
            .in_('id', user_ids)
            .execute()
            .data or []
        )
        for user_row in github_rows:
            github_map[user_row.get('id')] = {
                'github': user_row.get('github'),
                'github_url': user_row.get('github_url'),
                'github_username': user_row.get('github_username')
            }
    except Exception as e:
        print(f"GitHub fields lookup failed for ranking enrichment: {e}")

    for bucket_name in ['all', 'active', 'waitlist']:
        for row in (snapshot.get(bucket_name) or []):
            uid = row.get('user_id')
            completed_tasks = completed_map.get(uid, 0)
            row['completed_tasks'] = completed_tasks
            row['can_manual_rank'] = completed_tasks > 0

            github_info = github_map.get(uid, {})
            user_obj = row.get('user') or {}
            user_obj['github'] = github_info.get('github')
            user_obj['github_url'] = github_info.get('github_url')
            user_obj['github_username'] = github_info.get('github_username')
            row['user'] = user_obj

    completed_active = [
        row for row in (snapshot.get('all') or [])
        if _safe_int(row.get('completed_tasks'), 0) > 0
    ]
    completed_active.sort(
        key=lambda row: (
            -_safe_int(row.get('completed_tasks'), 0),
            _safe_int(row.get('rank'), 10**9)
        )
    )
    snapshot['completed_active'] = completed_active
    return snapshot


@app.route('/company/collaboration')
@company_login_required
def company_collaboration_dashboard():
    """Admin dashboard for teams, tasks and performance insights."""
    try:
        company_id = session.get('company_id')
        company = get_company_by_id(company_id)
        if not company:
            flash('Company not found. Please login again.', 'error')
            return redirect(url_for('login'))

        teams_response = supabase.table('teams').select('*').eq('company_id', company_id).order('created_at', desc=True).execute()
        teams = teams_response.data or []
        team_ids = [t['id'] for t in teams if t.get('id')]
        team_lookup = {t['id']: t for t in teams if t.get('id')}

        members = []
        if team_ids:
            members_response = supabase.table('team_members').select('*').in_('team_id', team_ids).execute()
            members = members_response.data or []

        user_ids = sorted(list({m.get('user_id') for m in members if m.get('user_id')}))
        users_map = {}
        if user_ids:
            users_response = supabase.table('users').select('id, full_name, email').in_('id', user_ids).execute()
            users_map = {u['id']: u for u in (users_response.data or [])}

        github_map = {}
        if user_ids:
            try:
                github_rows = (
                    supabase.table('users')
                    .select('id, github, github_url, github_username')
                    .in_('id', user_ids)
                    .execute()
                    .data or []
                )
                for user_row in github_rows:
                    github_map[user_row.get('id')] = {
                        'github': user_row.get('github'),
                        'github_url': user_row.get('github_url'),
                        'github_username': user_row.get('github_username')
                    }
            except Exception as github_error:
                print(f"GitHub lookup skipped in collaboration dashboard: {github_error}")

        for member in members:
            member['user'] = users_map.get(member.get('user_id'))

        team_member_count = {}
        for member in members:
            team_member_count[member['team_id']] = team_member_count.get(member['team_id'], 0) + 1

        team_scores = {}
        performer_rows = []
        for uid in user_ids:
            metrics = compute_user_performance_metrics(uid)
            user_obj = users_map.get(uid, {'full_name': 'Unknown', 'email': ''})
            performer_rows.append({
                'user_id': uid,
                'name': user_obj.get('full_name', 'Unknown'),
                'email': user_obj.get('email', ''),
                'score': metrics['performance_score'],
                'metrics': metrics
            })

        for team in teams:
            team_user_ids = [m['user_id'] for m in members if m.get('team_id') == team['id'] and m.get('user_id')]
            if not team_user_ids:
                team_scores[team['id']] = 0.0
                continue
            scores = [row['score'] for row in performer_rows if row['user_id'] in team_user_ids]
            team_scores[team['id']] = round(sum(scores) / len(scores), 2) if scores else 0.0

        top_performers = sorted(performer_rows, key=lambda x: x['score'], reverse=True)[:5]
        low_performers = sorted(performer_rows, key=lambda x: x['score'])[:5]

        tasks = []
        task_summary = {
            'total': 0,
            'pending': 0,
            'in_progress': 0,
            'completed': 0,
            'blocked': 0,
            'overdue': 0
        }
        if team_ids:
            tasks = (
                supabase.table('tasks')
                .select('id, team_id, assigned_to_user_id, title, description, deadline, status, created_at, updated_at, completed_at')
                .in_('team_id', team_ids)
                .order('created_at', desc=True)
                .limit(300)
                .execute()
                .data or []
            )

            assignee_ids = sorted(list({t.get('assigned_to_user_id') for t in tasks if t.get('assigned_to_user_id')}))
            app_lookup = {}
            if assignee_ids:
                try:
                    app_rows = (
                        supabase.table('team_applications')
                        .select('id, team_id, user_id, manual_rank, repository_link')
                        .in_('team_id', team_ids)
                        .in_('user_id', assignee_ids)
                        .execute()
                        .data or []
                    )
                except Exception as app_error:
                    if 'repository_link' in str(app_error).lower() and 'column' in str(app_error).lower():
                        app_rows = (
                            supabase.table('team_applications')
                            .select('id, team_id, user_id, manual_rank')
                            .in_('team_id', team_ids)
                            .in_('user_id', assignee_ids)
                            .execute()
                            .data or []
                        )
                    else:
                        raise
                for app_row in app_rows:
                    key = (app_row.get('team_id'), app_row.get('user_id'))
                    if key not in app_lookup:
                        app_lookup[key] = app_row

            now_utc = datetime.now(timezone.utc)
            team_deadline_over_map = {}
            for tid in team_ids:
                team_deadline_over_map[tid] = _is_team_deadline_over(tid)

            for t in tasks:
                status = t.get('status') or 'pending'
                task_summary['total'] += 1
                if status in task_summary:
                    task_summary[status] += 1

                deadline_dt = _parse_iso_datetime(t.get('deadline'))
                is_overdue = False
                if deadline_dt and status != 'completed':
                    is_overdue = deadline_dt.astimezone(timezone.utc) < now_utc
                t['is_overdue'] = is_overdue
                if is_overdue:
                    task_summary['overdue'] += 1

                assignee = users_map.get(t.get('assigned_to_user_id'), {})
                t['assignee_name'] = (assignee.get('full_name') or assignee.get('email') or 'Unassigned')
                app_row = app_lookup.get((t.get('team_id'), t.get('assigned_to_user_id')))
                t['rank_application_id'] = app_row.get('id') if app_row else None
                t['manual_rank'] = app_row.get('manual_rank') if app_row else None
                t['repository_link'] = app_row.get('repository_link') if app_row else None
                github_info = github_map.get(t.get('assigned_to_user_id'), {})
                t['assignee_github_url'] = github_info.get('github_url') or github_info.get('github')
                t['assignee_github_username'] = github_info.get('github_username')
                t['team_name'] = (team_lookup.get(t.get('team_id')) or {}).get('name') or f"Team {t.get('team_id')}"
                t['team_deadline_over'] = bool(team_deadline_over_map.get(t.get('team_id')))

                if not t.get('assigned_to_user_id'):
                    t['can_manual_rank'] = False
                    t['rank_lock_reason'] = 'Assign task first'
                elif status != 'completed':
                    t['can_manual_rank'] = False
                    t['rank_lock_reason'] = 'Enable after completion'
                elif not t['team_deadline_over']:
                    t['can_manual_rank'] = False
                    t['rank_lock_reason'] = 'Enable after team deadline'
                else:
                    t['can_manual_rank'] = True
                    t['rank_lock_reason'] = ''

        deadline_alerts = get_upcoming_deadline_alerts(team_ids=team_ids, within_hours=48)
        interns_response = supabase.table('users').select('id, full_name, email, profile_completed').eq('profile_completed', True).order('full_name').execute()
        available_interns = interns_response.data or []

        for team in teams:
            team['member_count'] = team_member_count.get(team['id'], 0)
            team['performance_score'] = team_scores.get(team['id'], 0.0)
            team['max_capacity'] = _get_team_capacity(team)
            team['status'] = _normalize_team_status(team.get('status'))

        selected_team_id = request.args.get('ranking_team_id', type=int)
        if not selected_team_id and teams:
            selected_team_id = teams[0]['id']

        ranking_snapshot = {'all': [], 'active': [], 'waitlist': []}
        if selected_team_id:
            ranking_snapshot = _enrich_admin_ranking_snapshot(
                selected_team_id,
                get_team_ranking_snapshot(selected_team_id)
            )

        return render_template(
            'company/team_collaboration.html',
            company=company,
            teams=teams,
            members=members,
            available_interns=available_interns,
            top_performers=top_performers,
            low_performers=low_performers,
            tasks=tasks,
            task_summary=task_summary,
            deadline_alerts=deadline_alerts,
            ranking_snapshot=ranking_snapshot,
            ranking_team_id=selected_team_id
        )
    except Exception as e:
        print(f"Error in collaboration dashboard: {e}")
        if _is_missing_relation_error(e):
            company = get_company_by_id(session.get('company_id'))
            return render_template(
                'company/team_collaboration.html',
                company=company,
                teams=[],
                members=[],
                available_interns=[],
                top_performers=[],
                low_performers=[],
                tasks=[],
                task_summary={'total': 0, 'pending': 0, 'in_progress': 0, 'completed': 0, 'blocked': 0, 'overdue': 0},
                deadline_alerts=[],
                db_setup_required=True,
                ranking_snapshot={'all': [], 'active': [], 'waitlist': []},
                ranking_team_id=None
            )

        flash('Failed to load collaboration dashboard.', 'error')
        return redirect(url_for('company_home'))


@app.route('/team/dashboard')
@login_required
def team_dashboard():
    """Intern dashboard showing team, tasks, chat and personal score."""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return redirect(url_for('login'))

        try:
            available_teams = (
                supabase.table('teams')
                .select('*')
                .eq('status', TEAM_STATUS_ACTIVE)
                .order('created_at', desc=True)
                .limit(100)
                .execute()
                .data
                or []
            )
        except Exception as query_error:
            # Backward compatibility when status column is not present.
            if 'status' in str(query_error).lower() and 'column' in str(query_error).lower():
                available_teams = supabase.table('teams').select('*').order('created_at', desc=True).limit(100).execute().data or []
            else:
                raise

        available_teams = [t for t in available_teams if _team_visible_for_non_member(t)]
        for t in available_teams:
            t['status'] = _normalize_team_status(t.get('status'))
            t['max_capacity'] = _get_team_capacity(t)

        my_apps = supabase.table('team_applications').select('*').eq('user_id', user['id']).order('applied_at', desc=True).execute().data or []
        app_team_ids = sorted(list({row.get('team_id') for row in my_apps if row.get('team_id')}))
        app_teams = []
        if app_team_ids:
            app_teams = supabase.table('teams').select('*').in_('id', app_team_ids).execute().data or []

        team_lookup = {t['id']: t for t in (available_teams + app_teams) if t.get('id')}
        for app_row in my_apps:
            app_row['team'] = team_lookup.get(app_row.get('team_id'))

        user_team_ids = _get_user_team_ids(user['id'])
        if not user_team_ids:
            return render_template(
                'team_dashboard.html',
                team=None,
                user_teams=[],
                tasks=[],
                messages=[],
                metrics={
                    'performance_score': 0,
                    'completed_tasks': 0,
                    'total_tasks': 0,
                    'timeliness': 0,
                    'messages_sent': 0
                },
                user=user,
                deadline_alerts=[],
                recent_activity=[],
                no_team_assigned=True,
                db_setup_required=False,
                available_teams=available_teams,
                my_team_applications=my_apps,
                my_team_application=None
            )

        team_id = request.args.get('team_id', type=int) or user_team_ids[0]
        if team_id not in user_team_ids:
            flash('Access denied for selected team.', 'error')
            return redirect(url_for('home'))

        team_response = supabase.table('teams').select('*').eq('id', team_id).limit(1).execute()
        team = team_response.data[0] if team_response.data else None
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('home'))

        user_teams_response = supabase.table('teams').select('id, name, project_name').in_('id', user_team_ids).order('name').execute()
        user_teams = user_teams_response.data or []

        tasks_response = (
            supabase.table('tasks')
            .select('*')
            .in_('team_id', user_team_ids)
            .eq('assigned_to_user_id', user['id'])
            .order('deadline')
            .execute()
        )
        tasks = tasks_response.data or []

        team_name_lookup = {t.get('id'): t.get('name') for t in (user_teams or []) if t.get('id')}

        now_utc = datetime.now(timezone.utc)
        for task in tasks:
            deadline_dt = _parse_iso_datetime(task.get('deadline'))
            task['is_overdue'] = bool(deadline_dt and task.get('status') != 'completed' and deadline_dt.astimezone(timezone.utc) < now_utc)
            task['team_name'] = team_name_lookup.get(task.get('team_id')) or f"Team {task.get('team_id')}"

        messages_response = supabase.table('team_messages').select('*').eq('team_id', team_id).order('created_at', desc=False).limit(100).execute()
        messages = messages_response.data or []

        sender_ids = sorted(list({m.get('sender_id') for m in messages if m.get('sender_id')}))
        sender_map = {}
        if sender_ids:
            users_response = supabase.table('users').select('id, full_name').in_('id', sender_ids).execute()
            sender_map = {u['id']: u.get('full_name', 'Unknown') for u in (users_response.data or [])}

        for msg in messages:
            msg['sender_name'] = sender_map.get(msg.get('sender_id'), 'Unknown')

        metrics = compute_user_performance_metrics(user['id'], team_id=team_id)
        deadline_alerts = get_upcoming_deadline_alerts(team_ids=[team_id], assigned_user_id=user['id'], within_hours=48)
        recent_activity = get_activity_feed(team_ids=[team_id], limit=20)
        my_team_application_rows = supabase.table('team_applications').select('*').eq('team_id', team_id).eq('user_id', user['id']).limit(1).execute().data or []
        my_team_application = my_team_application_rows[0] if my_team_application_rows else None
        try:
            member_rows = (
                supabase.table('team_members')
                .select('progress_status')
                .eq('team_id', team_id)
                .eq('user_id', user['id'])
                .limit(1)
                .execute()
                .data or []
            )
            my_member_progress_status = _normalize_member_progress((member_rows[0] or {}).get('progress_status')) if member_rows else MEMBER_PROGRESS_PENDING
        except Exception as member_status_error:
            if 'progress_status' in str(member_status_error).lower() and 'column' in str(member_status_error).lower():
                my_member_progress_status = MEMBER_PROGRESS_PENDING
            else:
                raise

        return render_template(
            'team_dashboard.html',
            team=team,
            user_teams=user_teams,
            tasks=tasks,
            messages=messages,
            metrics=metrics,
            user=user,
            deadline_alerts=deadline_alerts,
            recent_activity=recent_activity,
            my_team_application=my_team_application,
            available_teams=available_teams,
            my_team_applications=my_apps,
            no_team_assigned=False,
            my_member_progress_status=my_member_progress_status
        )
    except Exception as e:
        print(f"Error loading team dashboard: {e}")
        user = get_user_by_id(session.get('user_id'))
        if _is_missing_relation_error(e):
            return render_template(
                'team_dashboard.html',
                team=None,
                user_teams=[],
                tasks=[],
                messages=[],
                metrics={
                    'performance_score': 0,
                    'completed_tasks': 0,
                    'total_tasks': 0,
                    'timeliness': 0,
                    'messages_sent': 0
                },
                user=user,
                deadline_alerts=[],
                recent_activity=[],
                no_team_assigned=False,
                db_setup_required=True,
                available_teams=[],
                my_team_applications=[],
                my_team_application=None
            )

        flash('Failed to load team dashboard.', 'error')
        return redirect(url_for('home'))


# ------------ Team APIs (Admin) ------------

@app.route('/api/company/teams', methods=['GET'])
@company_login_required
def list_company_teams():
    try:
        company_id = session.get('company_id')
        response = supabase.table('teams').select('*').eq('company_id', company_id).order('created_at', desc=True).execute()
        teams = response.data or []
        for team in teams:
            team['status'] = _normalize_team_status(team.get('status'))
            team['max_capacity'] = _get_team_capacity(team)
        return jsonify({'success': True, 'teams': teams})
    except Exception as e:
        print(f"Error listing teams: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/teams/<int:team_id>/members', methods=['GET'])
@company_login_required
def list_team_members(team_id):
    try:
        company_id = session.get('company_id')
        if not _is_company_team_owner(company_id, team_id):
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        members = supabase.table('team_members').select('*').eq('team_id', team_id).execute().data or []
        user_ids = [m.get('user_id') for m in members if m.get('user_id')]
        users_map = {}
        if user_ids:
            users = supabase.table('users').select('id, full_name, email').in_('id', user_ids).execute().data or []
            users_map = {u['id']: u for u in users}

        for m in members:
            m['user'] = users_map.get(m.get('user_id'))

        return jsonify({'success': True, 'members': members})
    except Exception as e:
        print(f"Error listing team members: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/teams', methods=['POST'])
@company_login_required
def create_team():
    try:
        company_id = session.get('company_id')
        data = request.get_json(silent=True) or {}

        name = (data.get('name') or '').strip()
        project_name = (data.get('project_name') or '').strip()
        max_capacity = _safe_int(data.get('max_capacity'), 10)
        max_capacity = max(1, min(max_capacity, 1000))
        if not name or not project_name:
            return jsonify({'success': False, 'message': 'Team name and project are required'}), 400

        payload = {
            'company_id': company_id,
            'name': name,
            'project_name': project_name,
            'description': (data.get('description') or '').strip(),
            'max_capacity': max_capacity,
            'status': TEAM_STATUS_ACTIVE,
            'created_at': datetime.now(timezone.utc).isoformat()
        }

        try:
            response = supabase.table('teams').insert(payload).execute()
        except Exception as insert_error:
            # Backward compatibility when max_capacity column is not present yet.
            if 'max_capacity' in str(insert_error).lower() and 'column' in str(insert_error).lower():
                payload.pop('max_capacity', None)
                try:
                    response = supabase.table('teams').insert(payload).execute()
                except Exception as nested_insert_error:
                    if 'status' in str(nested_insert_error).lower() and 'column' in str(nested_insert_error).lower():
                        payload.pop('status', None)
                        response = supabase.table('teams').insert(payload).execute()
                    else:
                        raise
            elif 'status' in str(insert_error).lower() and 'column' in str(insert_error).lower():
                payload.pop('status', None)
                response = supabase.table('teams').insert(payload).execute()
            else:
                raise
        return jsonify({'success': True, 'team': (response.data or [None])[0], 'message': 'Team created successfully'})
    except Exception as e:
        print(f"Error creating team: {e}")
        return jsonify({'success': False, 'message': 'Failed to create team'}), 500


@app.route('/api/company/teams/<int:team_id>/status', methods=['PUT'])
@company_login_required
def update_team_status(team_id):
    try:
        company_id = session.get('company_id')
        if not _is_company_team_owner(company_id, team_id):
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        data = request.get_json(silent=True) or {}
        raw_status = str(data.get('status') or '').strip().lower()
        if raw_status not in ALLOWED_TEAM_STATUSES:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400
        status = _normalize_team_status(raw_status)

        try:
            update_response = supabase.table('teams').update({'status': status}).eq('id', team_id).eq('company_id', company_id).execute()
        except Exception as update_error:
            if 'status' in str(update_error).lower() and 'column' in str(update_error).lower():
                return jsonify({
                    'success': False,
                    'message': 'Please run latest team_collaboration_schema.sql to enable team pause/close controls.'
                }), 400
            raise

        team_row = (update_response.data or [None])[0]
        if team_row:
            team_row['status'] = _normalize_team_status(team_row.get('status'))

        return jsonify({'success': True, 'team': team_row, 'message': f'Team marked as {status}.'})
    except Exception as e:
        print(f"Error updating team status: {e}")
        return jsonify({'success': False, 'message': 'Failed to update team status'}), 500


@app.route('/api/company/teams/<int:team_id>', methods=['DELETE'])
@company_login_required
def remove_team(team_id):
    try:
        company_id = session.get('company_id')
        if not _is_company_team_owner(company_id, team_id):
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        supabase.table('teams').delete().eq('id', team_id).eq('company_id', company_id).execute()
        return jsonify({'success': True, 'message': 'Team removed successfully'})
    except Exception as e:
        print(f"Error removing team: {e}")
        return jsonify({'success': False, 'message': 'Failed to remove team'}), 500


@app.route('/api/company/teams/<int:team_id>/ranking', methods=['GET'])
@company_login_required
def company_team_ranking(team_id):
    try:
        company_id = session.get('company_id')
        if not _is_company_team_owner(company_id, team_id):
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        refresh_team_application_scores(team_id=team_id)
        snapshot = _enrich_admin_ranking_snapshot(team_id, get_team_ranking_snapshot(team_id))
        team_rows = supabase.table('teams').select('*').eq('id', team_id).limit(1).execute().data or []
        if not team_rows:
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        team = team_rows[0]
        team['status'] = _normalize_team_status(team.get('status'))
        return jsonify({
            'success': True,
            'team': team,
            'active': snapshot['active'],
            'waitlist': snapshot['waitlist'],
            'completed_active': snapshot.get('completed_active', []),
            'ranking': snapshot['all']
        })
    except Exception as e:
        print(f"Error loading company team ranking: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/teams/<int:team_id>/ranking/<int:application_id>', methods=['PUT'])
@company_login_required
def set_manual_applicant_rank(team_id, application_id):
    """Allow admin to manually set applicant priority rank for completed contributors."""
    try:
        company_id = session.get('company_id')
        if not _is_company_team_owner(company_id, team_id):
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        data = request.get_json(silent=True) or {}
        manual_rank = _safe_int(data.get('rank'))
        if manual_rank <= 0:
            return jsonify({'success': False, 'message': 'Rank must be a positive number'}), 400

        app_rows = (
            supabase.table('team_applications')
            .select('id, user_id, team_id, status')
            .eq('id', application_id)
            .eq('team_id', team_id)
            .limit(1)
            .execute()
            .data or []
        )
        if not app_rows:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        app_row = app_rows[0]
        user_id = app_row.get('user_id')

        completed_count = len(
            (
                supabase.table('tasks')
                .select('id')
                .eq('team_id', team_id)
                .eq('assigned_to_user_id', user_id)
                .eq('status', 'completed')
                .limit(1)
                .execute()
                .data or []
            )
        )
        if completed_count == 0:
            return jsonify({
                'success': False,
                'message': 'Manual ranking is allowed only for users with completed tasks.'
            }), 400

        try:
            supabase.table('team_applications').update({'manual_rank': manual_rank}).eq('id', application_id).execute()
        except Exception as rank_error:
            if 'manual_rank' in str(rank_error).lower() and 'column' in str(rank_error).lower():
                return jsonify({
                    'success': False,
                    'message': 'Please run latest team_collaboration_schema.sql to enable manual ranking.'
                }), 400
            raise

        recalculate_team_applicant_ranking(team_id)
        snapshot = get_team_ranking_snapshot(team_id)
        return jsonify({'success': True, 'message': 'Manual rank updated.', 'ranking': snapshot['all']})
    except Exception as e:
        print(f"Error setting manual applicant rank: {e}")
        return jsonify({'success': False, 'message': 'Failed to set manual rank'}), 500


@app.route('/api/company/teams/<int:team_id>/members', methods=['POST'])
@company_login_required
def add_team_member(team_id):
    try:
        company_id = session.get('company_id')
        if not _is_company_team_owner(company_id, team_id):
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        role = (data.get('role') or '').strip()
        if not user_id or role not in {'Frontend', 'Backend', 'AI/ML'}:
            return jsonify({'success': False, 'message': 'Valid user and role are required'}), 400

        existing = supabase.table('team_members').select('id').eq('team_id', team_id).eq('user_id', user_id).limit(1).execute()
        if existing.data:
            return jsonify({'success': False, 'message': 'User is already in this team'}), 400

        payload = {
            'team_id': team_id,
            'user_id': user_id,
            'role': role,
            'progress_status': MEMBER_PROGRESS_PENDING,
            'joined_at': datetime.now(timezone.utc).isoformat()
        }
        try:
            supabase.table('team_members').insert(payload).execute()
        except Exception as insert_error:
            if 'progress_status' in str(insert_error).lower() and 'column' in str(insert_error).lower():
                payload.pop('progress_status', None)
                supabase.table('team_members').insert(payload).execute()
            else:
                raise

        log_activity(user_id, action_type='joined_team', team_id=team_id, details={'role': role})
        return jsonify({'success': True, 'message': 'Member added successfully'})
    except Exception as e:
        print(f"Error adding team member: {e}")
        return jsonify({'success': False, 'message': 'Failed to add member'}), 500


@app.route('/api/company/tasks', methods=['POST'])
@company_login_required
def create_task():
    try:
        company_id = session.get('company_id')
        data = request.get_json(silent=True) or {}

        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        team_id = data.get('team_id')
        assigned_to_user_id = data.get('assigned_to_user_id')
        deadline = data.get('deadline')

        if not title or not description or not team_id or not deadline:
            return jsonify({'success': False, 'message': 'Title, description, team and deadline are required'}), 400

        parsed_deadline = _parse_iso_datetime(deadline)
        if not parsed_deadline:
            return jsonify({'success': False, 'message': 'Invalid deadline format'}), 400
        if parsed_deadline.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            return jsonify({'success': False, 'message': 'Deadline must be in the future'}), 400

        if not _is_company_team_owner(company_id, int(team_id)):
            return jsonify({'success': False, 'message': 'Invalid team selected'}), 400

        if assigned_to_user_id and not _is_user_in_team(int(assigned_to_user_id), int(team_id)):
            return jsonify({'success': False, 'message': 'Assigned user is not part of this team'}), 400

        payload = {
            'company_id': company_id,
            'team_id': int(team_id),
            'assigned_to_user_id': int(assigned_to_user_id) if assigned_to_user_id else None,
            'title': title,
            'description': description,
            'deadline': parsed_deadline.astimezone(timezone.utc).isoformat(),
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        response = supabase.table('tasks').insert(payload).execute()
        if assigned_to_user_id:
            log_activity(int(assigned_to_user_id), action_type='task_assigned', team_id=int(team_id), task_id=(response.data or [{}])[0].get('id'))

        return jsonify({'success': True, 'task': (response.data or [None])[0], 'message': 'Task assigned successfully'})
    except Exception as e:
        print(f"Error creating task: {e}")
        return jsonify({'success': False, 'message': 'Failed to assign task'}), 500


@app.route('/api/company/tasks', methods=['GET'])
@company_login_required
def list_company_tasks():
    try:
        company_id = session.get('company_id')
        team_id = request.args.get('team_id', type=int)
        status = request.args.get('status', '').strip()

        query = supabase.table('tasks').select('*').eq('company_id', company_id)
        if team_id:
            query = query.eq('team_id', team_id)
        if status in {'pending', 'in_progress', 'completed', 'blocked'}:
            query = query.eq('status', status)

        tasks = query.order('created_at', desc=True).limit(300).execute().data or []
        return jsonify({'success': True, 'tasks': tasks})
    except Exception as e:
        print(f"Error listing company tasks: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/tasks/<int:task_id>/status', methods=['PUT'])
@company_login_required
def update_company_task_status(task_id):
    try:
        company_id = session.get('company_id')
        data = request.get_json(silent=True) or {}
        new_status = (data.get('status') or '').strip()
        if new_status not in {'pending', 'in_progress', 'completed', 'blocked'}:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400

        task_row = (
            supabase.table('tasks')
            .select('id, team_id, assigned_to_user_id, status')
            .eq('id', task_id)
            .eq('company_id', company_id)
            .limit(1)
            .execute()
            .data
        )
        task = (task_row or [None])[0]
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404

        update_data = {'status': new_status, 'updated_at': datetime.now(timezone.utc).isoformat()}
        if new_status == 'completed':
            update_data['completed_at'] = datetime.now(timezone.utc).isoformat()

        supabase.table('tasks').update(update_data).eq('id', task_id).execute()

        assignee_id = task.get('assigned_to_user_id')
        if assignee_id:
            log_activity(
                assignee_id,
                action_type='task_status_updated_by_admin',
                team_id=task.get('team_id'),
                task_id=task_id,
                details={'status': new_status}
            )

        if task.get('team_id'):
            refresh_team_application_scores(team_id=task.get('team_id'), user_id=assignee_id)

        return jsonify({'success': True, 'message': 'Task status updated'})
    except Exception as e:
        print(f"Error updating company task status: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/tasks/<int:task_id>/rank', methods=['PUT'])
@company_login_required
def update_company_task_rank(task_id):
    try:
        company_id = session.get('company_id')
        data = request.get_json(silent=True) or {}
        manual_rank = _safe_int(data.get('rank'))
        if manual_rank <= 0:
            return jsonify({'success': False, 'message': 'Rank must be a positive number'}), 400

        task_rows = (
            supabase.table('tasks')
            .select('id, team_id, assigned_to_user_id, status')
            .eq('id', task_id)
            .eq('company_id', company_id)
            .limit(1)
            .execute()
            .data or []
        )
        task = task_rows[0] if task_rows else None
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404

        team_id = task.get('team_id')
        user_id = task.get('assigned_to_user_id')
        if not team_id or not user_id:
            return jsonify({'success': False, 'message': 'Task must be assigned to a user to set rank'}), 400

        if (task.get('status') or '').strip().lower() != 'completed':
            return jsonify({'success': False, 'message': 'Manual rank can be set only after task is completed'}), 400

        if not _is_team_deadline_over(team_id):
            return jsonify({'success': False, 'message': 'Manual rank is enabled only after team deadline is over'}), 400

        app_rows = (
            supabase.table('team_applications')
            .select('id')
            .eq('team_id', team_id)
            .eq('user_id', user_id)
            .limit(1)
            .execute()
            .data or []
        )
        app = app_rows[0] if app_rows else None
        if not app:
            created_app = (
                supabase.table('team_applications')
                .insert({
                    'team_id': team_id,
                    'user_id': user_id,
                    'status': 'active',
                    'applied_at': datetime.now(timezone.utc).isoformat()
                })
                .execute()
                .data or []
            )
            app = created_app[0] if created_app else None
            if not app:
                return jsonify({'success': False, 'message': 'Failed to initialize rank record for this assignee'}), 500

        try:
            supabase.table('team_applications').update({'manual_rank': manual_rank}).eq('id', app['id']).execute()
        except Exception as rank_error:
            if 'manual_rank' in str(rank_error).lower() and 'column' in str(rank_error).lower():
                return jsonify({
                    'success': False,
                    'message': 'Please run latest team_collaboration_schema.sql to enable manual ranking.'
                }), 400
            raise

        recalculate_team_applicant_ranking(team_id)
        return jsonify({'success': True, 'message': 'Manual rank updated'})
    except Exception as e:
        print(f"Error updating company task rank: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/company/performance', methods=['GET'])
@company_login_required
def company_performance_data():
    try:
        company_id = session.get('company_id')
        teams = supabase.table('teams').select('id').eq('company_id', company_id).execute().data or []
        team_ids = [t['id'] for t in teams if t.get('id')]
        if not team_ids:
            return jsonify({'success': True, 'performers': [], 'team_scores': []})

        members = supabase.table('team_members').select('user_id, team_id').in_('team_id', team_ids).execute().data or []
        user_ids = sorted(list({m['user_id'] for m in members if m.get('user_id')}))

        users_map = {}
        if user_ids:
            users = supabase.table('users').select('id, full_name, email').in_('id', user_ids).execute().data or []
            users_map = {u['id']: u for u in users}

        performers = []
        for user_id in user_ids:
            metrics = compute_user_performance_metrics(user_id)
            user = users_map.get(user_id, {'full_name': 'Unknown', 'email': ''})
            performers.append({
                'user_id': user_id,
                'name': user.get('full_name', 'Unknown'),
                'email': user.get('email', ''),
                'score': metrics['performance_score'],
                'metrics': metrics
            })

        team_scores = []
        for team_id in team_ids:
            team_user_ids = [m['user_id'] for m in members if m.get('team_id') == team_id]
            user_rows = [p for p in performers if p['user_id'] in team_user_ids]
            avg = round(sum([r['score'] for r in user_rows]) / len(user_rows), 2) if user_rows else 0.0
            team_scores.append({'team_id': team_id, 'score': avg})

        performers.sort(key=lambda x: x['score'], reverse=True)
        return jsonify({'success': True, 'performers': performers, 'team_scores': team_scores})
    except Exception as e:
        print(f"Error loading company performance data: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


# ------------ Team APIs (Intern + Admin) ------------

@app.route('/api/teams/<int:team_id>/messages', methods=['GET'])
@login_required
def get_team_messages(team_id):
    try:
        user_id = session.get('user_id')
        if not _is_user_in_team(user_id, team_id):
            return jsonify({'success': False, 'message': 'Not part of this team'}), 403

        response = supabase.table('team_messages').select('*').eq('team_id', team_id).order('created_at', desc=False).limit(200).execute()
        messages = response.data or []

        sender_ids = sorted(list({m.get('sender_id') for m in messages if m.get('sender_id')}))
        sender_map = {}
        if sender_ids:
            users = supabase.table('users').select('id, full_name').in_('id', sender_ids).execute().data or []
            sender_map = {u['id']: u.get('full_name', 'Unknown') for u in users}

        for m in messages:
            m['sender_name'] = sender_map.get(m.get('sender_id'), 'Unknown')

        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        print(f"Error getting messages: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/teams/<int:team_id>/messages', methods=['POST'])
@login_required
def send_team_message(team_id):
    try:
        user_id = session.get('user_id')
        if not _is_user_in_team(user_id, team_id):
            return jsonify({'success': False, 'message': 'Not part of this team'}), 403

        data = request.get_json(silent=True) or {}
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400

        payload = {
            'team_id': team_id,
            'sender_id': user_id,
            'message': message,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        response = supabase.table('team_messages').insert(payload).execute()

        log_activity(user_id, action_type='message_sent', team_id=team_id)
        refresh_team_application_scores(team_id=team_id, user_id=user_id)
        return jsonify({'success': True, 'message': 'Sent', 'data': (response.data or [None])[0]})
    except Exception as e:
        print(f"Error sending team message: {e}")
        return jsonify({'success': False, 'message': 'Failed to send message'}), 500


@app.route('/api/teams/<int:team_id>/tasks', methods=['GET'])
@login_required
def get_team_tasks(team_id):
    try:
        user_id = session.get('user_id')
        if not _is_user_in_team(user_id, team_id):
            return jsonify({'success': False, 'message': 'Not part of this team'}), 403

        response = supabase.table('tasks').select('*').eq('team_id', team_id).eq('assigned_to_user_id', user_id).order('deadline').execute()
        return jsonify({'success': True, 'tasks': response.data or []})
    except Exception as e:
        print(f"Error getting tasks: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/teams/<int:team_id>/activity', methods=['GET'])
@login_required
def get_team_activity(team_id):
    try:
        user_id = session.get('user_id')
        if not _is_user_in_team(user_id, team_id):
            return jsonify({'success': False, 'message': 'Not part of this team'}), 403

        feed = get_activity_feed(team_ids=[team_id], limit=30)
        return jsonify({'success': True, 'activity': feed})
    except Exception as e:
        print(f"Error getting team activity: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/teams/<int:team_id>/member-status', methods=['PUT'])
@login_required
def update_my_member_status(team_id):
    try:
        user_id = session.get('user_id')
        if not _is_user_in_team(user_id, team_id):
            return jsonify({'success': False, 'message': 'Not part of this team'}), 403

        data = request.get_json(silent=True) or {}
        new_status = _normalize_member_progress(data.get('status'))
        if new_status not in {MEMBER_PROGRESS_IN_PROGRESS, MEMBER_PROGRESS_COMPLETED}:
            return jsonify({'success': False, 'message': 'Status can be updated only to in_progress or completed'}), 400

        update_payload = {'progress_status': new_status}
        try:
            updated = (
                supabase.table('team_members')
                .update(update_payload)
                .eq('team_id', team_id)
                .eq('user_id', user_id)
                .execute()
                .data or []
            )
        except Exception as update_error:
            if 'progress_status' in str(update_error).lower() and 'column' in str(update_error).lower():
                return jsonify({
                    'success': False,
                    'message': 'Please run latest team_collaboration_schema.sql to enable member status tracking.'
                }), 400
            raise

        if not updated:
            return jsonify({'success': False, 'message': 'Team membership not found'}), 404

        log_activity(user_id, action_type='member_status_updated', team_id=team_id, details={'status': new_status})
        refresh_team_application_scores(team_id=team_id, user_id=user_id)
        return jsonify({'success': True, 'message': 'Status updated', 'status': new_status})
    except Exception as e:
        print(f"Error updating member status: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/tasks/<int:task_id>/status', methods=['PUT'])
@login_required
def update_task_status(task_id):
    try:
        user_id = session.get('user_id')
        data = request.get_json(silent=True) or {}
        new_status = data.get('status')
        if new_status not in {'pending', 'in_progress', 'completed', 'blocked'}:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400

        task_response = supabase.table('tasks').select('*').eq('id', task_id).eq('assigned_to_user_id', user_id).limit(1).execute()
        task = (task_response.data or [None])[0]
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404

        update_data = {
            'status': new_status,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        if new_status == 'completed':
            update_data['completed_at'] = datetime.now(timezone.utc).isoformat()

        supabase.table('tasks').update(update_data).eq('id', task_id).execute()

        duration_minutes = None
        if new_status == 'completed':
            created_dt = _parse_iso_datetime(task.get('created_at'))
            if created_dt:
                duration = datetime.now(timezone.utc) - created_dt.astimezone(timezone.utc)
                duration_minutes = int(duration.total_seconds() // 60)

        log_activity(
            user_id,
            action_type='task_completed' if new_status == 'completed' else 'task_status_updated',
            team_id=task.get('team_id'),
            task_id=task_id,
            duration_minutes=duration_minutes,
            details={'status': new_status}
        )

        if task.get('team_id'):
            refresh_team_application_scores(team_id=task.get('team_id'), user_id=user_id)

        return jsonify({'success': True, 'message': 'Task updated successfully'})
    except Exception as e:
        print(f"Error updating task status: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/me/performance', methods=['GET'])
@login_required
def my_performance():
    try:
        user_id = session.get('user_id')
        team_id = request.args.get('team_id', type=int)
        if team_id and not _is_user_in_team(user_id, team_id):
            return jsonify({'success': False, 'message': 'Not part of this team'}), 403

        metrics = compute_user_performance_metrics(user_id, team_id=team_id)
        return jsonify({'success': True, 'metrics': metrics})
    except Exception as e:
        print(f"Error loading personal performance: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/apply', methods=['POST'])
@login_required
def apply_for_team():
    """Unlimited team applications with ranking and waitlist support."""
    try:
        user_id = session.get('user_id')
        data = request.get_json(silent=True) or {}
        team_id = _safe_int(data.get('team_id'))
        desired_role = (data.get('role') or data.get('desired_role') or '').strip() or 'Frontend'
        repository_link = (data.get('repository_link') or '').strip()

        if not team_id:
            return jsonify({'success': False, 'message': 'team_id is required'}), 400
        if not repository_link:
            return jsonify({'success': False, 'message': 'Repository link is required'}), 400
        if not re.match(r'^https?://', repository_link, re.IGNORECASE):
            return jsonify({'success': False, 'message': 'Repository link must start with http:// or https://'}), 400

        team_rows = supabase.table('teams').select('*').eq('id', team_id).limit(1).execute().data or []
        if not team_rows:
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        team = team_rows[0]
        team_status = _normalize_team_status(team.get('status'))
        if team_status == TEAM_STATUS_PAUSED:
            return jsonify({'success': False, 'message': 'This team is paused. New applications are temporarily disabled.'}), 400
        if team_status == TEAM_STATUS_CLOSED:
            return jsonify({'success': False, 'message': 'This team is closed for applications.'}), 400

        existing = (
            supabase.table('team_applications')
            .select('*')
            .eq('team_id', team_id)
            .eq('user_id', user_id)
            .limit(1)
            .execute()
            .data or []
        )

        user = get_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        ats_score = _estimate_ats_score_from_profile(user)
        github_score = _estimate_github_score(user_id, user=user)
        performance_score = compute_user_performance_metrics(user_id, team_id=team_id).get('performance_score', 0)
        total_score = _calculate_total_rank_score(ats_score, github_score, performance_score)

        if existing:
            app_row = existing[0]
            update_payload = {
                'desired_role': desired_role,
                'repository_link': repository_link,
                'ats_score': ats_score,
                'github_score': github_score,
                'performance_score': round(_clamp_score(performance_score), 2),
                'total_score': total_score
            }
            try:
                supabase.table('team_applications').update(update_payload).eq('id', app_row['id']).execute()
            except Exception as update_error:
                if 'repository_link' in str(update_error).lower() and 'column' in str(update_error).lower():
                    return jsonify({'success': False, 'message': 'Please run latest team_collaboration_schema.sql to enable repository link for team joining.'}), 400
                raise
        else:
            payload = {
                'user_id': user_id,
                'team_id': team_id,
                'desired_role': desired_role,
                'repository_link': repository_link,
                'ats_score': ats_score,
                'github_score': github_score,
                'performance_score': round(_clamp_score(performance_score), 2),
                'total_score': total_score,
                'status': 'waitlisted',
                'rank': None,
                'applied_at': datetime.now(timezone.utc).isoformat()
            }
            try:
                supabase.table('team_applications').insert(payload).execute()
            except Exception as insert_error:
                if 'repository_link' in str(insert_error).lower() and 'column' in str(insert_error).lower():
                    return jsonify({'success': False, 'message': 'Please run latest team_collaboration_schema.sql to enable repository link for team joining.'}), 400
                raise

            log_activity(user_id, action_type='applied_to_team', team_id=team_id, details={'desired_role': desired_role, 'repository_link': repository_link})

        recalculate_team_applicant_ranking(team_id)
        current_rows = (
            supabase.table('team_applications')
            .select('*')
            .eq('team_id', team_id)
            .eq('user_id', user_id)
            .limit(1)
            .execute()
            .data or []
        )
        current = current_rows[0] if current_rows else {}

        return jsonify({
            'success': True,
            'message': 'Applied successfully',
            'application': current
        })
    except Exception as e:
        print(f"Error applying to team: {e}")
        return jsonify({'success': False, 'message': 'Failed to apply'}), 500


@app.route('/team/<int:team_id>/ranking', methods=['GET'])
def team_ranking(team_id):
    try:
        user_id = session.get('user_id')
        company_id = session.get('company_id')
        if not user_id and not company_id:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        team_rows = supabase.table('teams').select('*').eq('id', team_id).limit(1).execute().data or []
        if not team_rows:
            return jsonify({'success': False, 'message': 'Team not found'}), 404

        team = team_rows[0]
        team['status'] = _normalize_team_status(team.get('status'))

        # Closed teams are hidden from non-members/non-applicants.
        if team['status'] == TEAM_STATUS_CLOSED and user_id:
            is_member = _is_user_in_team(user_id, team_id)
            has_application = bool(
                supabase.table('team_applications').select('id').eq('team_id', team_id).eq('user_id', user_id).limit(1).execute().data
            )
            if not is_member and not has_application:
                return jsonify({'success': False, 'message': 'Team not found'}), 404

        refresh_team_application_scores(team_id=team_id)
        snapshot = get_team_ranking_snapshot(team_id)
        return jsonify({
            'success': True,
            'team': team,
            'active': snapshot['active'],
            'waitlist': snapshot['waitlist'],
            'ranking': snapshot['all']
        })
    except Exception as e:
        print(f"Error loading team ranking: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/update-performance', methods=['POST'])
@login_required
def update_applicant_performance():
    """Update performance and re-rank dynamically."""
    try:
        data = request.get_json(silent=True) or {}
        team_id = _safe_int(data.get('team_id'))
        user_id = _safe_int(data.get('user_id'), session.get('user_id'))

        if not team_id:
            return jsonify({'success': False, 'message': 'team_id is required'}), 400

        app_rows = (
            supabase.table('team_applications')
            .select('*')
            .eq('team_id', team_id)
            .eq('user_id', user_id)
            .limit(1)
            .execute()
            .data or []
        )
        if not app_rows:
            return jsonify({'success': False, 'message': 'Application not found'}), 404

        app_row = app_rows[0]
        user = get_user_by_id(user_id)

        ats_score = data.get('ats_score')
        github_score = data.get('github_score')
        performance_score = data.get('performance_score')

        if ats_score is None:
            ats_score = _estimate_ats_score_from_profile(user)
        if github_score is None:
            github_score = _estimate_github_score(user_id, user=user)
        if performance_score is None:
            performance_score = compute_user_performance_metrics(user_id, team_id=team_id).get('performance_score', 0)

        total_score = _calculate_total_rank_score(ats_score, github_score, performance_score)

        supabase.table('team_applications').update({
            'ats_score': round(_clamp_score(ats_score), 2),
            'github_score': round(_clamp_score(github_score), 2),
            'performance_score': round(_clamp_score(performance_score), 2),
            'total_score': total_score
        }).eq('id', app_row['id']).execute()

        log_activity(user_id, action_type='performance_updated', team_id=team_id, details={
            'ats_score': round(_clamp_score(ats_score), 2),
            'github_score': round(_clamp_score(github_score), 2),
            'performance_score': round(_clamp_score(performance_score), 2),
            'total_score': total_score
        })

        recalculate_team_applicant_ranking(team_id)

        current_rows = (
            supabase.table('team_applications')
            .select('*')
            .eq('team_id', team_id)
            .eq('user_id', user_id)
            .limit(1)
            .execute()
            .data or []
        )

        return jsonify({'success': True, 'application': current_rows[0] if current_rows else None})
    except Exception as e:
        print(f"Error updating applicant performance: {e}")
        return jsonify({'success': False, 'message': 'Failed to update performance'}), 500


@app.route('/leaderboard', methods=['GET'])
@login_required
def leaderboard():
    try:
        team_id = request.args.get('team_id', type=int)
        if team_id:
            snapshot = get_team_ranking_snapshot(team_id)
            return jsonify({'success': True, 'team_id': team_id, 'leaderboard': snapshot['all']})

        teams = supabase.table('teams').select('*').order('created_at', desc=True).limit(200).execute().data or []
        payload = []
        for team in teams:
            snapshot = get_team_ranking_snapshot(team['id'])
            payload.append({
                'team': team,
                'active': snapshot['active'],
                'waitlist_count': len(snapshot['waitlist'])
            })

        return jsonify({'success': True, 'leaderboard': payload})
    except Exception as e:
        print(f"Error loading leaderboard: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/waitlist', methods=['GET'])
@login_required
def waitlist():
    try:
        team_id = request.args.get('team_id', type=int)
        if team_id:
            snapshot = get_team_ranking_snapshot(team_id)
            return jsonify({'success': True, 'team_id': team_id, 'waitlist': snapshot['waitlist']})

        rows = (
            supabase.table('team_applications')
            .select('*')
            .eq('status', 'waitlisted')
            .order('team_id')
            .order('rank')
            .execute()
            .data or []
        )
        return jsonify({'success': True, 'waitlist': rows})
    except Exception as e:
        print(f"Error loading waitlist: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000)

# For Vercel deployment
app = app