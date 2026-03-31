1. git pull origin main
2. cd core
3. mkdir logs
4. cd logs
5. touch all_logs.log
6. cd ..
7. cd ..
8. docker compose build -d
9. docker compose up -d
10. docker compose exec ollama ollama pull llama3
11. docker compose exec ollama ollama pull llama3.2-vision