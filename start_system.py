#!/usr/bin/env python3
"""
Multi-Platform System Startup Launcher
Phase 7: Multi-Agent Orchestrator Ready

Starts the complete ERP Assistant system on macOS or Windows:
  - macOS: LangGraph service (port 5001) + Web UI (port 3000)
  - Windows: MCP Server (port 8000) with Scout Catalog

Usage:
    # macOS - start all services
    python start_system.py mac --all
    
    # macOS - start only LangGraph
    python start_system.py mac --langgraph
    
    # Windows - start MCP server
    python start_system.py windows
    
    # Check system status
    python start_system.py status
"""

import os
import sys
import platform
import subprocess
import time
import argparse
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Color codes for terminal output
class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color


def print_header(title: str, subtitle: str = ""):
    """Print a formatted header."""
    print()
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}{title:^60}{Colors.NC}")
    if subtitle:
        print(f"{Colors.BLUE}{subtitle:^60}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    print()


def print_success(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {message}{Colors.NC}")


def print_error(message: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {message}{Colors.NC}")


def print_warning(message: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.NC}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.NC}")


class SystemChecker:
    """Check system prerequisites and configuration."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.os_type = platform.system()
        
    def check_python(self) -> bool:
        """Check if Python 3.8+ is available."""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            print_error(f"Python 3.8+ required (found {version.major}.{version.minor})")
            return False
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    
    def check_env_file(self) -> bool:
        """Check if .env file exists."""
        env_path = self.project_root / ".env"
        if not env_path.exists():
            print_warning(".env file not found")
            print_info("Copy from .env.mac or .env.windows template and configure")
            return False
        print_success(".env file found")
        return True
    
    def check_directories(self) -> bool:
        """Check if required directories exist."""
        required_dirs = [
            "langgraph_integration",
            "mcp_server",
            "chatbot_ui",
            "tests"
        ]
        
        all_exist = True
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                print_success(f"Directory found: {dir_name}/")
            else:
                print_error(f"Directory missing: {dir_name}/")
                all_exist = False
        
        return all_exist
    
    def check_orchestrator(self) -> bool:
        """Check if multi-agent orchestrator exists."""
        orch_path = self.project_root / "langgraph_integration" / "orchestrator.py"
        if orch_path.exists():
            print_success("Multi-Agent Orchestrator found")
            return True
        print_error("Multi-Agent Orchestrator not found")
        print_info("Expected: langgraph_integration/orchestrator.py")
        return False
    
    def check_port(self, port: int) -> bool:
        """Check if a port is in use."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    
    def run_all_checks(self, check_env: bool = True) -> bool:
        """Run all system checks."""
        print_header("System Checks", f"Platform: {self.os_type}")
        
        checks = [
            ("Python version", self.check_python),
            ("Required directories", self.check_directories),
            ("Multi-Agent Orchestrator", self.check_orchestrator),
        ]
        
        if check_env:
            checks.insert(1, (".env configuration", self.check_env_file))
        
        all_pass = True
        for check_name, check_func in checks:
            try:
                if not check_func():
                    all_pass = False
            except Exception as e:
                print_error(f"{check_name}: {e}")
                all_pass = False
        
        return all_pass


class ServiceChecker:
    """Check if services are running and responsive."""
    
    @staticmethod
    def check_url(url: str, timeout: int = 5) -> bool:
        """Check if a URL is responding."""
        try:
            response = urllib.request.urlopen(url, timeout=timeout)
            return response.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            return False
    
    @staticmethod
    def get_url_json(url: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Fetch JSON from a URL."""
        try:
            response = urllib.request.urlopen(url, timeout=timeout)
            data = json.loads(response.read().decode())
            return data
        except Exception:
            return None


class MacStartup:
    """macOS service startup manager."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.script_path = project_root / "start_all_services_mac.sh"
    
    def run(self, services: str = "all"):
        """Start macOS services."""
        if not self.script_path.exists():
            print_error(f"Script not found: {self.script_path}")
            return False
        
        # Make script executable
        os.chmod(self.script_path, 0o755)
        
        print_header("Starting macOS Services", f"Mode: {services}")
        
        try:
            subprocess.run([str(self.script_path)], check=False)
            return True
        except Exception as e:
            print_error(f"Failed to start services: {e}")
            return False


class WindowsStartup:
    """Windows service startup manager."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.bat_path = project_root / "vpn_config" / "start_mcp_server_windows.bat"
        self.ps1_path = project_root / "vpn_config" / "start_mcp_server_windows.ps1"
    
    def run(self, use_powershell: bool = False):
        """Start Windows MCP server."""
        if use_powershell:
            return self._run_powershell()
        else:
            return self._run_batch()
    
    def _run_batch(self) -> bool:
        """Run Windows batch file."""
        if not self.bat_path.exists():
            print_error(f"Batch file not found: {self.bat_path}")
            return False
        
        print_header("Starting Windows MCP Server", "Using batch file")
        
        try:
            subprocess.run([str(self.bat_path)], check=False)
            return True
        except Exception as e:
            print_error(f"Failed to start MCP server: {e}")
            return False
    
    def _run_powershell(self) -> bool:
        """Run Windows PowerShell file."""
        if not self.ps1_path.exists():
            print_error(f"PowerShell file not found: {self.ps1_path}")
            return False
        
        print_header("Starting Windows MCP Server", "Using PowerShell")
        
        try:
            cmd = [
                "powershell",
                "-ExecutionPolicy", "Bypass",
                "-File", str(self.ps1_path)
            ]
            subprocess.run(cmd, check=False)
            return True
        except Exception as e:
            print_error(f"Failed to start MCP server: {e}")
            return False


class StatusChecker:
    """Check status of running services."""
    
    @staticmethod
    def check_all():
        """Check all service endpoints."""
        print_header("System Status Check")
        
        services = {
            "Web UI": "http://localhost:3000",
            "LangGraph Service": "http://localhost:5001/health",
            "MCP Server": "http://localhost:8000/health",
        }
        
        print()
        for name, url in services.items():
            if ServiceChecker.check_url(url):
                print_success(f"{name:20} {url}")
            else:
                print_warning(f"{name:20} (not responding)")
        
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Platform ERP Assistant System Launcher (Phase 7)"
    )
    
    parser.add_argument(
        "command",
        choices=["mac", "windows", "status", "check"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Start all services (macOS only)"
    )
    
    parser.add_argument(
        "--langgraph",
        action="store_true",
        help="Start only LangGraph service (macOS only)"
    )
    
    parser.add_argument(
        "--powershell",
        action="store_true",
        help="Use PowerShell instead of batch (Windows only)"
    )
    
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip system checks"
    )
    
    args = parser.parse_args()
    
    # Resolve project root
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir
    
    if args.command in ["mac", "windows"]:
        # Run system checks
        if not args.no_check:
            checker = SystemChecker(project_root)
            if not checker.run_all_checks():
                print_error("System check failed. Use --no-check to skip.")
                sys.exit(1)
        
        if args.command == "mac":
            startup = MacStartup(project_root)
            if not startup.run("all" if args.all else "langgraph"):
                sys.exit(1)
        
        elif args.command == "windows":
            startup = WindowsStartup(project_root)
            if not startup.run(use_powershell=args.powershell):
                sys.exit(1)
    
    elif args.command == "status":
        StatusChecker.check_all()
    
    elif args.command == "check":
        checker = SystemChecker(project_root)
        if not checker.run_all_checks(check_env=not args.no_check):
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_warning("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal error: {e}")
        sys.exit(1)