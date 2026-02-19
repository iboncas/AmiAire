# AmiAire Backend API

Backend API for the AmiAire air quality monitoring application.

## Setup

1. Install dependencies:
```bash
cd backend
npm install
```

2. Configure environment variables in `.env`:
```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=amiaire
MONGODB_COLLECTION=sensores
PORT=3001
```

3. Start the server:
```bash
npm run dev
```

## API Endpoints

### GET /api/sensores
Returns all sensors from MongoDB.

**Query Parameters:**
- `fields` (optional): Comma-separated list of fields to return
  - Example: `?fields=id,nombre,ubicacion,nivelPolucion,metricas.concentracion,fechaInicio,fechaRecogida`

**Response:**
```json
{
  "success": true,
  "count": 100,
  "data": [...]
}
```

### GET /api/sensores/:id
Returns a single sensor by ID.

### GET /health
Health check endpoint.

## Data Mapping

MongoDB schema → Frontend format:
- `_id` → `id`
- `Localización latitud` → `ubicacion.latitud`
- `Localización longitud` → `ubicacion.longitud`
- `PM2.5` → `metricas.concentracion`
- `Nivel de polución PM2.5` → `nivelPolucion`
- `Fecha de inicio` → `fechaInicio`
- `Fecha de recogida` → `fechaRecogida`
- `Imagen de entrada` → `imagen`
