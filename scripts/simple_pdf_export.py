#!/usr/bin/env python3
"""
Simple ADR PDF Export Script
Creates individual diagram images and a simple HTML version
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

def extract_mermaid_diagrams(markdown_file):
    """Extract all Mermaid diagrams from the markdown file."""
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all mermaid code blocks
    mermaid_pattern = r'```mermaid\n(.*?)\n```'
    diagrams = re.findall(mermaid_pattern, content, re.DOTALL)
    
    return diagrams, content

def create_individual_diagram_images(diagrams, output_dir):
    """Create individual PNG images for each Mermaid diagram."""
    images_dir = output_dir / "diagrams"
    images_dir.mkdir(exist_ok=True)
    
    created_images = []
    diagram_titles = [
        "System Overview",
        "Component Architecture", 
        "Class Diagram",
        "Complete Query Processing Flow",
        "Schema Discovery Process",
        "Error Handling and Clarification Flow",
        "Data Flow Architecture",
        "Database Schema Structure",
        "Component Responsibilities",
        "System Performance Metrics",
        "Scalability Architecture",
        "Security Layers",
        "Container Deployment",
        "Monitoring Stack",
        "System Evolution Roadmap"
    ]
    
    for i, diagram in enumerate(diagrams, 1):
        # Create temporary mermaid file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write(diagram)
            temp_file = f.name
        
        try:
            title = diagram_titles[i-1] if i-1 < len(diagram_titles) else f"Diagram {i}"
            safe_title = re.sub(r'[^a-zA-Z0-9\-_]', '_', title)
            output_image = images_dir / f"{i:02d}_{safe_title}.png"
            
            # Use mmdc to convert with high quality
            cmd = [
                'mmdc', 
                '-i', temp_file, 
                '-o', str(output_image), 
                '-b', 'white', 
                '-s', '3',  # Scale factor for higher quality
                '--width', '1200',
                '--height', '800'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ {title}: {output_image.name}")
                created_images.append((output_image, title))
            else:
                print(f"❌ Failed to create {title}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error creating diagram {i}: {e}")
        finally:
            # Clean up temp file
            os.unlink(temp_file)
    
    return created_images

def create_simple_html(markdown_file, output_dir, diagram_images):
    """Create a simple HTML version with links to diagrams."""
    output_file = output_dir / "ADR-0010-Architecture.html"
    
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple HTML template
    html_start = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ADR-0010: Dynamic ERP Assistant Architecture</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6; 
            max-width: 1000px; 
            margin: 0 auto; 
            padding: 20px; 
        }
        h1, h2, h3 { color: #2c3e50; }
        h1 { border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { border-bottom: 1px solid #ecf0f1; padding-bottom: 5px; }
        .diagram-link { 
            display: inline-block; 
            margin: 10px; 
            padding: 10px; 
            background: #f8f9fa; 
            border-radius: 5px; 
            text-decoration: none; 
            color: #2c3e50;
        }
        .diagram-link:hover { background: #e9ecef; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 5px; }
        code { background: #f1f2f6; padding: 2px 4px; border-radius: 3px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
"""
    
    # Convert basic markdown to HTML
    html_content = content
    
    # Remove mermaid blocks and replace with diagram links
    def replace_mermaid(match):
        return ""  # Remove mermaid blocks for now
    
    html_content = re.sub(r'```mermaid\n(.*?)\n```', replace_mermaid, html_content, flags=re.DOTALL)
    
    # Convert headers
    html_content = re.sub(r'^# (.*)', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.*)', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.*)', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^#### (.*)', r'<h4>\1</h4>', html_content, flags=re.MULTILINE)
    
    # Convert bold and code
    html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'`([^`]+)`', r'<code>\1</code>', html_content)
    
    # Convert paragraphs
    html_content = html_content.replace('\n\n', '</p>\n<p>')
    html_content = f'<p>{html_content}</p>'
    
    # Add diagram gallery
    diagram_gallery = "\n<h2>📊 Architecture Diagrams</h2>\n<div>\n"
    for img_path, title in diagram_images:
        rel_path = f"diagrams/{img_path.name}"
        diagram_gallery += f'<a href="{rel_path}" class="diagram-link" target="_blank">🖼️ {title}</a>\n'
    diagram_gallery += "</div>\n"
    
    # Insert diagram gallery after the first h2
    html_content = re.sub(r'(<h2>.*?</h2>)', r'\1' + diagram_gallery, html_content, count=1)
    
    html_end = "\n</body>\n</html>"
    
    final_html = html_start + html_content + html_end
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    print(f"✅ HTML created: {output_file}")
    return output_file

def create_pdf_with_chrome(html_file, output_dir):
    """Create PDF using Chrome headless."""
    output_file = output_dir / "ADR-0010-Architecture.pdf"
    
    chrome_commands = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        'google-chrome',
        'chromium',
        'chromium-browser'
    ]
    
    for chrome_cmd in chrome_commands:
        try:
            cmd = [
                chrome_cmd,
                '--headless',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--print-to-pdf=' + str(output_file),
                '--print-to-pdf-no-header',
                '--virtual-time-budget=2000',
                str(html_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and output_file.exists():
                print(f"✅ PDF created: {output_file}")
                return True
                
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    print("⚠️  Chrome/Chromium not found for PDF conversion")
    return False

def main():
    """Main export function."""
    project_root = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code")
    adr_file = project_root / "adrs" / "0010-dynamic-erp-assistant-complete-system-architecture.md"
    output_dir = project_root / "exports"
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    print("🚀 ADR-0010 Export Process")
    print("=" * 50)
    print(f"📄 Source: {adr_file.name}")
    print(f"📁 Output: {output_dir}")
    print()
    
    if not adr_file.exists():
        print(f"❌ ADR file not found: {adr_file}")
        return
    
    # Extract Mermaid diagrams
    diagrams, content = extract_mermaid_diagrams(adr_file)
    print(f"📊 Found {len(diagrams)} Mermaid diagrams")
    print()
    
    # Create individual diagram images
    print("🖼️  Creating diagram images...")
    created_images = create_individual_diagram_images(diagrams, output_dir)
    print()
    
    # Create HTML version
    print("🌐 Creating HTML version...")
    html_file = create_simple_html(adr_file, output_dir, created_images)
    print()
    
    # Try to create PDF
    print("📄 Creating PDF...")
    pdf_success = create_pdf_with_chrome(html_file, output_dir)
    print()
    
    # Summary
    print("=" * 50)
    print("📋 EXPORT COMPLETE")
    print("=" * 50)
    print(f"✅ Diagrams: {len(created_images)} PNG files")
    print(f"✅ HTML: {html_file.name}")
    print(f"{'✅' if pdf_success else '⚠️ '} PDF: {'Created' if pdf_success else 'Manual conversion needed'}")
    print()
    print(f"📁 Location: {output_dir}")
    
    # Open output directory
    try:
        subprocess.run(['open', str(output_dir)], check=True)
        print("📂 Opened in Finder")
    except:
        pass

if __name__ == "__main__":
    main()