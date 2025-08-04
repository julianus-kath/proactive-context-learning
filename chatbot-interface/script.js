// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const statusIndicator = document.getElementById('status-indicator');

// n8n webhook URL
const WEBHOOK_URL = 'http://localhost:5678/webhook-test/37694deb-f310-4a1e-b198-aaff97f28e8d';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    userInput.focus();
    
    // Auto-resize textarea as user types
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight < 150) ? 
            `${userInput.scrollHeight}px` : '150px';
    });
    
    // Send message on Enter (but allow Shift+Enter for new lines)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Send button click
    sendButton.addEventListener('click', sendMessage);
});

// Add a message to the chat
function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    // Process markdown-like formatting
    let formattedText = text;
    
    // Handle code blocks
    formattedText = formattedText.replace(/```([\s\S]*?)```/g, (match, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
    });
    
    // Handle inline code
    formattedText = formattedText.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Handle lists (simple implementation)
    formattedText = formattedText.replace(/^\s*-\s+(.*?)$/gm, '<li>$1</li>');
    if (formattedText.includes('<li>')) {
        formattedText = '<ul>' + formattedText + '</ul>';
    }
    
    // Handle line breaks
    formattedText = formattedText.replace(/\n/g, '<br>');
    
    messageContent.innerHTML = formattedText;
    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Show loading indicator
function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message assistant loading';
    loadingDiv.id = 'loading-indicator';
    
    const loadingContent = document.createElement('div');
    loadingContent.className = 'message-content';
    loadingContent.innerHTML = '<span></span><span></span><span></span>';
    
    loadingDiv.appendChild(loadingContent);
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Remove loading indicator
function hideLoading() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
}

// Send message to webhook
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;
    
    // Disable input while processing
    userInput.disabled = true;
    sendButton.disabled = true;
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Clear input
    userInput.value = '';
    userInput.style.height = 'auto';
    
    // Show loading indicator
    showLoading();
    
    try {
        // Send to n8n webhook
        const response = await fetch(WEBHOOK_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: message
            })
        });
        
        // Hide loading indicator
        hideLoading();
        
        if (response.ok) {
            const data = await response.json();
            
            // Display response from the agent
            if (data.result) {
                addMessage(data.result, 'assistant');
            } else {
                addMessage("I received your message, but I'm not sure how to respond.", 'assistant');
            }
            statusIndicator.textContent = '';
        } else {
            throw new Error(`Server responded with status: ${response.status}`);
        }
    } catch (error) {
        // Hide loading indicator
        hideLoading();
        
        console.error('Error:', error);
        addMessage("Sorry, I couldn't process your request. There was a network error or the server is not responding.", 'assistant');
        statusIndicator.textContent = `Error: ${error.message}`;
    } finally {
        // Re-enable input
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
    }
}

// Handle connection status
window.addEventListener('online', () => {
    statusIndicator.textContent = 'Connected';
    setTimeout(() => {
        statusIndicator.textContent = '';
    }, 2000);
});

window.addEventListener('offline', () => {
    statusIndicator.textContent = 'Disconnected - Check your internet connection';
});