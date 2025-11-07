#!/usr/bin/env python3
"""
Check catalog TTL and return status for Windows batch file
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

def check_catalog_ttl():
    """Check catalog TTL and print result for batch file parsing"""

    # Get paths from command line or use defaults
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])
    else:
        # Assume script is run from project root
        project_root = Path(__file__).parent

    metadata_file = project_root / "data" / "catalog" / "metadata.json"
    ttl_threshold = 3600  # 1 hour

    try:
        if not metadata_file.exists():
            print("NO_METADATA")
            return

        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        timestamp_str = metadata.get("timestamp")
        ttl_hours = metadata.get("ttl_hours", 24)

        if not timestamp_str:
            print("NO_TIMESTAMP")
            return

        # Parse timestamp
        timestamp = datetime.fromisoformat(timestamp_str)
        now = datetime.utcnow()
        age_seconds = (now - timestamp).total_seconds()
        ttl_seconds = ttl_hours * 3600

        # Print results in format batch file can parse
        print(f"AGE_SECONDS={int(age_seconds)}")
        print(f"TTL_SECONDS={int(ttl_seconds)}")
        print(f"TTL_THRESHOLD={ttl_threshold}")

        if age_seconds >= ttl_threshold:
            print("STATUS=OLD")
        else:
            print("STATUS=FRESH")

    except Exception as e:
        print(f"ERROR={e}")

if __name__ == "__main__":
    check_catalog_ttl()
