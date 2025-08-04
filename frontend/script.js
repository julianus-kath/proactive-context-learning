// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

// API Configuration
const API_URL = 'http://localhost:8000';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Enable/disable send button based on input
    userInput.addEventListener('input', () => {
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
});

// Add message to chat
function addMessage(type, content, additionalInfo = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // If content is a string, set it as text content
    if (typeof content === 'string') {
        contentDiv.textContent = content;
    } else {
        // Otherwise, assume it's HTML and set innerHTML
        contentDiv.innerHTML = content;
    }
    
    messageDiv.appendChild(contentDiv);
    
    // Add additional info if provided
    if (additionalInfo) {
        const infoDiv = document.createElement('div');
        infoDiv.className = 'message-info';
        
        // Create a button to toggle the info
        const toggleButton = document.createElement('button');
        toggleButton.className = 'toggle-info';
        toggleButton.textContent = 'Show Details';
        
        // Create the info content div (hidden by default)
        const infoContent = document.createElement('div');
        infoContent.className = 'info-content';
        infoContent.style.display = 'none';
        infoContent.innerHTML = additionalInfo;
        
        // Add toggle functionality
        toggleButton.addEventListener('click', () => {
            if (infoContent.style.display === 'none') {
                infoContent.style.display = 'block';
                toggleButton.textContent = 'Hide Details';
            } else {
                infoContent.style.display = 'none';
                toggleButton.textContent = 'Show Details';
            }
        });
        
        infoDiv.appendChild(toggleButton);
        infoDiv.appendChild(infoContent);
        messageDiv.appendChild(infoDiv);
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Generate a UUID for query_id
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Format SQL query with syntax highlighting
function formatSQLQuery(sql) {
    // Simple syntax highlighting
    return sql
        .replace(/\b(SELECT|FROM|WHERE|JOIN|ON|AND|OR|GROUP BY|ORDER BY|HAVING|LIMIT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|AS)\b/gi, '<span class="sql-keyword">$1</span>')
        .replace(/\b(COUNT|SUM|AVG|MIN|MAX)\b/gi, '<span class="sql-function">$1</span>')
        .replace(/'([^']*)'/g, '<span class="sql-string">\'$1\'</span>')
        .replace(/"([^"]*)"/g, '<span class="sql-string">"$1"</span>')
        .replace(/\b(\d+)\b/g, '<span class="sql-number">$1</span>');
}

// Send message to agent
async function sendMessage() {
    const query = userInput.value.trim();
    if (!query) return;
    
    // Clear input
    userInput.value = '';
    sendButton.disabled = true;
    
    // Add user message to chat
    addMessage('user', query);
    
    // Add loading message
    const loadingId = 'loading-' + Date.now();
    const loadingDiv = document.createElement('div');
    loadingDiv.id = loadingId;
    loadingDiv.className = 'message system';
    loadingDiv.innerHTML = `
        <div class="message-content">
            <div class="loading-spinner"></div>
            <p>Thinking...</p>
        </div>
    `;
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    try {
        // Send query to agent
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                query_id: generateUUID()
            })
        });
        
        const data = await response.json();
        
        // Remove loading message
        const loadingMessage = document.getElementById(loadingId);
        if (loadingMessage) {
            chatMessages.removeChild(loadingMessage);
        }
        
        // Add agent response to chat
        if (data.status === 'error' || data.error) {
            addMessage('error', `Error: ${data.error || 'Unknown error'}`);
        } else {
            // Prepare additional info HTML
            let additionalInfo = '';
            
            // Add SQL query if available
            if (data.sources && data.sources.length > 0 && data.sources[0].query) {
                const sqlQuery = data.sources[0].query;
                additionalInfo += `<h4>SQL Query:</h4><pre class="sql-query">${formatSQLQuery(sqlQuery)}</pre>`;
            }
            
            // Add execution time
            if (data.execution_time_ms) {
                additionalInfo += `<p><strong>Execution Time:</strong> ${data.execution_time_ms.toFixed(2)} ms</p>`;
            }
            
            // Add confidence
            if (data.confidence) {
                additionalInfo += `<p><strong>Confidence:</strong> ${data.confidence.toFixed(2)}</p>`;
            }
            
            addMessage('agent', data.answer, additionalInfo);
        }
    } catch (error) {
        // Remove loading message
        const loadingMessage = document.getElementById(loadingId);
        if (loadingMessage) {
            chatMessages.removeChild(loadingMessage);
        }
        
        addMessage('error', 'Failed to connect to the agent. Please try again.');
        console.error('Error:', error);
    }
    
    // Re-enable the send button
    sendButton.disabled = userInput.value.trim() === '';
}