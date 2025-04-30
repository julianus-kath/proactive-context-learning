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
    
    // Add summary of results
    if (data.results && data.results.length > 0) {
        const summary = document.createElement('p');
        summary.textContent = formatResults(data.results);
        container.appendChild(summary);
    } else {
        const noResults = document.createElement('p');
        noResults.textContent = 'No results found for your query.';
        container.appendChild(noResults);
    }
    
    // Add query details section (collapsible)
    const detailsContainer = document.createElement('div');
    detailsContainer.className = 'query-details';
    
    // Add thought process
    if (data.thought_process) {
        const thoughtTitle = document.createElement('h4');
        thoughtTitle.textContent = 'Thought Process';
        detailsContainer.appendChild(thoughtTitle);
        
        const thoughtPre = document.createElement('pre');
        thoughtPre.textContent = data.thought_process;
        detailsContainer.appendChild(thoughtPre);
    }
    
    // Add structured queries
    if (data.structured_queries && data.structured_queries.length > 0) {
        const queriesTitle = document.createElement('h4');
        queriesTitle.textContent = 'Structured Queries';
        detailsContainer.appendChild(queriesTitle);
        
        data.structured_queries.forEach((query, index) => {
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

// Format results for display
function formatResults(results) {
    if (!results || results.length === 0) {
        return 'No results found.';
    }
    
    // For simple result sets, just return a summary
    if (results.length === 1 && typeof results[0] === 'object') {
        const result = results[0];
        
        // Check if it's a count result
        if (result.count !== undefined) {
            return `Found ${result.count} records.`;
        }
        
        // Check if it's a simple object
        const keys = Object.keys(result);
        if (keys.length <= 3) {
            return keys.map(key => `${key}: ${result[key]}`).join(', ');
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