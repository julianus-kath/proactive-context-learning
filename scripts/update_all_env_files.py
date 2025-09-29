#!/usr/bin/env python3
"""
Update all .env files to use the new mywebshop database
"""

import os
import re

def update_env_file(filepath):
    """Update a single .env file"""
    if not os.path.exists(filepath):
        print(f"⚠️  {filepath} does not exist, skipping...")
        return
    
    print(f"🔧 Updating {filepath}...")
    
    # Read the file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Make the replacements
    original_content = content
    content = re.sub(r'^DB_NAME=synthetic_erp_data', 'DB_NAME=mywebshop', content, flags=re.MULTILINE)
    content = re.sub(r'^DB_USER=juli', 'DB_USER=postgres', content, flags=re.MULTILINE)
    
    # Write back if changed
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"   ✅ Updated {filepath}")
    else:
        print(f"   ℹ️  No changes needed in {filepath}")

def main():
    print("🎯 UPDATING ALL .ENV FILES FOR MYWEBSHOP DATABASE")
    print("="*60)
    
    # List of .env files to update
    env_files = [
        '.env',
        'mcp_server/.env',
        'synthetic_data_service/.env',
        'chatbot_ui/.env'
    ]
    
    for env_file in env_files:
        update_env_file(env_file)
    
    print("\n✅ ALL .ENV FILES UPDATED!")
    print("\n🚀 Next steps:")
    print("1. Stop your services if they're running (Ctrl+C)")
    print("2. Restart: ./start_all_services.sh")
    print("3. Your chatbot will now connect to mywebshop database!")
    print("\n🧪 Test with:")
    print("python debug_config.py")

if __name__ == "__main__":
    main()