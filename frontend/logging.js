class LoggingDisplay {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container with id ${containerId} not found`);
        }
        
        this.setupUI();
    }
    
    setupUI() {
        // Create the logging panel
        this.loggingPanel = document.createElement('div');
        this.loggingPanel.className = 'logging-panel';
        
        // Create header with title and clear button
        const header = document.createElement('div');
        header.className = 'logging-header';
        
        const title = document.createElement('h3');
        title.textContent = 'Execution Log';
        
        const clearButton = document.createElement('button');
        clearButton.textContent = 'Clear';
        clearButton.onclick = () => this.clear();
        
        header.appendChild(title);
        header.appendChild(clearButton);
        
        // Create log content area
        this.logContent = document.createElement('div');
        this.logContent.className = 'logging-content';
        
        // Assemble the panel
        this.loggingPanel.appendChild(header);
        this.loggingPanel.appendChild(this.logContent);
        
        // Add to container
        this.container.appendChild(this.loggingPanel);
    }
    
    log(message, type = 'info') {
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;
        
        const timestamp = document.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();
        
        const content = document.createElement('span');
        content.className = 'log-content';
        content.textContent = message;
        
        entry.appendChild(timestamp);
        entry.appendChild(content);
        
        this.logContent.appendChild(entry);
        this.logContent.scrollTop = this.logContent.scrollHeight;
    }
    
    logThinking(steps) {
        const thinkingSection = document.createElement('div');
        thinkingSection.className = 'thinking-section';
        
        const header = document.createElement('div');
        header.className = 'thinking-header';
        header.textContent = 'Thinking Steps:';
        thinkingSection.appendChild(header);
        
        steps.forEach((step, index) => {
            const stepElement = document.createElement('div');
            stepElement.className = 'thinking-step';
            stepElement.textContent = `${index + 1}. ${step}`;
            thinkingSection.appendChild(stepElement);
        });
        
        this.logContent.appendChild(thinkingSection);
        this.logContent.scrollTop = this.logContent.scrollHeight;
    }
    
    logQuery(query, parameters = null) {
        const querySection = document.createElement('div');
        querySection.className = 'query-section';
        
        const queryContent = document.createElement('pre');
        queryContent.className = 'query-content';
        queryContent.textContent = query;
        
        querySection.appendChild(queryContent);
        
        if (parameters) {
            const paramsContent = document.createElement('pre');
            paramsContent.className = 'query-params';
            paramsContent.textContent = 'Parameters:\n' + JSON.stringify(parameters, null, 2);
            querySection.appendChild(paramsContent);
        }
        
        this.logContent.appendChild(querySection);
        this.logContent.scrollTop = this.logContent.scrollHeight;
    }
    
    logResults(results) {
        const resultsSection = document.createElement('div');
        resultsSection.className = 'results-section';
        
        const header = document.createElement('div');
        header.className = 'results-header';
        header.textContent = 'Query Results:';
        resultsSection.appendChild(header);
        
        const content = document.createElement('pre');
        content.className = 'results-content';
        content.textContent = JSON.stringify(results, null, 2);
        resultsSection.appendChild(content);
        
        this.logContent.appendChild(resultsSection);
        this.logContent.scrollTop = this.logContent.scrollHeight;
    }
    
    logError(error) {
        const entry = document.createElement('div');
        entry.className = 'log-entry log-error';
        
        const timestamp = document.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();
        
        const content = document.createElement('span');
        content.className = 'log-content';
        content.textContent = `Error: ${error}`;
        
        entry.appendChild(timestamp);
        entry.appendChild(content);
        
        this.logContent.appendChild(entry);
        this.logContent.scrollTop = this.logContent.scrollHeight;
    }
    
    clear() {
        while (this.logContent.firstChild) {
            this.logContent.removeChild(this.logContent.firstChild);
        }
    }
} 