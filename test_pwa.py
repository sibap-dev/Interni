#!/usr/bin/env python3
"""
PWA Testing Script for PM Internship Portal
Tests all PWA components and functionality
"""

import os
import json
import sys

def check_file_exists(filepath, description):
    """Check if a file exists and print status"""
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"✅ {description}: {filepath} ({size} bytes)")
        return True
    else:
        print(f"❌ {description}: {filepath} (NOT FOUND)")
        return False

def validate_manifest():
    """Validate PWA manifest.json"""
    manifest_path = "static/manifest.json"
    if not check_file_exists(manifest_path, "PWA Manifest"):
        return False
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        required_fields = ['name', 'short_name', 'start_url', 'display', 'icons']
        missing_fields = [field for field in required_fields if field not in manifest]
        
        if missing_fields:
            print(f"❌ Manifest missing required fields: {missing_fields}")
            return False
        
        print(f"✅ Manifest valid: {manifest['name']}")
        print(f"   - Icons: {len(manifest['icons'])} defined")
        print(f"   - Display mode: {manifest['display']}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Manifest JSON invalid: {e}")
        return False
    except Exception as e:
        print(f"❌ Manifest error: {e}")
        return False

def check_icons():
    """Check if all required icons exist"""
    icons_dir = "static/images/icons"
    required_sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    print("\n📱 Checking PWA Icons:")
    all_exist = True
    
    for size in required_sizes:
        icon_path = f"{icons_dir}/icon-{size}x{size}.png"
        if not check_file_exists(icon_path, f"Icon {size}x{size}"):
            all_exist = False
    
    return all_exist

def check_service_worker():
    """Check service worker file"""
    sw_path = "static/service-worker.js"
    return check_file_exists(sw_path, "Service Worker")

def check_offline_page():
    """Check offline page"""
    offline_path = "templates/offline.html"
    return check_file_exists(offline_path, "Offline Page")

def check_pwa_integration():
    """Check PWA integration in templates"""
    templates_to_check = [
        ("templates/home.html", "Home template"),
        ("templates/login.html", "Login template")
    ]
    
    print("\n🔗 Checking PWA Integration:")
    all_good = True
    
    for template_path, description in templates_to_check:
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_manifest = 'rel="manifest"' in content
            has_sw_registration = 'serviceWorker' in content
            has_meta_theme = 'name="theme-color"' in content
            
            status = "✅" if (has_manifest and has_sw_registration and has_meta_theme) else "⚠️"
            print(f"{status} {description}: manifest({has_manifest}) SW({has_sw_registration}) theme({has_meta_theme})")
            
            if not (has_manifest and has_sw_registration and has_meta_theme):
                all_good = False
        else:
            print(f"❌ {description}: File not found")
            all_good = False
    
    return all_good

def main():
    """Run all PWA tests"""
    print("🧪 PM Internship Portal - PWA Testing")
    print("=" * 50)
    
    tests = [
        ("PWA Manifest", validate_manifest),
        ("Service Worker", check_service_worker),
        ("Offline Page", check_offline_page),
        ("PWA Icons", check_icons),
        ("Template Integration", check_pwa_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 PWA Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 PWA setup is complete and ready for mobile installation!")
        print("\n📱 To test on mobile:")
        print("   1. Open the website on your mobile browser")
        print("   2. Look for 'Add to Home Screen' or install prompt")
        print("   3. Install the app")
        print("   4. Launch from home screen for standalone experience")
    else:
        print("⚠️  Some PWA components need attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)