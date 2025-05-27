#!/bin/bash
# Script to load MongoDB data from a JSON file

# Default values
INPUT_FILE=${1:-"/mongodb_data.json"}
MONGO_URI=${2:-"mongodb://localhost:27017/"}
DB_NAME=${3:-"document_store"}

echo "Loading MongoDB data from $INPUT_FILE into $MONGO_URI/$DB_NAME..."

# Check if the input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found: $INPUT_FILE"
    exit 1
fi

# Use mongoimport to load the data
for collection in product_details customer_feedback support_tickets marketing_campaigns knowledge_base; do
    echo "Loading collection: $collection"
    
    # Extract the collection data from the JSON file
    # This requires jq, which might not be available in the container
    # As a fallback, we'll use a simple approach with temporary files
    
    # Create a temporary file for the collection data
    TMP_FILE="/tmp/${collection}.json"
    
    # Extract the collection data using grep and sed
    # This is a simple approach that works for well-formatted JSON
    # It extracts data between "collection_name": [ and the next ],
    cat "$INPUT_FILE" | 
        grep -A 100000 "\"$collection\":" | 
        sed '1s/.*\[/[/' | 
        sed '/^  \]/,$d' > "$TMP_FILE"
    
    # Add closing bracket
    echo "]" >> "$TMP_FILE"
    
    # Import the data into MongoDB
    mongoimport --uri "$MONGO_URI" --db "$DB_NAME" --collection "$collection" --drop --file "$TMP_FILE" --jsonArray
    
    # Clean up
    rm "$TMP_FILE"
done

echo "MongoDB data loading completed successfully"