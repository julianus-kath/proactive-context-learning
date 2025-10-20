#!/usr/bin/env python3
"""
Export script for ADR-0011: ERP Proxy Integration Architecture
Generates PDF and HTML exports with all diagrams
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error running command: {cmd}")
            print(f"Error output: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Exception running command: {cmd}")
        print(f"Exception: {e}")
        return False

def export_diagrams():
    """Export all Mermaid diagrams from ADR-0011 to PNG files."""
    
    # Project root
    project_root = Path("/")
    adr_file = project_root / "adrs" / "0011-erp-proxy-integration-architecture.md"
    exports_dir = project_root / "exports"
    diagrams_dir = exports_dir / "diagrams" / "proxy_architecture"
    
    # Create directories
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Creating export directories...")
    print(f"   Diagrams: {diagrams_dir}")
    
    # Read the ADR file
    if not adr_file.exists():
        print(f"❌ ADR file not found: {adr_file}")
        return False
    
    with open(adr_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract Mermaid diagrams
    diagrams = []
    lines = content.split('\n')
    i = 0
    diagram_count = 0
    
    while i < len(lines):
        if lines[i].strip() == '```mermaid':
            diagram_count += 1
            diagram_lines = []
            i += 1
            
            # Extract diagram content
            while i < len(lines) and lines[i].strip() != '```':
                diagram_lines.append(lines[i])
                i += 1
            
            if diagram_lines:
                # Determine diagram name from context
                diagram_name = f"{diagram_count:02d}_Proxy_Diagram"
                
                # Look for heading above the diagram
                for j in range(max(0, i-50), i):
                    line = lines[j].strip()
                    if line.startswith('### ') and 'System Overview' in line:
                        diagram_name = "01_System_Overview_with_Proxy"
                        break
                    elif line.startswith('### ') and 'Network Communication' in line:
                        diagram_name = "02_Network_Communication_Flow"
                        break
                    elif line.startswith('### ') and 'Adapter Layer' in line:
                        diagram_name = "03_Adapter_Layer_Architecture"
                        break
                    elif line.startswith('### ') and 'Database Client' in line:
                        diagram_name = "04_Database_Client_Abstraction"
                        break
                    elif line.startswith('### ') and 'Multi-Layer Security' in line:
                        diagram_name = "05_Multi_Layer_Security_Model"
                        break
                    elif line.startswith('### ') and 'Configuration' in line:
                        diagram_name = "06_Configuration_Management"
                        break
                    elif line.startswith('### ') and 'Query Processing' in line:
                        diagram_name = "07_Query_Processing_with_Proxy"
                        break
                    elif line.startswith('### ') and 'Error Handling' in line:
                        diagram_name = "08_Error_Handling_and_Fallback"
                        break
                    elif line.startswith('### ') and 'Multi-Environment' in line:
                        diagram_name = "09_Multi_Environment_Deployment"
                        break
                    elif line.startswith('### ') and 'Monitoring' in line:
                        diagram_name = "10_Monitoring_and_Observability"
                        break
                
                diagrams.append({
                    'name': diagram_name,
                    'content': '\n'.join(diagram_lines)
                })
        i += 1
    
    print(f"📊 Found {len(diagrams)} diagrams to export")
    
    # Export each diagram
    success_count = 0
    for diagram in diagrams:
        print(f"   Exporting: {diagram['name']}")
        
        # Create temporary mermaid file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write(diagram['content'])
            temp_file = f.name
        
        try:
            # Export to PNG
            output_file = diagrams_dir / f"{diagram['name']}.png"
            cmd = f"mmdc -i {temp_file} -o {output_file} --width 1200 --height 800 --scale 3 --backgroundColor white"
            
            if run_command(cmd):
                print(f"     ✅ {output_file.name}")
                success_count += 1
            else:
                print(f"     ❌ Failed to export {diagram['name']}")
        
        finally:
            # Clean up temp file
            os.unlink(temp_file)
    
    print(f"📊 Successfully exported {success_count}/{len(diagrams)} diagrams")
    return success_count == len(diagrams)

def create_html_export():
    """Create HTML export of ADR-0011."""
    
    project_root = Path("/")
    adr_file = project_root / "adrs" / "0011-erp-proxy-integration-architecture.md"
    exports_dir = project_root / "exports"
    
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
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        h1, h2, h3, h4 { color: #2c3e50; }
        h1 { border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; margin-top: 30px; }
        h3 { color: #34495e; margin-top: 25px; }
        code {
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Consolas', monospace;
        }
        pre {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            border-left: 4px solid #3498db;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        .mermaid-placeholder {
            background: #f8f9fa;
            border: 2px dashed #bdc3c7;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
            border-radius: 5px;
        }
        .status-badge {
            background: #27ae60;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .toc {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .toc ul { margin: 0; }
        .toc li { margin: 5px 0; }
        .diagram-link {
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            margin: 5px;
        }
        .diagram-link:hover {
            background: #2980b9;
        }
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
    
    <div class="diagram-links">
        <h3>🖼️ Architecture Diagrams</h3>
        <a href="diagrams/proxy_architecture/01_System_Overview_with_Proxy.png" class="diagram-link">System Overview</a>
        <a href="diagrams/proxy_architecture/02_Network_Communication_Flow.png" class="diagram-link">Network Flow</a>
        <a href="diagrams/proxy_architecture/03_Adapter_Layer_Architecture.png" class="diagram-link">Adapter Layer</a>
        <a href="diagrams/proxy_architecture/04_Database_Client_Abstraction.png" class="diagram-link">Client Abstraction</a>
        <a href="diagrams/proxy_architecture/05_Multi_Layer_Security_Model.png" class="diagram-link">Security Model</a>
        <a href="diagrams/proxy_architecture/06_Configuration_Management.png" class="diagram-link">Configuration</a>
        <a href="diagrams/proxy_architecture/07_Query_Processing_with_Proxy.png" class="diagram-link">Query Processing</a>
        <a href="diagrams/proxy_architecture/08_Error_Handling_and_Fallback.png" class="diagram-link">Error Handling</a>
        <a href="diagrams/proxy_architecture/09_Multi_Environment_Deployment.png" class="diagram-link">Deployment</a>
        <a href="diagrams/proxy_architecture/10_Monitoring_and_Observability.png" class="diagram-link">Monitoring</a>
    </div>
    
    {content}
    
    <hr>
    <footer>
        <p><strong>Generated:</strong> {date}<br>
        <strong>Source:</strong> ADR-0011 ERP Proxy Integration Architecture<br>
        <strong>Export Script:</strong> export_proxy_architecture.py</p>
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
        return f'<div class="mermaid-placeholder">📊 Diagram {diagram_count} - See exported PNG files</div>'
    
    html_content = re.sub(mermaid_pattern, replace_mermaid, html_content, flags=re.DOTALL)
    
    # Basic markdown to HTML conversion
    html_content = html_content.replace('**Status**: Accepted', '<span class="status-badge">Accepted</span>')
    html_content = re.sub(r'^# (.*)', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.*)', r'<h2 id="\1">\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.*)', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^#### (.*)', r'<h4>\1</h4>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html_content)
    html_content = re.sub(r'`(.*?)`', r'<code>\1</code>', html_content)
    
    # Convert line breaks
    html_content = html_content.replace('\n\n', '</p><p>')
    html_content = f'<p>{html_content}</p>'
    
    # Generate final HTML
    from datetime import datetime
    final_html = html_template.replace('{content}', html_content)
    final_html = final_html.replace('{date}', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Write HTML file
    html_file = exports_dir / "ADR-0011-Proxy-Architecture.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    print(f"📄 HTML export created: {html_file}")
    return True

def create_pdf_export():
    """Create PDF export using Chrome headless."""
    
    project_root = Path("/")
    exports_dir = project_root / "exports"
    html_file = exports_dir / "ADR-0011-Proxy-Architecture.html"
    pdf_file = exports_dir / "ADR-0011-Proxy-Architecture.pdf"
    
    if not html_file.exists():
        print(f"❌ HTML file not found: {html_file}")
        return False
    
    # Use Chrome to generate PDF
    cmd = f"""
    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \
        --headless \
        --disable-gpu \
        --print-to-pdf="{pdf_file}" \
        --print-to-pdf-no-header \
        --no-margins \
        "file://{html_file.absolute()}"
    """
    
    if run_command(cmd):
        print(f"📄 PDF export created: {pdf_file}")
        return True
    else:
        print(f"❌ Failed to create PDF export")
        return False

def update_readme():
    """Update the exports README to include proxy architecture."""
    
    project_root = Path("/")
    exports_dir = project_root / "exports"
    readme_file = exports_dir / "README.md"
    
    # Read current README
    if readme_file.exists():
        with open(readme_file, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = ""
    
    # Add proxy architecture section
    proxy_section = """

## 🔗 ADR-0011: ERP Proxy Integration Architecture

### 📄 Main Documents
- **`ADR-0011-Proxy-Architecture.pdf`** - Complete PDF version with all content
- **`ADR-0011-Proxy-Architecture.html`** - Interactive HTML version with diagram links
- **`0011-erp-proxy-integration-architecture.md`** - Original Markdown source

### 🖼️ Proxy Architecture Diagrams (`diagrams/proxy_architecture/` folder)
All 10 proxy integration diagrams exported as high-quality PNG images:

1. **`01_System_Overview_with_Proxy.png`** - Complete system with proxy integration
2. **`02_Network_Communication_Flow.png`** - HTTPS communication sequence
3. **`03_Adapter_Layer_Architecture.png`** - Adapter pattern implementation
4. **`04_Database_Client_Abstraction.png`** - Unified database client design
5. **`05_Multi_Layer_Security_Model.png`** - Security architecture layers
6. **`06_Configuration_Management.png`** - Environment configuration flow
7. **`07_Query_Processing_with_Proxy.png`** - End-to-end query processing
8. **`08_Error_Handling_and_Fallback.png`** - Error recovery mechanisms
9. **`09_Multi_Environment_Deployment.png`** - Development to production flow
10. **`10_Monitoring_and_Observability.png`** - System monitoring architecture

### 🎯 Key Features
- **Secure Proxy Communication**: HTTPS/TLS encrypted database access
- **Adapter Pattern**: Seamless integration with existing components
- **Environment Switching**: DB_MODE configuration for dev/prod
- **SQL Translation**: Automatic PostgreSQL to SQL Server conversion
- **Error Handling**: Robust fallback and retry mechanisms
"""
    
    # Add to README if not already present
    if "ADR-0011" not in content:
        content += proxy_section
    
    # Write updated README
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"📝 Updated README: {readme_file}")

def main():
    """Main export function."""
    
    print("🚀 ADR-0011 Proxy Architecture Export")
    print("=" * 50)
    
    # Check if mermaid CLI is available
    if not run_command("which mmdc"):
        print("❌ Mermaid CLI not found. Please install it:")
        print("   npm install -g @mermaid-js/mermaid-cli")
        return False
    
    success = True
    
    # Export diagrams
    print("\n📊 Exporting diagrams...")
    if not export_diagrams():
        success = False
    
    # Create HTML export
    print("\n📄 Creating HTML export...")
    if not create_html_export():
        success = False
    
    # Create PDF export
    print("\n📄 Creating PDF export...")
    if not create_pdf_export():
        success = False
    
    # Update README
    print("\n📝 Updating README...")
    update_readme()
    
    if success:
        print("\n✅ All exports completed successfully!")
        print("\n📁 Generated files:")
        print("   - ADR-0011-Proxy-Architecture.html")
        print("   - ADR-0011-Proxy-Architecture.pdf")
        print("   - diagrams/proxy_architecture/*.png")
    else:
        print("\n⚠️  Some exports failed. Check the output above.")
    
    return success

if __name__ == "__main__":
    main()