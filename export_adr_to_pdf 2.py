#!/usr/bin/env python3
"""
ADR PDF Export Script
Exports ADR-0010 with Mermaid diagrams to PDF using multiple methods
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

def create_pdf_with_pandoc(markdown_file, output_dir):
    """Create PDF using Pandoc with Mermaid filter."""
    output_file = output_dir / "ADR-0010-Architecture.pdf"
    
    try:
        # Check if pandoc is available
        subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
        
        # Try to convert with mermaid filter
        cmd = [
            'pandoc',
            str(markdown_file),
            '-o', str(output_file),
            '--pdf-engine=xelatex',
            '--filter', 'mermaid-filter',
            '-V', 'geometry:margin=1in',
            '--toc'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ PDF created with Pandoc: {output_file}")
            return True
        else:
            print(f"❌ Pandoc failed: {result.stderr}")
            return False
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Pandoc not available or mermaid-filter not installed")
        return False

def create_html_with_mermaid(markdown_file, output_dir):
    """Create HTML with embedded Mermaid diagrams."""
    output_file = output_dir / "ADR-0010-Architecture.html"
    
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Convert markdown to HTML with Mermaid support
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ADR-0010: Dynamic ERP Assistant Architecture</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #2c3e50;
            margin-top: 2em;
        }
        h1 {
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 5px;
        }
        .mermaid {
            text-align: center;
            margin: 20px 0;
        }
        pre {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }
        code {
            background: #f1f2f6;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Monaco', 'Consolas', monospace;
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
        blockquote {
            border-left: 4px solid #3498db;
            margin: 0;
            padding-left: 20px;
            color: #666;
        }
        .status-accepted {
            background: #d4edda;
            color: #155724;
            padding: 10px;
            border-radius: 5px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div id="content">
        {content}
    </div>
    <script>
        mermaid.initialize({{ 
            startOnLoad: true,
            theme: 'default',
            themeVariables: {{
                primaryColor: '#3498db',
                primaryTextColor: '#2c3e50',
                primaryBorderColor: '#2980b9',
                lineColor: '#34495e'
            }}
        }});
    </script>
</body>
</html>
"""
    
    # Simple markdown to HTML conversion
    html_content = content
    
    # Convert headers
    html_content = re.sub(r'^# (.*)', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.*)', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.*)', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^#### (.*)', r'<h4>\1</h4>', html_content, flags=re.MULTILINE)
    
    # Convert bold text
    html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)
    
    # Convert code blocks (preserve mermaid)
    html_content = re.sub(r'```mermaid\n(.*?)\n```', r'<div class="mermaid">\1</div>', html_content, flags=re.DOTALL)
    html_content = re.sub(r'```(.*?)\n(.*?)\n```', r'<pre><code class="\1">\2</code></pre>', html_content, flags=re.DOTALL)
    
    # Convert inline code
    html_content = re.sub(r'`([^`]+)`', r'<code>\1</code>', html_content)
    
    # Convert line breaks
    html_content = html_content.replace('\n\n', '</p><p>')
    html_content = f'<p>{html_content}</p>'
    
    # Add status styling
    html_content = re.sub(r'<p><strong>Status</strong>: Accepted', r'<div class="status-accepted"><strong>Status</strong>: Accepted', html_content)
    
    final_html = html_template.format(content=html_content)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    print(f"✅ HTML created: {output_file}")
    return output_file

def convert_html_to_pdf(html_file, output_dir):
    """Convert HTML to PDF using wkhtmltopdf or similar."""
    output_file = output_dir / "ADR-0010-Architecture-from-HTML.pdf"
    
    try:
        # Try wkhtmltopdf first
        cmd = [
            'wkhtmltopdf',
            '--page-size', 'A4',
            '--margin-top', '0.75in',
            '--margin-right', '0.75in',
            '--margin-bottom', '0.75in',
            '--margin-left', '0.75in',
            '--enable-javascript',
            '--javascript-delay', '2000',
            str(html_file),
            str(output_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ PDF created from HTML: {output_file}")
            return True
        else:
            print(f"❌ wkhtmltopdf failed: {result.stderr}")
            
    except FileNotFoundError:
        print("⚠️  wkhtmltopdf not available")
    
    # Try using Chrome/Chromium headless
    try:
        chrome_commands = ['google-chrome', 'chromium', 'chromium-browser', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
        
        for chrome_cmd in chrome_commands:
            try:
                cmd = [
                    chrome_cmd,
                    '--headless',
                    '--disable-gpu',
                    '--print-to-pdf=' + str(output_file),
                    '--print-to-pdf-no-header',
                    str(html_file)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and output_file.exists():
                    print(f"✅ PDF created with Chrome: {output_file}")
                    return True
                    
            except FileNotFoundError:
                continue
                
        print("⚠️  No suitable PDF converter found")
        
    except Exception as e:
        print(f"❌ Chrome PDF conversion failed: {e}")
    
    return False

def create_individual_diagram_images(diagrams, output_dir):
    """Create individual PNG images for each Mermaid diagram."""
    images_dir = output_dir / "diagrams"
    images_dir.mkdir(exist_ok=True)
    
    created_images = []
    
    for i, diagram in enumerate(diagrams, 1):
        # Create temporary mermaid file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write(diagram)
            temp_file = f.name
        
        try:
            output_image = images_dir / f"diagram_{i:02d}.png"
            
            # Use mmdc to convert
            cmd = ['mmdc', '-i', temp_file, '-o', str(output_image), '-b', 'white', '-s', '2']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Diagram {i} created: {output_image}")
                created_images.append(output_image)
            else:
                print(f"❌ Failed to create diagram {i}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error creating diagram {i}: {e}")
        finally:
            # Clean up temp file
            os.unlink(temp_file)
    
    return created_images

def main():
    """Main export function."""
    project_root = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code")
    adr_file = project_root / "adrs" / "0010-dynamic-erp-assistant-complete-system-architecture.md"
    output_dir = project_root / "exports"
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    print("🚀 Starting ADR-0010 PDF Export Process...")
    print(f"📄 Source: {adr_file}")
    print(f"📁 Output: {output_dir}")
    print()
    
    if not adr_file.exists():
        print(f"❌ ADR file not found: {adr_file}")
        return
    
    # Extract Mermaid diagrams
    diagrams, content = extract_mermaid_diagrams(adr_file)
    print(f"📊 Found {len(diagrams)} Mermaid diagrams")
    
    # Method 1: Create individual diagram images
    print("\n🖼️  Creating individual diagram images...")
    created_images = create_individual_diagram_images(diagrams, output_dir)
    
    # Method 2: Create HTML with embedded Mermaid
    print("\n🌐 Creating HTML version...")
    html_file = create_html_with_mermaid(adr_file, output_dir)
    
    # Method 3: Convert HTML to PDF
    print("\n📄 Converting HTML to PDF...")
    html_to_pdf_success = convert_html_to_pdf(html_file, output_dir)
    
    # Method 4: Try Pandoc
    print("\n📚 Trying Pandoc conversion...")
    pandoc_success = create_pdf_with_pandoc(adr_file, output_dir)
    
    # Summary
    print("\n" + "="*60)
    print("📋 EXPORT SUMMARY")
    print("="*60)
    print(f"✅ Individual diagrams: {len(created_images)} images created")
    print(f"✅ HTML version: {html_file}")
    print(f"{'✅' if html_to_pdf_success else '❌'} HTML to PDF: {'Success' if html_to_pdf_success else 'Failed'}")
    print(f"{'✅' if pandoc_success else '❌'} Pandoc PDF: {'Success' if pandoc_success else 'Failed'}")
    
    print(f"\n📁 All files saved to: {output_dir}")
    
    # Open output directory
    try:
        subprocess.run(['open', str(output_dir)], check=True)
        print("📂 Output directory opened in Finder")
    except:
        pass

if __name__ == "__main__":
    main()