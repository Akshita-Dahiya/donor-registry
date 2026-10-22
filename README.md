# Blood/Organ Donor-Recipient Matching Registry

React-free, one-command-to-run version: **PostgreSQL + FastAPI + a single-page UI** (served by FastAPI itself).

## 1. Setup (about 10 minutes)

1. Install PostgreSQL and Python 3.10+.
2. Create the database and load the schema + demo data:
   ```
   psql -U postgres -c "CREATE DATABASE donor_registry;"
   psql -U postgres -d donor_registry -f schema.sql
   psql -U postgres -d donor_registry -f seed.sql
   ```
   (Or open pgAdmin 4, create `donor_registry`, and run the two files in the Query Tool.)
3. Install and run:
   ```
   pip install -r requirements.txt
   set DATABASE_URL=dbname=donor_registry user=postgres password=YOURPASSWORD host=localhost port=5432   (Windows cmd)
   uvicorn main:app --reload
   ```
   On PowerShell use `$env:DATABASE_URL="..."`. On Linux/Mac use `export DATABASE_URL="..."`.
4. Open http://127.0.0.1:8000 (UI) and http://127.0.0.1:8000/docs (Swagger API docs).

To reset the demo: re-run `schema.sql` then `seed.sql`.

## 2. Files

| File | What it is |
|---|---|
| `schema.sql` | 5 tables, CHECK constraints, 27-row compatibility table, partial unique indexes, performance indexes |
| `seed.sql` | 2 hospitals, 5 donors, 3 recipients |
| `main.py` | FastAPI backend: register, list, match query, lock, confirm, release |
| `index.html` | UI: Find matches, Register, Hospital desk, Registry |
| `test_concurrency.py` | 8 recipients race for 1 donor; exactly one wins |

## 3. Demo script (about 4 minutes)

1. **Registry tab**: show the data. Say: "5 tables; blood compatibility is a lookup table, not if/else code."
2. **Find matches**: pick Meena Devi (A+, critical, Vellore). The list shows O- donor Arun at about 3.5 km first. Say: "That is one SQL query joining recipients, the compatibility table and donors, ranked by Haversine distance."
3. **Lock** Arun. The stats bar changes (locked 1, matched 1).
4. **Find matches** for Imran (AB+). Arun no longer appears because he is locked.
5. **Hospital desk**: confirm the match, then show donor = donated, recipient = fulfilled. Do one **Release** on a different match to show the donor returns to the pool.
6. **Terminal**: run `python test_concurrency.py`. Say: "8 requests hit the same donor at the same instant. Exactly one gets 200; seven get 409."

## 4. How the concurrency safety works (3 layers)

1. **Atomic conditional update**: `UPDATE donors SET status='locked' WHERE id=? AND status='available'`. Postgres row-locks the row, so a second request waits, re-checks the condition, finds `locked`, and updates 0 rows, which the code turns into HTTP 409.
2. **`SELECT ... FOR UPDATE` on the recipient row**, so the same recipient cannot lock two donors at once. Locks are always taken in the same order (recipient, then donor), so deadlocks cannot happen.
3. **Partial unique indexes** `one_live_match_per_donor` / `one_live_match_per_recipient`: even if the app code had a bug, the database itself refuses a second live match.

All steps run in one transaction (`with transaction()`), so a crash halfway rolls everything back.

## 5. Viva questions and answers

**Why a lookup table instead of if/else or a graph database?** Compatibility is fixed and small (27 pairs). Storing it as rows turns "who can give to whom" into a normal JOIN, which is declarative, easy to change, and needs no Neo4j.

**Why not just SELECT, then UPDATE?** Two requests can both SELECT "available" before either UPDATEs (a check-then-act race). The conditional UPDATE does the check and the write as one atomic statement.

**FOR UPDATE vs atomic UPDATE?** `FOR UPDATE` locks the row first and you decide in code afterwards; the atomic UPDATE needs no explicit lock and is shorter. Both rely on Postgres row-level locking. I used both: FOR UPDATE for the recipient, atomic UPDATE for the donor.

**Isolation level?** Default READ COMMITTED. It is enough here because the conditional UPDATE re-evaluates its WHERE clause after the competing transaction commits. SERIALIZABLE would also work but forces retry logic.

**What if the server crashes between the donor update and the match insert?** It is one transaction, so Postgres rolls both back and the donor stays available.

**Is the schema normalised?** `users` holds identity (name, phone) once; `donors` and `recipients` hold role-specific facts; `matches` is the junction table. No repeated groups and no partial dependencies, so it is 3NF. Blood types in `compatibility_rules` depend on the full composite key.

**Why can the Haversine formula crash, and how did you handle it?** Floating-point error can push the `acos` argument just above 1. I clamp it with `LEAST(1, GREATEST(-1, ...))`.

**How would you scale proximity search?** Add PostGIS with a GiST index and `ST_DWithin`, or prefilter with a latitude/longitude bounding box before computing exact distance.

**What does the CHECK constraint buy you?** Bad data (an invalid blood type, urgency or status) is rejected by the database even if some other client bypasses the API.

**Limitations?** Organ matching uses only ABO blood-group compatibility; real transplants also need HLA tissue typing, size and medical criteria. There is no authentication; hospital identity is passed by ID. Both are listed as future work.

**Future work:** login with JWT roles, PostGIS, HLA matching, notifications (SMS/email), lock expiry (auto-release after N hours), React + TypeScript frontend.

## 6. Mapping to your Review-1 document

Everything in the document is implemented, with these improvements: lock also checks compatibility and recipient status, confirm updates donor/recipient status, a release endpoint was added, connection pooling and transactions replaced raw connections, urgency and distance are combined in the match ranking, and the partial unique indexes were added as a database-level guarantee.
