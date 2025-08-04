"""
Test script for the SQL agent tools.
"""

import os
import sys
sys.path.append('/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code')

from agent_system.sql_agent import run_sql_query, get_table_info, get_database_schema
from agent_system.generate_data import check_database_exists, generate_synthetic_data

def main():
    """
    Test the SQL agent tools.
    """
    # Check if the database exists and generate it if needed
    if not check_database_exists():
        print("Database does not exist. Generating synthetic data...")
        generate_synthetic_data()
    else:
        print("Database exists.")
    
    # Test get_database_schema
    print("\nTesting get_database_schema:")
    schema = get_database_schema()
    print(schema[:500] + "..." if len(schema) > 500 else schema)
    
    # Test get_table_info
    print("\nTesting get_table_info for 'customers':")
    table_info = get_table_info("customers")
    print(table_info[:500] + "..." if len(table_info) > 500 else table_info)
    
    # Test run_sql_query
    print("\nTesting run_sql_query:")
    query_result = run_sql_query("SELECT * FROM customers LIMIT 3;")
    print(query_result[:500] + "..." if len(query_result) > 500 else query_result)
    
    print("\nAll tests completed.")

if __name__ == "__main__":
    main()