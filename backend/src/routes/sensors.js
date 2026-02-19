import express from 'express';
import { getAllSensors, getSensorById } from '../models/sensor.js';

const router = express.Router();

/**
 * GET /api/sensores
 * Returns all sensors with optional field filtering
 */
router.get('/sensores', async (req, res) => {
    try {
        const sensors = await getAllSensors();

        // Support field filtering via query params (e.g., ?fields=id,nombre,ubicacion)
        const fields = req.query.fields;
        let filteredSensors = sensors;

        if (fields) {
            const fieldList = fields.split(',').map(f => f.trim());
            filteredSensors = sensors.map(sensor => {
                const filtered = {};
                fieldList.forEach(field => {
                    if (field.includes('.')) {
                        // Handle nested fields like "metricas.concentracion"
                        const parts = field.split('.');
                        let value = sensor;
                        for (const part of parts) {
                            value = value?.[part];
                        }
                        if (value !== undefined) {
                            // Reconstruct nested structure
                            let current = filtered;
                            for (let i = 0; i < parts.length - 1; i++) {
                                if (!current[parts[i]]) {
                                    current[parts[i]] = {};
                                }
                                current = current[parts[i]];
                            }
                            current[parts[parts.length - 1]] = value;
                        }
                    } else if (sensor[field] !== undefined) {
                        filtered[field] = sensor[field];
                    }
                });
                return filtered;
            });
        }

        res.json({
            success: true,
            count: filteredSensors.length,
            data: filteredSensors
        });
    } catch (error) {
        console.error('Error in GET /api/sensores:', error);
        res.status(500).json({
            success: false,
            error: 'Error al obtener los sensores',
            message: error.message
        });
    }
});

/**
 * GET /api/sensores/:id
 * Returns a single sensor by ID
 */
router.get('/sensores/:id', async (req, res) => {
    try {
        const sensor = await getSensorById(req.params.id);

        if (!sensor) {
            return res.status(404).json({
                success: false,
                error: 'Sensor no encontrado'
            });
        }

        res.json({
            success: true,
            data: sensor
        });
    } catch (error) {
        console.error('Error in GET /api/sensores/:id:', error);
        res.status(500).json({
            success: false,
            error: 'Error al obtener el sensor',
            message: error.message
        });
    }
});

export default router;
