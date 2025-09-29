#!/usr/bin/env python3
"""
Demonstration of the startup indexing functionality.
This shows how the agent discovers and indexes all available schemas and tables.
"""

import asyncio
import logging
import sys
import os
import json

# Add the project root to the path
sys.path.append(os.path.dirname(__file__))

from langgraph_integration.direct_db_client import (
    index_database, 
    get_all_schemas, 
    get_database_schema,
    health_check
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def demonstrate_startup_indexing():
    """Demonstrate the startup indexing process."""
    print("🚀 Database Agent Startup Indexing Demo")
    print("="*50)
    
    # Step 1: Health check
    print("\n1️⃣ Performing health check...")
    try:
        is_healthy = await health_check()
        if is_healthy:
            print("✅ Database connection is healthy")
        else:
            print("❌ Database connection issues detected")
            return
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Step 2: Discover schemas
    print("\n2️⃣ Discovering available schemas...")
    try:
        schemas = await get_all_schemas()
        print(f"✅ Found {len(schemas)} schemas:")
        for schema in schemas:
            print(f"   - {schema}")
    except Exception as e:
        print(f"❌ Schema discovery failed: {e}")
        return
    
    # Step 3: Comprehensive database indexing
    print("\n3️⃣ Performing comprehensive database indexing...")
    try:
        index_info = await index_database()
        
        print(f"✅ Database indexing completed!")
        print(f"   Total schemas: {len(index_info['schemas'])}")
        print(f"   Total tables: {index_info['total_tables']}")
        print(f"   Total columns: {index_info['total_columns']}")
        
        # Show detailed breakdown by schema
        print("\n📊 Schema breakdown:")
        for schema_name in index_info['schemas']:
            schema_tables = {k: v for k, v in index_info['tables'].items() 
                           if k.startswith(f"{schema_name}.")}
            
            total_columns = sum(len(table_info['columns']) for table_info in schema_tables.values())
            total_rows = sum(table_info['row_count'] for table_info in schema_tables.values() 
                           if isinstance(table_info['row_count'], int))
            
            print(f"   {schema_name}:")
            print(f"     - Tables: {len(schema_tables)}")
            print(f"     - Columns: {total_columns}")
            print(f"     - Total rows: {total_rows}")
            
            # Show table details
            for table_name, table_info in schema_tables.items():
                row_count = table_info['row_count']
                row_display = f"{row_count} rows" if isinstance(row_count, int) else "Unknown rows"
                print(f"       • {table_name}: {len(table_info['columns'])} columns, {row_display}")
        
    except Exception as e:
        print(f"❌ Database indexing failed: {e}")
        return
    
    # Step 4: Generate comprehensive schema description
    print("\n4️⃣ Generating comprehensive schema description...")
    try:
        full_schema = await get_database_schema(include_all_schemas=True)
        
        # Save to file for inspection
        with open("database_schema.txt", "w") as f:
            f.write(full_schema)
        
        print(f"✅ Schema description generated ({len(full_schema)} characters)")
        print("   Saved to: database_schema.txt")
        
        # Show a preview
        lines = full_schema.split('\n')
        preview_lines = lines[:20]
        print("\n📋 Schema preview (first 20 lines):")
        for line in preview_lines:
            print(f"   {line}")
        
        if len(lines) > 20:
            print(f"   ... and {len(lines) - 20} more lines")
        
    except Exception as e:
        print(f"❌ Schema description generation failed: {e}")
        return
    
    # Step 5: Save indexing results
    print("\n5️⃣ Saving indexing results...")
    try:
        # Save the index info as JSON for later use
        with open("database_index.json", "w") as f:
            json.dump(index_info, f, indent=2, default=str)
        
        print("✅ Indexing results saved to: database_index.json")
        
    except Exception as e:
        print(f"❌ Failed to save indexing results: {e}")
    
    print("\n🎉 Startup indexing demonstration completed!")
    print("\nThe agent now has comprehensive knowledge of:")
    print("- All available schemas")
    print("- All tables in each schema")
    print("- Column details for each table")
    print("- Row counts for each table")
    print("\nThis information will be used to:")
    print("- Generate better SQL queries with proper schema qualification")
    print("- Provide accurate responses about available data")
    print("- Handle errors more intelligently with retry logic")

async def main():
    """Run the startup indexing demonstration."""
    await demonstrate_startup_indexing()

if __name__ == "__main__":
    asyncio.run(main())