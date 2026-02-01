// Load dependencies
document.write('<script src="/static/js/response-formatter.js"></script>');

// Chat state
let conversationHistory = [];
let isProcessing = false;
let currentConversationId = null;
let hasWelcomeMessage = false;


// Initialize chat
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('chatInput');
    
    input.focus();
    
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !isProcessing) {
            sendMessage();
        }
    });
    
    // Show welcome message
    showWelcomeMessage();
    
    scrollToBottom();
    
    // Load conversation history sidebar
    loadConversationList();
    
    // Create new conversation automatically
    createNewConversation();
});

function showWelcomeMessage() {
    if (hasWelcomeMessage) return;
    
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <h3>👋 Welcome to your AI Finance Assistant!</h3>
            <p style="margin-bottom: 1rem; color: #6B7280;">I can help you understand your spending patterns and manage your finances better.</p>
            <p style="font-weight: 600; color: #667eea; margin-bottom: 0.5rem;">Try asking me:</p>
            <ul>
                <li>"What's my total expense this month?"</li>
                <li>"How much did I spend on food?"</li>
                <li>"Show me top 5 spending areas"</li>
                <li>"Compare this month vs last month"</li>
            </ul>
        </div>
    `;
    hasWelcomeMessage = true;
}

// ============= CONVERSATION MANAGEMENT =============

async function createNewConversation() {
    try {
        const response = await fetch('/api/chat/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'New Conversation' })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentConversationId = data.conversation.id;
            console.log('✅ New conversation created:', currentConversationId);
        }
    } catch (error) {
        console.error('Failed to create conversation:', error);
    }
}

async function loadConversationList() {
    try {
        const response = await fetch('/api/chat/conversations');
        const data = await response.json();
        
        if (data.success) {
            displayConversationList(data.conversations);
        }
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

function displayConversationList(conversations) {
    const sidebar = document.getElementById('conversationList');
    if (!sidebar) return;
    
    if (conversations.length === 0) {
        sidebar.innerHTML = `
            <div class="empty-state" style="padding: 2rem 1rem;">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">💬</div>
                <p style="color: rgba(255,255,255,0.8); font-size: 0.9rem;">No conversations yet</p>
                <p style="color: rgba(255,255,255,0.6); font-size: 0.8rem; margin-top: 0.25rem;">Start a new chat to begin!</p>
            </div>
        `;
        return;
    }
    
    sidebar.innerHTML = conversations.map(conv => `
        <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" 
             onclick="loadConversation(${conv.id})">
            <div class="conversation-title">${escapeHtml(conv.title)}</div>
            <div class="conversation-meta">
                <span class="message-count-badge">
                    💬 ${conv.message_count} ${conv.message_count === 1 ? 'message' : 'messages'}
                </span>
            </div>
            <button class="delete-conversation" onclick="deleteConversation(${conv.id}, event)">
                🗑️
            </button>
        </div>
    `).join('');
}

// Loads a conversation, renders messages, and auto-closes the sidebar
async function loadConversation(conversationId) {
    try {
        const response = await fetch(`/api/chat/conversations/${conversationId}`);
        const data = await response.json();
        
        if (data.success) {
            currentConversationId = conversationId;
            
            // Clear messages and hide welcome
            const messagesContainer = document.getElementById('chatMessages');
            messagesContainer.innerHTML = '';
            hasWelcomeMessage = true; // Prevent showing welcome again
            
            // If no messages, show empty state
            if (data.conversation.messages.length === 0) {
                messagesContainer.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">💬</div>
                        <h3>No messages yet</h3>
                        <p>Start the conversation!</p>
                    </div>
                `;
            } else {
                // Load messages
                data.conversation.messages.forEach(msg => {
                    if (msg.role === 'user') {
                        addMessageToUI(msg.content, 'user', false);
                    } else {
                        addBotResponseSimple(msg.content, msg.confidence);
                    }
                });
            }
            
            // Update sidebar and close it
            loadConversationList();
            closeSidebar();
            scrollToBottom();
        }
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}


async function deleteConversation(conversationId, event) {
    event.stopPropagation();
    
    if (!confirm('Delete this conversation?')) return;
    
    try {
        const response = await fetch(`/api/chat/conversations/${conversationId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // If deleted current conversation, create new one
            if (conversationId === currentConversationId) {
                await createNewConversation();
                clearChatUI();
            }
            
            loadConversationList();
            showNotification('Conversation deleted', 'success');
        }
    } catch (error) {
        console.error('Failed to delete conversation:', error);
    }
}

function newChat() {
    createNewConversation();
    clearChatUI();
    loadConversationList();
    closeSidebar();
}

function clearChatUI() {
    hasWelcomeMessage = false;
    showWelcomeMessage();
    document.getElementById('quickSuggestions').style.display = 'flex';
}

// ============= MESSAGE HANDLING =============

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const query = input.value.trim();
    
    if (!query || isProcessing) return;
    
    isProcessing = true;
    input.value = '';
    
    await sendQuery(query);
    
    isProcessing = false;
    input.focus();
}

function sendQuickQuery(query) {
    if (isProcessing) return;
    document.getElementById('chatInput').value = query;
    sendMessage();
}

async function sendQuery(query) {

    if (hasWelcomeMessage) {
        const welcomeMsg = document.querySelector('.welcome-message');
        if (welcomeMsg) {
            welcomeMsg.remove();
        }
    }

    // Add user message to UI
    addMessageToUI(query, 'user', true);
    
    // NOTE: No separate saveMessage() call needed here.
    // The backend POST /messages endpoint saves both the user
    // message and the AI response in a single transaction.
    
    document.getElementById('quickSuggestions').style.display = 'none';
    showTypingIndicator();
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        
        const response = await fetch(`/api/chat/conversations/${currentConversationId}/messages`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: query }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        hideTypingIndicator();
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Backend already saved both messages — just render the response
            const result = {
                response: data.assistant_message.content,
                intent: data.assistant_message.intent,
                confidence: data.confidence,
                data: data.data,
                chart_type: data.chart_type,
                processing_time: data.understanding?.processing_time
            };
            
            addBotResponse(result);
            
            if (result.confidence && result.confidence < 50) {
                addConfidenceWarning(result.confidence);
            }
            
            // Refresh conversation list
            loadConversationList();
        }
        
    } catch (error) {
        hideTypingIndicator();
        
        if (error.name === 'AbortError') {
            addErrorMessage('Request timed out. Please try again.');
        } else if (error.message.includes('Failed to fetch')) {
            addErrorMessage('Network error. Please check your connection.');
        } else {
            console.error('Query error:', error);
            addErrorMessage('Sorry, something went wrong. Please try again.');
        }
    }
    
    scrollToBottom();
}

// ============= UI FUNCTIONS =============

function addMessageToUI(text, sender, animate = true) {
    const messagesContainer = document.getElementById('chatMessages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    if (animate) messageDiv.style.animation = 'messageSlideIn 0.3s ease-out';
    
    const avatar = sender === 'user' ? '👤' : '🤖';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">
                <p>${escapeHtml(text)}</p>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    conversationHistory.push({ text, sender, timestamp: Date.now() });
}

function addBotResponseSimple(text, confidence = null) {
    const messagesContainer = document.getElementById('chatMessages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    let contentHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-bubble">
    `;
    
    if (confidence) {
        const confidenceClass = confidence > 80 ? 'high' : confidence > 60 ? 'medium' : 'low';
        const confidenceEmoji = confidence > 80 ? '🎯' : confidence > 60 ? '✓' : '~';
        contentHTML += `
            <div class="confidence-badge ${confidenceClass}">
                <span class="confidence-icon">${confidenceEmoji}</span>
                ${confidence.toFixed(0)}% confident
            </div>
        `;
    }
    
    contentHTML += `
                <p>${escapeHtml(text)}</p>
            </div>
        </div>
    `;
    
    messageDiv.innerHTML = contentHTML;
    messagesContainer.appendChild(messageDiv);
}

function addBotResponse(result) {
    const messagesContainer = document.getElementById('chatMessages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    messageDiv.style.animation = 'messageSlideIn 0.3s ease-out';
    
    let contentHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-bubble">
    `;
    
    if (result.confidence) {
        const confidenceClass = result.confidence > 80 ? 'high' : 
                               result.confidence > 60 ? 'medium' : 'low';
        const confidenceEmoji = result.confidence > 80 ? '🎯' : 
                               result.confidence > 60 ? '✓' : '~';
        contentHTML += `
            <div class="confidence-badge ${confidenceClass}">
                <span class="confidence-icon">${confidenceEmoji}</span>
                ${result.confidence.toFixed(0)}% confident
            </div>
        `;
    }
    
    const formattedResponse = ResponseFormatter.formatResponse(result.response);
    contentHTML += `<div class="response-text">${formattedResponse}</div>`;
    
    if (result.processing_time) {
        contentHTML += `<p class="processing-time">⚡ Processed in ${result.processing_time}</p>`;
    }
    
    if (result.data && Object.keys(result.data).length > 0) {
        if (result.data.suggestions) {
            contentHTML += ResponseFormatter.formatSuggestions(result.data.suggestions);
        } else if (result.data.top_items) {
            contentHTML += ResponseFormatter.createSummaryCard('Top Spending', result.data.top_items);
        } else {
            contentHTML += ResponseFormatter.formatDataTable(result.data);
        }
    }
    
    contentHTML += `</div>`;
    
    if (result.chart_type && result.data) {
        const chartId = 'chart_' + Date.now();
        contentHTML += `
            <div class="message-chart">
                <div class="chart-loading" id="loading_${chartId}">
                    <div class="spinner"></div>
                    <p>Generating chart...</p>
                </div>
                <canvas id="${chartId}" style="display: none;"></canvas>
            </div>
        `;
        
        setTimeout(() => {
            renderChart(chartId, result.chart_type, result.data);
            setTimeout(() => {
                const loadingEl = document.getElementById(`loading_${chartId}`);
                const canvasEl = document.getElementById(chartId);
                if (loadingEl && canvasEl) {
                    loadingEl.style.display = 'none';
                    canvasEl.style.display = 'block';
                    canvasEl.style.animation = 'fadeIn 0.3s ease-in';
                }
            }, 300);
        }, 100);
    }
    
    contentHTML += `</div>`;
    
    messageDiv.innerHTML = contentHTML;
    messagesContainer.appendChild(messageDiv);
    
    conversationHistory.push({ 
        text: result.response, 
        sender: 'bot',
        timestamp: Date.now()
    });
}

function addConfidenceWarning(confidence) {
    const messagesContainer = document.getElementById('chatMessages');
    const warningDiv = document.createElement('div');
    warningDiv.className = 'confidence-warning';
    warningDiv.innerHTML = `
        <div class="warning-content">
            ⚠️ I'm ${confidence.toFixed(0)}% confident about this answer. 
            Try rephrasing if needed.
        </div>
    `;
    messagesContainer.appendChild(warningDiv);
}

function addErrorMessage(errorText) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message error-message';
    messageDiv.innerHTML = `
        <div class="message-avatar">❌</div>
        <div class="message-content">
            <div class="message-bubble error-bubble">
                <p><strong>Error:</strong> ${escapeHtml(errorText)}</p>
            </div>
        </div>
    `;
    messagesContainer.appendChild(messageDiv);
}

// ============= CHART RENDERING =============

function renderChart(chartId, chartType, data) {
    const ctx = document.getElementById(chartId);
    if (!ctx) return;
    
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: true,
        animation: {
            duration: 600,
            easing: 'easeInOutQuart'
        },
        plugins: {
            legend: {
                labels: {
                    font: {
                        size: 12,
                        family: "'Inter', -apple-system, sans-serif"
                    },
                    padding: 10,
                    usePointStyle: true
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                padding: 12,
                titleFont: { size: 14, weight: 'bold' },
                bodyFont: { size: 13 },
                cornerRadius: 8,
                displayColors: true
            }
        },
        interaction: {
            mode: 'index',
            intersect: false
        }
    };
    
    let chartConfig;
    
    if (chartType === 'comparison_bar') {
        chartConfig = {
            type: 'bar',
            data: {
                labels: ['Last Month', 'This Month'],
                datasets: [{
                    label: 'Expenses',
                    data: [data.last_month, data.this_month],
                    backgroundColor: ['rgba(148, 163, 184, 0.8)', 'rgba(79, 70, 229, 0.8)'],
                    borderColor: ['rgb(148, 163, 184)', 'rgb(79, 70, 229)'],
                    borderWidth: 2,
                    borderRadius: 8
                }]
            },
            options: {
                ...commonOptions,
                plugins: {
                    ...commonOptions.plugins,
                    legend: { display: false },
                    title: {
                        display: true,
                        text: 'Monthly Comparison',
                        font: { size: 16, weight: 'bold' },
                        padding: 20
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: value => '₹' + value.toLocaleString('en-IN')
                        }
                    }
                }
            }
        };
    } 
    else if (chartType === 'top_spending_bar') {
        const colors = [
            'rgba(79, 70, 229, 0.8)', 'rgba(16, 185, 129, 0.8)',
            'rgba(245, 158, 11, 0.8)', 'rgba(239, 68, 68, 0.8)',
            'rgba(139, 92, 246, 0.8)'
        ];
        
        chartConfig = {
            type: 'bar',
            data: {
                labels: data.top_items.map(item => item.name),
                datasets: [{
                    label: 'Spending',
                    data: data.top_items.map(item => item.amount),
                    backgroundColor: colors.slice(0, data.top_items.length),
                    borderRadius: 8
                }]
            },
            options: {
                ...commonOptions,
                indexAxis: 'y',
                plugins: {
                    ...commonOptions.plugins,
                    legend: { display: false },
                    title: {
                        display: true,
                        text: 'Top 5 Spending Areas',
                        font: { size: 16, weight: 'bold' },
                        padding: 20
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            callback: value => '₹' + value.toLocaleString('en-IN')
                        }
                    }
                }
            }
        };
    }
    else if (chartType === 'trend_line') {
        chartConfig = {
            type: 'line',
            data: {
                labels: data.months.map(m => m.month.substring(0, 3)),
                datasets: [{
                    label: 'Monthly Expenses',
                    data: data.months.map(m => m.total),
                    borderColor: 'rgb(79, 70, 229)',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointBackgroundColor: 'rgb(79, 70, 229)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                ...commonOptions,
                plugins: {
                    ...commonOptions.plugins,
                    legend: { display: false },
                    title: {
                        display: true,
                        text: '6-Month Spending Trend',
                        font: { size: 16, weight: 'bold' },
                        padding: 20
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: value => '₹' + value.toLocaleString('en-IN')
                        }
                    }
                }
            }
        };
    }
    else if (chartType === 'payment_pie') {
        const pieColors = [
            'rgba(79, 70, 229, 0.8)', 'rgba(16, 185, 129, 0.8)',
            'rgba(245, 158, 11, 0.8)', 'rgba(239, 68, 68, 0.8)',
            'rgba(139, 92, 246, 0.8)'
        ];
        
        chartConfig = {
            type: 'doughnut',
            data: {
                labels: data.payment_methods.map(pm => pm.method),
                datasets: [{
                    data: data.payment_methods.map(pm => pm.total),
                    backgroundColor: pieColors,
                    borderColor: '#fff',
                    borderWidth: 3,
                    hoverOffset: 10
                }]
            },
            options: {
                ...commonOptions,
                cutout: '60%',
                plugins: {
                    ...commonOptions.plugins,
                    title: {
                        display: true,
                        text: 'Payment Methods',
                        font: { size: 16, weight: 'bold' },
                        padding: 20
                    },
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    }
                }
            }
        };
    }
    
    if (chartConfig) {
        const existingChart = Chart.getChart(chartId);
        if (existingChart) existingChart.destroy();
        
        requestAnimationFrame(() => {
            new Chart(ctx, chartConfig);
        });
    }
}

// ============= UTILITY FUNCTIONS =============

function escapeHtml(text) {
    const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
    return text.replace(/[&<>"']/g, m => map[m]);
}

function showTypingIndicator() {
    document.getElementById('typingIndicator').style.display = 'block';
    scrollToBottom();
}

function hideTypingIndicator() {
    document.getElementById('typingIndicator').style.display = 'none';
}

function scrollToBottom() {
    const messagesContainer = document.getElementById('chatMessages');
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);
}

function clearChat() {
    if (!confirm('Start a new conversation?')) return;
    newChat();
}

function clearContext() {
    fetch('/api/clear-context', { method: 'POST' })
        .then(response => response.json())
        .then(data => console.log('Context cleared'))
        .catch(err => console.error('Failed to clear context:', err));
}

function showNotification(message, type = 'success') {
    console.log(`[${type}] ${message}`);
}

// ============= SIDEBAR TOGGLE FUNCTIONS =============

function toggleSidebar() {
    const sidebar = document.getElementById('chatSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
    
    // Load conversations when opening
    if (sidebar.classList.contains('open')) {
        loadConversationList();
    }
}

function closeSidebar() {
    const sidebar = document.getElementById('chatSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
}

// Close sidebar on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeSidebar();
    }
});