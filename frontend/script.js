// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const statusDot = document.querySelector('.status-dot');
const statusText = document.querySelector('.status-text');

// API Configuration
const API_URL = window.location.hostname === 'localhost' ? 'http://localhost:8000' : `http://${window.location.hostname}:8000`;
const HEALTH_CHECK_INTERVAL = 5000; // 5 seconds

// State
let isConnected = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Auto-resize textarea
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight) + 'px';
        
        // Enable/disable send button based on input
        sendButton.disabled = userInput.value.trim() === '';
    });
    
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);
    
    // Send message on Enter key (but allow Shift+Enter for new lines)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Check API health
    checkHealth();
    setInterval(checkHealth, HEALTH_CHECK_INTERVAL);
    
    // Highlight code blocks
    highlightCodeBlocks();
});

// Check API health
async function checkHealth() {
    try {
        statusDot.className = 'status-dot connecting';
        statusText.textContent = 'Connecting...';
        
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();
        
        if (data.status === 'healthy') {
            isConnected = true;
            statusDot.className = 'status-dot online';
            statusText.textContent = 'Online';
            sendButton.disabled = userInput.value.trim() === '';
        } else {
            isConnected = false;
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'Unhealthy';
            sendButton.disabled = true;
        }
    } catch (error) {
        console.error('Health check failed:', error);
        isConnected = false;
        statusDot.className = 'status-dot offline';
        statusText.textContent = 'Offline';
        sendButton.disabled = true;
    }
}

// Send message
async function sendMessage() {
    const query = userInput.value.trim();
    
    if (!query || !isConnected) return;
    
    // Add user message to chat
    addMessage('user', query);
    
    // Clear input
    userInput.value = '';
    userInput.style.height = 'auto';
    sendButton.disabled = true;
    
    // Add loading indicator
    const loadingId = addLoadingIndicator();
    
    try {
        // Send query to API
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                query_id: generateQueryId(),
                context: {}
            })
        });
        
        const data = await response.json();
        
        // Remove loading indicator
        removeLoadingIndicator(loadingId);
        
        // Process response
        if (data.status === 'error') {
            addErrorMessage(data.error || 'An error occurred while processing your query.');
        } else {
            addAgentResponse(data);
        }
    } catch (error) {
        console.error('Query failed:', error);
        
        // Remove loading indicator
        removeLoadingIndicator(loadingId);
        
        // Add error message
        addErrorMessage('Failed to connect to the API. Please check your connection and try again.');
    }
    
    // Scroll to bottom
    scrollToBottom();
}

// Add message to chat
function addMessage(type, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (typeof content === 'string') {
        const p = document.createElement('p');
        p.textContent = content;
        contentDiv.appendChild(p);
    } else {
        contentDiv.appendChild(content);
    }
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
    return messageDiv;
}

// Add loading indicator
function addLoadingIndicator() {
    const loadingId = 'loading-' + Date.now();
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message agent';
    loadingDiv.id = loadingId;
    
    const loadingContent = document.createElement('div');
    loadingContent.className = 'loading';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'loading-dot';
        loadingContent.appendChild(dot);
    }
    
    loadingDiv.appendChild(loadingContent);
    chatMessages.appendChild(loadingDiv);
    
    scrollToBottom();
    return loadingId;
}

// Remove loading indicator
function removeLoadingIndicator(loadingId) {
    const loadingDiv = document.getElementById(loadingId);
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

// Add error message
function addErrorMessage(errorText) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message error';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const p = document.createElement('p');
    p.textContent = errorText;
    contentDiv.appendChild(p);
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
}

// Add agent response
function addAgentResponse(data) {
    const container = document.createElement('div');
    
    // Check for a direct answer in the response
    let answer = '';
    
    // First check if there's a dedicated answer field
    if (data.answer) {
        answer = data.answer;
    } 
    // Then check if there's an answer in the results object
    else if (data.results && typeof data.results === 'object') {
        // If results is an array of objects with an answer field
        if (Array.isArray(data.results)) {
            for (const result of data.results) {
                if (result.answer) {
                    answer = result.answer;
                    break;
                }
            }
        } 
        // If results is an object with an answer field
        else if (data.results.answer) {
            answer = data.results.answer;
        }
        // If results is an object with a summary field
        else if (data.results.summary) {
            answer = data.results.summary;
        }
    }
    // Then check if there's a summary in the data
    else if (data.summary) {
        answer = data.summary;
    }
    // Finally, extract summary from thought process if available
    else if (data.thought_process) {
        const summaryMatch = data.thought_process.match(/Summary: (.*?)(\n|$)/);
        if (summaryMatch && summaryMatch[1]) {
            answer = summaryMatch[1];
        }
    }
    
    // Log the answer for debugging
    console.log("Extracted answer:", answer);
    
    // Check if there's an error in the response
    if (data.error) {
        const errorPara = document.createElement('p');
        errorPara.className = 'agent-error';
        errorPara.textContent = `Error: ${data.error}`;
        container.appendChild(errorPara);
    }
    // Add the answer as a prominent response
    else if (answer) {
        const answerPara = document.createElement('p');
        answerPara.className = 'agent-answer';
        answerPara.textContent = answer;
        container.appendChild(answerPara);
    } 
    // Fallback to formatting results if no answer is available
    else if (data.results && data.results.length > 0) {
        const summaryPara = document.createElement('p');
        summaryPara.textContent = formatResults(data.results);
        container.appendChild(summaryPara);
    } 
    // Show no results message if nothing else is available
    else {
        const noResults = document.createElement('p');
        noResults.textContent = 'No results found for your query.';
        container.appendChild(noResults);
    }
    
    // Add query details section (collapsible)
    const detailsContainer = document.createElement('div');
    detailsContainer.className = 'query-details';
    
    // Extract intent from thought process if available
    let intent = '';
    let entities = [];
    
    if (data.thought_process) {
        const intentMatch = data.thought_process.match(/intent: ([a-z]+)/i);
        if (intentMatch && intentMatch[1]) {
            intent = intentMatch[1].toLowerCase();
        }
        
        // Extract entities
        const entityMatches = data.thought_process.match(/entities?:.*?(\w+)/gi);
        if (entityMatches) {
            entities = entityMatches.map(match => {
                const entityMatch = match.match(/(\w+)$/);
                return entityMatch ? entityMatch[1].toLowerCase() : '';
            }).filter(Boolean);
        }
    }
    
    // Add query intent and entities if available
    if (intent || entities.length > 0) {
        const intentDiv = document.createElement('div');
        intentDiv.className = 'query-intent';
        
        let intentText = '';
        if (intent) {
            intentText += `Intent: ${intent.charAt(0).toUpperCase() + intent.slice(1)}`;
        }
        
        if (entities.length > 0) {
            if (intentText) intentText += ' • ';
            intentText += `Entities: ${entities.join(', ')}`;
        }
        
        intentDiv.textContent = intentText;
        detailsContainer.appendChild(intentDiv);
    }
    
    // Add thought process
    if (data.thought_process) {
        // Create a toggle button for thought process
        const thoughtToggle = document.createElement('button');
        thoughtToggle.className = 'thought-toggle';
        thoughtToggle.textContent = 'Show Thinking Process';
        thoughtToggle.onclick = function() {
            const thoughtProcess = this.nextElementSibling;
            if (thoughtProcess.style.display === 'none') {
                thoughtProcess.style.display = 'block';
                this.textContent = 'Hide Thinking Process';
            } else {
                thoughtProcess.style.display = 'none';
                this.textContent = 'Show Thinking Process';
            }
        };
        detailsContainer.appendChild(thoughtToggle);
        
        // Create the thought process container
        const thoughtContainer = document.createElement('div');
        thoughtContainer.className = 'thought-process-container';
        thoughtContainer.style.display = 'none'; // Hidden by default
        
        const thoughtPre = document.createElement('pre');
        thoughtPre.className = 'thought-process-text';
        
        // Format the thought process for better readability
        const formattedThoughtProcess = formatThoughtProcess(data.thought_process);
        thoughtPre.textContent = formattedThoughtProcess;
        
        thoughtContainer.appendChild(thoughtPre);
        detailsContainer.appendChild(thoughtContainer);
    }
    
    // Add structured queries
    if (data.structured_queries && data.structured_queries.length > 0) {
        const queriesTitle = document.createElement('h4');
        queriesTitle.textContent = 'Structured Queries';
        detailsContainer.appendChild(queriesTitle);
        
        data.structured_queries.forEach((query, index) => {
            // Add query status (executed, skipped)
            const queryStatus = document.createElement('div');
            
            // Check if this query was executed or skipped
            let wasSkipped = false;
            
            // First check in the results array
            if (data.results) {
                for (const result of data.results) {
                    if (result._source && result._source.tool === query.tool_name && result._source.status === 'skipped') {
                        wasSkipped = true;
                        break;
                    }
                    
                    if (result.tool_name === query.tool_name && result.status === 'skipped') {
                        wasSkipped = true;
                        break;
                    }
                }
            }
            
            // Set the appropriate class and text
            if (wasSkipped) {
                queryStatus.className = 'query-status skipped';
                queryStatus.textContent = `Query ${index + 1}: ${query.tool_name} (Skipped)`;
            } else {
                queryStatus.className = 'query-status executed';
                queryStatus.textContent = `Query ${index + 1}: ${query.tool_name} (Executed)`;
            }
            
            detailsContainer.appendChild(queryStatus);
            
            const queryPre = document.createElement('pre');
            const queryCode = document.createElement('code');
            
            // Determine language for syntax highlighting
            let language = 'json';
            if (query.tool_name === 'erp_query') {
                language = 'sql';
            } else if (query.tool_name === 'knowledge_graph_query') {
                language = 'sparql';
            }
            
            queryCode.className = language;
            
            if (query.parameters && query.parameters.query) {
                queryCode.textContent = query.parameters.query;
            } else {
                queryCode.textContent = JSON.stringify(query.parameters, null, 2);
            }
            
            queryPre.appendChild(queryCode);
            detailsContainer.appendChild(queryPre);
        });
    }
    
    // Add execution time
    if (data.execution_time_ms) {
        const timeDiv = document.createElement('div');
        timeDiv.className = 'execution-time';
        timeDiv.textContent = `Execution time: ${(data.execution_time_ms / 1000).toFixed(2)}s`;
        detailsContainer.appendChild(timeDiv);
    }
    
    container.appendChild(detailsContainer);
    
    // Add the message
    addMessage('agent', container);
    
    // Highlight code blocks
    highlightCodeBlocks();
}

// Format thought process for better readability
function formatThoughtProcess(thoughtProcess) {
    if (!thoughtProcess) return '';
    
    // Split by sections
    let formatted = thoughtProcess;
    
    // Highlight intent
    formatted = formatted.replace(/intent:?\s*([a-z]+)/gi, '🎯 INTENT: $1');
    
    // Highlight entities
    formatted = formatted.replace(/entities?:?\s*([^.]+)/gi, '📦 ENTITIES: $1');
    
    // Highlight data sources
    formatted = formatted.replace(/data sources?:?\s*([^.]+)/gi, '🗄️ DATA SOURCES: $1');
    
    // Highlight tool names
    formatted = formatted.replace(/Tool \d+ \((.*?)\) reasoning:/g, '🔧 TOOL: $1');
    
    // Highlight necessary/not necessary statements
    formatted = formatted.replace(/this query is necessary/gi, '✅ THIS QUERY IS NECESSARY');
    formatted = formatted.replace(/this query is not necessary/gi, '❌ THIS QUERY IS NOT NECESSARY');
    
    // Highlight results processing
    formatted = formatted.replace(/Results processing:/g, '🔄 RESULTS PROCESSING:');
    
    // Highlight summary
    formatted = formatted.replace(/Summary:/g, '📋 SUMMARY:');
    
    return formatted;
}

// Format results for display
function formatResults(results) {
    if (!results || results.length === 0) {
        return 'No results found.';
    }
    
    // Extract summary from thought process if available
    const thoughtProcess = document.querySelector('.thought-process-text');
    if (thoughtProcess) {
        const text = thoughtProcess.textContent;
        const summaryMatch = text.match(/Summary: (.*?)(\n|$)/);
        if (summaryMatch && summaryMatch[1]) {
            return summaryMatch[1];
        }
    }
    
    // For simple result sets, generate a summary
    if (results.length === 1 && typeof results[0] === 'object') {
        const result = results[0];
        
        // Check if it's a count result
        if (result.count !== undefined) {
            return `Found ${result.count} records.`;
        }
        
        // Check if it's a simple object
        const keys = Object.keys(result).filter(k => !k.startsWith('_'));
        if (keys.length <= 3) {
            return keys.map(key => `${key}: ${result[key]}`).join(', ');
        }
    }
    
    // For specific types of results, create more detailed summaries
    if (results.length > 0) {
        // Check for product results
        if (results[0].name && results[0].price) {
            const mostExpensive = results.reduce((prev, current) => 
                (prev.price > current.price) ? prev : current);
            return `Found ${results.length} products. The most expensive is '${mostExpensive.name}' at $${mostExpensive.price.toFixed(2)}.`;
        }
        
        // Check for employee results
        if (results[0].name && results[0].department) {
            return `Found ${results.length} employees in the ${results[0].department} department.`;
        }
        
        // Check for order results
        if (results[0].status && results[0].status === 'Completed') {
            const total = results.reduce((sum, order) => sum + (order.total || 0), 0);
            return `Found ${results.length} completed orders with a total value of $${total.toFixed(2)}.`;
        }
    }
    
    // For multiple results, return a summary
    return `Found ${results.length} results.`;
}

// Generate a random query ID
function generateQueryId() {
    return 'query-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
}

// Scroll to bottom of chat
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Highlight code blocks
function highlightCodeBlocks() {
    document.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
}