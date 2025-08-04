#!/bin/bash

# Test script for the n8n webhook
# This simulates what the chatbot interface will do

echo "Testing n8n webhook..."

# The webhook URL
WEBHOOK_URL="http://localhost:5678/webhook-test/37694deb-f310-4a1e-b198-aaff97f28e8d"

# The query to send
QUERY="Show me the top 5 customers by total sales amount"

# Send the request
echo "Sending query: '$QUERY'"
echo ""

curl -X POST \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$QUERY\"}" \
  $WEBHOOK_URL

echo ""
echo ""
echo "If you see a JSON response with 'result' field, the webhook is working correctly!"
echo "If you see an error or no response, check that n8n is running and the workflow is active."