#!/usr/bin/env python3
"""
Test catalog TTL checking functionality
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

def test_catalog_ttl():
    """Test the catalog TTL logic"""

    # Paths
    project_root = Path(__file__).parent
    catalog_file = project_root / "data" / "catalog" / "catalog.json.gz"
    metadata_file = project_root / "data" / "catalog" / "metadata.json"

    print("🔍 Testing Catalog TTL Logic...")
    print(f"Catalog file: {catalog_file}")
    print(f"Metadata file: {metadata_file}")
    print()

    # Check if files exist
    if not metadata_file.exists():
        print("❌ No metadata file found")
        return

    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        timestamp_str = metadata.get("timestamp")
        ttl_hours = metadata.get("ttl_hours", 24)

        if not timestamp_str:
            print("❌ No timestamp in metadata")
            return

        # Parse timestamp
        timestamp = datetime.fromisoformat(timestamp_str)
        now = datetime.utcnow()

        age_seconds = (now - timestamp).total_seconds()
        ttl_seconds = ttl_hours * 3600
        remaining_ttl = ttl_seconds - age_seconds

        print("📊 Catalog Metadata:")
        print(f"   Timestamp: {timestamp_str}")
        print(f"   TTL Hours: {ttl_hours}")
        print(f"   Age: {age_seconds:.1f} seconds ({age_seconds/3600:.1f} hours)")
        print(f"   Remaining TTL: {remaining_ttl:.1f} seconds")

        # TTL threshold (1 hour)
        ttl_threshold = 3600

        if age_seconds >= ttl_threshold:
            print("⚠️  Catalog is OLDER than TTL threshold (3600 seconds)")
            print("   → User would be prompted to rebuild")
        else:
            print("✅ Catalog is FRESH (under TTL threshold)")
            print("   → Would use existing catalog")

        print(f"\n🎯 TTL Threshold: {ttl_threshold} seconds (1 hour)")
        print(f"🔄 Should {'REBUILD' if age_seconds >= ttl_threshold else 'KEEP'} catalog")

    except Exception as e:
        print(f"❌ Error reading metadata: {e}")

if __name__ == "__main__":
    test_catalog_ttl()
