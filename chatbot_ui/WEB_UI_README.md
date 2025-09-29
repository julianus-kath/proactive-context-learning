# ERP Chatbot - Modern Web UI

A sleek, responsive web interface for the ERP Chatbot system, replacing the previous Streamlit implementation with a modern HTML/CSS/JavaScript frontend.

## Features

### 🎨 Modern Design
- **Color Palette**: Professional dark theme with blue accents
  - Primary Dark: `#2B3137` (backgrounds, sidebars)
  - Primary Accent: `#00B8FF` (buttons, highlights)
  - Light Background: `#F8F8F8` (message areas)
- **Typography**: Inter font family for clean, readable text
- **Responsive**: Works seamlessly on desktop and mobile devices

### 💬 Enhanced Chat Experience
- **Two-column layout**: Conversation history on the left, active chat on the right
- **Message bubbles**: User messages on light background, bot messages on blue
- **Real-time typing**: Auto-resizing input field with character counter
- **Sample queries**: Quick-start buttons for common questions
- **Clarification support**: Special styling for clarification requests

### 📱 Responsive Design
- **Desktop-first**: Optimized for desktop use with full two-column layout
- **Mobile-friendly**: Stacked layout on smaller screens
- **Touch-friendly**: Large buttons and touch targets for mobile users

### 🔧 Advanced Features
- **Conversation history**: Persistent storage of chat sessions
- **Settings modal**: Configure API endpoints and keys
- **Help system**: Built-in help with sample queries
- **Status indicators**: Real-time service health monitoring
- **Keyboard shortcuts**: Enter to send, Shift+Enter for new line

## Quick Start

### Option 1: Use the Startup Script (Recommended)
```bash
cd chatbot_ui
python start_web_ui.py
```

This will automatically start both the LangGraph service and the web UI.

### Option 2: Manual Startup
```bash
# Terminal 1: Start LangGraph service
cd chatbot_ui
python langgraph_service.py

# Terminal 2: Start Web UI
cd chatbot_ui
python web_app.py
```

### Access the Application
- **Web UI**: http://localhost:3000
- **LangGraph API**: http://localhost:5001

## File Structure

```
chatbot_ui/
├── index.html          # Main HTML interface
├── styles.css          # Modern CSS styling
├── script.js           # JavaScript functionality
├── web_app.py          # FastAPI server for web UI
├── langgraph_service.py # Backend API service
├── start_web_ui.py     # Startup script
├── app.py              # Legacy Streamlit app (kept for compatibility)
└── requirements.txt    # Python dependencies
```

## Configuration

### Environment Variables
Create a `.env` file in the parent directory with:
```env
OPENAI_API_KEY=your_openai_api_key_here
LANGGRAPH_URL=http://localhost:5001
API_KEY=supersecretapikey
```

### Settings Modal
Access settings through the gear icon in the top-right corner:
- **Service URL**: LangGraph service endpoint
- **API Key**: Authentication key for the service
- **Session ID**: Unique identifier for your session

## Architecture

### Frontend (HTML/CSS/JS)
- **Pure JavaScript**: No frameworks, lightweight and fast
- **Modern CSS**: CSS Grid, Flexbox, custom properties
- **Responsive design**: Mobile-first approach with desktop enhancements

### Backend Integration
- **FastAPI**: Serves the web interface and static files
- **LangGraph Service**: Handles AI processing and database queries
- **MCP Server**: Manages database connections and operations

### Data Flow
1. User enters query in web interface
2. JavaScript sends request to LangGraph service
3. LangGraph processes query through AI agents
4. Response displayed in chat interface
5. Conversation saved to browser localStorage

## Customization

### Color Scheme
The color palette is defined in CSS custom properties at the top of `styles.css`:
```css
:root {
    --primary-dark: #2B3137;
    --primary-accent: #00B8FF;
    --light-background: #F8F8F8;
    /* ... more colors */
}
```

### Sample Queries
Edit the sample queries in `index.html`:
```html
<button class="sample-query" data-query="Your custom query">
    Your custom query
</button>
```

### Styling
All styles are contained in `styles.css` with:
- **Responsive breakpoints**: 768px and 480px
- **Smooth animations**: 0.2-0.3s transitions
- **Accessibility**: High contrast support, focus indicators

## Browser Support

- **Chrome**: 90+
- **Firefox**: 88+
- **Safari**: 14+
- **Edge**: 90+

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Check what's using the port
   lsof -i :3000
   lsof -i :5001
   ```

2. **Service not responding**
   - Check that MCP server is running on port 8000
   - Verify PostgreSQL database is accessible
   - Check OpenAI API key is set correctly

3. **Conversation history not saving**
   - Check browser localStorage is enabled
   - Clear browser cache and try again

### Debug Mode
Open browser developer tools (F12) to see:
- Network requests to the API
- JavaScript console logs
- Local storage contents

## Migration from Streamlit

The new web UI maintains compatibility with the existing backend while providing:
- **Better performance**: No Python server-side rendering
- **Modern UX**: Responsive design and smooth animations
- **Offline capability**: Conversation history stored locally
- **Customization**: Easy to modify colors, layout, and features

The original Streamlit app (`app.py`) is kept for backward compatibility.

## Development

### Adding New Features
1. **Frontend**: Modify `script.js` for functionality, `styles.css` for styling
2. **Backend**: Update `langgraph_service.py` for new API endpoints
3. **UI**: Edit `index.html` for new interface elements

### Testing
- **Manual testing**: Use the web interface
- **API testing**: Use the FastAPI docs at http://localhost:5001/docs
- **Browser testing**: Test on different devices and browsers

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the browser console for errors
3. Check the LangGraph service logs
4. Verify all prerequisites are running