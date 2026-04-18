"""Phase 7 — Streamlit admin dashboard.

Talks to the FastAPI backend on BACKEND_URL. Run with:
    streamlit run dashboard.py
(and keep run_server.py running in another terminal).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import requests
import streamlit as st
import time

# In production (Streamlit Community Cloud) BACKEND_URL comes from st.secrets.
# Locally it falls back to config.py.
try:
    BACKEND_URL = st.secrets["BACKEND_URL"]
except (FileNotFoundError, KeyError):
    from config import BACKEND_URL


# ---------- HTTP helpers ----------

def api_get(path: str, **params) -> Any:
    try:
        r = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=4)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.error(f"Backend unreachable ({path}): {e}")
        return None


def api_post(path: str, json: dict | None = None) -> Any:
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=json, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        return {"_error": str(e), "status_code": getattr(e.response, "status_code", None)}


# ---------- page chrome ----------

st.set_page_config(
    page_title="ShohojToll — Admin",
    page_icon="🛣",
    layout="wide",
)

# Auto-refresh: rerun every 4 seconds
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
if time.time() - st.session_state.last_refresh > 4:
    st.session_state.last_refresh = time.time()
    st.rerun()

st.markdown(
    """
    <style>
    .metric-card {
      background: #fff; padding: 14px 18px; border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .sms-bubble {
      background: #e6f4ea; color: #0b2d19; padding: 10px 14px;
      border-radius: 14px 14px 14px 2px; margin: 6px 0; font-size: 13px;
      max-width: 100%;
    }
    .sms-bubble.reminder  { background: #fff3e0; }
    .sms-bubble.late_fee  { background: #ffe8d6; }
    .sms-bubble.fine      { background: #fdecea; }
    .sms-bubble.brta_block{ background: #fcd2cf; border:1px solid #c62828; }
    .sms-bubble .from { font-size: 11px; color: #666; margin-bottom: 3px; }
    .sms-bubble .body { white-space: pre-wrap; font-family: -apple-system, Segoe UI, Roboto; }
    .pill { display:inline-block; padding:2px 9px; border-radius:999px;
            font-size:11px; font-weight:700; letter-spacing:0.3px; }
    .pill.paid     { background:#e6f4ea; color:#0b7a3b; }
    .pill.unpaid   { background:#fff3e0; color:#b26a00; }
    .pill.reminded { background:#fff3e0; color:#b26a00; }
    .pill.late     { background:#ffe0cc; color:#b24700; }
    .pill.fined    { background:#fdecea; color:#c62828; }
    .pill.blocked  { background:#c62828; color:#fff; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🛣 ShohojToll — Admin Console")
st.caption(f"Backend: `{BACKEND_URL}`  ·  refreshed {datetime.now():%H:%M:%S}")


# ---------- top metrics ----------

stats = api_get("/stats") or {}
by_status: dict[str, int] = stats.get("by_status", {}) or {}

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue collected", f"BDT {stats.get('revenue_bdt', 0):,.0f}")
c2.metric("Outstanding",       f"BDT {stats.get('outstanding_bdt', 0):,.0f}")
c3.metric("Total events",      f"{stats.get('total_events', 0)}")
c4.metric("Paid events",       f"{by_status.get('PAID', 0)}")
c5.metric("Vehicles blocked",  f"{stats.get('blocked_vehicles', 0)}",
          delta_color="inverse")

with st.sidebar:
    st.subheader("Demo controls")
    if st.button("⏩ Run enforcement tick", use_container_width=True):
        res = api_post("/admin/tick")
        if res and "transitions" in res:
            st.success(f"Transitions: {res['transitions']}")
        else:
            st.error(res)
    st.caption("One tick advances events that have aged past "
              "REMINDED / LATE / FINED / BLOCKED thresholds.")
    st.divider()
    st.write("**Refresh:** every 4s")
    if st.button("↻ Refresh now", use_container_width=True):
        st.rerun()


# ---------- tabs ----------

tab_live, tab_events, tab_vehicles, tab_analytics = st.tabs(
    ["📡 Live Feed", "🧾 Events", "🚗 Vehicles", "📊 Analytics"]
)


def _pill(status: str) -> str:
    cls = status.lower()
    return f'<span class="pill {cls}">{status}</span>'


def _event_total(e: dict) -> float:
    return (e.get("amount_bdt") or 0) + (e.get("late_fee_bdt") or 0) + (e.get("fine_bdt") or 0)


# ---------- Live Feed ----------

with tab_live:
    col_events, col_sms = st.columns([3, 2])

    with col_events:
        st.subheader("Recent plate captures")
        events = api_get("/events", limit=15) or []
        if not events:
            st.info("No events yet. Hold a plate in front of the camera.")
        for e in events:
            total = _event_total(e)
            when = e["created_at"][11:19]
            blocked = e["status"] == "BLOCKED"
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                c1.markdown(
                    f"**{e['plate']}**  \n"
                    f"<span style='color:#666;font-size:12px;'>"
                    f"#{e['id']} · {e['gantry_id']} · {when}</span>",
                    unsafe_allow_html=True,
                )
                c2.markdown(
                    f"BDT **{total:,.0f}**  \n"
                    f"<span style='color:#666;font-size:12px;'>"
                    f"base {e['amount_bdt']:.0f}"
                    + (f" + late {e['late_fee_bdt']:.0f}" if e['late_fee_bdt'] else "")
                    + (f" + fine {e['fine_bdt']:.0f}" if e['fine_bdt'] else "")
                    + "</span>",
                    unsafe_allow_html=True,
                )
                c3.markdown(_pill(e["status"]), unsafe_allow_html=True)
                if e["status"] != "PAID":
                    c3.markdown(
                        f"[Pay page →]({BACKEND_URL}/pay/{e['id']})",
                        unsafe_allow_html=True,
                    )
                if blocked:
                    st.warning("🚫 BRTA block active on this vehicle.", icon="⚠")

    with col_sms:
        st.subheader("SMS outbox")
        sms = api_get("/sms", limit=15) or []
        if not sms:
            st.info("No SMS sent yet.")
        for m in sms:
            kind = m["kind"].lower()
            tg = "📲 Telegram · " if m.get("telegram_sent") else ""
            ts = m["created_at"][11:19]
            body = m["body"].replace("<", "&lt;").replace(">", "&gt;")
            st.markdown(
                f'<div class="sms-bubble {kind}">'
                f'<div class="from">{tg}to {m["to_phone"]} · {ts} · {m["kind"]}</div>'
                f'<div class="body">{body}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ---------- Events tab ----------

with tab_events:
    st.subheader("All toll events")
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "UNPAID", "REMINDED", "LATE", "FINED", "BLOCKED", "PAID"],
        index=0,
    )
    params: dict[str, Any] = {"limit": 200}
    if status_filter != "All":
        params["status"] = status_filter
    events = api_get("/events", **params) or []

    if not events:
        st.info("No events match that filter.")
    else:
        df = pd.DataFrame(events)
        df["total_bdt"] = df["amount_bdt"].fillna(0) + \
                         df["late_fee_bdt"].fillna(0) + \
                         df["fine_bdt"].fillna(0)
        df["pay_link"] = df["id"].apply(lambda i: f"{BACKEND_URL}/pay/{i}")
        cols = ["id", "plate", "gantry_id", "status",
                "amount_bdt", "late_fee_bdt", "fine_bdt", "total_bdt",
                "created_at", "paid_at", "pay_link"]
        st.dataframe(
            df[cols],
            use_container_width=True,
            column_config={
                "pay_link": st.column_config.LinkColumn(
                    "Pay page", display_text="open"),
                "amount_bdt":  st.column_config.NumberColumn("Toll", format="%.0f"),
                "late_fee_bdt":st.column_config.NumberColumn("Late",  format="%.0f"),
                "fine_bdt":    st.column_config.NumberColumn("Fine",  format="%.0f"),
                "total_bdt":   st.column_config.NumberColumn("Total", format="%.0f"),
            },
            hide_index=True,
        )

        # Quick-pay controls for live demos
        unpaid_ids = [e["id"] for e in events if e["status"] != "PAID"]
        if unpaid_ids:
            st.markdown("### Quick-pay (demo)")
            c1, c2 = st.columns([1, 3])
            target = c1.selectbox("Event", unpaid_ids, key="qp_event")
            if c2.button("Mark as PAID", type="primary"):
                res = api_post(f"/events/{target}/pay")
                if res and "event" in res:
                    st.success(f"#{target} paid. {res.get('message','')}")
                    st.rerun()
                else:
                    st.error(res)


# ---------- Vehicles tab ----------

with tab_vehicles:
    st.subheader("Vehicle registry")
    vehicles = api_get("/vehicles") or []
    if not vehicles:
        st.info("No vehicles in DB. Run `python seed.py`.")
    else:
        rows = []
        for v in vehicles:
            detail = api_get(f"/vehicles/{v['plate']}") or {}
            rows.append({
                "plate": v["plate"],
                "owner": v.get("owner_name", ""),
                "phone": v.get("phone", ""),
                "class": v.get("vehicle_class", ""),
                "registered": v.get("registered", False),
                "brta_blocked": v.get("brta_blocked", False),
                "unpaid": detail.get("unpaid_count", 0),
                "total_due_bdt": detail.get("total_due_bdt", 0.0),
            })
        df = pd.DataFrame(rows).sort_values(
            ["brta_blocked", "total_due_bdt"], ascending=[False, False]
        )
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "brta_blocked": st.column_config.CheckboxColumn("BRTA block"),
                "registered":   st.column_config.CheckboxColumn("Registered"),
                "total_due_bdt":st.column_config.NumberColumn("Total due", format="BDT %.0f"),
            },
        )
        blocked = df[df["brta_blocked"]]
        if len(blocked):
            st.error(
                f"🚫 {len(blocked)} vehicle(s) under BRTA block — "
                f"fitness / ownership / route-permit renewal suspended."
            )


# ---------- Analytics tab ----------

with tab_analytics:
    st.subheader("Throughput and collection")
    events = api_get("/events", limit=500) or []

    m1, m2, m3 = st.columns(3)
    total = len(events)
    paid = sum(1 for e in events if e["status"] == "PAID")
    collection = (paid / total * 100) if total else 0.0
    m1.metric("Collection rate", f"{collection:.1f}%")
    m2.metric("Gantry passes (last 500)", f"{total}")
    m3.metric("Avg toll (BDT)",
              f"{(sum(_event_total(e) for e in events) / total):.0f}" if total else "—")

    if not events:
        st.info("No data yet.")
    else:
        df = pd.DataFrame(events)
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["total"] = df["amount_bdt"].fillna(0) + \
                      df["late_fee_bdt"].fillna(0) + \
                      df["fine_bdt"].fillna(0)

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Events by status**")
            status_counts = (df.groupby("status").size()
                               .reindex(["UNPAID","REMINDED","LATE","FINED","BLOCKED","PAID"])
                               .fillna(0).astype(int))
            st.bar_chart(status_counts)

        with c2:
            st.markdown("**Passes over time (per minute)**")
            timeline = (df.set_index("created_at")
                          .resample("1min")
                          .size()
                          .rename("passes"))
            st.line_chart(timeline)

        st.markdown("**Revenue vs outstanding**")
        split = pd.DataFrame({
            "BDT": [
                df.loc[df["status"] == "PAID", "total"].sum(),
                df.loc[df["status"] != "PAID", "total"].sum(),
            ],
        }, index=["Collected", "Outstanding"])
        st.bar_chart(split)
