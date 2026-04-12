#!/usr/bin/env python
"""
Verification script to test Flask app structure and imports.
Run this to validate the Flask migration.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test all critical imports."""
    print("🔍 Testing Flask application structure...\n")
    
    tests_passed = 0
    tests_failed = 0
    
    tests = [
        ("Flask", lambda: __import__("flask")),
        ("SQLAlchemy", lambda: __import__("sqlalchemy")),
        ("Flask-JWT-Extended", lambda: __import__("flask_jwt_extended")),
        ("Flask-Mail", lambda: __import__("flask_mail")),
        ("Flask-CORS", lambda: __import__("flask_cors")),
        ("Flask-Limiter", lambda: __import__("flask_limiter")),
        ("Marshmallow", lambda: __import__("marshmallow")),
        ("BCrypt", lambda: __import__("bcrypt")),
        ("JWT", lambda: __import__("jwt")),
        ("PostgreSQL Driver", lambda: __import__("psycopg2")),
    ]
    
    print("📦 Checking dependencies...\n")
    for name, import_fn in tests:
        try:
            import_fn()
            print(f"  ✅ {name}")
            tests_passed += 1
        except ImportError as e:
            print(f"  ❌ {name}: {str(e)}")
            tests_failed += 1
    
    print(f"\n✅ Dependencies: {tests_passed} passed")
    if tests_failed > 0:
        print(f"❌ Dependencies: {tests_failed} failed\n")
        print("👉 Run: pip install -r requirements.txt")
        return False
    
    print("\n📂 Checking Flask app structure...\n")
    
    # Test app imports
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from app.extensions import db, jwt, cors, limiter, socketio, mail
        print("  ✅ Extensions initialized")
        
        from app.models import User, Project, ConversionJob, Report, VerificationToken, GitHubRepo
        print("  ✅ Models imported")
        
        from app.services.auth_service import AuthService
        print("  ✅ Auth service imported")
        
        from app.services.email_service import EmailService
        print("  ✅ Email service imported")
        
        from app.services.storage_service import StorageService
        print("  ✅ Storage service imported")
        
        from app.services.conversion_service import ConversionService
        print("  ✅ Conversion service imported")
        
        from app.services.github_service import GitHubService
        print("  ✅ GitHub service imported")
        
        from app.routes.auth import auth_bp
        print("  ✅ Auth routes imported")
        
        from app.routes.user import user_bp
        print("  ✅ User routes imported")
        
        from app.routes.project import project_bp
        print("  ✅ Project routes imported")
        
        from app.routes.conversion import conversion_bp
        print("  ✅ Conversion routes imported")
        
        from app.routes.github import github_bp
        print("  ✅ GitHub routes imported")
        
        from app.routes.admin import admin_bp
        print("  ✅ Admin routes imported")
        
        from config import DevelopmentConfig
        print("  ✅ Configuration imported")
        
        print("\n✅ All Flask components verified!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def create_app_test():
    """Test app factory."""
    print("\n\n🏭 Testing Flask app factory...\n")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from app import create_app
        app = create_app()
        
        print("  ✅ Flask app created successfully")
        
        # Test routes
        with app.test_client() as client:
            resp = client.get("/health")
            if resp.status_code == 200:
                print("  ✅ Health endpoint works")
            else:
                print(f"  ❌ Health endpoint failed ({resp.status_code})")
                return False
        
        # List all routes
        print("\n  📍 Registered routes:")
        routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                route_info = f"{rule.rule} [{','.join(rule.methods - {'OPTIONS', 'HEAD'})}]"
                routes.append(route_info)
        
        for route in sorted(routes):
            print(f"    {route}")
        
        print("\n✅ Flask app factory test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 FrameShift Flask Migration Verification")
    print("=" * 60 + "\n")
    
    # Test imports
    imports_ok = test_imports()
    
    if imports_ok:
        # Test app creation
        app_ok = create_app_test()
        
        if app_ok:
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED - Flask migration is ready!")
            print("=" * 60)
            print("\n🚀 To start the development server, run:")
            print("   python wsgi.py")
            sys.exit(0)
    
    print("\n" + "=" * 60)
    print("❌ TESTS FAILED - Fix errors above")
    print("=" * 60)
    sys.exit(1)
