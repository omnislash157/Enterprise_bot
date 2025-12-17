#!/bin/bash
# Azure AD SSO Testing Script
# Tests backend endpoints to verify Azure AD configuration

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_BASE="${API_BASE:-http://localhost:8000}"

echo "=================================================="
echo "Azure AD SSO Testing Script"
echo "=================================================="
echo ""
echo "Testing backend at: $API_BASE"
echo ""

# Test 1: Health check
echo "Test 1: Health check"
echo "-------------------"
if curl -s -f "$API_BASE/health" > /dev/null; then
    echo -e "${GREEN}✓${NC} Backend is running"
else
    echo -e "${RED}✗${NC} Backend is not responding"
    exit 1
fi
echo ""

# Test 2: Auth config
echo "Test 2: Auth configuration"
echo "-------------------------"
CONFIG_RESPONSE=$(curl -s "$API_BASE/api/auth/config")
echo "Response: $CONFIG_RESPONSE"

AZURE_ENABLED=$(echo $CONFIG_RESPONSE | grep -o '"azure_ad_enabled":[^,}]*' | cut -d':' -f2 | tr -d ' ')
if [ "$AZURE_ENABLED" = "true" ]; then
    echo -e "${GREEN}✓${NC} Azure AD is enabled"
else
    echo -e "${YELLOW}⚠${NC} Azure AD is not enabled (check environment variables)"
fi
echo ""

# Test 3: Login URL generation
echo "Test 3: Login URL generation"
echo "----------------------------"
LOGIN_URL_RESPONSE=$(curl -s "$API_BASE/api/auth/login-url")
echo "Response: $LOGIN_URL_RESPONSE"

if echo $LOGIN_URL_RESPONSE | grep -q "login.microsoftonline.com"; then
    echo -e "${GREEN}✓${NC} Microsoft login URL generated successfully"

    # Extract and display the URL
    URL=$(echo $LOGIN_URL_RESPONSE | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
    echo ""
    echo "Microsoft Login URL:"
    echo "$URL"
else
    echo -e "${RED}✗${NC} Failed to generate Microsoft login URL"
    echo "Check AZURE_AD_TENANT_ID, AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET in .env"
fi
echo ""

# Test 4: Database connection (via main.py import test)
echo "Test 4: Database connectivity"
echo "----------------------------"
python3 -c "
import os
os.environ.setdefault('SKIP_STARTUP', '1')
try:
    from auth_service import get_auth_service
    auth = get_auth_service()
    print('${GREEN}✓${NC} Database connection successful')
except Exception as e:
    print('${YELLOW}⚠${NC} Database connection issue:', str(e))
" 2>/dev/null || echo -e "${YELLOW}⚠${NC} Could not test database connection"
echo ""

# Summary
echo "=================================================="
echo "Test Summary"
echo "=================================================="
echo ""
echo "If all tests passed, your backend is ready for Azure AD SSO!"
echo ""
echo "Next steps:"
echo "1. Ensure database migration has run (check migrations/verify_azure_oid.sql)"
echo "2. Start frontend: cd frontend && npm run dev"
echo "3. Visit http://localhost:5173 and test Microsoft login"
echo ""
echo "For production deployment:"
echo "- Add production redirect URI to Azure Portal"
echo "- Set VITE_API_URL in frontend environment"
echo "- Deploy both backend and frontend to Railway"
echo ""
