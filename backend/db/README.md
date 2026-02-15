# PostgreSQL schema

Apply the schema with:

```bash
psql "$DATABASE_URL" -f backend/db/schema.sql
```

The migration snapshot is available at `backend/db/migrations/001_initial_schema.sql`.
