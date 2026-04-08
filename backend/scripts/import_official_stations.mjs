import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { MongoClient } from 'mongodb';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const csvPath = path.resolve(__dirname, '../src/data/stations_coordinates.csv');
const mongoUri =
    process.env.MONGO_URI || process.env.MONGODB_URI || 'mongodb://localhost:27017/tfg';
const dbName = process.env.MONGODB_DATABASE || 'tfg';
const collectionName = 'official';

function parseCsv(text) {
    const lines = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    if (!lines.length) return [];

    const headers = lines[0].split(',').map((h) => h.trim().toLowerCase());
    const idx = {
        gmlId: headers.indexOf('gml_id'),
        name: headers.indexOf('name'),
        latitude: headers.indexOf('latitude'),
        longitude: headers.indexOf('longitude'),
    };
    if (idx.gmlId < 0 || idx.name < 0 || idx.latitude < 0 || idx.longitude < 0) {
        throw new Error('CSV header must include: gml_id,name,latitude,longitude');
    }

    return lines
        .slice(1)
        .map((line) => {
            const parts = line.split(',');
            const id = parts[idx.gmlId]?.trim();
            const name = parts[idx.name]?.trim();
            const lat = Number(parts[idx.latitude]);
            const long = Number(parts[idx.longitude]);

            if (!id || !name || !Number.isFinite(lat) || !Number.isFinite(long)) return null;
            return { id, name, lat, long };
        })
        .filter(Boolean);
}

async function run() {
    const csvText = await fs.readFile(csvPath, 'utf8');
    const stations = parseCsv(csvText);
    if (!stations.length) {
        throw new Error('No valid stations parsed from CSV');
    }

    const client = new MongoClient(mongoUri);
    await client.connect();

    try {
        const db = client.db(dbName);
        const collection = db.collection(collectionName);

        await collection.createIndex({ id: 1 }, { unique: true });

        const operations = stations.map((station) => ({
            updateOne: {
                filter: { id: station.id },
                update: {
                    $set: {
                        id: station.id,
                        name: station.name,
                        lat: station.lat,
                        long: station.long,
                        pm25: '',
                        pm10: '',
                        fetched_at: '',
                    },
                },
                upsert: true,
            },
        }));

        const result = await collection.bulkWrite(operations, { ordered: false });
        const total = await collection.countDocuments();

        console.log(
            JSON.stringify(
                {
                    success: true,
                    collection: `${dbName}.${collectionName}`,
                    parsed: stations.length,
                    matched: result.matchedCount,
                    modified: result.modifiedCount,
                    upserted: result.upsertedCount,
                    totalDocuments: total,
                },
                null,
                2
            )
        );
    } finally {
        await client.close();
    }
}

run().catch((error) => {
    console.error('Import failed:', error.message);
    process.exit(1);
});
