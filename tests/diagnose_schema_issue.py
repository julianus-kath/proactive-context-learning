#!/usr/bin/env python3
"""
Diagnostic script for schema JSON parsing issues.

This script helps identify why the database schema indexing is failing
by testing each step of the process and logging detailed information.

Run with:
    python tests/diagnose_schema_issue.py
"""

import asyncio
import sys
import os
import json
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph_integration.mcp_client import MCPDatabaseTool, _extract_json_from_text


async def diagnose_schema_issue():
    """Run diagnostic checks on schema retrieval."""
    
    print("\n" + "="*80)
    print("🔍 SCHEMA INDEXING DIAGNOSTIC TOOL")
    print("="*80)
    
    print("\n[Step 1] Testing MCP Server Connection")
    print("-" * 80)
    
    tool = MCPDatabaseTool()
    
    # Test health check
    try:
        is_healthy = await tool.health_check()
        if is_healthy:
            print("✅ MCP server is healthy")
        else:
            print("❌ MCP server health check failed")
            print("   → Check: Windows MCP server is running")
            print("   → Check: MCP_SERVER_URL in .env is correct")
            return
    except Exception as e:
        print(f"❌ Failed to check MCP server health: {e}")
        return
    
    print("\n[Step 2] Fetching Raw Schema")
    print("-" * 80)
    
    try:
        schema_content = await tool.get_schema()
        print(f"✅ Successfully fetched schema content")
        print(f"   Content type: {type(schema_content)}")
        print(f"   Content length: {len(schema_content) if isinstance(schema_content, list) else 'N/A'}")
        
        if not schema_content or len(schema_content) == 0:
            print("❌ Schema content is empty!")
            print("   → The MCP server returned an empty response")
            return
        
        first_item = schema_content[0]
        print(f"   First item type: {type(first_item)}")
        if isinstance(first_item, dict):
            print(f"   First item keys: {list(first_item.keys())}")
            
            # Check for text field
            if "text" in first_item:
                text = first_item["text"]
                print(f"   Text field type: {type(text)}")
                print(f"   Text field length: {len(text) if text else 0} bytes")
                
                if text:
                    print(f"\n   Text preview (first 500 chars):")
                    print("   " + "-" * 76)
                    for line in text[:500].split("\n"):
                        print(f"   {line}")
                    print("   " + "-" * 76)
                    
                    if len(text) > 500:
                        print(f"   ... ({len(text) - 500} more chars)")
                else:
                    print("   ❌ Text field is empty!")
            else:
                print(f"   ❌ No 'text' field in first item!")
                print(f"   Available fields: {list(first_item.keys())}")
        else:
            print(f"   ❌ First item is not a dict: {type(first_item)}")
            print(f"   Content: {first_item}")
            
    except Exception as e:
        print(f"❌ Failed to fetch schema: {e}")
        return
    
    print("\n[Step 3] Testing JSON Extraction")
    print("-" * 80)
    
    if not schema_content or len(schema_content) == 0:
        print("❌ No schema content to extract JSON from")
        return
    
    text = schema_content[0].get("text", "")
    if not text:
        print("❌ No text content to parse")
        return
    
    try:
        payload = _extract_json_from_text(text)
        print("✅ JSON extraction successful!")
        print(f"   Payload keys: {list(payload.keys())}")
        
        # Check structure
        if "data" in payload:
            print(f"   ✓ 'data' key found")
            data = payload["data"]
            print(f"     Data keys: {list(data.keys())}")
            
            if "tables" in data:
                tables = data["tables"]
                print(f"     ✓ 'tables' key found (count: {len(tables)})")
            else:
                print(f"     ✗ 'tables' key NOT found")
            
            if "page_info" in data:
                page_info = data["page_info"]
                print(f"     ✓ 'page_info' key found")
                print(f"       page_info content: {page_info}")
            else:
                print(f"     ✗ 'page_info' key NOT found")
        else:
            print(f"   ✗ 'data' key NOT found. Top-level keys: {list(payload.keys())}")
        
        print(f"\n   Full payload preview:")
        print("   " + "-" * 76)
        print(json.dumps(payload, indent=2)[:1000])
        print("   " + "-" * 76)
        
    except ValueError as e:
        print(f"❌ JSON extraction failed: {e}")
        print(f"\n   Troubleshooting:")
        
        # Analyze the text to help debug
        text_lower = text.lower()
        
        if "full response (json):" not in text_lower:
            print(f"   ❌ Expected marker 'Full response (JSON):' NOT found")
            print(f"      Text starts with: {text[:100]}")
        
        if "{" not in text:
            print(f"   ❌ No opening brace '{{' found in text")
        
        if "}" not in text:
            print(f"   ❌ No closing brace '}}' found in text")
        
        # Try manual extraction
        print(f"\n   Attempting manual JSON extraction...")
        start = text.find("{")
        end = text.rfind("}")
        
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end+1]
            print(f"   Found potential JSON between positions {start}-{end}")
            print(f"   Length: {len(json_str)} chars")
            
            try:
                manual_parse = json.loads(json_str)
                print(f"   ✅ Manual JSON parsing succeeded!")
                print(f"   Keys: {list(manual_parse.keys())}")
            except json.JSONDecodeError as je:
                print(f"   ❌ Manual JSON parsing failed: {je}")
                print(f"   Problem area: {json_str[max(0,je.pos-50):min(len(json_str),je.pos+50)]}")
        else:
            if start == -1:
                print(f"   ❌ No opening brace found")
            if end == -1:
                print(f"   ❌ No closing brace found")
            if end <= start:
                print(f"   ❌ Braces in wrong order or malformed")
        
        return
    
    except Exception as e:
        print(f"❌ Unexpected error during extraction: {e}", exc_info=True)
        return
    
    print("\n[Step 4] Validating Schema Structure")
    print("-" * 80)
    
    try:
        data = payload.get("data", {})
        tables = data.get("tables", [])
        page_info = data.get("page_info", {})
        
        total_items = page_info.get("total_items", len(tables))
        total_pages = page_info.get("total_pages", 1)
        current_page = page_info.get("page", 1)
        
        print(f"✅ Schema structure is valid")
        print(f"   Tables on current page: {len(tables)}")
        print(f"   Total tables in database: {total_items}")
        print(f"   Total pages: {total_pages}")
        print(f"   Current page: {current_page}")
        
        if len(tables) > 0:
            first_table = tables[0]
            print(f"\n   Sample table (first):")
            print(f"   - Name: {first_table.get('name', 'N/A')}")
            print(f"   - Columns: {len(first_table.get('columns', []))}")
            print(f"   - Row count: {first_table.get('row_count', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Failed to validate schema structure: {e}")
        return
    
    print("\n" + "="*80)
    print("✅ DIAGNOSTIC COMPLETE - No issues found!")
    print("="*80)
    print("\nThe schema indexing should work correctly. If you're still seeing errors:")
    print("1. Check the full logs: tail -f logs/langgraph_debug.log")
    print("2. Verify MCP server is running: start_mcp_server_windows.bat")
    print("3. Check network connectivity between Mac and Windows")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(diagnose_schema_issue())
    except KeyboardInterrupt:
        print("\n\n❌ Diagnostic interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error during diagnosis: {e}", exc_info=True)
        sys.exit(1)