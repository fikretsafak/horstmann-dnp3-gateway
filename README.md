# Horstman Smart Logger Platform

Windows-first, Docker-free industrial monitoring platform starter for Horstmann Smart Navigator 2.0 devices.

## Structure

- `apps/frontend-web`: React + TypeScript operator UI
- `apps/backend-api`: FastAPI central backend
- `apps/collector-dnp3`: DNP3 collector service starter
- `apps/notification-worker`: email/sms worker starter
- `packages/shared-contracts`: shared payload contracts
- `infra/scripts`: Windows/Linux service scripts

## First Run (Development)

### Backend

1. Install Python 3.10
2. `cd apps/backend-api`
3. `pip install -r requirements.txt`
4. `uvicorn app.main:app --reload --port 8000`

### Frontend

1. Install Node.js LTS
2. `cd apps/frontend-web`
3. `npm install`
4. `npm run dev`

### Collector (Starter)

1. `cd apps/collector-dnp3`
2. Install Python 3.10 and dependencies
3. Run as standalone process or Windows service
