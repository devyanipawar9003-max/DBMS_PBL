from datetime import date

import streamlit as st

from db import query_df, query_one
from ui import page_header, rupees

page_header("Dashboard", "Today's front-desk snapshot, pulled live from the database.")

day = st.date_input("Show schedule for", value=date.today())

k = query_one(
    """SELECT
         (SELECT COUNT(*) FROM appointment WHERE appointment_date = %s
             AND status IN ('BOOKED','COMPLETED'))                          AS appts_today,
         (SELECT COALESCE(SUM(total_amount),0) FROM bill
           WHERE YEAR(bill_date) = YEAR(%s) AND MONTH(bill_date) = MONTH(%s))   AS month_billed,
         (SELECT COALESCE(SUM(balance_due),0) FROM v_bill_summary)          AS outstanding,
         (SELECT COUNT(*) FROM v_product_usage WHERE stock_status='REORDER') AS low_stock,
         (SELECT COUNT(*) FROM customer)                                     AS customers""",
    (day, day, day),
)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Appointments on day", int(k.appts_today))
c2.metric("Billed this month", rupees(k.month_billed))
c3.metric("Outstanding dues", rupees(k.outstanding))
c4.metric("Products to reorder", int(k.low_stock))
c5.metric("Registered customers", int(k.customers))

st.subheader(f"Schedule · {day:%a, %d %b %Y}")
sched = query_df(
    """SELECT start_time AS `Start`, end_time AS `End`, customer_name AS `Customer`,
              service_name AS `Service`, staff_name AS `Staff`, status AS `Status`,
              from_package AS `Package`
         FROM v_appointment_details
        WHERE appointment_date = %s
        ORDER BY start_time, staff_name""",
    (day,),
)
if sched.empty:
    st.info("No appointments on this day.")
else:
    st.dataframe(sched, hide_index=True, width="stretch")

left, right = st.columns(2)
with left:
    st.subheader("Monthly revenue")
    rev = query_df("SELECT month, billed, collected FROM v_monthly_revenue ORDER BY month")
    if not rev.empty:
        st.bar_chart(rev.set_index("month"), stack=False, y_label="₹", color=["#9C3D6B", "#E3A6C2"])
with right:
    st.subheader("Top 8 services")
    pop = query_df("""SELECT service_name, times_booked FROM v_service_popularity
                      ORDER BY times_booked DESC LIMIT 8""")
    if not pop.empty:
        st.bar_chart(pop.set_index("service_name"), horizontal=True, x_label="bookings", sort=False, color="#9C3D6B")
