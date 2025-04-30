#!/usr/bin/env python
"""
Simple HTTP server for the frontend.
"""
import os
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver


class CORSRequestHandler(SimpleHTTPRequestHandler):
    """
    Request handler with CORS support.
    """
    
    def end_headers(self):
        """Add CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests."""
        self.send_response(200)
        self.end_headers()


def run(host="localhost", port=8080):
    """
    Run the server.
    
    Args:
        host: Host to bind to
        port: Port to listen on
    """
    # Change to the directory containing this script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Create the server
    handler = CORSRequestHandler
    httpd = socketserver.TCPServer((host, port), handler)
    
    print(f"Serving frontend at http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Frontend server")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    
    args = parser.parse_args()
    run(args.host, args.port)