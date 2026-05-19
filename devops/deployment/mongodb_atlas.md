# MetricGuard - MongoDB Atlas Setup Guide

## Overview

[MongoDB Atlas](https://www.mongodb.com/atlas) is a fully managed cloud database service. MetricGuard uses MongoDB to store all collected system metrics. This guide walks you through setting up a free-tier Atlas cluster for MetricGuard.

---

## Why MongoDB Atlas?

| Feature | Benefit |
|---------|---------|
| Free tier (M0) | 512 MB storage, free forever |
| Managed backups | Automatic daily snapshots |
| Global regions | Deploy close to your app |
| Built-in monitoring | Track database performance |
| Easy scaling | Upgrade without downtime |

---

## Step 1: Create an Atlas Account

1. Go to [https://www.mongodb.com/atlas](https://www.mongodb.com/atlas)
2. Click **"Try Free"**
3. Sign up with email or Google account
4. Verify your email address

---

## Step 2: Create a Free Cluster

1. Click **"Build a Database"**
2. Choose **"M0 FREE"** tier
3. Select a **Cloud Provider** (AWS recommended)
4. Select a **Region** closest to your deployment:
   - For India: `Mumbai (ap-south-1)`
   - For US: `Virginia (us-east-1)`
5. Name your cluster: `MetricGuardCluster`
6. Click **"Create Cluster"**

> ⏳ Cluster creation takes 1-3 minutes.

---

## Step 3: Create a Database User

1. Go to **"Database Access"** in the left sidebar
2. Click **"Add New Database User"**
3. Choose **"Password"** authentication
4. Set credentials:

| Field | Value |
|-------|-------|
| Username | `metricguard` |
| Password | `your-secure-password-here` |
| Role | `Read and write to any database` |

5. Click **"Add User"**

> ⚠️ **Important**: Use a strong password. Don't use the default example password in production.

---

## Step 4: Configure Network Access

1. Go to **"Network Access"** in the left sidebar
2. Click **"Add IP Address"**
3. For development: Click **"Allow Access from Anywhere"** (`0.0.0.0/0`)
4. For production: Add only your server's IP addresses

> ⚠️ **Security Note**: `0.0.0.0/0` is convenient for development but should be restricted in production.

---

## Step 5: Get Your Connection String

1. Go to **"Database"** → Click **"Connect"** on your cluster
2. Choose **"Connect your application"**
3. Select **Driver**: `Python`, **Version**: `3.12 or later`
4. Copy the connection string:

```
mongodb+srv://metricguard:<password>@metricguardcluster.xxxxx.mongodb.net/metricguard_db?retryWrites=true&w=majority
```

5. Replace `<password>` with your actual password.

---

## Step 6: Configure MetricGuard

### For Docker Compose (docker-compose.yml):

Update the backend environment variable:

```yaml
backend:
  environment:
    MONGO_URI: "mongodb+srv://metricguard:your-password@metricguardcluster.xxxxx.mongodb.net/metricguard_db?retryWrites=true&w=majority"
```

### For Render Deployment:

Set the `MONGO_URI` environment variable in the Render dashboard.

### For Local Development:

Create a `.env` file:

```env
MONGO_URI=mongodb+srv://metricguard:your-password@metricguardcluster.xxxxx.mongodb.net/metricguard_db?retryWrites=true&w=majority
```

---

## Step 7: Verify the Connection

### Using Python:

```python
from pymongo import MongoClient

# Replace with your actual connection string
uri = "mongodb+srv://metricguard:your-password@metricguardcluster.xxxxx.mongodb.net/metricguard_db?retryWrites=true&w=majority"

client = MongoClient(uri)

# Test the connection
try:
    client.admin.command("ping")
    print("✅ Successfully connected to MongoDB Atlas!")
except Exception as e:
    print(f"❌ Connection failed: {e}")

# Check the database
db = client["metricguard_db"]
print(f"Collections: {db.list_collection_names()}")
```

### Using mongosh CLI:

```bash
mongosh "mongodb+srv://metricguardcluster.xxxxx.mongodb.net/" \
  --username metricguard \
  --password your-password

# Once connected:
use metricguard_db
db.metrics.countDocuments()
```

---

## Step 8: Create an Index (Recommended)

For better query performance, create an index on the `timestamp` field:

```javascript
// In mongosh:
use metricguard_db
db.metrics.createIndex({ "timestamp": -1 })
```

Or using Python:

```python
from pymongo import MongoClient, DESCENDING

client = MongoClient(uri)
db = client["metricguard_db"]
db.metrics.create_index([("timestamp", DESCENDING)])
print("Index created on 'timestamp'")
```

---

## MongoDB Atlas Free Tier Limits

| Resource | Limit |
|----------|-------|
| Storage | 512 MB |
| RAM | Shared |
| Connections | 500 |
| Network Transfer | 10 GB/week |
| Backups | Daily snapshots |
| Clusters | 1 free cluster per project |

> For MetricGuard's expected data volume (~1 KB per metric × 12 metrics/min × 60 min × 24 hr ≈ **17 MB/day**), the free tier lasts about **30 days** before needing cleanup.

---

## Data Retention Strategy

To prevent running out of space on the free tier, set up automatic cleanup:

```python
from pymongo import MongoClient
from datetime import datetime, timedelta

client = MongoClient(uri)
db = client["metricguard_db"]

# Delete metrics older than 7 days
cutoff = datetime.utcnow() - timedelta(days=7)
result = db.metrics.delete_many({
    "timestamp": {"$lt": cutoff.strftime("%Y-%m-%dT%H:%M:%S")}
})
print(f"Deleted {result.deleted_count} old metrics")
```

---

## Monitoring Your Atlas Cluster

1. Go to your Atlas dashboard
2. Click on your cluster name
3. View the **"Metrics"** tab for:
   - Operations/sec
   - Connections
   - Data size
   - Network I/O

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ServerSelectionTimeoutError` | Check network access whitelist |
| `AuthenticationFailed` | Verify username/password in connection string |
| `DNSLookupFailed` | Check internet connection; Atlas requires DNS |
| Connection works locally but not in Docker | Use `host.docker.internal` or whitelist Docker host IP |
| Slow queries | Create indexes on frequently queried fields |
| Storage full | Run the data retention cleanup script above |
