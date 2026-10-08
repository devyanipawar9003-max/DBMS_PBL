from datetime import date, timedelta

import streamlit as st

from db import query_df
from ui import page_header

page_header("Reports", "Six management reports, each backed by a SQL view or aggregate query.")


def show(df, name, chart=None):
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button(f"⬇ Download {name}.csv", df.to_csv(index=False).encode(), f"{name}.csv", "text/csv")
    if chart is not None:
        chart()


t1, t2, t3, t4, t5, t6 = st.tabs(["📅 Appointments", "👥 Staff utilisation", "⭐ Service popularity",
                                  "🎁 Package balances", "🧴 Product use", "💰 Revenue"])

with t1:
    c1, c2 = st.columns(2)
    d1 = c1.date_input("From", date.today() - timedelta(days=30), key="r1a")
    d2 = c2.date_input("To", date.today(), key="r1b")
    df = query_df(
        """SELECT appointment_date AS Date,
                  COUNT(DISTINCT appointment_id) AS Appointments,
                  COUNT(DISTINCT CASE WHEN status='COMPLETED' THEN appointment_id END) AS Completed,
                  COUNT(DISTINCT CASE WHEN status='CANCELLED' THEN appointment_id END) AS Cancelled,
                  COUNT(DISTINCT CASE WHEN status='NO_SHOW'   THEN appointment_id END) AS `No-show`,
                  COUNT(*) AS `Services booked`
             FROM v_appointment_details
            WHERE appointment_date BETWEEN %s AND %s
            GROUP BY appointment_date ORDER BY appointment_date""", (d1, d2))
    if not df.empty:
        tot = df[["Appointments", "Completed", "Cancelled", "No-show"]].sum()
        m = st.columns(4)
        for col, (k, v) in zip(m, tot.items()):
            col.metric(k, int(v))
    show(df, "appointments", lambda: st.line_chart(df.set_index("Date")[["Appointments", "Completed"]], color=["#9C3D6B", "#E3A6C2"]))

with t2:
    df = query_df("""SELECT full_name AS Staff, designation AS Role, services_done AS Services,
                            minutes_worked AS Minutes, revenue_generated AS `Revenue ₹`,
                            utilization_pct AS `Utilisation %` FROM v_staff_utilization
                      ORDER BY utilization_pct DESC""")
    st.caption("Utilisation = minutes of completed services ÷ scheduled shift minutes over the period.")
    show(df, "staff_utilisation", lambda: st.bar_chart(df.set_index("Staff")["Utilisation %"], horizontal=True, sort=False, color="#9C3D6B"))

with t3:
    df = query_df("""SELECT service_name AS Service, category_name AS Category, times_booked AS Bookings,
                            via_package AS `Via package`, revenue AS `Revenue ₹`
                       FROM v_service_popularity ORDER BY times_booked DESC""")
    show(df, "service_popularity", lambda: st.bar_chart(df.head(10).set_index("Service")["Bookings"], horizontal=True, sort=False, color="#9C3D6B"))
    cat = query_df("""SELECT category_name AS Category, SUM(revenue) AS `Revenue ₹`
                        FROM v_service_popularity GROUP BY category_name ORDER BY 2 DESC""")
    st.markdown("**Revenue by category**")
    st.bar_chart(cat.set_index("Category"), sort=False, color="#9C3D6B")

with t4:
    df = query_df("""SELECT customer_name AS Customer, package_name AS Package, service_name AS Service,
                            sessions_included AS Included, sessions_used AS Used,
                            sessions_included - sessions_used AS `Left`, expiry_date AS Expires, status AS Status
                       FROM v_package_balance ORDER BY status, expiry_date""")
    show(df, "package_balances")

with t5:
    df = query_df("""SELECT product_name AS Product, brand AS Brand, unit AS Unit, total_used AS Used,
                            consumption_cost AS `Cost ₹`, stock_qty AS `In stock`, reorder_level AS `Reorder at`,
                            stock_status AS Status FROM v_product_usage ORDER BY consumption_cost DESC""")
    show(df, "product_use", lambda: st.bar_chart(df.set_index("Product")["Cost ₹"], horizontal=True, sort=False, color="#9C3D6B"))

with t6:
    df = query_df("""SELECT month AS Month, bills AS Bills, gross_sales AS `Gross ₹`, discounts AS `Discounts ₹`,
                            gst AS `GST ₹`, billed AS `Billed ₹`, collected AS `Collected ₹` FROM v_monthly_revenue
                      ORDER BY month""")
    show(df, "revenue", lambda: st.bar_chart(df.set_index("Month")[["Billed ₹", "Collected ₹"]], stack=False, color=["#9C3D6B", "#E3A6C2"]))
    pm = query_df("SELECT method AS Method, COUNT(*) AS Payments, SUM(amount) AS `Amount ₹` FROM payment GROUP BY method")
    st.markdown("**Collections by payment method**")
    st.dataframe(pm, hide_index=True)
