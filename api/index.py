# api/index.py - Vercel entry point (corrected for root-level app.py)
import sys
import os

# Add the parent directory to sys.path to import from root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    # Import your main Flask app from the root directory
    from app import app
    
    print("✅ Successfully imported Flask app from root directory")
    
    # This exports your app for Vercel
    # DO NOT include app.run() here
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    
    # Fallback minimal app if import fails
    from flask import Flask
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    @app.route('/')
    def error():
        return f'''
        <h1>🔧 PM Internship Portal - Import Debug</h1>
        <p><strong>Import Error:</strong> {e}</p>
        
        <h2>🔍 Debug Information:</h2>
        <ul>
            <li><strong>Current Directory:</strong> {os.getcwd()}</li>
            <li><strong>Python Path:</strong> {sys.path}</li>
            <li><strong>Files in Root:</strong> {os.listdir('..')}</li>
            <li><strong>Files in API:</strong> {os.listdir('.')}</li>
        </ul>
        
        <h2>📋 Expected Structure:</h2>
        <pre>
your-project/
├── api/
│   └── index.py          ← This file
├── app.py               ← Your main Flask app (ROOT LEVEL)
├── templates/           ← HTML templates
├── static/             ← CSS, JS, images
└── requirements.txt    ← Dependencies
        </pre>
        
        <p><a href="/test">Test Basic Functionality</a></p>
        '''
    
    @app.route('/test')
    def test():
        return {
            'status': 'error',
            'message': f'Import failed: {e}',
            'debug': {
                'cwd': os.getcwd(),
                'root_files': os.listdir('..'),
                'api_files': os.listdir('.')
            }
        }

except Exception as e:
    print(f"❌ Unexpected error: {e}")
    
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def unexpected_error():
        return f'<h1>❌ Unexpected Error</h1><p>{e}</p>'
