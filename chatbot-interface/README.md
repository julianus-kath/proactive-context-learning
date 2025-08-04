# Data Fusion Chatbot Interface

A simple, modern chatbot interface for interacting with the multi-agent data fusion system through n8n.

## Features

- Clean, responsive UI that works on desktop and mobile
- Real-time message exchange with the n8n webhook
- Support for basic text formatting (code blocks, lists)
- Visual feedback for message status and loading
- No server-side dependencies - pure HTML, CSS, and JavaScript

## Setup

1. Make sure n8n is running and your webhook is configured at:
   `http://localhost:5678/webhook-test/37694deb-f310-4a1e-b198-aaff97f28e8d`

2. Open `index.html` in a web browser to start using the chatbot

   You can use any local server to serve these files. For example:

   ```bash
   # Using Python
   python -m http.server 8000
   
   # Using Node.js (with http-server)
   npx http-server
   ```

3. Access the chatbot at `http://localhost:8000` (or whatever port you specified)

## n8n Webhook Configuration

For this interface to work properly, your n8n webhook should:

1. Accept POST requests with JSON data
2. Expect a `query` field containing the user's message
3. Return a JSON response with a `result` field containing the agent's response

Example webhook data structure:

**Request:**
```json
{
  "query": "Show me the top 5 customers by total sales amount"
}
```

**Response:**
```json
{
  "result": "Here are the top 5 customers by total sales amount:\n\n1. Acme Corp - $15,230\n2. Globex Industries - $12,450\n3. Initech Systems - $9,870\n4. Umbrella Corporation - $8,540\n5. Stark Industries - $7,650"
}
```

## Customization

- Edit `styles.css` to change the appearance
- Modify the example queries in `index.html`
- Adjust the webhook URL in `script.js` if needed

## Browser Compatibility

This interface works with all modern browsers:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Android Chrome)