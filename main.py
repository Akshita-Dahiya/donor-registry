"""
Blood/Organ Donor-Recipient Matching Registry  -  FastAPI backend

Run:  uvicorn main:app --reload
Open: http://127.0.0.1:8000      (UI)      http://127.0.0.1:8000/docs   (Swagger API docs)
"""
import os
from contextlib import contextmanager
from typing import Literal

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from pydantic import BaseModel, Field

DATABASE_URL = os.getenv(
    "DATABASE_URL", "dbname=donor_registry user=postgres password=postgres host=localhost port=5432"
)
pool = ThreadedConnectionPool(1, 20, DATABASE_URL)

app = FastAPI(title="Donor-Recipient Matching Registry")

BloodType = Literal["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
Organ = Literal["blood", "kidney", "liver", "bone marrow"]
Urgency = Literal["critical", "high", "normal"]


@contextmanager
def transaction():
    """One DB transaction: commit if the block succeeds, roll back if anything raises."""
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ---------- request models ----------
class DonorIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None
    blood_type: BloodType
    organ_type: Organ = "blood"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RecipientIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None
    blood_type_needed: BloodType
    organ_needed: Organ = "blood"
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    urgency: Urgency = "normal"


class HospitalIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None


class LockIn(BaseModel):
    donor_id: int
    recipient_id: int


class HospitalAction(BaseModel):
    hospital_user_id: int


# ---------- registration ----------
@app.post("/api/donors")
def register_donor(d: DonorIn):
    with transaction() as cur:
        cur.execute("INSERT INTO users (name, role, phone) VALUES (%s,'donor',%s) RETURNING id",
                    (d.name, d.phone))
        uid = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO donors (user_id, blood_type, organ_type, latitude, longitude)
               VALUES (%s,%s,%s,%s,%s) RETURNING id""",
            (uid, d.blood_type, d.organ_type, d.latitude, d.longitude))
        return {"donor_id": cur.fetchone()["id"]}


@app.post("/api/recipients")
def register_recipient(r: RecipientIn):
    with transaction() as cur:
        cur.execute("INSERT INTO users (name, role, phone) VALUES (%s,'recipient',%s) RETURNING id",
                    (r.name, r.phone))
        uid = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO recipients
                 (user_id, blood_type_needed, organ_needed, latitude, longitude, urgency)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (uid, r.blood_type_needed, r.organ_needed, r.latitude, r.longitude, r.urgency))
        return {"recipient_id": cur.fetchone()["id"]}


@app.post("/api/hospitals")
def register_hospital(h: HospitalIn):
    with transaction() as cur:
        cur.execute("INSERT INTO users (name, role, phone) VALUES (%s,'hospital',%s) RETURNING id",
                    (h.name, h.phone))
        return {"hospital_user_id": cur.fetchone()["id"]}


# ---------- listings ----------
@app.get("/api/donors")
def list_donors():
    with transaction() as cur:
        cur.execute("""SELECT d.id, u.name, d.blood_type, d.organ_type, d.latitude, d.longitude, d.status
                       FROM donors d JOIN users u ON u.id = d.user_id ORDER BY d.id""")
        return cur.fetchall()


@app.get("/api/recipients")
def list_recipients():
    with transaction() as cur:
        cur.execute("""SELECT r.id, u.name, r.blood_type_needed, r.organ_needed, r.urgency,
                              r.latitude, r.longitude, r.status
                       FROM recipients r JOIN users u ON u.id = r.user_id ORDER BY r.id""")
        return cur.fetchall()


@app.get("/api/hospitals")
def list_hospitals():
    with transaction() as cur:
        cur.execute("SELECT id, name FROM users WHERE role='hospital' ORDER BY id")
        return cur.fetchall()


@app.get("/api/matches")
def list_matches():
    with transaction() as cur:
        cur.execute("""
            SELECT m.id, m.status, m.created_at, m.locked_at,
                   m.donor_id, du.name AS donor_name, d.blood_type AS donor_blood_type,
                   m.recipient_id, ru.name AS recipient_name, r.blood_type_needed, r.urgency,
                   hu.name AS confirmed_by_name
            FROM matches m
            JOIN donors d      ON d.id = m.donor_id
            JOIN users du      ON du.id = d.user_id
            JOIN recipients r  ON r.id = m.recipient_id
            JOIN users ru      ON ru.id = r.user_id
            LEFT JOIN users hu ON hu.id = m.confirmed_by
            ORDER BY m.id DESC""")
        return cur.fetchall()


@app.get("/api/stats")
def stats():
    with transaction() as cur:
        cur.execute("""SELECT
            (SELECT count(*) FROM donors WHERE status='available')    AS donors_available,
            (SELECT count(*) FROM donors WHERE status='locked')       AS donors_locked,
            (SELECT count(*) FROM donors WHERE status='donated')      AS donors_donated,
            (SELECT count(*) FROM recipients WHERE status='waiting')  AS recipients_waiting,
            (SELECT count(*) FROM recipients WHERE status='matched')  AS recipients_matched,
            (SELECT count(*) FROM recipients WHERE status='fulfilled') AS recipients_fulfilled""")
        return cur.fetchone()


# ---------- the "complex query": compatibility + proximity join ----------
MATCH_SQL = """
SELECT d.id AS donor_id, u.name AS donor_name, d.blood_type, d.organ_type,
       r.urgency,
       ROUND((6371 * acos(
           -- LEAST/GREATEST clamp: floating-point error can push the value just outside [-1, 1]
           LEAST(1.0, GREATEST(-1.0,
               cos(radians(r.latitude)) * cos(radians(d.latitude)) *
               cos(radians(d.longitude) - radians(r.longitude)) +
               sin(radians(r.latitude)) * sin(radians(d.latitude))
           ))
       ))::numeric, 1) AS distance_km
FROM recipients r
JOIN compatibility_rules cr ON cr.recipient_blood_type = r.blood_type_needed
JOIN donors d               ON d.blood_type = cr.donor_blood_type
                           AND d.organ_type = r.organ_needed
JOIN users u                ON u.id = d.user_id
WHERE cr.compatible = TRUE
  AND d.status = 'available'
  AND r.status = 'waiting'
  AND r.id = %s
ORDER BY distance_km ASC
LIMIT 10
"""


@app.get("/api/recipients/{recipient_id}/matches")
def find_matches(recipient_id: int):
    with transaction() as cur:
        cur.execute("SELECT status, urgency FROM recipients WHERE id=%s", (recipient_id,))
        rec = cur.fetchone()
        if rec is None:
            raise HTTPException(404, "Recipient not found")
        cur.execute(MATCH_SQL, (recipient_id,))
        rows = cur.fetchall()
        for r in rows:
            r["distance_km"] = float(r["distance_km"])
        return {"recipient_status": rec["status"], "urgency": rec["urgency"], "matches": rows}


# ---------- claim-locking ----------
@app.post("/api/matches/lock")
def lock_match(body: LockIn):
    """
    Everything below runs in ONE transaction, always in the same order
    (recipient row first, then donor row) so two requests can never deadlock.
    """
    with transaction() as cur:
        # 1. Lock the recipient row; reject if they are not waiting any more.
        cur.execute("SELECT status, blood_type_needed, organ_needed FROM recipients "
                    "WHERE id=%s FOR UPDATE", (body.recipient_id,))
        rec = cur.fetchone()
        if rec is None:
            raise HTTPException(404, "Recipient not found")
        if rec["status"] != "waiting":
            raise HTTPException(409, "Recipient already has a match")

        # 2. Server-side compatibility check (never trust the client).
        cur.execute("""SELECT 1 FROM donors d
                       JOIN compatibility_rules cr ON cr.donor_blood_type = d.blood_type
                       WHERE d.id=%s AND cr.recipient_blood_type=%s AND cr.compatible
                         AND d.organ_type=%s""",
                    (body.donor_id, rec["blood_type_needed"], rec["organ_needed"]))
        if cur.fetchone() is None:
            raise HTTPException(400, "Donor is not compatible with this recipient")

        # 3. Atomic conditional update: only one request can flip available -> locked.
        cur.execute("UPDATE donors SET status='locked' WHERE id=%s AND status='available'",
                    (body.donor_id,))
        if cur.rowcount == 0:
            raise HTTPException(409, "Donor already claimed by someone else")

        # 4. Record the match and update the recipient.
        cur.execute("""INSERT INTO matches (donor_id, recipient_id, status, locked_at)
                       VALUES (%s,%s,'locked',NOW()) RETURNING id""",
                    (body.donor_id, body.recipient_id))
        match_id = cur.fetchone()["id"]
        cur.execute("UPDATE recipients SET status='matched' WHERE id=%s", (body.recipient_id,))
        return {"match_id": match_id, "status": "locked"}


def _hospital_check(cur, user_id: int):
    cur.execute("SELECT 1 FROM users WHERE id=%s AND role='hospital'", (user_id,))
    if cur.fetchone() is None:
        raise HTTPException(403, "Only hospital staff can confirm or reject a match")


@app.post("/api/matches/{match_id}/confirm")
def confirm_match(match_id: int, body: HospitalAction):
    with transaction() as cur:
        _hospital_check(cur, body.hospital_user_id)
        cur.execute("""UPDATE matches SET status='confirmed', confirmed_by=%s
                       WHERE id=%s AND status='locked' RETURNING donor_id, recipient_id""",
                    (body.hospital_user_id, match_id))
        m = cur.fetchone()
        if m is None:
            raise HTTPException(400, "Match not in locked state")
        cur.execute("UPDATE donors SET status='donated' WHERE id=%s", (m["donor_id"],))
        cur.execute("UPDATE recipients SET status='fulfilled' WHERE id=%s", (m["recipient_id"],))
        return {"match_id": match_id, "status": "confirmed"}


@app.post("/api/matches/{match_id}/reject")
def reject_match(match_id: int, body: HospitalAction):
    """Hospital releases the lock: donor becomes available again, recipient waits again."""
    with transaction() as cur:
        _hospital_check(cur, body.hospital_user_id)
        cur.execute("""UPDATE matches SET status='rejected', confirmed_by=%s
                       WHERE id=%s AND status='locked' RETURNING donor_id, recipient_id""",
                    (body.hospital_user_id, match_id))
        m = cur.fetchone()
        if m is None:
            raise HTTPException(400, "Match not in locked state")
        cur.execute("UPDATE donors SET status='available' WHERE id=%s", (m["donor_id"],))
        cur.execute("UPDATE recipients SET status='waiting' WHERE id=%s", (m["recipient_id"],))
        return {"match_id": match_id, "status": "rejected"}


# ---------- UI ----------
@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))
