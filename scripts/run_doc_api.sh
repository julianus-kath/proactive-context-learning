#!/bin/bash
# Script to run the document store API

# Install required packages
pip install motor pymongo

# Run the document store API
python -m crawling_agent.api.doc_api --host 0.0.0.0 --port 8002