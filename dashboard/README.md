# Observability Dashboard

Internal dashboard for monitoring signing and validation events from the Flask signing service.

## Architecture

```
Flask Sign Service  ──(structured events)──►  PostgreSQL (obs_dashboard)
                                                    ▲
Dashboard (Next.js)  ──(server queries)─────────────┘
```

## Services

| Service        | Port | Description                              |
|--------------- |------|------------------------------------------|
| obs-postgres   | 5432 | PostgreSQL 16 for observability + auth   |
| dashboard      | 3000 | Next.js dashboard UI                     |

## Quick Start

```bash
docker compose up -d
```

The dashboard will be available at `http://localhost:3000`.

Default credentials: `admin` / `admin` (change via `ADMIN_USERNAME` and `ADMIN_PASSWORD` env vars).

## Environment Variables

### Flask Service (obs event writer)
| Variable         | Default        | Description                  |
|-----------------|----------------|------------------------------|
| OBS_DB_HOST     | obs-postgres   | Observability DB hostname    |
| OBS_DB_PORT     | 5432           | Observability DB port        |
| OBS_DB_NAME     | obs_dashboard  | Observability DB name        |
| OBS_DB_USER     | obs_user       | Observability DB user        |
| OBS_DB_PASSWORD | obs_password   | Observability DB password    |

### Dashboard
| Variable         | Default        | Description                  |
|-----------------|----------------|------------------------------|
| OBS_DB_*        | (same as above)| Database connection          |
| ADMIN_USERNAME  | admin          | Bootstrap admin username     |
| ADMIN_PASSWORD  | admin          | Bootstrap admin password     |
| NODE_ENV        | production     | Node environment             |

## Database

### Schemas

- **observability** — `log_operation` (request envelopes) + `log_event` (timeline facts, partitioned monthly)
- **dashboard_auth** — `users`, `sessions`, `audit_login`

### Migrations

Init script: `dashboard/db/init/001_init.sql` (auto-applied on first postgres start).

### Partitions

Monthly partitions are auto-created for 18 months ahead on init. Run `dashboard/db/maintain_partitions.sql` monthly to extend the range and clean expired sessions.

### Key Indexes

- `(document_id, occurred_at DESC)` for document timeline lookups
- `(expediente_key, occurred_at DESC)` for expediente timeline lookups
- `(stage, status, occurred_at DESC)` for filtered queries
- Partial index on `is_error = true` for the failures view
- `(operation_id, occurred_at DESC)` for operation drill-down

## Retention

Default hot retention: keep all data. To drop old partitions, uncomment the DROP section in `maintain_partitions.sql` and adjust the interval.

## Health Check

```
GET http://localhost:3000/api/health
```

Returns `{ "status": "healthy", "db": "connected" }` when the dashboard and its database are operational.

## Credential Rotation

1. Update `ADMIN_PASSWORD` env var in compose.
2. Restart the dashboard service.
3. The admin can then log in with the new password (existing sessions remain valid until they expire).

To add new users, connect to the obs-postgres database and insert into `dashboard_auth.users` with a bcrypt-hashed password.
