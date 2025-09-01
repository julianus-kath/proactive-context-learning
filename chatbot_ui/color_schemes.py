"""
Color Schemes for ERP Chatbot UI
Copy any of these color schemes into the COLORS dictionary in app.py
"""

# Original Blue Theme (Current)
BLUE_THEME = {
    'primary': '#1f77b4',      # Blue
    'secondary': '#ff7f0e',    # Orange
    'success': '#2e7d32',      # Green
    'error': '#c62828',        # Red
    'warning': '#f57c00',      # Orange
    'user_bg': '#e3f2fd',      # Light blue
    'bot_bg': '#f5f5f5',       # Light gray
    'success_bg': '#e8f5e8',   # Light green
    'error_bg': '#ffebee',     # Light red
    'text_dark': '#333333',    # Dark text
    'text_light': '#00000',   # Light text
}

# Professional Dark Blue Theme
PROFESSIONAL_THEME = {
    'primary': '#2c3e50',      # Dark blue-gray
    'secondary': '#3498db',    # Bright blue
    'success': '#27ae60',      # Green
    'error': '#e74c3c',        # Red
    'warning': '#f39c12',      # Orange
    'user_bg': '#ecf0f1',      # Very light gray
    'bot_bg': '#bdc3c7',       # Light gray
    'success_bg': '#d5f4e6',   # Light green
    'error_bg': '#fadbd8',     # Light red
    'text_dark': '#2c3e50',    # Dark blue-gray
    'text_light': '#7f8c8d',   # Medium gray
}

# Modern Purple Theme
PURPLE_THEME = {
    'primary': '#9b59b6',      # Purple
    'secondary': '#e74c3c',    # Red accent
    'success': '#2ecc71',      # Green
    'error': '#e74c3c',        # Red
    'warning': '#f39c12',      # Orange
    'user_bg': '#f4ecf7',      # Light purple
    'bot_bg': '#f8f9fa',       # Very light gray
    'success_bg': '#d5f4e6',   # Light green
    'error_bg': '#fadbd8',     # Light red
    'text_dark': '#2c3e50',    # Dark
    'text_light': '#6c757d',   # Gray
}

# Green Nature Theme
GREEN_THEME = {
    'primary': '#27ae60',      # Green
    'secondary': '#f39c12',    # Orange
    'success': '#2ecc71',      # Bright green
    'error': '#e74c3c',        # Red
    'warning': '#f39c12',      # Orange
    'user_bg': '#d5f4e6',      # Light green
    'bot_bg': '#f8f9fa',       # Light gray
    'success_bg': '#d1f2eb',   # Very light green
    'error_bg': '#fadbd8',     # Light red
    'text_dark': '#1e3a2e',    # Dark green
    'text_light': '#5d6d5b',   # Medium green-gray
}

# Corporate Red Theme
CORPORATE_THEME = {
    'primary': '#dc3545',      # Corporate red
    'secondary': '#6c757d',    # Gray
    'success': '#28a745',      # Green
    'error': '#dc3545',        # Red
    'warning': '#ffc107',      # Yellow
    'user_bg': '#f8d7da',      # Light red
    'bot_bg': '#f8f9fa',       # Light gray
    'success_bg': '#d4edda',   # Light green
    'error_bg': '#f8d7da',     # Light red
    'text_dark': '#212529',    # Dark
    'text_light': '#6c757d',   # Gray
}

# Ocean Blue Theme
OCEAN_THEME = {
    'primary': '#0077be',      # Ocean blue
    'secondary': '#00a8cc',    # Cyan
    'success': '#00c851',      # Green
    'error': '#ff4444',        # Red
    'warning': '#ffbb33',      # Amber
    'user_bg': '#e1f5fe',      # Very light blue
    'bot_bg': '#f5f5f5',       # Light gray
    'success_bg': '#e8f5e8',   # Light green
    'error_bg': '#ffebee',     # Light red
    'text_dark': '#263238',    # Dark blue-gray
    'text_light': '#607d8b',   # Blue-gray
}

# Dark Mode Theme
DARK_THEME = {
    'primary': '#bb86fc',      # Purple
    'secondary': '#03dac6',    # Teal
    'success': '#4caf50',      # Green
    'error': '#cf6679',        # Pink-red
    'warning': '#ff9800',      # Orange
    'user_bg': '#3700b3',      # Dark purple
    'bot_bg': '#1e1e1e',       # Dark gray
    'success_bg': '#1b5e20',   # Dark green
    'error_bg': '#b71c1c',     # Dark red
    'text_dark': '#ffffff',    # White text
    'text_light': '#b0b0b0',   # Light gray text
}

# Instructions for use:
"""
To use any of these themes:

1. Open chatbot_ui/app.py
2. Find the COLORS dictionary (around line 30)
3. Replace the entire COLORS dictionary with one of the themes above

Example:
# Replace this:
COLORS = {
    'primary': '#1f77b4',
    # ... rest of current colors
}

# With this (for purple theme):
COLORS = {
    'primary': '#9b59b6',
    'secondary': '#e74c3c',
    'success': '#2ecc71',
    'error': '#e74c3c',
    'warning': '#f39c12',
    'user_bg': '#f4ecf7',
    'bot_bg': '#f8f9fa',
    'success_bg': '#d5f4e6',
    'error_bg': '#fadbd8',
    'text_dark': '#2c3e50',
    'text_light': '#6c757d',
}
"""