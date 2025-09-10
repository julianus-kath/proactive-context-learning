"""
ERP Chatbot UI - Phase 3 Blueprint Implementation
A user-friendly Streamlit interface for querying the ERP database through LangGraph.

🚀 NEW: Modern Web UI Available!
For a better experience, try the new web interface:
- Run: python start_web_ui.py
- Open: http://localhost:3000
- Features: Responsive design, conversation history, modern UI

This Streamlit version is kept for compatibility.
"""

import os
import requests
import streamlit as st
from dotenv import load_dotenv
import time
import json
import datetime
from typing import List, Tuple

# Load environment variables
load_dotenv()

# Configuration
LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:5001")
API_KEY = os.getenv("API_KEY", "supersecretapikey")

# Page configuration
st.set_page_config(
    page_title="ERP Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
# Color scheme configuration - easily customizable
COLORS = {
    'primary': '#1f77b4',      # Main blue color
    'secondary': '#ff7f0e',    # Orange accent
    'success': '#2e7d32',      # Green for success messages
    'error': '#c62828',        # Red for error messages
    'warning': '#f57c00',      # Orange for warnings
    'user_bg': '#e3f2fd',      # Light blue for user messages
    'bot_bg': '#f5f5f5',       # Light gray for bot messages
    'success_bg': '#e8f5e8',   # Light green background
    'error_bg': '#ffebee',     # Light red background
    'text_dark': '#333333',    # Dark text
    'text_light': '#666666',   # Light text
}

st.markdown(f"""
<style>
    /* Main application styling */
    .main-header {{
        text-align: center;
        color: {COLORS['primary']};
        margin-bottom: 2rem;
        font-weight: 600;
    }}
    
    /* Chat message styling */
    .chat-message {{
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 15px;
        max-width: 80%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        animation: fadeIn 0.3s ease-in;
    }}
    
    .user-message {{
        background: linear-gradient(135deg, {COLORS['user_bg']}, #bbdefb);
        margin-left: auto;
        text-align: right;
        border: 1px solid {COLORS['primary']}33;
    }}
    
    .bot-message {{
        background: linear-gradient(135deg, {COLORS['bot_bg']}, #eeeeee);
        margin-right: auto;
        border: 1px solid #ddd;
    }}
    
    /* Status message styling */
    .error-message {{
        background-color: {COLORS['error_bg']};
        color: {COLORS['error']};
        border-left: 4px solid {COLORS['error']};
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    
    .success-message {{
        background-color: {COLORS['success_bg']};
        color: {COLORS['success']};
        border-left: 4px solid {COLORS['success']};
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    
    /* Input styling */
    .stTextInput > div > div > input {{
        font-size: 16px;
        border-radius: 10px;
        border: 2px solid {COLORS['primary']}33;
        transition: border-color 0.3s ease;
    }}
    
    .stTextInput > div > div > input:focus {{
        border-color: {COLORS['primary']};
        box-shadow: 0 0 0 2px {COLORS['primary']}22;
    }}
    
    /* Button styling */
    .stButton > button {{
        background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['secondary']});
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s ease;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }}
    
    /* Sidebar styling */
    .css-1d391kg {{
        background-color: #fafafa;
    }}
    
    /* Animation */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    /* Expander styling */
    .streamlit-expanderHeader {{
        background-color: {COLORS['primary']}11;
        border-radius: 8px;
    }}
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables."""
    if "history" not in st.session_state:
        st.session_state.history = []  # Keep for display: [(user_msg, bot_msg), ...]
    if "messages" not in st.session_state:
        st.session_state.messages = []  # New: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    if "loading" not in st.session_state:
        st.session_state.loading = False
    if "last_was_clarification" not in st.session_state:
        st.session_state.last_was_clarification = False  # Track if last response was a clarification

def log_chat_interaction(user_input: str, bot_response: str, log_file: str = "chat_logs.json"):
    """
    Log chat interactions to a JSON file for persistence and analysis.
    
    Args:
        user_input: The user's question
        bot_response: The bot's response
        log_file: Path to the log file
    """
    try:
        # Create log entry
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_input": user_input,
            "bot_response": bot_response,
            "session_id": st.session_state.get("session_id", "unknown")
        }
        
        # Read existing logs
        log_path = os.path.join(os.path.dirname(__file__), log_file)
        logs = []
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logs = []
        
        # Append new log
        logs.append(log_entry)
        
        # Write back to file
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
            
        print(f"💾 Chat logged to {log_path}")
        
    except Exception as e:
        print(f"⚠️ Failed to log chat interaction: {e}")

def get_session_id():
    """Generate or retrieve a unique session ID."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(datetime.datetime.now())) % 10000}"
    return st.session_state.session_id

def check_service_health() -> bool:
    """Check if the LangGraph service is healthy."""
    try:
        response = requests.get(f"{LANGGRAPH_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def send_conversation(user_input: str) -> str:
    """
    Send the entire conversation history to the LangGraph service.
    
    Args:
        user_input: The user's latest query
        
    Returns:
        The response from the service or an error message
    """
    try:
        # Add the new user message to the conversation
        current_messages = st.session_state.messages.copy()
        current_messages.append({"role": "user", "content": user_input})
        
        payload = {
            "messages": current_messages,
            "api_key": API_KEY
        }
        
        # Log the payload for debugging
        print(f"🔍 Sending payload to LangGraph service:")
        print(f"   Messages count: {len(current_messages)}")
        print(f"   Latest message: {current_messages[-1] if current_messages else 'None'}")
        
        response = requests.post(
            f"{LANGGRAPH_URL}/process_conversation",
            json=payload,
            timeout=60  # Allow up to 60 seconds for complex queries
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Handle different response types
            if result.get("clarify", False):
                # Return clarifying question
                return result.get("question", result.get("clarification", "I need more information to help you."))
            else:
                # Return final response
                return result.get("response", result.get("final_response", "Query executed successfully."))
            
        elif response.status_code == 401:
            return "⚠️ Authentication failed. Please check your API key."
        elif response.status_code == 400:
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = f": {error_data.get('detail', 'Invalid request format')}"
            except:
                pass
            return f"⚠️ Invalid request{error_detail}. Please check your input."
        elif response.status_code == 503:
            return "⚠️ Service temporarily unavailable. Please try again later."
        else:
            return f"⚠️ Service error (Status: {response.status_code}). Please try again."
            
    except requests.exceptions.Timeout:
        return "⚠️ Request timed out. The query might be too complex. Please try a simpler query."
    except requests.exceptions.ConnectionError:
        return "⚠️ Cannot connect to the service. Please make sure the LangGraph service is running."
    except requests.exceptions.RequestException as e:
        return f"⚠️ Something went wrong: {str(e)}"
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"

def send_conversation_with_context(user_input: str) -> dict:
    """
    Send the entire conversation history to the LangGraph service and return full response data.
    
    Args:
        user_input: The user's latest query
        
    Returns:
        Dict with full response data including messages
    """
    try:
        # Add the new user message to the conversation
        current_messages = st.session_state.messages.copy()
        current_messages.append({"role": "user", "content": user_input})
        
        payload = {
            "messages": current_messages,
            "api_key": API_KEY
        }
        
        # Log the payload for debugging
        print(f"🔍 Sending payload to LangGraph service:")
        print(f"   Messages count: {len(current_messages)}")
        print(f"   Latest message: {current_messages[-1] if current_messages else 'None'}")
        
        response = requests.post(
            f"{LANGGRAPH_URL}/process_conversation",
            json=payload,
            timeout=60  # Allow up to 60 seconds for complex queries
        )
        
        if response.status_code == 200:
            result = response.json()
            return result
        elif response.status_code == 401:
            return {"error": "Authentication failed. Please check your API key."}
        elif response.status_code == 400:
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = f": {error_data.get('detail', 'Invalid request format')}"
            except:
                pass
            return {"error": f"Invalid request{error_detail}. Please check your input."}
        elif response.status_code == 503:
            return {"error": "Service temporarily unavailable. Please try again later."}
        else:
            return {"error": f"Service error (Status: {response.status_code}). Please try again."}
            
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. The query might be too complex. Please try a simpler query."}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to the service. Please make sure the LangGraph service is running."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Something went wrong: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def display_chat_history():
    """Display the chat history."""
    if st.session_state.history:
        st.markdown("### 💬 Chat History")
        
        for i, (user_msg, bot_msg) in enumerate(st.session_state.history):
            # User message
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>You:</strong> {user_msg}
            </div>
            """, unsafe_allow_html=True)
            
            # Bot message
            st.markdown(f"""
            <div class="chat-message bot-message">
                <strong>🤖 ERP Assistant:</strong> {bot_msg}
            </div>
            """, unsafe_allow_html=True)
            
            # Add separator except for the last message
            if i < len(st.session_state.history) - 1:
                st.markdown("---")

def display_sample_queries():
    """Display sample queries for users to try."""
    with st.expander("💡 Sample Queries to Try"):
        st.markdown("""
        **Database Structure:**
        - "What tables are available in the database?"
        - "Show me the structure of the customers table"
        
        **Customer Queries:**
        - "How many customers do we have?"
        - "Show me all customers from New York"
        - "Who are our top 5 customers by total sales?"
        
        **Product Queries:**
        - "How many products do we have?"
        - "What's our top-selling product?"
        - "Show me products in the Electronics category"
        
        **Sales Analysis:**
        - "What were our total sales last month?"
        - "Show me sales trends by month"
        - "Which products have the highest profit margins?"
        
        **Inventory:**
        - "What products are low in stock?"
        - "Show me warehouse inventory levels"
        """)

def main():
    """Main application function."""
    initialize_session_state()
    get_session_id()  # Initialize session tracking
    
    # Header
    st.markdown('<h1 class="main-header">🤖 ERP Chatbot</h1>', unsafe_allow_html=True)
    st.markdown("Ask questions about your ERP data in natural language!")
    
    # New Web UI notification
    st.info("🚀 **NEW**: Try our modern web interface! Run `python start_web_ui.py` and visit http://localhost:3000 for a better experience with responsive design and conversation history.")
    
    # Service health check
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if check_service_health():
            st.markdown('<div class="success-message">✅ Service is online and ready</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="error-message">❌ Cannot connect to LangGraph service at {LANGGRAPH_URL}</div>', unsafe_allow_html=True)
            st.markdown("**Please make sure:**")
            st.markdown("- The LangGraph service is running on port 5001")
            st.markdown("- The MCP server is running on port 8000")
            st.markdown("- Your environment variables are set correctly")
            return
    
    # Main input area with context-aware messaging
    if st.session_state.get("last_was_clarification", False):
        st.markdown("### 🤔 Please Provide More Details")
        st.info("💡 The system needs additional information to answer your question accurately.")
    else:
        st.markdown("### 💭 Ask Your Question")
    
    # Use a form to handle input and submission properly
    with st.form(key="query_form", clear_on_submit=True):
        # Create columns for input and button
        col1, col2 = st.columns([4, 1])
        
        with col1:
            # Dynamic placeholder based on context
            if st.session_state.get("last_was_clarification", False):
                placeholder_text = "Please provide the additional details requested above..."
            else:
                placeholder_text = "e.g., How many customers do we have?"
                
            user_input = st.text_input(
                "Enter your question:",
                placeholder=placeholder_text,
                label_visibility="collapsed"
            )
        
        with col2:
            button_text = "Clarify" if st.session_state.get("last_was_clarification", False) else "Send"
            send_button = st.form_submit_button(button_text, type="primary", use_container_width=True)
    
    # Handle query submission
    if send_button and user_input.strip():
        st.session_state.loading = True
        
        # Show loading spinner
        with st.spinner("🤔 Processing your query..."):
            # Send conversation to service
            response_data = send_conversation_with_context(user_input.strip())
            
            if isinstance(response_data, dict):
                if "error" in response_data:
                    # Handle error response
                    response_text = f"⚠️ {response_data['error']}"
                    
                    # Update both history formats
                    st.session_state.history.append((user_input.strip(), response_text))
                    st.session_state.messages.append({"role": "user", "content": user_input.strip()})
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    
                elif "messages" in response_data:
                    # Use updated messages from server (preferred method)
                    st.session_state.messages = response_data["messages"]
                    
                    # Extract the response text and check if it's a clarification
                    if response_data.get("clarify", False):
                        # This is a clarifying question
                        response_text = f"🤔 {response_data.get('question', response_data.get('clarification', 'I need more information to help you.'))}"
                        # Mark this as a clarification in session state for UI styling
                        st.session_state.last_was_clarification = True
                    else:
                        # This is a final response
                        response_text = response_data.get("response", response_data.get("final_response", "Query executed successfully."))
                        st.session_state.last_was_clarification = False
                    
                    # Update display history
                    st.session_state.history.append((user_input.strip(), response_text))
                    
                elif response_data.get("clarify", False):
                    # Handle clarification without full messages update
                    response_text = f"🤔 {response_data.get('question', response_data.get('clarification', 'I need more information to help you.'))}"
                    
                    # Update both history formats
                    st.session_state.history.append((user_input.strip(), response_text))
                    st.session_state.messages.append({"role": "user", "content": user_input.strip()})
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    st.session_state.last_was_clarification = True
                    
                else:
                    # Handle other response data
                    response_text = response_data.get("response", response_data.get("final_response", str(response_data)))
                    
                    # Update both history formats
                    st.session_state.history.append((user_input.strip(), response_text))
                    st.session_state.messages.append({"role": "user", "content": user_input.strip()})
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    st.session_state.last_was_clarification = False
            else:
                # Fallback to old method
                response_text = str(response_data)
                
                # Update both history formats
                st.session_state.history.append((user_input.strip(), response_text))
                st.session_state.messages.append({"role": "user", "content": user_input.strip()})
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                st.session_state.last_was_clarification = False
            
            # Log the interaction
            log_chat_interaction(user_input.strip(), response_text)
        
        st.session_state.loading = False
        st.rerun()
    
    elif send_button and not user_input.strip():
        st.warning("Please enter a question before sending.")
    
    # Display chat history
    if st.session_state.history:
        st.markdown("---")
        display_chat_history()
        
        # Clear history button
        if st.button("🗑️ Clear Chat History"):
            st.session_state.history = []
            st.session_state.messages = []
            st.session_state.last_was_clarification = False
            st.rerun()
    
    # Sidebar with additional information
    with st.sidebar:
        st.markdown("### 🔧 Configuration")
        st.markdown(f"**Service URL:** {LANGGRAPH_URL}")
        st.markdown(f"**API Key:** {'✅ Set' if API_KEY else '❌ Not Set'}")
        st.markdown(f"**Session ID:** `{get_session_id()}`")
        st.markdown(f"**Context Messages:** {len(st.session_state.messages)}")
        
        # Debug: Show current messages structure
        if st.session_state.messages and st.checkbox("🔍 Show Message Debug"):
            st.json(st.session_state.messages[-2:] if len(st.session_state.messages) > 2 else st.session_state.messages)
        
        st.markdown("### 📋 Chat Logs")
        log_path = os.path.join(os.path.dirname(__file__), "chat_logs.json")
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                st.markdown(f"**Total Interactions:** {len(logs)}")
                st.markdown(f"**Log File:** `chat_logs.json`")
                if st.button("📥 Download Logs"):
                    st.download_button(
                        label="Download chat_logs.json",
                        data=json.dumps(logs, indent=2),
                        file_name=f"chat_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
            except Exception as e:
                st.markdown("⚠️ Error reading logs")
        else:
            st.markdown("📝 No logs yet - start chatting!")
        
        st.markdown("### 📊 Database Info")
        st.markdown("""
        **Available Tables:**
        - customers
        - products
        - sales
        - suppliers
        - warehouse
        - employees
        """)
        
        st.markdown("### 🆘 Need Help?")
        st.markdown("""
        **Troubleshooting:**
        1. Make sure MCP server is running
        2. Check LangGraph service is running
        3. Verify your API key is correct
        4. Try simpler queries first
        """)
    
    # Sample queries section
    display_sample_queries()
    
    # Footer
    st.markdown("---")
    st.markdown("*Powered by LangGraph, MCP, and OpenAI*")

if __name__ == "__main__":
    main()