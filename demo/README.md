# ShohojToll — Demo Kit

Phase 8 materials for pitching the prototype.

| File              | Purpose                                                   |
|-------------------|-----------------------------------------------------------|
| `plates.html`     | Printable A4 sheet with 6 persona plate cards. Open in a  |
|                   | browser → `Ctrl+P` → **100 % scale** → print → cut.       |
| `DEMO_SCRIPT.md`  | 5-minute live walkthrough (golden path, USSD, enforcement, |
|                   | BRTA block, dashboard tour).                              |
| `HANDOUT.md`      | One-page ministry handout. Print as PDF and bring copies. |
| `RECORDING.md`    | How to record a 2-minute fallback video on Windows.       |

## Run order on demo day

```bash
# 1. clean DB (optional)
Remove-Item toll.db ; python seed.py

# 2. three terminals
python run_server.py
python detect_plates.py
python run_dashboard.py
```

Then open:

- `http://localhost:8501` — admin dashboard (the centrepiece).
- `http://localhost:8000/ussd` — USSD simulator.
- `http://localhost:8000/pay/<id>` — payment page (opened via dashboard links).

Hold the printed plate cards ~30 cm from the phone camera. Follow
`DEMO_SCRIPT.md` verbatim — it's timed to 5 minutes.
