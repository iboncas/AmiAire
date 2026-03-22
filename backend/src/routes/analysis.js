import express from 'express';

const router = express.Router();

const ANALYSIS_SERVICE_URL = process.env.ANALYSIS_SERVICE_URL || 'http://localhost:8000';

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
        const modelType = typeof req.body?.modelType === 'string' ? req.body.modelType : 'PM10';
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
                body: JSON.stringify({ image_b64: imageB64, model_type: modelType }),
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
            });
        }

        return res.json({
            success: true,
            data: {
                contourImageB64: data.contour_image_b64 || '',
                roiImageB64: data.roi_image_b64 || '',
                binaryB64: data.binary_b64 || '',
                overlayB64: data.overlay_b64 || '',
                analysisResults: data.analysis_results || {},
                pollutionData: data.pollution_data || {},
                pollutionLevel: data.pollution_level || '',
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

export default router;
