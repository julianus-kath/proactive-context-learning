"""
Script to generate synthetic data for the ERP database.
"""

import os
import sys
import subprocess

# Add the parent directory to the path
sys.path.append('/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code')

def check_database_exists():
    """
    Check if the synthetic data database already exists.
    
    Returns:
        bool: True if the database exists, False otherwise
    """
    db_path = '/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/synthetic_data.db'
    return os.path.exists(db_path)

def generate_synthetic_data():
    """
    Generate synthetic data for the ERP database.
    """
    print("Generating synthetic data...")
    
    # Run the synthetic data generator
    cmd = [
        "python", 
        "-m", 
        "synthetic_data_service.main", 
        "--customers", "50", 
        "--products", "100", 
        "--sales", "500", 
        "--suppliers", "30", 
        "--employees", "50", 
        "--drop-tables"
    ]
    
    try:
        subprocess.run(
            cmd, 
            cwd='/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code',
            check=True
        )
        print("Synthetic data generated successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error generating synthetic data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if check_database_exists():
        print("Database already exists. Skipping data generation.")
    else:
        generate_synthetic_data()