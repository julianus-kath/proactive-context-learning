// ERP Chatbot UI - JavaScript Implementation
class ERPChatbot {
    constructor() {
        this.serviceUrl = '';
        this.apiKey = null;
        this.apiKeyIsServerManaged = false;
        this.sessionId = this.generateSessionId();
        this.messages = [];
        this.conversations = [];
        this.currentConversationId = null;
        this.isLoading = false;
        this.lastWasClarification = false;
        this.currentRequestController = null;
        this.isUserNearBottom = true;
        this.stopRequested = false;
        this.lastFocusedElement = null;
        this.activeModal = null;
        this.theme = 'light';
        this.streamReader = null;
        this.thinkingContainer = null;
        this.thinkingStartTime = null;
        this.useStreaming = true;

        this.initializeElements();
        this.bindEvents();
        this.loadSettings();
        this.loadConversations();
        this.initConfig();
        this.initTheme();
    }

    initializeElements() {
        // Main elements
        this.statusIndicator = document.getElementById('statusIndicator');
        if (this.statusIndicator) {
            this.statusDot = this.statusIndicator.querySelector('.status-dot');
            this.statusText = this.statusIndicator.querySelector('.status-text');
        }
        this.conversationHistory = document.getElementById('conversationHistory');
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.inputHelpBtn = document.getElementById('inputHelpBtn');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.jumpToLatestBtn = document.getElementById('jumpToLatestBtn');
        
        // Buttons
        this.clearHistoryBtn = document.getElementById('clearHistoryBtn');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.helpBtn = document.getElementById('helpBtn');
        this.settingsBtn = document.getElementById('settingsBtn');
        this.themeToggleBtn = document.getElementById('themeToggleBtn');
        this.dbDialectTag = document.getElementById('dbDialectTag');
        this.dbNameTag = document.getElementById('dbNameTag');
        
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
        if (this.messageInput) {
            this.messageInput.addEventListener('input', () => this.handleInputChange());
            this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        }
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this.sendMessage());
        }
        if (this.inputHelpBtn) {
            this.inputHelpBtn.addEventListener('click', () => this.showModal('help'));
        }
        
        // Button events
        if (this.clearHistoryBtn) {
            this.clearHistoryBtn.addEventListener('click', () => this.clearHistory());
        }
        if (this.newChatBtn) {
            this.newChatBtn.addEventListener('click', () => this.startNewChat());
        }
        if (this.helpBtn) {
            this.helpBtn.addEventListener('click', () => this.showModal('help'));
        }
        if (this.settingsBtn) {
            this.settingsBtn.addEventListener('click', () => this.showModal('settings'));
        }
        if (this.themeToggleBtn) {
            this.themeToggleBtn.addEventListener('click', () => this.toggleTheme());
        }

        // Chat scroll events
        if (this.chatMessages) {
            this.chatMessages.addEventListener('scroll', () => this.handleChatScroll());
        }
        if (this.jumpToLatestBtn) {
            this.jumpToLatestBtn.addEventListener('click', () => {
                this.scrollToBottom();
                this.isUserNearBottom = true;
                this.hideJumpToLatest();
            });
        }
        
        // Modal events
        if (this.helpModalClose) {
            this.helpModalClose.addEventListener('click', () => this.hideModal('help'));
        }
        if (this.settingsModalClose) {
            this.settingsModalClose.addEventListener('click', () => this.hideModal('settings'));
        }
        
        // Modal backdrop and focus trap events
        if (this.helpModal) {
            this.helpModal.addEventListener('click', (e) => {
                if (e.target === this.helpModal) this.hideModal('help');
            });
            this.helpModal.addEventListener('keydown', (e) => this.handleModalKeyDown(e, this.helpModal));
        }
        if (this.settingsModal) {
            this.settingsModal.addEventListener('click', (e) => {
                if (e.target === this.settingsModal) this.hideModal('settings');
            });
            this.settingsModal.addEventListener('keydown', (e) => this.handleModalKeyDown(e, this.settingsModal));
        }
        
        // Settings events
        if (this.resetSettingsBtn) {
            this.resetSettingsBtn.addEventListener('click', () => this.resetSettings());
        }
        if (this.saveSettingsBtn) {
            this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
        }
        
        // Sample query events
        document.addEventListener('click', (e) => {
            if (e.target.classList && e.target.classList.contains('sample-query')) {
                const query = e.target.getAttribute('data-query');
                if (this.messageInput) {
                    this.messageInput.value = query || '';
                    this.handleInputChange();
                    this.messageInput.focus();
                }
            }
        });
        
        // Escape key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                if (this.activeModal === this.helpModal) {
                    this.hideModal('help');
                } else if (this.activeModal === this.settingsModal) {
                    this.hideModal('settings');
                }
            }
        });
    }

    generateSessionId() {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const random = Math.floor(Math.random() * 10000);
        return `session_${timestamp}_${random}`;
    }

    initTheme() {
        let theme = 'light';
        try {
            const saved = localStorage.getItem('erp_chatbot_theme');
            if (saved === 'dark' || saved === 'light') {
                theme = saved;
            }
        } catch (error) {
            console.error('Error loading theme:', error);
        }
        this.applyTheme(theme);
    }

    applyTheme(theme) {
        this.theme = theme === 'dark' ? 'dark' : 'light';
        const isDark = this.theme === 'dark';
        document.body.classList.toggle('theme-dark', isDark);
    }

    toggleTheme() {
        const next = this.theme === 'dark' ? 'light' : 'dark';
        this.applyTheme(next);
        try {
            localStorage.setItem('erp_chatbot_theme', next);
        } catch (error) {
            console.error('Error saving theme:', error);
        }
    }

    async initConfig() {
        try {
            const response = await this.fetchWithTimeout('/config', { method: 'GET' }, 5000);
            if (response.ok) {
                const config = await response.json();
                const langgraphUrl = config.langgraph_url || 'http://localhost:5001';
                this.apiKeyIsServerManaged = !!config.api_key_set;
                this.dbDialect = config.db_dialect || null;
                this.dbDatabase = config.db_database || null;

                if (this.dbDialectTag) {
                    this.dbDialectTag.textContent = this.dbDialect
                        ? `Dialect: ${this.dbDialect.toUpperCase()}`
                        : 'Dialect: -';
                }
                if (this.dbNameTag) {
                    this.dbNameTag.textContent = this.dbDatabase
                        ? `DB: ${this.dbDatabase}`
                        : 'DB: -';
                }

                if (this.apiKeyIsServerManaged) {
                    this.serviceUrl = '';
                    if (this.apiKeyInput) {
                        this.apiKeyInput.disabled = true;
                        this.apiKeyInput.placeholder = 'Configured on server';
                        this.apiKeyInput.value = '';
                    }
                } else {
                    this.serviceUrl = langgraphUrl;
                    if (this.apiKeyInput) {
                        this.apiKeyInput.disabled = false;
                    }
                }

                if (this.serviceUrlInput) {
                    this.serviceUrlInput.value = this.apiKeyIsServerManaged
                        ? `${window.location.origin}/process_conversation`
                        : this.serviceUrl;
                }
            } else {
                this.serviceUrl = this.serviceUrl || 'http://localhost:5001';
            }
        } catch (error) {
            console.error('Error loading config:', error);
            this.serviceUrl = this.serviceUrl || 'http://localhost:5001';
        } finally {
            this.checkServiceHealth();
        }
    }

    async fetchWithTimeout(url, options = {}, timeoutMs = 60000, controller) {
        const abortController = controller || new AbortController();
        const timeoutId = setTimeout(() => abortController.abort(), timeoutMs);
        try {
            return await fetch(url, {
                ...options,
                signal: abortController.signal
            });
        } finally {
            clearTimeout(timeoutId);
        }
    }

    handleInputChange() {
        if (!this.messageInput) return;

        // Auto-resize textarea
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
        
        // Enable/disable send button
        if (this.sendBtn) {
            const length = this.messageInput.value.length;
            this.sendBtn.disabled = length === 0 || this.isLoading;
        }
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    }

    async checkServiceHealth() {
        try {
            let url;
            if (this.apiKeyIsServerManaged) {
                url = '/backend_health';
            } else if (this.serviceUrl) {
                url = `${this.serviceUrl.replace(/\/+$/, '')}/health`;
            } else {
                url = '/health';
            }

            const response = await this.fetchWithTimeout(url, { method: 'GET' }, 5000);

            if (response.ok) {
                if (this.apiKeyIsServerManaged && url.endsWith('/backend_health')) {
                    let data = null;
                    try {
                        data = await response.json();
                    } catch (_) {
                        data = null;
                    }
                    if (data && data.status === 'degraded') {
                        this.updateStatus('degraded', 'Service Degraded');
                    } else {
                        this.updateStatus('online', 'Service Online');
                    }
                } else {
                    this.updateStatus('online', 'Service Online');
                }
            } else {
                this.updateStatus('offline', 'Service Error');
            }
        } catch (error) {
            console.error('Error checking service health:', error);
            this.updateStatus('offline', 'Service Offline');
        }
    }

    updateStatus(status, text) {
        if (this.statusDot) {
            this.statusDot.className = `status-dot ${status}`;
        }
        if (this.statusText) {
            this.statusText.textContent = text;
        }

        const isConnected = status === 'online';
        if (this.dbDialectTag) {
            this.dbDialectTag.classList.toggle('connected', isConnected);
        }
        if (this.dbNameTag) {
            this.dbNameTag.classList.toggle('connected', isConnected);
        }
    }

    handleChatScroll() {
        if (!this.chatMessages) return;
        const { scrollTop, scrollHeight, clientHeight } = this.chatMessages;
        const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
        this.isUserNearBottom = distanceFromBottom <= 100;
        if (this.isUserNearBottom) {
            this.hideJumpToLatest();
        }
    }

    scrollToBottom() {
        if (!this.chatMessages) return;
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        this.hideJumpToLatest();
    }

    showJumpToLatest() {
        if (this.jumpToLatestBtn) {
            this.jumpToLatestBtn.hidden = false;
            this.jumpToLatestBtn.classList.add('visible');
        }
    }

    hideJumpToLatest() {
        if (this.jumpToLatestBtn) {
            this.jumpToLatestBtn.classList.remove('visible');
            this.jumpToLatestBtn.hidden = true;
        }
    }

    async sendMessage() {
        if (!this.messageInput) return;
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading) return;

        this.messageInput.value = '';
        this.handleInputChange();
        this.setLoading(true);

        const startTime = (typeof performance !== 'undefined' && performance.now)
            ? performance.now()
            : Date.now();

        let status = 'ok';
        let response = null;

        try {
            this.addMessage('user', message);
            this.messages.push({ role: 'user', content: message });

            if (this.useStreaming) {
                // Use streaming mode
                response = await this.sendMessageStreaming();
            } else {
                // Use non-streaming mode
                response = await this.sendToService();
            }

            if (response && response.error) {
                status = 'backend_error';
                this.addMessage('bot', `Error: ${response.error}`, true);
                this.messages.push({ role: 'assistant', content: response.error });
            } else if (response) {
                const isClarification = response.clarify || response.operation === 'clarify';
                const responseText =
                    response.final_response ||
                    response.response ||
                    response.clarification ||
                    response.question ||
                    '';

                const clarificationOptions = Array.isArray(response.clarification_options)
                    ? response.clarification_options
                    : null;

                this.addMessage('bot', responseText, false, isClarification, clarificationOptions);
                this.lastWasClarification = isClarification;

                if (response.messages && Array.isArray(response.messages)) {
                    this.messages = response.messages;
                } else if (responseText) {
                    this.messages.push({ role: 'assistant', content: responseText });
                }
            }

            this.updateConversationHistory();
        } catch (error) {
            console.error('Error sending message:', error);
            if (error.name === 'AbortError') {
                status = this.stopRequested ? 'cancelled' : 'timeout';
                const label = this.stopRequested
                    ? 'Request cancelled.'
                    : 'Request timed out. Please try again.';
                this.addMessage('bot', label, true);
            } else {
                const errorMessage = error.message || 'Unknown error';
                if (
                    String(errorMessage).startsWith('Authentication failed') ||
                    String(errorMessage).startsWith('Invalid request format') ||
                    String(errorMessage).startsWith('Service temporarily unavailable') ||
                    String(errorMessage).startsWith('Service error')
                ) {
                    status = 'backend_error';
                } else {
                    status = 'network_error';
                }
                this.addMessage('bot', `Error: ${errorMessage}`, true);
            }
        } finally {
            const endTime = (typeof performance !== 'undefined' && performance.now)
                ? performance.now()
                : Date.now();
            const durationMs = Math.round(endTime - startTime);
            this.stopRequested = false;
            this.setLoading(false);
            this.hideThinkingContainer();
            if (this.messageInput) {
                this.messageInput.focus();
            }
            this.logInteraction(message, response, { status, durationMs });
        }
    }

    async sendToService() {
        const payload = {
            messages: this.messages
        };

        if (!this.apiKeyIsServerManaged && this.apiKey) {
            payload.api_key = this.apiKey;
        }

        const baseUrl =
            this.apiKeyIsServerManaged || !this.serviceUrl
                ? ''
                : this.serviceUrl.replace(/\/+$/, '');
        const url = `${baseUrl}/process_conversation`;

        const controller = new AbortController();
        this.currentRequestController = controller;

        let response;
        try {
            response = await this.fetchWithTimeout(
                url,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                },
                60000,
                controller
            );
        } finally {
            this.currentRequestController = null;
        }

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Authentication failed. Please check your API key or server configuration.');
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

    async sendMessageStreaming() {
        const payload = {
            messages: this.messages
        };

        const baseUrl = this.apiKeyIsServerManaged || !this.serviceUrl ? '' : this.serviceUrl.replace(/\/+$/, '');
        const url = `${baseUrl}/stream_conversation`;

        const controller = new AbortController();
        this.currentRequestController = controller;
        this.thinkingStartTime = Date.now();

        let finalResponse = null;
        let llmContent = '';

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            if (!response.ok) {
                throw new Error(`Service error (${response.status})`);
            }

            if (!response.body) {
                throw new Error('ReadableStream not supported');
            }

            const reader = response.body.getReader();
            this.streamReader = reader;
            const decoder = new TextDecoder();
            let buffer = '';

            this.showThinkingContainer();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const eventData = JSON.parse(line.slice(6));
                            const result = this.handleStreamEvent(eventData);
                            if (result && result.type === 'llm_response') {
                                llmContent = result.content || '';
                            }
                            if (result && result.type === 'complete') {
                                finalResponse = {
                                    final_response: llmContent,
                                    sql_query: result.sql_query,
                                    status: 'success'
                                };
                            }
                            if (result && result.type === 'error') {
                                finalResponse = { error: result.error };
                            }
                        } catch (parseError) {
                            console.warn('Failed to parse SSE event:', line, parseError);
                        }
                    }
                }
            }

            this.streamReader = null;
            return finalResponse || { final_response: llmContent || 'No response received', status: 'success' };
        } finally {
            this.currentRequestController = null;
            this.streamReader = null;
        }
    }

    handleStreamEvent(event) {
        const type = event.type;
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        switch (type) {
            case 'query_start':
                this.addThinkingStep('Starting analysis...', timestamp);
                break;

            case 'llm_start':
                this.addThinkingStep('Reasoning about your question...', timestamp);
                break;

            case 'tool_call':
                const toolName = event.tool_name || 'unknown';
                let toolLabel = toolName;

                if (toolName === 'discover_tables' || toolName.includes('discover')) {
                    toolLabel = 'Discovering relevant tables...';
                } else if (toolName === 'execute_query' || toolName.includes('execute')) {
                    toolLabel = 'Executing SQL query...';
                } else if (toolName === 'get_table_schema' || toolName.includes('schema')) {
                    toolLabel = 'Analyzing table schema...';
                } else {
                    toolLabel = `Calling ${toolName}...`;
                }

                this.addThinkingStep(toolLabel, timestamp);
                break;

            case 'tool_result':
                this.updateLastThinkingStep('complete');
                break;

            case 'llm_response':
                return { type: 'llm_response', content: event.content };

            case 'complete':
                const latency = event.latency_ms || (Date.now() - this.thinkingStartTime);
                this.addThinkingStep(`Completed in ${latency}ms`, timestamp);
                return { type: 'complete', sql_query: event.sql_query };

            case 'error':
                this.addThinkingStep(`Error: ${event.error}`, timestamp);
                return { type: 'error', error: event.error };
        }

        return null;
    }

    showThinkingContainer() {
        if (!this.chatMessages) return;

        // Remove existing thinking container if any
        this.hideThinkingContainer();

        const container = document.createElement('div');
        container.className = 'thinking-container';
        container.innerHTML = `
            <button type="button" class="thinking-header" aria-label="Toggle thinking details">
                <div class="thinking-spinner"></div>
                <span class="thinking-title">Agent is working...</span>
                <span class="toggle-arrow"></span>
            </button>
            <div class="thinking-steps"></div>
        `;

        // Bind toggle event to the whole header
        const header = container.querySelector('.thinking-header');
        if (header) {
            header.addEventListener('click', () => {
                container.classList.toggle('collapsed');
            });
        }

        this.chatMessages.appendChild(container);
        this.thinkingContainer = container;
        this.scrollToBottom();
    }

    hideThinkingContainer() {
        if (this.thinkingContainer) {
            this.thinkingContainer.classList.add('completed');
            const header = this.thinkingContainer.querySelector('.thinking-header');
            if (header) {
                const spinner = header.querySelector('.thinking-spinner');
                if (spinner) spinner.remove();
                const title = header.querySelector('.thinking-title');
                if (title) title.textContent = 'Agent completed';
            }
            // Auto-collapse after completion
            this.thinkingContainer.classList.add('collapsed');
        }
    }

    addThinkingStep(text, time) {
        if (!this.thinkingContainer) return;

        const stepsDiv = this.thinkingContainer.querySelector('.thinking-steps');
        if (!stepsDiv) return;

        const step = document.createElement('div');
        step.className = 'thinking-step';
        step.innerHTML = `
            <span class="step-text">${this.escapeHtml(text)}</span>
            <span class="step-time">${time}</span>
        `;

        stepsDiv.appendChild(step);

        // Animate in
        requestAnimationFrame(() => {
            step.classList.add('visible');
        });

        this.scrollToBottom();
    }

    updateLastThinkingStep(status) {
        if (!this.thinkingContainer) return;

        const stepsDiv = this.thinkingContainer.querySelector('.thinking-steps');
        if (!stepsDiv) return;

        const lastStep = stepsDiv.lastElementChild;
        if (lastStep) {
            lastStep.classList.add('completed');
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    addMessage(sender, content, isError = false, isClarification = false, clarificationOptions = null) {
        if (!this.chatMessages) return;

        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        if (isClarification) {
            messageDiv.classList.add('clarification');
        }
        if (sender === 'bot' && isError) {
            messageDiv.classList.add('error');
        }

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        const avatarImg = document.createElement('img');
        avatarImg.alt = sender === 'user' ? 'User' : 'Assistant';
        avatarImg.className = 'message-avatar-img';
        avatarImg.src = sender === 'user'
            ? '/static/icons/user-avatar.png'
            : '/static/icons/assistant-avatar.png';
        avatar.appendChild(avatarImg);

        const messageBody = document.createElement('div');

        if (sender === 'bot' && isClarification) {
            const label = document.createElement('div');
            label.className = 'clarification-label';
            label.textContent = 'Clarification needed';
            messageBody.appendChild(label);
        }

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatMessageContent(content);

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString();

        messageBody.appendChild(contentDiv);

        if (
            sender === 'bot' &&
            isClarification &&
            Array.isArray(clarificationOptions) &&
            clarificationOptions.length > 0
        ) {
            const optionsContainer = document.createElement('div');
            optionsContainer.className = 'clarification-options';
            clarificationOptions.forEach((optionText) => {
                const optionBtn = document.createElement('button');
                optionBtn.type = 'button';
                optionBtn.className = 'sample-query';
                optionBtn.textContent = optionText;
                optionBtn.addEventListener('click', () => {
                    if (this.messageInput) {
                        this.messageInput.value = optionText;
                        this.handleInputChange();
                        this.sendMessage();
                    }
                });
                optionsContainer.appendChild(optionBtn);
            });
            messageBody.appendChild(optionsContainer);
        }

        if (sender === 'bot' && isError) {
            const actions = document.createElement('div');
            actions.className = 'message-actions';
            const retryBtn = document.createElement('button');
            retryBtn.type = 'button';
            retryBtn.className = 'retry-btn';
            retryBtn.textContent = 'Retry';
            retryBtn.addEventListener('click', () => this.retryLastUserMessage());
            actions.appendChild(retryBtn);
            messageBody.appendChild(actions);
        }

        messageBody.appendChild(timeDiv);

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageBody);

        const shouldAutoScroll = this.isUserNearBottom || !this.chatMessages.hasChildNodes();

        this.chatMessages.appendChild(messageDiv);

        if (shouldAutoScroll) {
            this.scrollToBottom();
        } else {
            this.showJumpToLatest();
        }
    }

    formatMessageContent(content) {
        if (typeof content !== 'string') {
            content = String(content ?? '');
        }

        const escaped = content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');

        return escaped
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    setLoading(loading) {
        this.isLoading = loading;
        if (this.sendBtn) {
            const hasText = this.messageInput && this.messageInput.value.trim().length > 0;
            this.sendBtn.disabled = loading || !hasText;
        }
    }

    showTypingIndicator() {
        if (this.typingIndicator) {
            this.typingIndicator.hidden = false;
            this.typingIndicator.classList.add('show');
        }
    }

    hideTypingIndicator() {
        if (this.typingIndicator) {
            this.typingIndicator.classList.remove('show');
            this.typingIndicator.hidden = true;
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
        if (!this.conversationHistory) return;

        if (this.conversations.length === 0) {
            this.conversationHistory.innerHTML = `
                <div class="history-empty">
                    <div class="empty-icon">
                        <img src="/static/icons/no_conversations.png" alt="" class="history-empty-icon-img" />
                    </div>
                    <p>No conversations yet</p>
                    <small>Start chatting to see your conversation history</small>
                </div>
            `;
            return;
        }
        
        this.conversationHistory.innerHTML = '';
        
        this.conversations.forEach(conversation => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'conversation-item';
            if (conversation.id === this.currentConversationId) {
                item.classList.add('active');
            }
            item.setAttribute('aria-label', `Conversation: ${conversation.title}`);
            
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
        this.isUserNearBottom = true;
        
        // Clear and rebuild chat messages
        if (this.chatMessages) {
            this.chatMessages.innerHTML = '';
        }
        
        conversation.messages.forEach(message => {
            this.addMessage(
                message.role === 'user' ? 'user' : 'bot',
                message.content,
                false,
                message.content.includes('🤔'),
                null
            );
        });
        
        this.renderConversationHistory();
        this.scrollToBottom();
    }

    renderWelcomeState() {
        if (!this.chatMessages) return;
        this.chatMessages.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-content">
                        <h3>Welcome to ERP Assistant!</h3>
                        <p>I can help you query your ERP database using natural language. Try asking questions like:</p>
                        <div class="sample-queries">
                            <button class="sample-query" type="button" data-query="How many customers do we have?">
                                How many customers do we have?
                            </button>
                            <button class="sample-query" type="button" data-query="Show me our top 5 products by sales">
                                Show me our top 5 products by sales
                            </button>
                            <button class="sample-query" type="button" data-query="What were our total sales last month?">
                                What were our total sales last month?
                            </button>
                            <button class="sample-query" type="button" data-query="Which products are low in stock?">
                                Which products are low in stock?
                            </button>
                        </div>
                    </div>
                </div>
            `;
    }

    startNewChat() {
        if (this.isLoading) return;
        this.messages = [];
        this.currentConversationId = null;
        this.lastWasClarification = false;
        this.isUserNearBottom = true;
        this.hideJumpToLatest();
        this.hideTypingIndicator();
        this.renderWelcomeState();
        this.renderConversationHistory();
        this.scrollToBottom();
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
            this.renderWelcomeState();
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

    getFocusableElements(container) {
        if (!container) return [];
        const selectors = [
            'button',
            '[href]',
            'input',
            'select',
            'textarea',
            '[tabindex]:not([tabindex="-1"])'
        ];
        return Array.from(container.querySelectorAll(selectors.join(','))).filter(
            (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true'
        );
    }

    handleModalKeyDown(event, modal) {
        if (event.key !== 'Tab') return;
        const focusable = this.getFocusableElements(modal);
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (event.shiftKey) {
            if (document.activeElement === first) {
                event.preventDefault();
                last.focus();
            }
        } else if (document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    showModal(type) {
        const modal = type === 'help' ? this.helpModal : this.settingsModal;
        if (!modal) return;

        this.activeModal = modal;
        this.lastFocusedElement =
            document.activeElement && document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null;

        modal.classList.add('show');
        modal.setAttribute('aria-hidden', 'false');

        if (type === 'settings') {
            this.loadSettingsToModal();
        }

        const focusable = this.getFocusableElements(modal);
        if (focusable.length > 0) {
            focusable[0].focus();
        } else {
            const modalContent = modal.querySelector('.modal-content');
            if (modalContent && typeof modalContent.focus === 'function') {
                modalContent.focus();
            }
        }
    }

    hideModal(type) {
        const modal = type === 'help' ? this.helpModal : this.settingsModal;
        if (!modal) return;

        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');

        if (this.activeModal === modal) {
            this.activeModal = null;
        }

        if (this.lastFocusedElement && typeof this.lastFocusedElement.focus === 'function') {
            this.lastFocusedElement.focus();
            this.lastFocusedElement = null;
        }
    }

    loadSettingsToModal() {
        if (this.serviceUrlInput) {
            this.serviceUrlInput.value = this.apiKeyIsServerManaged
                ? `${window.location.origin}/process_conversation`
                : this.serviceUrl || this.serviceUrlInput.value;
        }
        if (this.apiKeyInput && !this.apiKeyIsServerManaged) {
            this.apiKeyInput.value = this.apiKey || '';
        }
        if (this.sessionIdInput) {
            this.sessionIdInput.value = this.sessionId;
        }
    }

    resetSettings() {
        this.sessionId = this.generateSessionId();
        this.apiKey = null;
        if (this.apiKeyInput && !this.apiKeyIsServerManaged) {
            this.apiKeyInput.value = '';
        }
        this.loadSettingsToModal();
        this.saveSettings();
    }

    saveSettings() {
        if (!this.apiKeyIsServerManaged && this.apiKeyInput) {
            const value = this.apiKeyInput.value.trim();
            this.apiKey = value || null;
        }

        try {
            localStorage.setItem(
                'erp_chatbot_settings',
                JSON.stringify({
                    sessionId: this.sessionId
                })
            );
        } catch (error) {
            console.error('Error saving settings:', error);
        }

        this.hideModal('settings');
        this.checkServiceHealth();
        this.showNotification('Settings saved successfully!', 'success');
    }

    loadSettings() {
        try {
            const saved = localStorage.getItem('erp_chatbot_settings');
            if (saved) {
                const settings = JSON.parse(saved);
                if (settings.sessionId) {
                    this.sessionId = settings.sessionId;
                }
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

    stopCurrentRequest() {
        this.stopRequested = true;
        if (this.currentRequestController) {
            this.currentRequestController.abort();
        }
        if (this.streamReader) {
            try {
                this.streamReader.cancel();
            } catch (e) {
                console.warn('Error canceling stream:', e);
            }
            this.streamReader = null;
        }
        this.hideThinkingContainer();
    }

    retryLastUserMessage() {
        if (this.isLoading || !this.messageInput) return;
        const lastUserMessage = [...this.messages].reverse().find((m) => m.role === 'user');
        if (!lastUserMessage) return;
        this.messageInput.value = lastUserMessage.content || '';
        this.handleInputChange();
        this.sendMessage();
    }

    logInteraction(userInput, response, metadata = {}) {
        const logEntry = {
            timestamp: new Date().toISOString(),
            sessionId: this.sessionId,
            userInput,
            response,
            conversationId: this.currentConversationId,
            ...metadata
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
