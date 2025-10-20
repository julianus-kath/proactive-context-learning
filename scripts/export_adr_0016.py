#!/usr/bin/env python3
"""
Export script for ADR-0016 diagrams and documentation.
Generates PNG diagrams from Mermaid code and creates HTML/PDF exports.

Usage:
  python3 export_adr_0016.py [--format pdf|html|png|all]
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import re

# Configuration
REPO_ROOT = Path("/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code")
ADR_FILE = REPO_ROOT / "adrs" / "0016-phase-7-complete-architecture-with-scout-and-semantic-ranking.md"
EXPORT_DIR = REPO_ROOT / "exports"
DIAGRAMS_DIR = EXPORT_DIR / "diagrams" / "adr_0016"
LOG_FILE = EXPORT_DIR / "export_log.txt"

# Diagram names (extracted from markdown)
DIAGRAMS = {
    "01_system_overview": "High-Level System Architecture (Phase 7+)",
    "02_scout_mode_lifecycle": "Scout Mode Architecture & Lifecycle",
    "03_answer_first_pipeline": "Answer-First Pipeline with Semantic Ranking",
    "04_mcp_data_access": "MCP-Only Data Access Architecture",
    "05_complete_query_flow": "Complete Query Execution Flow",
    "06_proxy_vpm_architecture": "Windows Proxy VPN Architecture",
    "07_component_responsibilities": "Component Responsibilities",
    "08_scout_cache_lifecycle": "Scout Mode Cache Lifecycle",
    "09_performance_characteristics": "Performance Characteristics",
    "10_error_handling": "Error Handling & Recovery",
    "11_observability_logging": "Observability & Debug Logging",
    "12_deployment_architecture": "Deployment Architecture",
}

class ADRExporter:
    """Export ADR-0016 diagrams and documentation."""
    
    def __init__(self):
        self.diagrams_dir = DIAGRAMS_DIR
        self.export_dir = EXPORT_DIR
        self.adr_file = ADR_FILE
        self.log_messages = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {level}: {message}"
        print(full_msg)
        self.log_messages.append(full_msg)
    
    def extract_mermaid_diagrams(self) -> dict:
        """Extract all mermaid code blocks from ADR."""
        if not self.adr_file.exists():
            self.log(f"ADR file not found: {self.adr_file}", "ERROR")
            return {}
        
        with open(self.adr_file, 'r') as f:
            content = f.read()
        
        # Find all mermaid code blocks
        pattern = r'```mermaid\n(.*?)\n```'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        diagrams = {}
        for i, match in enumerate(matches, 1):
            mermaid_code = match.group(1)
            key = f"{i:02d}"
            diagrams[key] = mermaid_code
        
        self.log(f"Extracted {len(diagrams)} mermaid diagrams from ADR")
        return diagrams
    
    def create_directories(self):
        """Create export directories."""
        self.diagrams_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"Created directories: {self.diagrams_dir}")
    
    def export_diagrams_to_png(self, diagrams: dict):
        """Export mermaid diagrams to PNG using mermaid CLI."""
        if not diagrams:
            self.log("No diagrams to export", "WARN")
            return
        
        # Check if mermaid-cli is installed
        try:
            subprocess.run(["mmdc", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("mermaid-cli (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli", "WARN")
            self.log("Skipping PNG export", "WARN")
            return
        
        for key, mermaid_code in diagrams.items():
            # Get diagram name
            diagram_num = int(key)
            diagram_names = list(DIAGRAMS.keys())
            diagram_name = diagram_names[diagram_num - 1] if diagram_num <= len(diagram_names) else f"diagram_{key}"
            
            # Create temp file
            temp_mmd = self.diagrams_dir / f"temp_{key}.mmd"
            output_png = self.diagrams_dir / f"{diagram_name}.png"
            
            try:
                # Write mermaid code to temp file
                with open(temp_mmd, 'w') as f:
                    f.write(mermaid_code)
                
                # Convert to PNG
                cmd = [
                    "mmdc",
                    "-i", str(temp_mmd),
                    "-o", str(output_png),
                    "-s", "3",  # 3x scale for high quality
                    "--backgroundColor", "white",
                ]
                
                subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                self.log(f"✓ Exported: {output_png.name}")
                
                # Clean up temp file
                temp_mmd.unlink()
                
            except subprocess.TimeoutExpired:
                self.log(f"✗ Timeout exporting {diagram_name}", "ERROR")
            except Exception as e:
                self.log(f"✗ Error exporting {diagram_name}: {e}", "ERROR")
    
    def create_html_export(self, diagrams: dict):
        """Create HTML export with embedded diagrams."""
        html_file = self.export_dir / "ADR-0016-Architecture.html"
        
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADR-0016: Phase 7+ Complete Architecture</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        header h1 { font-size: 2.5em; margin-bottom: 10px; }
        header p { font-size: 1.1em; opacity: 0.9; }
        
        main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .toc {
            background: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .toc h2 { margin-bottom: 20px; color: #667eea; }
        
        .toc ul {
            list-style: none;
            columns: 2;
            gap: 20px;
        }
        
        .toc li {
            margin-bottom: 10px;
        }
        
        .toc a {
            color: #667eea;
            text-decoration: none;
            transition: color 0.3s;
        }
        
        .toc a:hover { color: #764ba2; }
        
        .section {
            background: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .section h2 {
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        
        .section h3 {
            color: #764ba2;
            margin-top: 20px;
            margin-bottom: 15px;
        }
        
        .diagram-container {
            background: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
            overflow-x: auto;
        }
        
        .diagram-container img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .diagram-description {
            color: #666;
            font-style: italic;
            margin-top: 10px;
            font-size: 0.95em;
        }
        
        code {
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', monospace;
        }
        
        pre {
            background: #f5f5f5;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            overflow-x: auto;
            margin: 15px 0;
        }
        
        pre code {
            background: none;
            padding: 0;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        
        table th, table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        
        table th {
            background: #667eea;
            color: white;
        }
        
        table tr:nth-child(even) {
            background: #f9f9f9;
        }
        
        .metrics-table {
            font-size: 0.95em;
        }
        
        .metrics-table strong {
            color: #2e7d32;
        }
        
        footer {
            background: #333;
            color: #999;
            text-align: center;
            padding: 20px;
            margin-top: 40px;
        }
        
        .nav-top {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #667eea;
            color: white;
            padding: 10px 15px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 0.9em;
            transition: background 0.3s;
            z-index: 1000;
        }
        
        .nav-top:hover { background: #764ba2; }
        
        @media (max-width: 768px) {
            header h1 { font-size: 1.8em; }
            .toc ul { columns: 1; }
            .section { padding: 20px; }
        }
    </style>
</head>
<body>
    <header>
        <h1>🏗️ ADR-0016: Phase 7+ Complete Architecture</h1>
        <p>Scout Mode, Semantic Ranking, MCP-Only Data Access</p>
    </header>
    
    <main>
        <section class="toc">
            <h2>📋 Contents</h2>
            <ul>
"""
        
        for i, (key, title) in enumerate(DIAGRAMS.items(), 1):
            html_content += f'                <li><a href="#{i}">{i}. {title}</a></li>\n'
        
        html_content += """            </ul>
        </section>
"""
        
        # Add sections for each diagram
        section_descriptions = {
            "01": "Complete system architecture for Phase 7+, showing all major components and data flow.",
            "02": "Scout Mode startup sequence, cache lifecycle, and semantic metadata pre-computation.",
            "03": "Answer-first pipeline: intent parsing, table ranking, blueprint generation, and execution.",
            "04": "Unified MCP-only data access layer eliminating dual interfaces.",
            "05": "Complete query execution sequence from user input to response.",
            "06": "Windows proxy architecture for secure VPN-tunneled production database access.",
            "07": "Responsibility breakdown across all system components.",
            "08": "Scout Mode cache states, lifecycle, and TTL management.",
            "09": "Performance improvements across phases 6, 7, and 7.1.",
            "10": "Error detection, recovery strategies, and user communication.",
            "11": "Comprehensive observability system with real-time debug logging.",
            "12": "Development and production deployment architectures.",
        }
        
        i = 1
        for key, (diagram_name, diagram_title) in enumerate(DIAGRAMS.items(), 1):
            description = section_descriptions.get(key, "")
            
            html_content += f"""        <section class="section" id="{i}">
            <h2>{i}. {diagram_title}</h2>
            <p>{description}</p>
            <div class="diagram-container">
                <div style="color: #999; padding: 40px; font-size: 0.9em;">
                    📊 Diagram: {diagram_name}.png<br>
                    <small>(See exports/diagrams/adr_0016/ for high-resolution PNG)</small>
                </div>
            </div>
        </section>
"""
            i += 1
        
        html_content += """
        <section class="section">
            <h2>📈 Key Metrics</h2>
            <table class="metrics-table">
                <tr>
                    <th>Operation</th>
                    <th>Phase 6</th>
                    <th>Phase 7</th>
                    <th>Phase 7.1</th>
                    <th>Improvement</th>
                </tr>
                <tr>
                    <td><strong>Schema Discovery</strong></td>
                    <td>10-50s</td>
                    <td>10-50s</td>
                    <td>50ms</td>
                    <td><strong>200-1000x</strong></td>
                </tr>
                <tr>
                    <td><strong>Entity Ranking</strong></td>
                    <td>N/A</td>
                    <td>2-5s</td>
                    <td>50-100ms</td>
                    <td><strong>20-100x</strong></td>
                </tr>
                <tr>
                    <td><strong>Total Query Time</strong></td>
                    <td>17-65s</td>
                    <td>16-62s</td>
                    <td>&lt;500ms</td>
                    <td><strong>40-130x</strong></td>
                </tr>
            </table>
        </section>
        
        <section class="section">
            <h2>🔗 Architecture Decisions</h2>
            <h3>Scout Mode Cache (ADR-0014)</h3>
            <p>Pre-computes and caches semantic metadata on startup, enabling O(1) table discovery instead of O(n) database queries.</p>
            
            <h3>MCP-Only Data Access (ADR-0012)</h3>
            <p>Single unified interface through MCP Server, eliminating dual code paths and maintenance burden.</p>
            
            <h3>Semantic Table Ranking (ADR-0015)</h3>
            <p>Multi-dimensional scoring combining entity matching, type compatibility, fuzzy matching, and connectivity analysis.</p>
            
            <h3>Answer-First Pipeline (Phase 7)</h3>
            <p>Autonomous query generation and execution before interactive clarification, enabling sub-second response times.</p>
        </section>
        
        <section class="section">
            <h2>🚀 Performance Characteristics</h2>
            <pre>Phase 6 (Interactive - 17-65s):
  └─ Schema Discovery: 10-50s ⚠️ BOTTLENECK
  └─ LLM Processing: 5-10s
  └─ Query Execution: 2-5s

Phase 7.1 (Answer-First - <500ms):
  └─ Cache Load: 50ms ✓ FAST
  └─ Table Ranking: 50-100ms ✓ FAST
  └─ LLM Processing: 2-3s
  └─ Query Execution: 1-2s
  └─ Response Format: ~100ms</pre>
        </section>
        
        <section class="section">
            <h2>📚 Related Documents</h2>
            <ul>
                <li><strong>ADR-0012:</strong> MCP-Only Architecture Migration</li>
                <li><strong>ADR-0014:</strong> Scout Mode Semantic Caching</li>
                <li><strong>ADR-0015:</strong> Semantic Table Ranking for Autonomous Query Execution</li>
                <li><strong>Phase 7 Documentation:</strong> Answer-First Pipeline Implementation</li>
                <li><strong>Phase 7.1 Documentation:</strong> Scout Mode Integration</li>
            </ul>
        </section>
        
        <footer>
            <p>Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            <p>Source: ADR-0016 Phase 7+ Complete Architecture with Scout Mode and Semantic Ranking</p>
            <p>For diagrams, see: exports/diagrams/adr_0016/</p>
        </footer>
    </main>
    
    <a href="#" class="nav-top">↑ Top</a>
</body>
</html>
"""
        
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        self.log(f"✓ Created HTML export: {html_file}")
        return html_file
    
    def save_log(self):
        """Save export log to file."""
        with open(LOG_FILE, 'a') as f:
            f.write("\n".join(self.log_messages) + "\n\n")
        
        self.log(f"Log saved to: {LOG_FILE}")
    
    def run_export(self, formats: list = None):
        """Run the export process."""
        if formats is None:
            formats = ["html", "png"]
        
        self.log("=" * 60)
        self.log(f"ADR-0016 Export Started")
        self.log(f"Formats: {', '.join(formats)}")
        self.log("=" * 60)
        
        try:
            self.create_directories()
            diagrams = self.extract_mermaid_diagrams()
            
            if "png" in formats or "all" in formats:
                self.log("Exporting diagrams to PNG...")
                self.export_diagrams_to_png(diagrams)
            
            if "html" in formats or "all" in formats:
                self.log("Exporting to HTML...")
                self.create_html_export(diagrams)
            
            self.log("=" * 60)
            self.log("✓ Export completed successfully!")
            self.log("=" * 60)
            
        except Exception as e:
            self.log(f"✗ Export failed: {e}", "ERROR")
            raise
        finally:
            self.save_log()


def main():
    """Main entry point."""
    formats = ["png", "html"]  # Default
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("--format="):
            format_str = arg.split("=")[1]
            if format_str == "all":
                formats = ["png", "html"]
            else:
                formats = format_str.split("|")
    
    exporter = ADRExporter()
    exporter.run_export(formats)


if __name__ == "__main__":
    main()