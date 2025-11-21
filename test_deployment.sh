#!/bin/bash
# Test STRAT Stock Scanner Deployment
# Usage: ./test_deployment.sh <your-railway-url>

RAILWAY_URL=$1

if [ -z "$RAILWAY_URL" ]; then
    echo "Usage: ./test_deployment.sh https://your-app.up.railway.app"
    exit 1
fi

echo "Testing STRAT Stock Scanner at: $RAILWAY_URL"
echo ""

echo "1. Testing Health Endpoint..."
curl -s "$RAILWAY_URL/health" | grep -q "ok" && echo "   SUCCESS" || echo "   FAILED"
echo ""

echo "2. Testing OAuth Protected Resource Metadata..."
curl -s "$RAILWAY_URL/.well-known/oauth-protected-resource" | grep -q "authorization_servers" && echo "   SUCCESS" || echo "   FAILED"
echo ""

echo "3. Testing MCP Endpoint (should require auth)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$RAILWAY_URL/mcp")
if [ "$HTTP_CODE" = "401" ]; then
    echo "   SUCCESS (Correctly requires authentication)"
elif [ "$HTTP_CODE" = "200" ]; then
    echo "   WARNING (MCP endpoint accessible without auth - check middleware)"
else
    echo "   FAILED (Unexpected HTTP $HTTP_CODE)"
fi

echo ""
echo "Deployment test complete!"
