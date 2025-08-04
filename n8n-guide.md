# Setting Up n8n with the Data Fusion Project

This guide explains how to set up n8n as an orchestration engine for your Data Fusion project, connecting your SQLite database and agent system to a chatbot interface.

## Quick Start

1. **Stop any existing n8n instances**:

   ```bash
   # Make the stop script executable
   chmod +x stop-n8n.sh
   
   # Stop all n8n instances
   ./stop-n8n.sh
   ```

2. **Generate synthetic data and prepare the environment**:

   ```bash
   # Make the setup script executable
   chmod +x setup-n8n.sh
   
   # Run the setup script
   ./setup-n8n.sh
   ```

3. **Start the Docker containers**:

   ```bash
   docker-compose up -d
   ```

4. **Test the SQLite connection**:

   ```bash
   # Make the test script executable
   chmod +x test-sqlite.sh
   
   # Test the SQLite connection
   ./test-sqlite.sh
   ```

5. **Access n8n**:
   - Open your browser and go to: http://localhost:5678
   - Create an account or log in

6. **Access the chatbot interface**:
   - Open your browser and go to: http://localhost:8080

## Setting Up the n8n Workflow

### 1. Create a New Workflow

1. In the n8n interface, click on "Workflows" in the sidebar
2. Click the "+ Create Workflow" button
3. Give your workflow a name, e.g., "Data Fusion Chatbot"

### 2. Add a Webhook Node

1. Click the "+" button to add a node
2. Search for "Webhook" and select it
3. Configure the webhook:
   - **Authentication**: None (for simplicity)
   - **HTTP Method**: POST
   - **Path**: webhook-test/37694deb-f310-4a1e-b198-aaff97f28e8d
   - **Response Mode**: Last Node
4. Click "Save" and then "Execute Node" to activate the webhook

### 3. Add a Function Node to Process the Query

1. Add a new node after the webhook
2. Search for "Function" and select it
3. Enter the following code:

```javascript
// Extract the query from the webhook request
const query = $input.body.query;

// Log the received query
console.log('Received query:', query);

// Return the query for further processing
return {
  query: query
};
```

### 4. Add an Execute Command Node

1. Add a new node after the Function node
2. Search for "Execute Command" and select it
3. Configure it:
   - **Command**: python
   - **Arguments**: /home/node/project/agent_system/interactive_test.py "{{$json.query}}"
   - **Working Directory**: /home/node/project
   - **Execution Timeout**: 120 (seconds)

### 5. Add a SQLite Node

1. Add a new node after the Execute Command node
2. Search for "SQLite" and select it
3. Configure it:
   - **Database Path**: /home/node/synthetic_data.db
   - **Operation**: Execute Query
   - **Query**: You can use a placeholder query or leave it empty, as the agent will generate the appropriate SQL

### 6. Add a Final Function Node

1. Add a new node after the SQLite node
2. Search for "Function" and select it
3. Enter the following code:

```javascript
// Get the agent's response
const agentResponse = $input.data;

// Format the response
return {
  result: agentResponse
};
```

### 7. Connect the Nodes

1. Connect the nodes in sequence:
   - Webhook → Function (Process Query) → Execute Command → SQLite → Function (Format Response)

2. Save the workflow

### 8. Test the Workflow

1. Make sure the webhook is active (should show "active" in the webhook node)
2. Use the chatbot interface or curl to send a test query:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me the top 5 customers by total sales amount"}' \
  http://localhost:5678/webhook-test/37694deb-f310-4a1e-b198-aaff97f28e8d
```

## Troubleshooting

### Port Conflict Issues

If you see an error like "Ports are not available: exposing port TCP 0.0.0.0:5678 -> 0.0.0.0:0: listen tcp 0.0.0.0:5678: bind: address already in use":

1. Use the stop script to kill all n8n instances:
   ```bash
   ./stop-n8n.sh
   ```

2. If the port is still in use, find what's using it:
   ```bash
   lsof -i :5678
   ```

3. Kill the process manually:
   ```bash
   kill -9 <PID>
   ```

4. For a complete reset, try:
   ```bash
   # Stop all n8n instances
   ./stop-n8n.sh
   
   # Remove all Docker containers
   docker-compose down
   
   # Remove n8n data (only if you want to start fresh)
   rm -rf n8n-data
   
   # Start again
   ./setup-n8n.sh
   docker-compose up -d
   ```

### Database Connection Issues

If n8n can't connect to the SQLite database:

1. Run the test script to diagnose issues:
   ```bash
   ./test-sqlite.sh
   ```

2. Check that the database file exists and has the right permissions:
   ```bash
   ls -la synthetic_data.db
   chmod 644 synthetic_data.db
   ```

3. Verify the file is mounted correctly in the container:
   ```bash
   docker-compose exec n8n ls -la /home/node/synthetic_data.db
   ```

4. Make sure the SQLite3 node is installed:
   ```bash
   docker-compose exec n8n npm list -g n8n-nodes-sqlite3
   ```

### Agent System Issues

If the agent system isn't responding correctly:

1. Check that the OPENAI_API_KEY is set in the .env file
2. Test the agent system directly:
   ```bash
   python -m agent_system.interactive_test "Show me the top 5 customers"
   ```

3. Check the n8n logs:
   ```bash
   docker-compose logs n8n
   ```

### Webhook Issues

If the chatbot can't connect to the webhook:

1. Check that the webhook URL is correct in the chatbot's script.js file
2. Verify the webhook is active in n8n (should show "active" in the webhook node)
3. Check for CORS issues in your browser's developer console

## Advanced Configuration

### Using Environment Variables

You can add environment variables to the `.env` file:

```
OPENAI_API_KEY=your_api_key_here
```

### Persistent Storage

The n8n data directory is mounted at `./n8n-data` to persist workflows and credentials between container restarts.

### Security Considerations

For production use:
- Enable authentication for n8n
- Use HTTPS for all connections
- Restrict access to the webhook with proper authentication