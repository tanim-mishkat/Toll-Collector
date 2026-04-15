# ShohojToll — One-page Ministry Handout

**Automated, cashless, booth-less toll collection for Bangladesh.**
A prototype for the Ministry of Road Transport & Bridges / Bangladesh Bridge
Authority / BRTA.

---

### The problem today

- Every toll plaza is a bottleneck: 2–8 minutes per vehicle at peak.
- Cash handling at booths invites leakage; reconciliation is manual.
- No shared enforcement lever — a non-payer today simply drives on tomorrow.
- FASTag-style RFID needs every vehicle re-fitted. Not feasible short-term.

### What ShohojToll does

1. **Camera-only capture.** Overhead gantry reads the plate with YOLOv8 +
   OCR. No sticker, no tag, no driver action.
2. **Mobile-money first.** bKash / Nagad / bank — same rails citizens
   already use for recharge and bills. One-tap PIN confirm.
3. **USSD fallback.** `*999#` on any feature phone. No smartphone needed.
4. **Automated escalation.** UNPAID → REMINDED → LATE → FINED → BRTA BLOCK.
   Every step is an SMS, auto-timed, no human touch.
5. **BRTA integration as the teeth.** A blocked plate cannot renew fitness,
   cannot transfer ownership, cannot obtain a route permit — without any
   new legal instrument.

### What the prototype proves

| Capability                                 | Status  |
|--------------------------------------------|---------|
| ANPR on Bangladeshi two-line plates        | Working |
| Toll pricing per vehicle class             | Working |
| bKash / Nagad / USSD payment simulation    | Working |
| Automated SMS + Telegram mirror            | Working |
| State-machine enforcement (reminder → block)| Working |
| Admin dashboard with live feed + analytics | Working |
| Runs on a laptop + a phone camera          | Working |

### Economics (rough)

- Per-gantry hardware: ≈ BDT 2–3 lakh (IP cam + edge box + signage).
- Staffing: 0 at the booth; ops team centralised.
- Break-even vs. a single manned booth: under 6 months at Padma-Bridge
  volumes (≈ 15k vehicles/day).

### Roadmap from here

| Phase | Scope                                                           | Time   |
|-------|-----------------------------------------------------------------|--------|
| Pilot | One gantry, one lane, 500 pre-enrolled vehicles                 | 2–3 mo |
| A     | bKash / Nagad merchant integration (real APIs, SSLCommerz)      | 1 mo   |
| B     | BRTA data pipe — block/unblock via official API                 | 2 mo   |
| C     | Multi-gantry, speed-based / distance-based pricing (ERP-style)  | 3 mo   |
| D     | National rollout, appeal portal, revenue audit dashboard        | 6 mo+  |

### International precedent

- **Singapore ERP 2.0** — satellite + camera, no cash, no RFID card.
- **London Congestion Charge** — pure ANPR, payment by app / SMS.
- **India FASTag** — worked, but required mass sticker rollout. We skip that.

### Contact

Prototype code, demo video, and technical design available on request.
