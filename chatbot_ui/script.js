// ERP Chatbot UI - JavaScript Implementation
class ERPChatbot {
    constructor() {
        this.serviceUrl = 'http://localhost:5001';
        this.apiKey = 'supersecretapikey';
        this.sessionId = this.generateSessionId();
        this.messages = [];
        this.conversations = [];
        this.currentConversationId = null;
        this.isLoading = false;
        this.lastWasClarification = false;

        this.initializeElements();
        this.bindEvents();
        this.checkServiceHealth();
        this.loadSettings();
        this.loadConversations();
    }

    initializeElements() {
        // Main elements
        this.statusIndicator = document.getElementById('statusIndicator');
        this.statusDot = this.statusIndicator.querySelector('.status-dot');
        this.statusText = this.statusIndicator.querySelector('.status-text');
        this.conversationHistory = document.getElementById('conversationHistory');
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.charCount = document.getElementById('charCount');
        this.loadingOverlay = document.getElementById('loadingOverlay');

        // Buttons
        this.clearHistoryBtn = document.getElementById('clearHistoryBtn');
        this.helpBtn = document.getElementById('helpBtn');
        this.settingsBtn = document.getElementById('settingsBtn');

        // Modals
        this.helpModal = document.getElementById('helpModal');
        this.settingsModal = document.getElementById('settingsModal');
        this.helpModalClose = document.getElementById('helpModalClose');
        this.settingsModalClose = document.getElementById('settingsModalClose');

        // Settings
        this.serviceUrlInput = document.getElementById('serviceUrl');
        this.apiKeyInput = document.getElementById('apiKey');
        this.sessionIdInput = document.getElementById('sessionId');
        this.resetSettingsBtn = document.getElementById('resetSettings');
        this.saveSettingsBtn = document.getElementById('saveSettings');
    }

    bindEvents() {
        // Message input events
        this.messageInput.addEventListener('input', () => this.handleInputChange());
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.sendBtn.addEventListener('click', () => this.sendMessage());

        // Button events
        this.clearHistoryBtn.addEventListener('click', () => this.clearHistory());
        this.helpBtn.addEventListener('click', () => this.showModal('help'));
        this.settingsBtn.addEventListener('click', () => this.showModal('settings'));

        // Modal events
        this.helpModalClose.addEventListener('click', () => this.hideModal('help'));
        this.settingsModalClose.addEventListener('click', () => this.hideModal('settings'));

        // Settings events
        this.resetSettingsBtn.addEventListener('click', () => this.resetSettings());
        this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());

        // Sample query events
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('sample-query')) {
                const query = e.target.getAttribute('data-query');
                this.messageInput.value = query;
                this.handleInputChange();
                this.messageInput.focus();
            }
        });

        // Modal backdrop events
        this.helpModal.addEventListener('click', (e) => {
            if (e.target === this.helpModal) this.hideModal('help');
        });
        this.settingsModal.addEventListener('click', (e) => {
            if (e.target === this.settingsModal) this.hideModal('settings');
        });

        // Escape key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideModal('help');
                this.hideModal('settings');
            }
        });
    }

    generateSessionId() {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const random = Math.floor(Math.random() * 10000);
        return `session_${timestamp}_${random}`;
    }

    handleInputChange() {
        const length = this.messageInput.value.length;
        this.charCount.textContent = length;

        // Update character counter styling
        this.charCount.className = '';
        if (length > 800) {
            this.charCount.classList.add('warning');
        }
        if (length > 950) {
            this.charCount.classList.add('error');
        }

        // Auto-resize textarea
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';

        // Enable/disable send button
        this.sendBtn.disabled = length === 0 || this.isLoading;
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    }

    async checkServiceHealth() {
        try {
            const response = await fetch(`${this.serviceUrl}/health`, {
                method: 'GET',
                timeout: 5000
            });

            if (response.ok) {
                this.updateStatus('online', 'Service Online');
            } else {
                this.updateStatus('offline', 'Service Error');
            }
        } catch (error) {
            this.updateStatus('offline', 'Service Offline');
        }
    }

    updateStatus(status, text) {
        this.statusDot.className = `status-dot ${status}`;
        this.statusText.textContent = text;
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading) return;

        // Clear input and show loading
        this.messageInput.value = '';
        this.handleInputChange();
        this.setLoading(true);

        try {
            // Add user message to UI
            this.addMessage('user', message);

            // Add user message to conversation
            this.messages.push({ role: 'user', content: message });

            // Send to service
            const response = await this.sendToService(message);

            // Handle response
            if (response.error) {
                this.addMessage('bot', `⚠️ ${response.error}`, true);
                this.messages.push({ role: 'assistant', content: response.error });
            } else {
                // Check if it's a clarification
                const isClarification = response.clarify || response.operation === 'clarify';
                const responseText = response.final_response || response.response || response.clarification || response.question;

                this.addMessage('bot', responseText, false, isClarification);
                this.lastWasClarification = isClarification;

                // Update messages from server if available
                if (response.messages && Array.isArray(response.messages)) {
                    this.messages = response.messages;
                } else {
                    this.messages.push({ role: 'assistant', content: responseText });
                }
            }

            // Update conversation history
            this.updateConversationHistory();

            // Log interaction
            this.logInteraction(message, response);

        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('bot', `⚠️ Connection error: ${error.message}`, true);
        } finally {
            this.setLoading(false);
            this.messageInput.focus();
        }
    }

    async sendToService(userInput) {
        const payload = {
            messages: this.messages.concat([{ role: 'user', content: userInput }]),
            api_key: this.apiKey
        };

        const response = await fetch(`${this.serviceUrl}/process_conversation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
            timeout: 60000
        });

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Authentication failed. Please check your API key.');
            } else if (response.status === 400) {
                throw new Error('Invalid request format.');
            } else if (response.status === 503) {
                throw new Error('Service temporarily unavailable.');
            } else {
                throw new Error(`Service error (${response.status})`);
            }
        }

        return await response.json();
    }

    addMessage(sender, content, isError = false, isClarification = false) {
        // Hide welcome message if it exists
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        if (isClarification) {
            messageDiv.classList.add('clarification');
        }

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = sender === 'user' ? '👤' : '🤖';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        // Format content (basic markdown-like formatting)
        const formattedContent = this.formatMessageContent(content);
        contentDiv.innerHTML = formattedContent;

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString();

        messageDiv.appendChild(avatar);
        const messageBody = document.createElement('div');
        messageBody.appendChild(contentDiv);
        messageBody.appendChild(timeDiv);
        messageDiv.appendChild(messageBody);

        this.chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    formatMessageContent(content) {
        // Basic formatting for better readability
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    setLoading(loading) {
        this.isLoading = loading;
        this.sendBtn.disabled = loading || this.messageInput.value.trim().length === 0;

        if (loading) {
            this.loadingOverlay.classList.add('show');
        } else {
            this.loadingOverlay.classList.remove('show');
        }
    }

    updateConversationHistory() {
        if (this.messages.length === 0) return;

        // Get the first user message as conversation title
        const firstUserMessage = this.messages.find(m => m.role === 'user');
        if (!firstUserMessage) return;

        const conversationTitle = firstUserMessage.content.substring(0, 50) +
                                (firstUserMessage.content.length > 50 ? '...' : '');

        // Create or update conversation
        const conversation = {
            id: this.currentConversationId || this.generateConversationId(),
            title: conversationTitle,
            messages: [...this.messages],
            timestamp: new Date().toISOString(),
            lastMessage: this.messages[this.messages.length - 1]?.content || ''
        };

        // Update conversations array
        const existingIndex = this.conversations.findIndex(c => c.id === conversation.id);
        if (existingIndex >= 0) {
            this.conversations[existingIndex] = conversation;
        } else {
            this.conversations.unshift(conversation);
            this.currentConversationId = conversation.id;
        }

        // Limit to 50 conversations
        if (this.conversations.length > 50) {
            this.conversations = this.conversations.slice(0, 50);
        }

        this.saveConversations();
        this.renderConversationHistory();
    }

    generateConversationId() {
        return `conv_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    }

    renderConversationHistory() {
        if (this.conversations.length === 0) {
            this.conversationHistory.innerHTML = `
                <div class="history-empty">
                    <div class="empty-icon">💬</div>
                    <p>No conversations yet</p>
                    <small>Start chatting to see your conversation history</small>
                </div>
            `;
            return;
        }

        this.conversationHistory.innerHTML = '';

        this.conversations.forEach(conversation => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            if (conversation.id === this.currentConversationId) {
                item.classList.add('active');
            }

            item.innerHTML = `
                <div class="conversation-preview">${conversation.title}</div>
                <div class="conversation-time">${this.formatTime(conversation.timestamp)}</div>
            `;

            item.addEventListener('click', () => this.loadConversation(conversation.id));
            this.conversationHistory.appendChild(item);
        });
    }

    loadConversation(conversationId) {
        const conversation = this.conversations.find(c => c.id === conversationId);
        if (!conversation) return;

        this.currentConversationId = conversationId;
        this.messages = [...conversation.messages];

        // Clear and rebuild chat messages
        this.chatMessages.innerHTML = '';

        conversation.messages.forEach(message => {
            this.addMessage(
                message.role === 'user' ? 'user' : 'bot',
                message.content,
                false,
                message.content.includes('🤔') // Simple clarification detection
            );
        });

        this.renderConversationHistory();
    }

    clearHistory() {
        if (confirm('Are you sure you want to clear all conversation history?')) {
            this.conversations = [];
            this.messages = [];
            this.currentConversationId = null;
            this.lastWasClarification = false;

            this.saveConversations();
            this.renderConversationHistory();

            // Reset chat messages to welcome state
            this.chatMessages.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-content">
                        <div class="welcome-icon">🚀</div>
                        <h3>Welcome to ERP Assistant!</h3>
                        <p>I can help you query your ERP database using natural language. Try asking questions like:</p>
                        <div class="sample-queries">
                            <button class="sample-query" data-query="How many customers do we have?">
                                How many customers do we have?
                            </button>
                            <button class="sample-query" data-query="Show me our top 5 products by sales">
                                Show me our top 5 products by sales
                            </button>
                            <button class="sample-query" data-query="What were our total sales last month?">
                                What were our total sales last month?
                            </button>
                            <button class="sample-query" data-query="Which products are low in stock?">
                                Which products are low in stock?
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    }

    showModal(type) {
        if (type === 'help') {
            this.helpModal.classList.add('show');
        } else if (type === 'settings') {
            this.settingsModal.classList.add('show');
            this.loadSettingsToModal();
        }
    }

    hideModal(type) {
        if (type === 'help') {
            this.helpModal.classList.remove('show');
        } else if (type === 'settings') {
            this.settingsModal.classList.remove('show');
        }
    }

    loadSettingsToModal() {
        this.serviceUrlInput.value = this.serviceUrl;
        this.apiKeyInput.value = this.apiKey;
        this.sessionIdInput.value = this.sessionId;
    }

    resetSettings() {
        this.serviceUrl = 'http://localhost:5001';
        this.apiKey = 'supersecretapikey';
        this.sessionId = this.generateSessionId();
        this.loadSettingsToModal();
        this.saveSettings();
    }

    saveSettings() {
        this.serviceUrl = this.serviceUrlInput.value.trim();
        this.apiKey = this.apiKeyInput.value.trim();

        // Save to localStorage
        localStorage.setItem('erp_chatbot_settings', JSON.stringify({
            serviceUrl: this.serviceUrl,
            apiKey: this.apiKey,
            sessionId: this.sessionId
        }));

        this.hideModal('settings');
        this.checkServiceHealth();

        // Show success message
        this.showNotification('Settings saved successfully!', 'success');
    }

    loadSettings() {
        try {
            const saved = localStorage.getItem('erp_chatbot_settings');
            if (saved) {
                const settings = JSON.parse(saved);
                this.serviceUrl = settings.serviceUrl || this.serviceUrl;
                this.apiKey = settings.apiKey || this.apiKey;
                this.sessionId = settings.sessionId || this.sessionId;
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }

    saveConversations() {
        try {
            localStorage.setItem('erp_chatbot_conversations', JSON.stringify(this.conversations));
        } catch (error) {
            console.error('Error saving conversations:', error);
        }
    }

    loadConversations() {
        try {
            const saved = localStorage.getItem('erp_chatbot_conversations');
            if (saved) {
                this.conversations = JSON.parse(saved);
                this.renderConversationHistory();
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }

    logInteraction(userInput, response) {
        const logEntry = {
            timestamp: new Date().toISOString(),
            sessionId: this.sessionId,
            userInput: userInput,
            response: response,
            conversationId: this.currentConversationId
        };

        console.log('Chat interaction:', logEntry);

        // Could send to analytics service here
    }

    showNotification(message, type = 'info') {
        // Simple notification system
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            background-color: var(--primary-accent);
            color: white;
            border-radius: 8px;
            z-index: 3000;
            animation: slideInRight 0.3s ease-out;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
}

// Initialize the chatbot when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.erpChatbot = new ERPChatbot();
});

// Add notification animations to CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100%);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes slideOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100%);
        }
    }
`;
document.head.appendChild(style);
