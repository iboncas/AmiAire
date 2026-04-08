import { MongoClient } from 'mongodb';
import dotenv from 'dotenv';

dotenv.config();

const MONGODB_URI =
    process.env.MONGODB_URI || process.env.MONGO_URI || 'mongodb://localhost:27017';
const DATABASE_FROM_URI = (() => {
    try {
        const pathname = new URL(MONGODB_URI).pathname;
        if (pathname && pathname !== '/') return pathname.replace(/^\//, '');
    } catch {
        // fallback to env/default below
    }
    return null;
})();
const MONGODB_DATABASE =
    process.env.MONGODB_DATABASE || process.env.MONGO_DB || DATABASE_FROM_URI || 'amiaire';

let client;
let db;

export async function connectToDatabase() {
    if (db) {
        return db;
    }

    try {
        client = new MongoClient(MONGODB_URI);
        await client.connect();
        console.log('✅ Connected to MongoDB');

        db = client.db(MONGODB_DATABASE);
        return db;
    } catch (error) {
        console.error('❌ MongoDB connection error:', error);
        throw error;
    }
}

export async function closeDatabaseConnection() {
    if (client) {
        await client.close();
        console.log('MongoDB connection closed');
    }
}

export function getDatabase() {
    if (!db) {
        throw new Error('Database not initialized. Call connectToDatabase first.');
    }
    return db;
}
