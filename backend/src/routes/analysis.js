import express from 'express';

const router = express.Router();

const ANALYSIS_SERVICE_URL = process.env.ANALYSIS_SERVICE_URL || 'http://localhost:8000';

function normalizeModelType(modelType) {
    if (typeof modelType !== 'string') return 'PM10';
    const compact = modelType
        .trim()
        .toUpperCase()
        .replace(/\s+/g, '')
        .replace(/_/g, '')
        .replace(',', '.')
        .replace(/\./g, '');
    if (compact === 'PM25') return 'PM25';
    if (compact === 'PM10') return 'PM10';
    return 'PM10';
}

router.get('/analysis/health', async (_req, res) => {
    try {
        const response = await fetch(`${ANALYSIS_SERVICE_URL}/health`);
        if (!response.ok) {
            return res.status(502).json({
                success: false,
                error: 'Analysis service is unavailable',
            });
        }
        const data = await response.json();
        return res.json({ success: true, data });
    } catch (error) {
        return res.status(502).json({
            success: false,
            error: 'Analysis service is unavailable',
            message: error.message,
        });
    }
});

router.post('/analysis/process', async (req, res) => {
    try {
        const imageB64 = typeof req.body?.imageB64 === 'string' ? req.body.imageB64 : '';
        const modelType = normalizeModelType(req.body?.modelType);
        const metadata = req.body?.metadata && typeof req.body.metadata === 'object' ? req.body.metadata : {};
        const contextualData =
            req.body?.contextualData && typeof req.body.contextualData === 'object'
                ? req.body.contextualData
                : {};
        if (!imageB64) {
            return res.status(400).json({
                success: false,
                error: 'Missing image payload',
            });
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 120000);

        let response;
        try {
            response = await fetch(`${ANALYSIS_SERVICE_URL}/process-image`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_b64: imageB64,
                    model_type: modelType,
                    metadata,
                    contextual_data: contextualData,
                }),
                signal: controller.signal,
            });
        } finally {
            clearTimeout(timeout);
        }

        const rawText = await response.text();
        let data = null;
        try {
            data = rawText ? JSON.parse(rawText) : null;
        } catch {
            data = null;
        }
        if (!response.ok || !data?.success) {
            return res.status(response.status || 422).json({
                success: false,
                error: data?.error || `Image analysis failed (status ${response.status})`,
                details: data?.details || (!data && rawText ? rawText.slice(0, 300) : undefined),
                datasetOutputs: data?.dataset_outputs || null,
            });
        }

        return res.json({
            success: true,
            data: {
                contourImageB64: data.contour_image_b64 || '',
                roiImageB64: data.roi_image_b64 || '',
                binaryB64: data.binary_b64 || '',
                overlayB64: data.overlay_b64 || '',
                validation: data.validation || null,
                analysisResults: data.analysis_results || {},
                pollutionData: data.pollution_data || {},
                pollutionLevel: data.pollution_level || '',
                pollutionLevels: data.pollution_levels || {},
                taxonomyModel: data.taxonomy_model || null,
                datasetOutputs: data.dataset_outputs || null,
            },
        });
    } catch (error) {
        const isAbort = error?.name === 'AbortError';
        return res.status(502).json({
            success: false,
            error: isAbort ? 'Analysis timed out' : 'Analysis service error',
            message: error.message,
        });
    }
});

router.post('/analysis/validate-sensor', async (req, res) => {
    try {
        const imageB64 = typeof req.body?.imageB64 === 'string' ? req.body.imageB64 : '';
        if (!imageB64) {
            return res.status(400).json({
                success: false,
                error: 'Missing image payload',
            });
        }

        const response = await fetch(`${ANALYSIS_SERVICE_URL}/validate-sensor-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_b64: imageB64 }),
        });

        const rawText = await response.text();
        let data = null;
        try {
            data = rawText ? JSON.parse(rawText) : null;
        } catch {
            data = null;
        }

        if (!response.ok || !data?.success) {
            return res.status(response.status || 422).json({
                success: false,
                error: data?.error || `Sensor validation failed (status ${response.status})`,
                details: data?.details || (!data && rawText ? rawText.slice(0, 300) : undefined),
            });
        }

        return res.json({
            success: true,
            data: data.data,
        });
    } catch (error) {
        return res.status(502).json({
            success: false,
            error: 'Analysis service error',
            message: error.message,
        });
    }
});

export default router;
