# ShohojToll — 5-minute Live Demo Script

Audience: ministry / BRTA / bridge-authority officials. Goal: show an end-to-end
toll pass, payment, and enforcement cycle without any manual booth step.

---

## 0. Pre-flight (do before the audience walks in)

Three terminals, in this order:

```bash
# (a) backend
python run_server.py

# (b) camera + ANPR
python detect_plates.py

# (c) admin dashboard
python run_dashboard.py
```

Then open two browser windows side by side:

- **Left**: `http://localhost:8501` — admin dashboard (Live Feed tab)
- **Right**: a blank tab (for the payment page when it opens)

Reset the DB if you want a clean board:

```bash
Remove-Item toll.db ; python seed.py
```

Print `demo/plates.html` at 100% scale and cut the six cards.

---

## 1. The pitch (0:00 – 0:30)

> "Today every toll plaza in Bangladesh is a traffic jam. Cash, queues,
> leakage. This prototype replaces the booth with a camera and your phone —
> no RFID sticker, no smart card, no new hardware for the driver."

Point at the three windows. One sentence each:

- Camera = the gantry eye.
- Backend = the toll authority.
- Dashboard = what BRTA and the ministry would see.

---

## 2. Golden path — Karim pays on bKash (0:30 – 1:30)

1. Hold the **DHAKA METRO GA 11-1234** card in front of the phone camera.
2. Watch the dashboard Live Feed — a new row appears with status `UNPAID`.
3. Click the **Pay page →** link next to it (opens the right browser window).
4. Click **bKash**, type any 4-digit PIN (e.g. `1234`), submit.
5. Back on the dashboard: status flips to **PAID**, revenue metric ticks up,
   and a green SMS bubble appears in the outbox ("Payment received…").

> "One car, one camera frame, one tap. No staff, no cash, no stopping."

---

## 3. USSD flow — Fatima has a button phone (1:30 – 2:15)

1. Hold the **DHAKA METRO KHA 22-5678** card up.
2. In the right browser open `http://localhost:8000/ussd`.
3. Dial the menu: `1` (no, `2` to pay) → enter plate `DHAKA-METRO-KHA-22-5678`
   → enter PIN `12345` → "Dhonnobad."
4. Dashboard shows PAID.

> "40% of Bangladeshis still use feature phones. The same toll clears over
> USSD — works on a Nokia 1280."

---

## 4. Enforcement cycle — Rahim evades (2:15 – 3:45)

1. Hold **CHATTO METRO HA 14-9012** up — status `UNPAID`, BDT 750 truck toll.
2. Do *nothing* on the payment page.
3. In the dashboard sidebar click **⏩ Run enforcement tick** four times,
   roughly one per beat while narrating:
   - Tick 1 → status `REMINDED`, orange SMS bubble ("Friendly reminder…").
   - Tick 2 → `LATE`, late fee added (BDT 750 + 750).
   - Tick 3 → `FINED`, 8× fine applied (BDT ~6750 total).
   - Tick 4 → `BLOCKED` + red BRTA-block SMS. Vehicles tab shows the red banner.

> "The evader just lost fitness renewal, ownership transfer, and route
> permit — all at BRTA. That's the enforcement lever we don't have today."

---

## 5. Already blocked — Abdul's Sylhet bus (3:45 – 4:15)

1. Hold **SYLHET GA 17-7788** up.
2. Dashboard instantly shows status `BLOCKED` and a warning banner.
3. Open its pay page — the red "BRTA BLOCK ACTIVE" ribbon is visible.

> "When the gantry sees a blocked vehicle, we know in one frame. Current
> system: you find out weeks later at the BRTA counter."

---

## 6. Dashboard story (4:15 – 5:00)

Click through the tabs:

- **Events** — all passes, filter by `LATE` or `FINED`. Point at fee breakdown.
- **Vehicles** — sorted by BRTA block first. Red banner if any blocked.
- **Analytics** — collection rate, passes/minute, revenue vs outstanding.

> "Every number on this screen is auditable — one event per pass, one SMS
> per notification, one row per payment. Zero discretionary cash-handling."

---

## Closing line

> "This runs on a phone camera, a laptop, and open-source models. Deploying
> on a real gantry is the easy part — the hard part, the policy and the
> BRTA integration, is what we'd like to discuss today."

---

## If something breaks live

| Symptom                              | Fallback                                            |
|--------------------------------------|-----------------------------------------------------|
| Camera misreads plate                | Hold steady ~30 cm, good light; or type in dashboard |
| Backend 500                          | Restart `run_server.py`; events persist in SQLite   |
| Dashboard won't load                 | Refresh; check `http://localhost:8000/health`       |
| Nothing works                        | Play the 2-minute capture video (see `RECORDING.md`) |
