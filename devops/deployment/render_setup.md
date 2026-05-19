# MetricGuard - Render Deployment Guide

## Overview

[Render](https://render.com) is a cloud platform that lets you deploy Docker containers, web services, and databases with minimal configuration. This guide explains how to deploy the MetricGuard backend and monitoring services on Render.

---

## Architecture on Render

```
┌──────────────────────────────────────────┐
│              Render Cloud                 │
│                                          │
│  ┌────────────────┐  ┌────────────────┐  │
│  │  Web Service   │  │  Background    │  │
│  │  (Backend API) │◀─│  Worker        │  │
│  │  Port 5000     │  │  (Collector)   │  │
│  └───────┬────────┘  └────────────────┘  │
│          │                               │
│          ▼                               │
│  ┌────────────────┐                      │
│  │ MongoDB Atlas  │ (external)           │
│  └────────────────┘                      │
└──────────────────────────────────────────┘
```

> **Note**: Render does not offer a managed MongoDB service. Use MongoDB Atlas (see `mongodb_atlas.md`).

---

## Prerequisites

1. A [Render account](https://render.com) (free tier available)
2. Project code pushed to GitHub or GitLab
3. MongoDB Atlas cluster set up (see `mongodb_atlas.md`)
4. MongoDB connection string ready

---

## Step 1: Deploy the Backend API

### 1.1 Create a New Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub/GitLab repository
4. Configure the service:

| Setting | Value |
|---------|-------|
| **Name** | `metricguard-backend` |
| **Region** | Choose closest to your users |
| **Branch** | `main` |
| **Runtime** | `Docker` |
| **Dockerfile Path** | `docker/Dockerfile.backend` (from backend team) |
| **Instance Type** | Free (or Starter for production) |

### 1.2 Set Environment Variables

Click **"Environment"** and add:

| Key | Value |
|-----|-------|
| `MONGO_URI` | `mongodb+srv://<user>:<pass>@cluster.mongodb.net/metricguard_db` |
| `PORT` | `5000` |

### 1.3 Deploy

Click **"Create Web Service"**. Render will build and deploy automatically.

Note the URL: `https://metricguard-backend.onrender.com`

---

## Step 2: Deploy the Monitoring Collector

### 2.1 Create a Background Worker

1. Click **"New +"** → **"Background Worker"**
2. Connect the same repository
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `metricguard-monitoring` |
| **Branch** | `main` |
| **Runtime** | `Docker` |
| **Dockerfile Path** | `docker/Dockerfile.monitoring` |
| **Instance Type** | Free (or Starter) |

### 2.2 Set Environment Variables

| Key | Value |
|-----|-------|
| `BACKEND_URL` | `https://metricguard-backend.onrender.com/metrics` |
| `COLLECTION_INTERVAL` | `5` |
| `MAX_RETRIES` | `3` |
| `LOG_LEVEL` | `INFO` |

### 2.3 Deploy

Click **"Create Background Worker"**. The collector will start automatically.

---

## Step 3: Verify Deployment

### Check Backend:
```bash
curl https://metricguard-backend.onrender.com/health
```

Expected:
```json
{"status": "healthy"}
```

### Check Monitoring Logs:
1. Go to Render Dashboard → `metricguard-monitoring`
2. Click **"Logs"** tab
3. Verify metrics are being collected and sent

---

## Auto-Deploy on Git Push

Render automatically redeploys when you push to the `main` branch:

```bash
git add .
git commit -m "Update monitoring config"
git push origin main
# Render auto-deploys in ~2 minutes
```

---

## Render Free Tier Limitations

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| Services sleep after 15 min of inactivity | Backend may be slow on first request | Use a cron service to ping every 10 min |
| 750 free hours/month | Shared across all services | Upgrade to Starter ($7/month) |
| No persistent disk | Log files are lost on redeploy | Use a cloud logging service |
| Limited memory (512MB) | Sufficient for MetricGuard | Monitor usage in Render dashboard |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Backend returns 502 | Service is still starting or crashed. Check logs. |
| Collector can't reach backend | Verify `BACKEND_URL` environment variable |
| MongoDB connection timeout | Whitelist Render IPs in MongoDB Atlas (or use `0.0.0.0/0`) |
| Build fails | Check Dockerfile path and ensure all files are committed |
| Service sleeps on free tier | Set up an external uptime monitor to ping the service |
