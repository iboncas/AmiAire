# Commands

## Project Organization

- `iteration1/` contains the first clustering iteration, including the downstream analysis code, generated outputs, and supporting docs.
- `iteration2/` contains the second clustering iteration with enriched features.
- `iteration3a/` is the no-grid rerun that evolves from `iteration1`.
- `iteration3b/` is the no-grid rerun that evolves from `iteration2` and replaces the old `iteration3/` naming.

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

### Analysis Service
1. `cd analysis-service`
2. `pip install -r requirements.txt`
3. `python src/app.py`
   (API at `http://localhost:8000`)

Taxonomy compatibility prototype:
- Open `http://localhost:8000/taxonomy-compatibility`
- Sensor lookup API: `GET /taxonomy-score?sensor_id=...`
- Image upload API: `POST /taxonomy-score-image`

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`
   (http://localhost:5173)

## Utilities
### MongoDB
Connect via CLI:  
```docker exec -it tfg-mongodb mongosh -u admin -p admin```  
