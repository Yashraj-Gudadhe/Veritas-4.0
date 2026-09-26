python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
SERVER_PID=$!
for i in {1..15}; do
    if curl -s http://localhost:8000/api/health > health.json; then
        echo "Server is up!"
        cat health.json
        break
    fi
    sleep 2
done
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null
echo "Server stopped."
