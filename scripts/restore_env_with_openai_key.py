#!/usr/bin/env python3
"""
Restore .env file with the correct OpenAI key and database settings
"""

def create_correct_env_file():
    """Create the correct .env file with OpenAI key and mywebshop database"""
    
    env_content = '''# LLM Provider Configuration
LLM_PROVIDER=openai

# OpenAI Configuration (RESTORED)
OPENAI_API_KEY=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
OPENAI_MODEL=gpt-4

# Database Configuration - SINGLE SOURCE OF TRUTH
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mywebshop
DB_SCHEMA=webshop
DB_USER=postgres
DB_PASSWORD=

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
    
    print("🔧 Creating .env file with OpenAI key and mywebshop database...")
    with open('.env', 'w') as f:
        f.write(env_content)
    print("✅ .env file restored!")

def main():
    print("🎯 RESTORING .ENV FILE WITH OPENAI KEY")
    print("="*50)
    
    create_correct_env_file()
    
    print("\n✅ RESTORATION COMPLETE!")
    print("\n🎯 Your .env file now has:")
    print("   ✅ Your original OpenAI API key")
    print("   ✅ Correct mywebshop database configuration")
    print("   ✅ All service configurations")
    
    print("\n🚀 Ready to restart services!")
    print("./start_all_services.sh")

if __name__ == "__main__":
    main()