#!/usr/bin/env python3
"""
Test connection to mywebshop database specifically.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def test_mywebshop_connection():
    """Test direct connection to mywebshop database."""
    
    # Get config from environment
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'mywebshop'),
        'user': os.getenv('DB_USER', 'juli'),
        'password': os.getenv('DB_PASSWORD', '')
    }
    
    print(f"Attempting to connect with config: {db_config}")
    
    try:
        # Create direct connection
        conn = await asyncpg.connect(**db_config)
        
        # Check current database
        result = await conn.fetchrow("SELECT current_database()")
        print(f"✅ Connected to database: {result['current_database']}")
        
        # Check schemas
        result = await conn.fetch("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY schema_name
        """)
        
        print("Available schemas:")
        for row in result:
            print(f"  - {row['schema_name']}")
        
        # Check if webshop schema exists
        result = await conn.fetch("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'webshop'
        """)
        
        if result:
            print(f"\n✅ webshop schema found!")
            
            # Check tables in webshop schema
            result = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'webshop'
                ORDER BY table_name
            """)
            print("Tables in webshop schema:")
            for row in result:
                print(f"  - {row['table_name']}")
                
            # Count customers
            result = await conn.fetchrow("SELECT COUNT(*) as count FROM webshop.customer")
            print(f"\nCustomers in webshop.customer: {result['count']}")
            
        else:
            print(f"\n❌ webshop schema not found")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mywebshop_connection())