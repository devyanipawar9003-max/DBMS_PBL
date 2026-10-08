from datetime import date

import streamlit as st

from db import DBError, query_df, transaction
from ui import add_minutes, customer_picker, page_header, rupees, time_slots

page_header("Book Appointment",
            "Pick the customer, date and services. Only staff who have the required skill, are on "
            "shift and are free are offered. The database re-checks every rule when you confirm.")

if "cart" not in st.session_state:
    st.session_state.cart = []
cart = st.session_state.cart

c1, c2 = st.columns([2, 1])
with c1:
    cid = customer_picker("book")
with c2:
    appt_date = st.date_input("Appointment date", value=date.today(), min_value=date.today())
if not cid:
    st.stop()

# a booking belongs to one customer + date: reset the cart if either changes
if st.session_state.get("cart_key") != (cid, appt_date):
    st.session_state.cart_key = (cid, appt_date)
    cart.clear()

st.divider()
st.subheader("Add a service")
services = query_df(
    """SELECT s.service_id, s.service_name, c.category_name, s.duration_min, s.price,
              s.required_skill_id, k.skill_name
         FROM service s JOIN service_category c ON c.category_id = s.category_id
         JOIN skill k ON k.skill_id = s.required_skill_id
        WHERE s.is_active = 1 ORDER BY c.category_name, s.service_name""")
svc_label = {int(r.service_id): f"{r.category_name} · {r.service_name} ({r.duration_min} min, {rupees(r.price)})"
             for r in services.itertuples()}

a1, a2 = st.columns([3, 1])
sid = a1.selectbox("Service", list(svc_label), format_func=svc_label.get)
svc = services[services.service_id == sid].iloc[0]
start = a2.selectbox("Start time", time_slots(int(svc.duration_min)),
                     format_func=lambda t: t.strftime("%I:%M %p"), index=8)
end = add_minutes(start, int(svc.duration_min))
st.caption(f"Required skill: **{svc.skill_name}** · ends at {end.strftime('%I:%M %p')}")

# ---- package redemption -------------------------------------------------
pk = query_df(
    """SELECT customer_package_id, package_name, sessions_included - sessions_used AS left_
         FROM v_package_balance
        WHERE customer_id = %s AND service_id = %s AND status = 'ACTIVE'
          AND expiry_date >= %s AND sessions_used < sessions_included""",
    (cid, sid, appt_date))
cpkg_id = None
if not pk.empty:
    p = pk.iloc[0]
    already = sum(1 for x in cart if x["cpkg_id"] == int(p.customer_package_id) and x["service_id"] == sid)
    if p.left_ - already > 0 and st.checkbox(
            f"🎁 Redeem from package **{p.package_name}** ({int(p.left_ - already)} session(s) left) — no charge",
            value=True):
        cpkg_id = int(p.customer_package_id)

# ---- skilled-staff assignment ------------------------------------------
only_free = st.toggle("Show only available skilled staff", value=True,
                      help="Turn off to pick any staff member - the database will reject "
                           "skill mismatches or clashes (useful to demonstrate validation).")
if only_free:
    staff = query_df(
        """SELECT st.staff_id, st.full_name, st.designation, ss.proficiency_level
             FROM staff st
             JOIN staff_skill ss    ON ss.staff_id = st.staff_id AND ss.skill_id = %s
             JOIN staff_schedule sc ON sc.staff_id = st.staff_id
                                   AND sc.day_of_week = DAYOFWEEK(%s)
                                   AND sc.shift_start <= %s AND sc.shift_end >= %s
            WHERE st.status = 'ACTIVE'
              AND NOT EXISTS (SELECT 1 FROM appointment_service s
                                JOIN appointment a ON a.appointment_id = s.appointment_id
                               WHERE s.staff_id = st.staff_id AND a.appointment_date = %s
                                 AND a.status NOT IN ('CANCELLED','NO_SHOW')
                                 AND s.start_time < %s AND %s < s.end_time)
            ORDER BY ss.proficiency_level DESC, st.full_name""",
        (int(svc.required_skill_id), appt_date, start, end, appt_date, end, start))
    # also exclude staff already holding an overlapping slot in this cart
    busy = {x["staff_id"] for x in cart if x["start"] < end and start < x["end"]}
    staff = staff[~staff.staff_id.isin(busy)]
else:
    staff = query_df("""SELECT staff_id, full_name, designation, NULL AS proficiency_level
                          FROM staff WHERE status='ACTIVE' ORDER BY full_name""")

if staff.empty:
    st.warning("No skilled staff member is free for this slot. Try another time.")
else:
    labels = {int(r.staff_id): f"{r.full_name} — {r.designation}" +
              (f" · skill level {int(r.proficiency_level)}/5" if r.proficiency_level == r.proficiency_level and r.proficiency_level is not None else "")
              for r in staff.itertuples()}
    stid = st.selectbox("Assign staff", list(labels), format_func=labels.get)
    if st.button("➕ Add to booking"):
        cart.append(dict(service_id=sid, service_name=svc.service_name, staff_id=stid,
                         staff_name=labels[stid].split(" — ")[0], start=start, end=end,
                         price=0.0 if cpkg_id else float(svc.price), cpkg_id=cpkg_id))
        st.rerun()

# ---- cart & confirm -------------------------------------------------------
st.divider()
st.subheader("Booking summary")
if not cart:
    st.info("No services added yet.")
    st.stop()

for i, x in enumerate(sorted(cart, key=lambda x: x["start"])):
    r1, r2, r3, r4, r5 = st.columns([2, 3, 3, 2, 1])
    r1.write(f"{x['start'].strftime('%I:%M %p')} – {x['end'].strftime('%I:%M %p')}")
    r2.write(x["service_name"])
    r3.write(x["staff_name"])
    r4.write("🎁 package" if x["cpkg_id"] else rupees(x["price"]))
    if r5.button("✖", key=f"rm{i}"):
        cart.remove(x)
        st.rerun()
st.markdown(f"**Estimated amount (before discount & GST): {rupees(sum(x['price'] for x in cart))}**")
notes = st.text_input("Notes (optional)", max_chars=200)

if st.button("✅ Confirm booking", type="primary"):
    try:
        # one transaction: header + all service lines, or nothing at all
        with transaction() as cur:
            cur.execute("INSERT INTO appointment (customer_id, appointment_date, notes) VALUES (%s,%s,%s)",
                        (cid, appt_date, notes or None))
            appt_id = cur.lastrowid
            for x in cart:
                cur.execute(
                    """INSERT INTO appointment_service
                         (appointment_id, service_id, staff_id, start_time, end_time,
                          price_charged, customer_package_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (appt_id, x["service_id"], x["staff_id"], x["start"], x["end"],
                     x["price"], x["cpkg_id"]))
        cart.clear()
        st.success(f"Appointment #{appt_id} booked for {appt_date:%d %b %Y}.")
        st.balloons()
    except DBError as e:
        st.error(f"❌ Booking rejected and rolled back: {e}")
