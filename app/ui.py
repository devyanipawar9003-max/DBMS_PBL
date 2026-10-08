"""Shared UI helpers and validation used by every screen."""
import re
from datetime import date, time, timedelta

import streamlit as st

from db import DBError, query_df

PHONE_RE = re.compile(r"^[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{0,39}$")
GST_RATE = 0.18


def rupees(x) -> str:
    return f"₹{float(x):,.2f}"


def to_time(hhmm: str) -> time:
    h, m = map(int, hhmm.split(":"))
    return time(h, m)


def add_minutes(t: time, minutes: int) -> time:
    dt = (timedelta(hours=t.hour, minutes=t.minute) + timedelta(minutes=minutes))
    secs = int(dt.total_seconds())
    return time(secs // 3600, secs % 3600 // 60)


def time_slots(duration: int, step: int = 15):
    """Start times between 09:00 and 21:00 that let the service finish by 21:00."""
    slots, t = [], 9 * 60
    while t + duration <= 21 * 60:
        slots.append(time(t // 60, t % 60))
        t += step
    return slots


def validate_customer(first, last, phone, email, dob):
    errors = []
    if not NAME_RE.match(first.strip()):
        errors.append("First name is required and may contain letters, spaces, . ' - only.")
    if not NAME_RE.match(last.strip()):
        errors.append("Last name is required and may contain letters, spaces, . ' - only.")
    if not PHONE_RE.match(phone.strip()):
        errors.append("Phone must be a 10-digit Indian mobile number starting with 6-9.")
    if email.strip() and not EMAIL_RE.match(email.strip()):
        errors.append("Email address is not valid.")
    if dob and dob > date.today():
        errors.append("Date of birth cannot be in the future.")
    return errors


def customer_picker(key: str, label: str = "Customer"):
    """Search box + select box. Returns customer_id or None."""
    term = st.text_input(f"Search {label.lower()} by name or phone", key=f"{key}_term",
                         placeholder="e.g. Sahithi or 98480...")
    like = f"%{term.strip()}%"
    df = query_df(
        """SELECT customer_id, CONCAT(first_name,' ',last_name) AS name, phone
             FROM customer
            WHERE CONCAT(first_name,' ',last_name) LIKE %s OR phone LIKE %s
            ORDER BY first_name, last_name LIMIT 200""", (like, like))
    if df.empty:
        st.info("No matching customer. Register the customer first.")
        return None
    options = {f"{r.name}  ·  {r.phone}  (#{r.customer_id})": int(r.customer_id) for r in df.itertuples()}
    choice = st.selectbox(label, list(options.keys()), key=f"{key}_sel")
    return options[choice]


def run_safely(fn, success_msg=None, rerun=False):
    """Run a DB action; show a green message on success and a red one on error.
    With rerun=True the page is refreshed so tables show the new state, and the
    success message is carried over to the refreshed page."""
    try:
        result = fn()
        msg = success_msg.format(result=result) if success_msg else None
        if rerun:
            st.session_state["_flash"] = msg
            st.rerun()
        if msg:
            st.success(msg)
        return result
    except DBError as e:
        st.error(f"❌ {e}")
        return None


def page_header(title: str, caption: str = ""):
    st.title(title)
    if caption:
        st.caption(caption)
    flash = st.session_state.pop("_flash", None)
    if flash:
        st.success(flash)
