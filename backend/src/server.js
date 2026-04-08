import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { connectToDatabase, closeDatabaseConnection } from './config/database.js';
import sensorRoutes from './routes/sensors.js';
import officialStationsRoutes from './routes/officialStations.js';
import imageRoutes from './routes/images.js';
import experimentRoutes from './routes/experiments.js';
import analysisRoutes from './routes/analysis.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json({ limit: '25mb' }));
app.use(express.urlencoded({ limit: '25mb', extended: true }));

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ status: 'ok', message: 'AmiAire Backend API is running' });
});

// API routes
app.use('/api', sensorRoutes);
app.use('/api', officialStationsRoutes);
app.use('/api', imageRoutes);
app.use('/api', experimentRoutes);
app.use('/api', analysisRoutes);

// 404 handler
app.use((req, res) => {
    res.status(404).json({
        success: false,
        error: 'Endpoint no encontrado'
    });
});

// Error handler
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    if (err?.type === 'entity.too.large') {
        return res.status(413).json({
            success: false,
            error: 'Payload demasiado grande',
            message: 'La imagen supera el tamaño máximo permitido por la API',
        });
    }
    res.status(500).json({
        success: false,
        error: 'Error interno del servidor',
        message: err.message
    });
});

// Start server
async function startServer() {
    try {
        // Connect to MongoDB
        await connectToDatabase();

        // Start Express server
        app.listen(PORT, () => {
            console.log(`🚀 AmiAire Backend API running on http://localhost:${PORT}`);
            console.log(`📊 Health check: http://localhost:${PORT}/health`);
            console.log(`🗺️  Sensors endpoint: http://localhost:${PORT}/api/sensores`);
        });
    } catch (error) {
        console.error('Failed to start server:', error);
        process.exit(1);
    }
}

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\n🛑 Shutting down gracefully...');
    await closeDatabaseConnection();
    process.exit(0);
});

process.on('SIGTERM', async () => {
    console.log('\n🛑 Shutting down gracefully...');
    await closeDatabaseConnection();
    process.exit(0);
});

startServer();
