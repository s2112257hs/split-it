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

Receipt draft/finalized lifecycle migration:

```bash
psql "$DATABASE_URL" -f backend/db/migrations/004_receipt_draft_finalize.sql
```

Rollback:

```bash
psql "$DATABASE_URL" -f backend/db/migrations/004_receipt_draft_finalize.rollback.sql
```

Folio math reference: `backend/db/FOLIO_FORMULA_SHEET.md`.
