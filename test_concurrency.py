"""
Concurrency demo: 8 recipients try to lock the SAME donor at the same instant.
Expected result: exactly ONE succeeds (200), the other seven get 409 Conflict.

Run (with the server already running):  python test_concurrency.py
"""
import threading
import httpx

BASE = "http://127.0.0.1:8000/api"
N = 8

donor = httpx.post(f"{BASE}/donors", json={
    "name": "Race Donor", "blood_type": "O-", "latitude": 12.97, "longitude": 79.15}).json()["donor_id"]

recipients = [
    httpx.post(f"{BASE}/recipients", json={
        "name": f"Race Recipient {i}", "blood_type_needed": "A+", "urgency": "critical",
        "latitude": 12.95, "longitude": 79.13}).json()["recipient_id"]
    for i in range(N)
]
print(f"Donor {donor} vs recipients {recipients}\n")

results = [None] * N
barrier = threading.Barrier(N)  # makes all threads fire at the same moment


def attempt(i):
    barrier.wait()
    r = httpx.post(f"{BASE}/matches/lock", json={"donor_id": donor, "recipient_id": recipients[i]})
    results[i] = (r.status_code, r.json())


threads = [threading.Thread(target=attempt, args=(i,)) for i in range(N)]
[t.start() for t in threads]
[t.join() for t in threads]

for i, (code, body) in enumerate(results):
    print(f"recipient {recipients[i]}: HTTP {code}  {body}")

wins = sum(1 for code, _ in results if code == 200)
print(f"\nSuccessful locks: {wins}  (expected 1)")
assert wins == 1, "DOUBLE BOOKING!"
print("PASS: exactly one recipient locked the donor.")
