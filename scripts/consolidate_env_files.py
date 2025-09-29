#!/usr/bin/env python3
"""
Consolidate all .env files into ONE root .env file
Remove duplicates and use single source of truth
"""

import os
import shutil

def backup_and_remove_env_file(filepath):
    """Backup and remove an .env file"""
    if not os.path.exists(filepath):
        return
    
    print(f"🗑️  Removing {filepath}...")
    
    # Create backup
    backup_path = filepath + '.backup'
    shutil.copy2(filepath, backup_path)
    print(f"   📁 Backup created: {backup_path}")
    
    # Remove original
    os.remove(filepath)
    print(f"   ✅ Removed {filepath}")

def create_master_env_file():
    """Create the master .env file with correct settings"""
    
    env_content = '''# MASTER DATABASE CONFIGURATION
# This is the ONLY .env file - all services use this!

# OpenAI API Key (required for LangGraph)
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration - SINGLE SOURCE OF TRUTH
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mywebshop
DB_SCHEMA=webshop
DB_USER=postgres
DB_PASSWORD=

# Alternative user (uncomment if you prefer juli):
# DB_USER=juli
# DB_PASSWORD=your_password_here

# LangGraph Service Configuration
LANGGRAPH_URL=http://localhost:5001
API_KEY=supersecretapikey

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000
MCP_API_KEY=supersecretapikey

# Other settings
MAX_QUERY_RESULTS=1000
QUERY_TIMEOUT=30
'''
    
    print("📝 Creating master .env file...")
    with open('.env', 'w') as f:
        f.write(env_content)
    print("✅ Master .env file created!")

def main():
    print("🎯 CONSOLIDATING TO ONE .ENV FILE")
    print("="*50)
    
    # Remove duplicate .env files (keep backups)
    duplicate_env_files = [
        'mcp_server/.env',
        'synthetic_data_service/.env',
        'chatbot_ui/.env'
    ]
    
    for env_file in duplicate_env_files:
        backup_and_remove_env_file(env_file)
    
    print(f"\n📝 Updating root .env file...")
    create_master_env_file()
    
    print(f"\n✅ CONSOLIDATION COMPLETE!")
    print(f"\n🎯 Now you have:")
    print(f"   ✅ ONE master .env file in the root directory")
    print(f"   ✅ All duplicate .env files removed (with backups)")
    print(f"   ✅ Single source of truth for database configuration")
    
    print(f"\n🚀 Next steps:")
    print(f"1. Add your OPENAI_API_KEY to .env")
    print(f"2. Add your database password if needed")
    print(f"3. Restart services: ./start_all_services.sh")
    print(f"4. Your chatbot will use mywebshop database!")
    
    print(f"\n📁 Backup files created in case you need to restore:")
    for env_file in duplicate_env_files:
        backup_path = env_file + '.backup'
        if os.path.exists(backup_path):
            print(f"   - {backup_path}")

if __name__ == "__main__":
    main()