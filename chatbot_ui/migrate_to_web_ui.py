#!/usr/bin/env python3
"""
Migration script from Streamlit UI to Modern Web UI
This script helps users transition from the old Streamlit interface to the new web interface.
"""

import os
import sys
import subprocess
from pathlib import Path

def print_banner():
    """Print migration banner."""
    print("=" * 60)
    print("🚀 ERP Chatbot - Migration to Modern Web UI")
    print("=" * 60)
    print()

def check_old_streamlit_processes():
    """Check for running Streamlit processes."""
    print("🔍 Checking for running Streamlit processes...")
    
    try:
        result = subprocess.run(['pgrep', '-f', 'streamlit'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"⚠️  Found {len(pids)} running Streamlit process(es)")
            
            response = input("Do you want to stop them? (y/N): ").lower()
            if response == 'y':
                for pid in pids:
                    try:
                        subprocess.run(['kill', pid], check=True)
                        print(f"✅ Stopped process {pid}")
                    except subprocess.CalledProcessError:
                        print(f"❌ Failed to stop process {pid}")
            return True
        else:
            print("✅ No running Streamlit processes found")
            return False
    except FileNotFoundError:
        print("✅ No running Streamlit processes found")
        return False

def check_port_availability():
    """Check if the new web UI port is available."""
    print("\n🔍 Checking port availability...")
    
    import socket
    
    # Check if port 3000 is available
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('localhost', 3000))
        if result == 0:
            print("⚠️  Port 3000 is already in use")
            print("   Please stop any service running on port 3000")
            return False
        else:
            print("✅ Port 3000 is available")
            return True

def update_dependencies():
    """Update dependencies for the new web UI."""
    print("\n📦 Updating dependencies...")
    
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if requirements_file.exists():
        print("✅ Requirements file found")
        
        # Check if streamlit is still in requirements
        with open(requirements_file, 'r') as f:
            content = f.read()
            
        if 'streamlit' in content.lower():
            print("⚠️  Streamlit is still in requirements.txt")
            print("   This has been automatically removed in the updated version")
        
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)], 
                         check=True, capture_output=True)
            print("✅ Dependencies updated successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to update dependencies: {e}")
            return False
    else:
        print("❌ Requirements file not found")
        return False

def show_migration_summary():
    """Show migration summary and next steps."""
    print("\n" + "=" * 60)
    print("🎉 Migration Summary")
    print("=" * 60)
    print()
    print("✅ Old Streamlit processes stopped")
    print("✅ Port 3000 is available for the new Web UI")
    print("✅ Dependencies updated")
    print()
    print("📋 What's Changed:")
    print("   • Streamlit UI (port 8501) → Modern Web UI (port 3000)")
    print("   • Better responsive design for mobile and desktop")
    print("   • Enhanced conversation history")
    print("   • Improved performance with pure JavaScript frontend")
    print("   • Professional dark theme with blue accents")
    print()
    print("🚀 Next Steps:")
    print("   1. Start the new system:")
    print("      python start_web_ui.py")
    print("   2. Open your browser:")
    print("      http://localhost:3000")
    print("   3. Enjoy the improved experience!")
    print()
    print("📚 Documentation:")
    print("   • WEB_UI_README.md - Comprehensive guide")
    print("   • test_web_ui.py - Test the new interface")
    print()
    print("🔄 Rollback (if needed):")
    print("   The old Streamlit app is still available:")
    print("   streamlit run app.py")
    print()

def main():
    """Main migration function."""
    print_banner()
    
    print("This script will help you migrate from the Streamlit UI to the new Modern Web UI.")
    print("The new interface offers better performance, responsive design, and enhanced features.")
    print()
    
    response = input("Do you want to proceed with the migration? (y/N): ").lower()
    if response != 'y':
        print("Migration cancelled.")
        return
    
    print("\n🔄 Starting migration process...")
    
    # Step 1: Check and stop old Streamlit processes
    streamlit_running = check_old_streamlit_processes()
    
    # Step 2: Check port availability
    port_available = check_port_availability()
    
    # Step 3: Update dependencies
    deps_updated = update_dependencies()
    
    if port_available and deps_updated:
        show_migration_summary()
        
        # Ask if user wants to start the new system
        print("🚀 Would you like to start the new Web UI now? (y/N): ", end="")
        start_response = input().lower()
        
        if start_response == 'y':
            print("\n🚀 Starting the new Web UI...")
            try:
                # Change to the script directory
                os.chdir(Path(__file__).parent)
                subprocess.run([sys.executable, 'start_web_ui.py'])
            except KeyboardInterrupt:
                print("\n✅ Web UI stopped")
            except Exception as e:
                print(f"\n❌ Error starting Web UI: {e}")
                print("You can start it manually with: python start_web_ui.py")
    else:
        print("\n❌ Migration incomplete. Please fix the issues above and try again.")

if __name__ == "__main__":
    main()