#!/usr/bin/env python
"""
Simple HTTP server for the frontend.
"""
import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    # Change to the directory containing this script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8080)