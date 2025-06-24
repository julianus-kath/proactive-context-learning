"""
Test script for OpenAI client initialization.
"""
import os
from openai import OpenAI

# Set the API key
api_key = "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"
os.environ["OPENAI_API_KEY"] = api_key

try:
    # Try to create the client
    client = OpenAI()
    print("Successfully created OpenAI client")
    
    # Try to make a simple API call
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello, world!"}]
    )
    print("Successfully made API call")
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"Error: {str(e)}")