from datetime import date, timedelta

import streamlit as st

from db import execute, query_df, query_one
from ui import add_minutes, page_header, run_safely, time_slots, to_time

page_header("Manage Appointments", "Search appointments, update their status, reschedule or reassign staff.")

f1, f2, f3, f4 = st.columns(4)
d_from = f1.date_input("From", date.today())
d_to = f2.date_input("To", date.today() + timedelta(days=7))
status = f3.multiselect("Status", ["BOOKED", "COMPLETED", "CANCELLED", "NO_SHOW"], default=["BOOKED", "COMPLETED"])
term = f4.text_input("Customer name / phone")

if not status:
    st.stop()
ph = ",".join(["%s"] * len(status))
df = query_df(
    f"""SELECT appointment_id AS Appt, appointment_date AS Date, start_time AS Start, end_time AS End,
               customer_name AS Customer, customer_phone AS Phone, service_name AS Service,
               staff_name AS Staff, price_charged AS `Price ₹`, from_package AS Package, status AS Status
          FROM v_appointment_details
         WHERE appointment_date BETWEEN %s AND %s AND status IN ({ph})
           AND (customer_name LIKE %s OR customer_phone LIKE %s)
         ORDER BY appointment_date, start_time""",
    (d_from, d_to, *status, f"%{term}%", f"%{term}%"))
st.caption(f"{df['Appt'].nunique() if not df.empty else 0} appointment(s), {len(df)} service line(s)")
st.dataframe(df, hide_index=True, width="stretch", height=300)
if df.empty:
    st.stop()

st.divider()
appt_id = st.selectbox("Select appointment", sorted(df["Appt"].unique()),
                       format_func=lambda a: f"#{a} – {df[df.Appt == a].iloc[0].Customer} on {df[df.Appt == a].iloc[0].Date}")
appt = query_one("SELECT * FROM appointment WHERE appointment_id=%s", (int(appt_id),))
st.markdown(f"**Current status:** `{appt.status}`")

b1, b2, b3 = st.columns(3)
if appt.status == "BOOKED":
    if b1.button("✔ Mark completed", type="primary"):
        if appt.appointment_date > date.today():
            st.error("A future appointment cannot be marked completed.")
        else:
            run_safely(lambda: execute("UPDATE appointment SET status='COMPLETED' WHERE appointment_id=%s",
                                       (int(appt_id),)), "Marked completed. You can now raise the bill.", rerun=True)
    confirm = b2.checkbox("Confirm cancellation")
    if b2.button("✖ Cancel appointment", disabled=not confirm):
        run_safely(lambda: execute("UPDATE appointment SET status='CANCELLED' WHERE appointment_id=%s",
                                   (int(appt_id),)), "Appointment cancelled; staff slots and package sessions released.", rerun=True)
    if b3.button("🚫 Mark no-show"):
        run_safely(lambda: execute("UPDATE appointment SET status='NO_SHOW' WHERE appointment_id=%s",
                                   (int(appt_id),)), "Marked as no-show.", rerun=True)

    st.subheader("Reschedule / reassign a service")
    lines = query_df(
        """SELECT s.appt_service_id, sv.service_name, sv.duration_min, sv.required_skill_id,
                  s.staff_id, s.start_time
             FROM appointment_service s JOIN service sv ON sv.service_id = s.service_id
            WHERE s.appointment_id = %s""", (int(appt_id),))
    line_id = st.selectbox("Service line", lines.appt_service_id.tolist(),
                           format_func=lambda i: f"{lines[lines.appt_service_id == i].iloc[0].service_name} "
                                                 f"@ {lines[lines.appt_service_id == i].iloc[0].start_time}")
    ln = lines[lines.appt_service_id == line_id].iloc[0]
    staff = query_df("""SELECT st.staff_id, st.full_name FROM staff st
                          JOIN staff_skill ss ON ss.staff_id = st.staff_id AND ss.skill_id = %s
                         WHERE st.status = 'ACTIVE' ORDER BY st.full_name""", (int(ln.required_skill_id),))
    st.caption("Same-day changes only; to move to another date, cancel and book again.")
    r2, r3 = st.columns(2)
    slots = time_slots(int(ln.duration_min))
    cur_t = to_time(ln.start_time)
    new_start = r2.selectbox("New start", slots, index=slots.index(cur_t) if cur_t in slots else 0,
                             format_func=lambda t: t.strftime("%I:%M %p"))
    ids = staff.staff_id.tolist()
    new_staff = r3.selectbox("Staff (skilled only)", ids,
                             index=ids.index(ln.staff_id) if ln.staff_id in ids else 0,
                             format_func=lambda i: staff[staff.staff_id == i].iloc[0].full_name)
    if st.button("💾 Save reschedule"):
        run_safely(lambda: execute(
            """UPDATE appointment_service SET staff_id=%s, start_time=%s, end_time=%s
                WHERE appt_service_id=%s""",
            (int(new_staff), new_start, add_minutes(new_start, int(ln.duration_min)), int(line_id))),
            "Rescheduled - the database confirmed there is no clash.", rerun=True)
else:
    st.info("Only BOOKED appointments can be changed.")
