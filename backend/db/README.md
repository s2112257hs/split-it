# PostgreSQL schema

Apply the schema with:

```bash
psql "$DATABASE_URL" -f backend/db/schema.sql
```

The migration snapshot is available at `backend/db/migrations/001_initial_schema.sql`.

Settlement folio migration:

```bash
psql "$DATABASE_URL" -f backend/db/migrations/002_participant_settlements.sql
```

Rollback:

```bash
psql "$DATABASE_URL" -f backend/db/migrations/002_participant_settlements.rollback.sql
```

Repayments migration:

```bash
psql "$DATABASE_URL" -f backend/db/migrations/003_participant_repayments.sql
```

Rollback:

```bash
psql "$DATABASE_URL" -f backend/db/migrations/003_participant_repayments.rollback.sql
```

Folio math reference: `backend/db/FOLIO_FORMULA_SHEET.md`.
