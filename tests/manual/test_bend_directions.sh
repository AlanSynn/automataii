#!/bin/bash
# Start the app in background and capture output
timeout 90 uv run python -m automataii 2>&1 | tee bend_test.log &
APP_PID=$!

# Wait for app to start
sleep 5

# Monitor the log file for bend direction changes
echo "Monitoring for bend direction changes..."
tail -f bend_test.log | grep -E "(Joint.*bend direction|IK: Passing bend|FABRIK: Received|Bend hint)" &
TAIL_PID=$!

# Wait for user to test
echo ""
echo "========================================"
echo "TEST INSTRUCTIONS:"
echo "1. Go to Editor tab"
echo "2. Click on elbow joints to change bend direction"
echo "3. Press Play to animate"
echo "4. Watch the log output above"
echo "========================================"
echo "Press Ctrl+C when done testing..."

wait $APP_PID
kill $TAIL_PID 2>/dev/null
