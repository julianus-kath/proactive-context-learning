#!/bin/bash

# Update .env file with proxy configuration
ENV_FILE="/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/.env"

echo "🔧 Updating .env file with proxy configuration..."

# Check if proxy settings already exist
if grep -q "DB_MODE=proxy" "$ENV_FILE"; then
    echo "✅ Proxy configuration already exists in .env file"
else
    echo "📝 Adding proxy configuration to .env file..."
    
    # Add proxy configuration
    cat >> "$ENV_FILE" << EOF

# Database Proxy Configuration (for ERP access)
DB_MODE=proxy
PROXY_BASE_URL=http://172.20.10.3:5000
PROXY_DEFAULT_CONN=corp_sql_erp
PROXY_API_KEY=dummy-key-for-testing

EOF
    
    echo "✅ Proxy configuration added to .env file"
fi

echo "🎉 Environment configuration updated!"
echo ""
echo "Your .env file now includes:"
echo "  - DB_MODE=proxy (use Windows proxy for database access)"
echo "  - PROXY_BASE_URL=http://172.20.10.3:5000 (your Windows machine)"
echo "  - PROXY_DEFAULT_CONN=corp_sql_erp (your ERP database)"
echo "  - PROXY_API_KEY=dummy-key-for-testing (development key)"
echo ""
echo "🚀 You can now run: ./start_all_services.sh"