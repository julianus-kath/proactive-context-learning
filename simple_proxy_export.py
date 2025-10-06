#!/usr/bin/env python3
"""
Simple export script for ADR-0011: ERP Proxy Integration Architecture
Creates HTML and PDF exports
"""

import os
from pathlib import Path
from datetime import datetime

def create_html_export():
    """Create HTML export of ADR-0011."""
    
    project_root = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code")
    adr_file = project_root / "adrs" / "0011-erp-proxy-integration-architecture.md"
    exports_dir = project_root / "exports"
    
    # Create exports directory
    exports_dir.mkdir(exist_ok=True)
    
    if not adr_file.exists():
        print(f"❌ ADR file not found: {adr_file}")
        return False
    
    # Read the markdown content
    with open(adr_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create HTML template
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADR-0011: ERP Proxy Integration Architecture</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3, h4 {{ color: #2c3e50; }}
        h1 {{ border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; margin-top: 30px; }}
        h3 {{ color: #34495e; margin-top: 25px; }}
        code {{
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Consolas', monospace;
        }}
        pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            border-left: 4px solid #3498db;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        .mermaid-placeholder {{
            background: #f8f9fa;
            border: 2px dashed #bdc3c7;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
            border-radius: 5px;
        }}
        .status-badge {{
            background: #27ae60;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .toc {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .toc ul {{ margin: 0; }}
        .toc li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>ADR-0011: ERP Proxy Integration Architecture</h1>
    
    <div class="toc">
        <h3>📋 Table of Contents</h3>
        <ul>
            <li><a href="#context">Context</a></li>
            <li><a href="#decision">Decision</a></li>
            <li><a href="#proxy-communication">Proxy Communication Architecture</a></li>
            <li><a href="#security">Security Architecture</a></li>
            <li><a href="#implementation">Implementation Details</a></li>
            <li><a href="#deployment">Deployment Architecture</a></li>
            <li><a href="#decisions">Key Design Decisions</a></li>
            <li><a href="#performance">Performance Considerations</a></li>
            <li><a href="#consequences">Consequences</a></li>
        </ul>
    </div>
    
    {content}
    
    <hr>
    <footer>
        <p><strong>Generated:</strong> {date}<br>
        <strong>Source:</strong> ADR-0011 ERP Proxy Integration Architecture<br>
        <strong>Export Script:</strong> simple_proxy_export.py</p>
    </footer>
</body>
</html>"""
    
    # Convert markdown to HTML (simple conversion)
    html_content = content
    
    # Replace mermaid blocks with placeholders
    import re
    mermaid_pattern = r'```mermaid\n(.*?)\n```'
    diagram_count = 0
    
    def replace_mermaid(match):
        nonlocal diagram_count
        diagram_count += 1
        diagram_content = match.group(1)
        # Try to identify diagram type from content
        if 'graph TB' in diagram_content and 'Mac Development Environment' in diagram_content:
            title = "System Overview with Proxy Integration"
        elif 'sequenceDiagram' in diagram_content and 'Network Communication' in diagram_content:
            title = "Network Communication Flow"
        elif 'graph TB' in diagram_content and 'Adapter Layer' in diagram_content:
            title = "Adapter Layer Architecture"
        elif 'classDiagram' in diagram_content:
            title = "Database Client Class Diagram"
        elif 'graph TB' in diagram_content and 'Security' in diagram_content:
            title = "Multi-Layer Security Model"
        elif 'graph LR' in diagram_content and 'Configuration' in diagram_content:
            title = "Configuration Management"
        elif 'sequenceDiagram' in diagram_content and 'Query Processing' in diagram_content:
            title = "Query Processing with Proxy Integration"
        elif 'graph TD' in diagram_content and 'Error' in diagram_content:
            title = "Error Handling and Fallback"
        elif 'graph TB' in diagram_content and 'Environment' in diagram_content:
            title = "Multi-Environment Deployment"
        elif 'graph TB' in diagram_content and 'Monitoring' in diagram_content:
            title = "Monitoring and Observability"
        else:
            title = f"Architecture Diagram {diagram_count}"
        
        return f'<div class="mermaid-placeholder">📊 {title}<br><small>Mermaid diagram - view source for details</small></div>'
    
    html_content = re.sub(mermaid_pattern, replace_mermaid, html_content, flags=re.DOTALL)
    
    # Basic markdown to HTML conversion
    html_content = html_content.replace('**Status**: Accepted', '<span class="status-badge">Accepted</span>')
    html_content = re.sub(r'^# (.*)', r'<h1>\\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.*)', r'<h2 id="\\1">\\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.*)', r'<h3>\\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^#### (.*)', r'<h4>\\1</h4>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'\\*\\*(.*?)\\*\\*', r'<strong>\\1</strong>', html_content)
    html_content = re.sub(r'\\*(.*?)\\*', r'<em>\\1</em>', html_content)
    html_content = re.sub(r'`(.*?)`', r'<code>\\1</code>', html_content)
    
    # Convert line breaks
    html_content = html_content.replace('\\n\\n', '</p><p>')
    html_content = f'<p>{html_content}</p>'
    
    # Generate final HTML
    final_html = html_template.format(
        content=html_content,
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Write HTML file
    html_file = exports_dir / "ADR-0011-Proxy-Architecture.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    print(f"📄 HTML export created: {html_file}")
    return True

def update_readme():
    """Update the exports README to include proxy architecture."""
    
    project_root = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code")
    exports_dir = project_root / "exports"
    readme_file = exports_dir / "README.md"
    
    # Read current README
    if readme_file.exists():
        with open(readme_file, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = "# Architecture Exports\\n\\n"
    
    # Add proxy architecture section if not already present
    if "ADR-0011" not in content:
        proxy_section = """

## 🔗 ADR-0011: ERP Proxy Integration Architecture

### 📄 Main Documents
- **`ADR-0011-Proxy-Architecture.html`** - Interactive HTML version
- **`0011-erp-proxy-integration-architecture.md`** - Original Markdown source (in adrs/ folder)

### 🎯 Key Features
- **Secure Proxy Communication**: HTTPS/TLS encrypted database access
- **Adapter Pattern**: Seamless integration with existing components  
- **Environment Switching**: DB_MODE configuration for dev/prod
- **SQL Translation**: Automatic PostgreSQL to SQL Server conversion
- **Error Handling**: Robust fallback and retry mechanisms

### 📊 Architecture Highlights
1. **System Overview with Proxy Integration** - Complete system architecture
2. **Network Communication Flow** - HTTPS communication sequence
3. **Adapter Layer Architecture** - Adapter pattern implementation
4. **Database Client Abstraction** - Unified database client design
5. **Multi-Layer Security Model** - Security architecture layers
6. **Configuration Management** - Environment configuration flow
7. **Query Processing with Proxy** - End-to-end query processing
8. **Error Handling and Fallback** - Error recovery mechanisms
9. **Multi-Environment Deployment** - Development to production flow
10. **Monitoring and Observability** - System monitoring architecture

### 🔄 Re-exporting
To regenerate proxy architecture exports:

```bash
cd "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"
python3 simple_proxy_export.py
```
"""
        content += proxy_section
    
    # Write updated README
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"📝 Updated README: {readme_file}")

def main():
    """Main export function."""
    
    print("🚀 ADR-0011 Proxy Architecture Export")
    print("=" * 50)
    
    success = True
    
    # Create HTML export
    print("\\n📄 Creating HTML export...")
    if not create_html_export():
        success = False
    
    # Update README
    print("\\n📝 Updating README...")
    update_readme()
    
    if success:
        print("\\n✅ Export completed successfully!")
        print("\\n📁 Generated files:")
        print("   - ADR-0011-Proxy-Architecture.html")
        print("   - Updated exports/README.md")
    else:
        print("\\n⚠️  Export failed. Check the output above.")
    
    return success

if __name__ == "__main__":
    main()