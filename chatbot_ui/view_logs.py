#!/usr/bin/env python3
"""
Chat Log Viewer
Simple script to view and analyze chat logs from the Streamlit app
"""

import json
import os
import sys
from datetime import datetime
import pandas as pd

def load_logs(log_file="chat_logs.json"):
    """Load chat logs from JSON file."""
    log_path = os.path.join(os.path.dirname(__file__), log_file)
    
    if not os.path.exists(log_path):
        print(f"❌ Log file not found: {log_path}")
        print("💡 Start using the Streamlit app to generate logs!")
        return []
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        print(f"✅ Loaded {len(logs)} chat interactions from {log_path}")
        return logs
    except Exception as e:
        print(f"❌ Error loading logs: {e}")
        return []

def display_logs(logs, limit=None):
    """Display chat logs in a readable format."""
    if not logs:
        print("📝 No logs to display")
        return
    
    print("\n" + "="*80)
    print("📋 CHAT LOGS")
    print("="*80)
    
    # Sort by timestamp (newest first)
    sorted_logs = sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)
    
    if limit:
        sorted_logs = sorted_logs[:limit]
        print(f"Showing latest {limit} interactions:")
    
    for i, log in enumerate(sorted_logs, 1):
        timestamp = log.get('timestamp', 'Unknown')
        session_id = log.get('session_id', 'Unknown')
        user_input = log.get('user_input', 'No input')
        bot_response = log.get('bot_response', 'No response')
        
        # Parse timestamp for better display
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            formatted_time = timestamp
        
        print(f"\n📅 {i}. {formatted_time} | Session: {session_id}")
        print("-" * 80)
        print(f"👤 USER: {user_input}")
        print(f"🤖 BOT:  {bot_response[:200]}{'...' if len(bot_response) > 200 else ''}")

def analyze_logs(logs):
    """Provide basic analytics on the chat logs."""
    if not logs:
        print("📊 No logs to analyze")
        return
    
    print("\n" + "="*80)
    print("📊 LOG ANALYTICS")
    print("="*80)
    
    # Basic stats
    total_interactions = len(logs)
    unique_sessions = len(set(log.get('session_id', 'unknown') for log in logs))
    
    print(f"📈 Total Interactions: {total_interactions}")
    print(f"👥 Unique Sessions: {unique_sessions}")
    print(f"💬 Avg Interactions per Session: {total_interactions/unique_sessions:.1f}")
    
    # Time analysis
    timestamps = [log.get('timestamp') for log in logs if log.get('timestamp')]
    if timestamps:
        try:
            dates = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in timestamps]
            earliest = min(dates)
            latest = max(dates)
            print(f"📅 Time Range: {earliest.strftime('%Y-%m-%d %H:%M')} to {latest.strftime('%Y-%m-%d %H:%M')}")
        except:
            print("📅 Time Range: Unable to parse timestamps")
    
    # Most common queries (first 10 words)
    user_inputs = [log.get('user_input', '') for log in logs]
    query_starts = [' '.join(query.split()[:3]).lower() for query in user_inputs if query]
    
    if query_starts:
        from collections import Counter
        common_queries = Counter(query_starts).most_common(5)
        print(f"\n🔍 Most Common Query Patterns:")
        for pattern, count in common_queries:
            print(f"   '{pattern}...' - {count} times")

def export_to_csv(logs, filename=None):
    """Export logs to CSV format."""
    if not logs:
        print("📝 No logs to export")
        return
    
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"chat_logs_export_{timestamp}.csv"
    
    try:
        df = pd.DataFrame(logs)
        df.to_csv(filename, index=False)
        print(f"✅ Logs exported to {filename}")
    except Exception as e:
        print(f"❌ Error exporting to CSV: {e}")

def main():
    """Main function."""
    print("🔍 Chat Log Viewer")
    print("=" * 50)
    
    # Load logs
    logs = load_logs()
    
    if not logs:
        return
    
    # Interactive menu
    while True:
        print("\n📋 What would you like to do?")
        print("1. View latest 10 interactions")
        print("2. View all interactions")
        print("3. Show analytics")
        print("4. Export to CSV")
        print("5. Search logs")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            display_logs(logs, limit=10)
        elif choice == '2':
            display_logs(logs)
        elif choice == '3':
            analyze_logs(logs)
        elif choice == '4':
            export_to_csv(logs)
        elif choice == '5':
            search_term = input("Enter search term: ").strip().lower()
            if search_term:
                filtered_logs = [
                    log for log in logs 
                    if search_term in log.get('user_input', '').lower() 
                    or search_term in log.get('bot_response', '').lower()
                ]
                print(f"\n🔍 Found {len(filtered_logs)} interactions containing '{search_term}':")
                display_logs(filtered_logs)
        elif choice == '6':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")