# Commands

## Docker (Recommended)
Run the entire application (Frontend, Backend, Database, MinIO) with a single command:
```bash
docker compose up -d --build
```
Access the services:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:3001
- **Mongo Express**: http://localhost:8081
- **MinIO Console**: http://localhost:9001 (minioadmin:minioadmin)

Stop the application:
```bash
docker compose down
```

## Manual Setup (Development)

### Backend
1. `cd backend`
2. `npm install`
3. `npm run dev`
   (http://localhost:3001)

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`
   (http://localhost:5173)

## Utilities
### MongoDB
Connect via CLI:  
```docker exec -it tfg-mongodb mongosh -u admin -p admin```  