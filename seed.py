"""Seed the DB with fake BD-style vehicles for demo.

Run:  python seed.py
"""
from backend.db import SessionLocal, init_db
from backend import models

FAKE_VEHICLES = [
    # (plate,              owner,                  phone,          nid,            class,        balance, blocked)
    ("DHAKA-METRO-GA-11-1234", "Karim Ahmed",        "01711000001", "1990123456789", "car",        500.0,  False),
    ("DHAKA-METRO-KHA-22-5678", "Fatima Begum",       "01811000002", "1988234567890", "car",        0.0,    False),
    ("CHATTO-METRO-HA-14-9012", "Rahim Uddin",        "01911000003", "1985345678901", "truck",      0.0,    False),
    ("DHAKA-METRO-BA-13-3456", "Nadia Hossain",      "01611000004", "1992456789012", "car",        1200.0, False),
    ("SYLHET-GA-17-7788",       "Abdul Motin",        "01511000005", "1983567890123", "bus",        0.0,    True),   # already blocked
    ("DHAKA-METRO-CHA-12-2468", "Shahana Khan",       "01711000006", "1995678901234", "cng",        50.0,   False),
    ("RAJSHAHI-LA-11-0011",     "Jamal Hossain",      "01811000007", "1978789012345", "pickup",     0.0,    False),
    ("DHAKA-METRO-GA-11-5555", "Rafiq Islam",        "01911000008", "1991890123456", "car",        0.0,    False),
    ("KHULNA-HA-15-4321",       "Salma Akter",        "01611000009", "1987901234567", "bus",        300.0,  False),
    ("DHAKA-METRO-DA-19-8080", "Imran Chowdhury",    "01511000010", "1993012345678", "motorcycle", 0.0,    False),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    added = 0
    for plate, owner, phone, nid, vclass, bal, blocked in FAKE_VEHICLES:
        plate = plate.upper()
        if db.get(models.Vehicle, plate):
            continue
        db.add(models.Vehicle(
            plate=plate,
            owner_name=owner,
            phone=phone,
            nid=nid,
            vehicle_class=vclass,
            balance_bdt=bal,
            brta_blocked=blocked,
            registered=True,
        ))
        added += 1
    db.commit()
    print(f"Seed complete. {added} new vehicles added "
          f"(total in DB: {db.query(models.Vehicle).count()}).")
    db.close()


if __name__ == "__main__":
    main()
