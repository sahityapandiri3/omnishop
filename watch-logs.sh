#!/bin/bash
# Real-time log watcher for Omnishop backend
# Usage: ./watch-logs.sh [filter]
# Example: ./watch-logs.sh "CACHE"
# Example: ./watch-logs.sh (no filter - shows all relevant logs)

LOG_FILE="/tmp/claude/-Users-sahityapandiri-Omnishop/tasks/bb74ef5.output"

# Default filter for relevant logs
DEFAULT_FILTER="Precompute|CACHE|segment-at-point|Segmenting|visualiz|Error|error|POST|←"

FILTER="${1:-$DEFAULT_FILTER}"

echo "=========================================="
echo "  Omnishop Backend Log Watcher"
echo "=========================================="
echo "Filter: $FILTER"
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found. Is the backend running?"
    echo "Start backend with: cd /Users/sahityapandiri/Omnishop/api && python3 -m uvicorn main:app --reload"
    exit 1
fi

# Tail with color highlighting
tail -f "$LOG_FILE" | grep --line-buffered -E "$FILTER" | while read line; do
    # Color code different log types
    if echo "$line" | grep -q "CACHE HIT"; then
        echo -e "\033[32m$line\033[0m"  # Green for cache hits
    elif echo "$line" | grep -q "CACHE MISS"; then
        echo -e "\033[33m$line\033[0m"  # Yellow for cache misses
    elif echo "$line" | grep -q "Precompute"; then
        echo -e "\033[36m$line\033[0m"  # Cyan for precompute
    elif echo "$line" | grep -q -i "error"; then
        echo -e "\033[31m$line\033[0m"  # Red for errors
    elif echo "$line" | grep -q "← 200"; then
        echo -e "\033[32m$line\033[0m"  # Green for success responses
    elif echo "$line" | grep -q "← [45]"; then
        echo -e "\033[31m$line\033[0m"  # Red for error responses
    else
        echo "$line"
    fi
done
