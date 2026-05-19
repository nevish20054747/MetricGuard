# MetricGuard - Docker Deployment Guide

## Overview

This guide explains how to deploy the complete MetricGuard system using Docker and Docker Compose. Docker packages each service into isolated containers that run consistently on any machine.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Network                  │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Monitoring│──▶│ Backend  │──▶│ MongoDB  │  │
│  │Collector │  │   API    │  │ Database │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│    :none         :5000         :27017       │
└─────────────────────────────────────────────┘
```

---

## Prerequisites

1. **Docker** installed: [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)
2. **Docker Compose** installed (included with Docker Desktop)
3. At least **2 GB RAM** and **5 GB disk space**

### Verify Installation:
```bash
docker --version
# Docker version 24.x or later

docker-compose --version
# Docker Compose version 2.x or later
```

---

## Quick Start (3 Commands)

```bash
# 1. Navigate to the project directory
cd devops/

# 2. Build and start all services
docker-compose -f docker/docker-compose.yml up --build -d

# 3. Check that all containers are running
docker ps
```

### Expected Output:
```
CONTAINER ID  IMAGE                    STATUS         PORTS
abc123        metricguard-monitoring   Up 30 seconds
def456        metricguard-backend      Up 30 seconds  0.0.0.0:5000->5000/tcp
ghi789        mongo:7.0                Up 30 seconds  0.0.0.0:27017->27017/tcp
```

---

## Step-by-Step Deployment

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd devops/
```

### Step 2: Configure Environment Variables (Optional)

Create a `.env` file in the project root to override defaults:

```env
# Backend connection
BACKEND_URL=http://backend:5000/metrics

# Collection settings
COLLECTION_INTERVAL=5

# Retry settings
MAX_RETRIES=3
RETRY_DELAY=2

# Logging
LOG_LEVEL=INFO

# MongoDB
MONGO_INITDB_ROOT_USERNAME=metricguard
MONGO_INITDB_ROOT_PASSWORD=metricguard123
```

### Step 3: Build the Docker Images

```bash
docker-compose -f docker/docker-compose.yml build
```

This builds:
- `metricguard-monitoring` from `docker/Dockerfile.monitoring`
- Uses `mongo:7.0` image for MongoDB (pre-built)
- Backend image should be built by the backend team

### Step 4: Start the Services

```bash
# Start in detached mode (background)
docker-compose -f docker/docker-compose.yml up -d

# Or start in foreground (see all logs)
docker-compose -f docker/docker-compose.yml up
```

### Step 5: Verify Services

```bash
# Check running containers
docker ps

# Check monitoring logs
docker logs metricguard-monitoring -f

# Check backend logs
docker logs metricguard-backend -f

# Check MongoDB logs
docker logs metricguard-mongodb -f
```

---

## Managing the Deployment

### Stop All Services
```bash
docker-compose -f docker/docker-compose.yml down
```

### Stop and Remove Data (Clean Start)
```bash
docker-compose -f docker/docker-compose.yml down -v
```

### Restart a Specific Service
```bash
docker-compose -f docker/docker-compose.yml restart monitoring
```

### Rebuild After Code Changes
```bash
docker-compose -f docker/docker-compose.yml up --build -d
```

### View Real-Time Logs
```bash
# All services
docker-compose -f docker/docker-compose.yml logs -f

# Only monitoring
docker-compose -f docker/docker-compose.yml logs -f monitoring
```

---

## Scaling the Monitoring Service

To run multiple collector instances:
```bash
docker-compose -f docker/docker-compose.yml up --scale monitoring=3 -d
```

> **Note**: Multiple collectors will send duplicate metrics. Only scale if monitoring different hosts.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `port 5000 already in use` | Stop other services using port 5000 or change the port in docker-compose.yml |
| `port 27017 already in use` | Stop local MongoDB or change the port mapping |
| Monitoring can't reach backend | Verify both are on the `metricguard-network` |
| MongoDB data lost after restart | Ensure the `mongo_data` volume is configured |
| Build fails | Run `docker system prune` to free space, then rebuild |
| Container keeps restarting | Check logs with `docker logs <container-name>` |

---

## Production Checklist

- [ ] Change MongoDB password from default
- [ ] Set `LOG_LEVEL=WARNING` to reduce log volume
- [ ] Configure persistent volume for MongoDB data
- [ ] Set up monitoring alerts for container health
- [ ] Enable Docker restart policies (already set to `always`)
- [ ] Configure log rotation to prevent disk fill
- [ ] Use Docker secrets for sensitive environment variables
