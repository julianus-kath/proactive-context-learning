"""
Catalog Store for Scout Mode
Phase 1: Atomic writes, TTL, compression, and versioning.

Handles persistence of Scout-generated schema catalogs with:
- GZIP compression for space efficiency
- Atomic writes to prevent corruption
- Checksum validation for integrity
- TTL-based expiration
- Versioning for compatibility
"""

import os
import json
import gzip
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CatalogStore:
    """
    Persistent storage for Scout Mode schema catalogs.

    Features:
    - Atomic writes with temporary files
    - GZIP compression (typically 80% reduction)
    - SHA256 checksums for corruption detection
    - TTL-based expiration
    - Versioning for format compatibility
    """

    CATALOG_VERSION = "1.0"
    DEFAULT_TTL_HOURS = 24 * 7  # 7 days

    def __init__(
        self,
        catalog_dir: str = "data/catalog",
        ttl_hours: int = DEFAULT_TTL_HOURS,
        compression_level: int = 6
    ):
        """
        Initialize catalog store.

        Args:
            catalog_dir: Directory to store catalog files
            ttl_hours: Time-to-live in hours for cached catalogs
            compression_level: GZIP compression level (1-9)
        """
        self.catalog_dir = Path(catalog_dir)
        self.ttl_hours = ttl_hours
        self.compression_level = compression_level

        # Ensure catalog directory exists
        self.catalog_dir.mkdir(parents=True, exist_ok=True)

        # Catalog file paths
        self.catalog_file = self.catalog_dir / "scout_catalog.json.gz"
        self.metadata_file = self.catalog_dir / "catalog_metadata.json"

        logger.info(f"✅ CatalogStore initialized: dir={self.catalog_dir}, TTL={self.ttl_hours}h")

    def store_catalog(self, catalog_data: Dict[str, Any]) -> bool:
        """
        Store catalog data atomically with compression and integrity checks.

        Args:
            catalog_data: Catalog dictionary to store

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add metadata
            enriched_data = {
                "version": self.CATALOG_VERSION,
                "timestamp": datetime.utcnow().isoformat(),
                "ttl_hours": self.ttl_hours,
                "compression": "gzip",
                "data": catalog_data
            }

            # Serialize to JSON (without checksum first)
            json_data = json.dumps(enriched_data, indent=None, default=str)
            json_bytes = json_data.encode('utf-8')

            # Calculate checksum on the JSON bytes
            checksum = hashlib.sha256(json_bytes).hexdigest()

            # Add checksum to metadata
            enriched_data["checksum"] = checksum

            # Final serialization with checksum
            json_data = json.dumps(enriched_data, indent=None, default=str)
            json_bytes = json_data.encode('utf-8')

            # Compress
            compressed_data = gzip.compress(
                json_bytes,
                compresslevel=self.compression_level
            )

            # Atomic write: write to temp file first
            temp_file = self.catalog_file.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                f.write(compressed_data)

            # Atomic move
            temp_file.replace(self.catalog_file)

            # Store metadata separately (uncompressed for quick access)
            metadata = {
                "version": self.CATALOG_VERSION,
                "timestamp": enriched_data["timestamp"],
                "ttl_hours": self.ttl_hours,
                "checksum": checksum,
                "compressed_size": len(compressed_data),
                "uncompressed_size": len(json_bytes),
                "compression_ratio": len(compressed_data) / len(json_bytes)
            }

            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(
                f"✅ Catalog stored: {len(compressed_data):,} bytes compressed "
                f"({metadata['compression_ratio']:.2f} ratio), TTL={self.ttl_hours}h"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Failed to store catalog: {e}")
            return False

    def load_catalog(self) -> Optional[Dict[str, Any]]:
        """
        Load catalog data with integrity verification and TTL checking.

        Returns:
            Catalog data dict if valid and not expired, None otherwise
        """
        try:
            # Check if files exist
            if not self.catalog_file.exists() or not self.metadata_file.exists():
                logger.debug("Catalog files not found")
                return None

            # Load metadata first (quick check)
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)

            # Check version compatibility
            if metadata.get("version") != self.CATALOG_VERSION:
                logger.warning(f"Catalog version mismatch: {metadata.get('version')} != {self.CATALOG_VERSION}")
                return None

            # Check TTL
            timestamp = datetime.fromisoformat(metadata["timestamp"])
            age_hours = (datetime.utcnow() - timestamp).total_seconds() / 3600

            if age_hours > metadata["ttl_hours"]:
                logger.info(f"Catalog expired: {age_hours:.1f}h > {metadata['ttl_hours']}h TTL")
                return None

            # Load compressed catalog (gzip.open automatically decompresses)
            with gzip.open(self.catalog_file, 'rb') as f:
                json_bytes = f.read()

            # Parse JSON
            enriched_data = json.loads(json_bytes.decode('utf-8'))

            # Verify checksum: calculate on data without checksum field
            stored_checksum = enriched_data.pop("checksum", "")
            json_without_checksum = json.dumps(enriched_data, indent=None, default=str).encode('utf-8')
            calculated_checksum = hashlib.sha256(json_without_checksum).hexdigest()

            # Restore checksum for return
            enriched_data["checksum"] = stored_checksum

            if stored_checksum != calculated_checksum:
                logger.error("Catalog checksum mismatch - data corrupted")
                return None

            # Verify version again
            if enriched_data.get("version") != self.CATALOG_VERSION:
                logger.error("Catalog version mismatch in data")
                return None

            catalog_data = enriched_data["data"]

            logger.info(
                f"✅ Catalog loaded: {len(json_bytes):,} bytes, "
                f"age={age_hours:.1f}h, TTL={metadata['ttl_hours']}h"
            )

            return catalog_data

        except Exception as e:
            logger.error(f"❌ Failed to load catalog: {e}")
            return None

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get catalog metadata without loading full catalog.

        Returns:
            Metadata dict or None if not available
        """
        try:
            if not self.metadata_file.exists():
                return None

            with open(self.metadata_file, 'r') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Failed to load catalog metadata: {e}")
            return None

    def is_valid(self) -> bool:
        """
        Check if catalog exists and is valid/not expired.

        Returns:
            True if catalog is available and usable
        """
        metadata = self.get_metadata()
        if not metadata:
            return False

        # Check TTL
        timestamp = datetime.fromisoformat(metadata["timestamp"])
        age_hours = (datetime.utcnow() - timestamp).total_seconds() / 3600

        return age_hours <= metadata["ttl_hours"]

    def get_age_hours(self) -> Optional[float]:
        """
        Get catalog age in hours.

        Returns:
            Age in hours, or None if no catalog
        """
        metadata = self.get_metadata()
        if not metadata:
            return None

        timestamp = datetime.fromisoformat(metadata["timestamp"])
        return (datetime.utcnow() - timestamp).total_seconds() / 3600

    def clear_catalog(self) -> bool:
        """
        Remove catalog files.

        Returns:
            True if successful
        """
        try:
            if self.catalog_file.exists():
                self.catalog_file.unlink()
            if self.metadata_file.exists():
                self.metadata_file.unlink()
            logger.info("✅ Catalog cleared")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clear catalog: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get catalog statistics.

        Returns:
            Stats dictionary
        """
        metadata = self.get_metadata()
        age_hours = self.get_age_hours()

        return {
            "exists": self.catalog_file.exists(),
            "valid": self.is_valid(),
            "age_hours": age_hours,
            "ttl_hours": metadata.get("ttl_hours") if metadata else None,
            "compressed_size": metadata.get("compressed_size") if metadata else None,
            "compression_ratio": metadata.get("compression_ratio") if metadata else None,
            "version": metadata.get("version") if metadata else None,
            "timestamp": metadata.get("timestamp") if metadata else None
        }
