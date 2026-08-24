# Banking App

A full-stack banking application: FastAPI backend, React (Vite) frontend, MySQL database, orchestrated with Docker Compose.

## Features

- Signup / login with JWT authentication (passwords hashed with bcrypt)
- Create and view bank accounts
- Transfer money between accounts, with row-level locking to keep balance updates correct under concurrent transfers
- Transaction history per account

## Getting started

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
docker compose up --build
```

- Backend API: http://localhost:8000 (interactive docs at `/docs`)
- Frontend: http://localhost:5173
- MySQL: localhost:3306

The backend container runs Alembic migrations automatically on startup before starting the API server.

## Running backend tests

```bash
docker compose exec backend pytest
```

## Project structure

```
backend/    FastAPI app (routers -> services -> models), Alembic migrations, tests
frontend/   React + Vite app (pages, components, api client, auth context)
```

See `backend/app` for the API implementation and `frontend/src` for the UI.

## Known simplifications (learning-project scope)

- JWT is stored in `localStorage` on the frontend — fine for local/portfolio use, but for production you'd want httpOnly cookies to mitigate XSS token theft.
- No rate limiting, audit logging, or refresh-token rotation.
- Transfers are synchronous and always resolve to `completed` or raise an error (no async/pending states).
