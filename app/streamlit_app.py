"""
Glow & Grace - Salon & Spa Appointment Management System
Entry point.  Run with:   streamlit run streamlit_app.py
"""
import streamlit as st

st.set_page_config(page_title="Salon & Spa Manager", page_icon="💇", layout="wide")

from db import DBError, query_one  # noqa: E402

st.markdown(
    """
    <style>
      [data-testid="stMetricValue"] {font-size: 1.6rem;}
      .block-container {padding-top: 2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# fail early with a clear message if the database is not reachable
try:
    query_one("SELECT 1 AS ok")
except DBError as e:
    st.error(f"Database not reachable: {e}")
    st.code("mysql -u root -p < database/salon_spa_full.sql", language="bash")
    st.stop()

pages = {
    "Front desk": [
        st.Page("views/dashboard.py", title="Dashboard", icon="🏠", default=True),
        st.Page("views/customers.py", title="Customers", icon="👤"),
        st.Page("views/booking.py", title="Book Appointment", icon="📅"),
        st.Page("views/appointments.py", title="Manage Appointments", icon="🗂️"),
    ],
    "Operations": [
        st.Page("views/packages.py", title="Packages & Memberships", icon="🎁"),
        st.Page("views/products.py", title="Products & Stock", icon="🧴"),
        st.Page("views/billing.py", title="Billing & Payments", icon="🧾"),
        st.Page("views/staff.py", title="Staff & Services", icon="✂️"),
    ],
    "Insights": [
        st.Page("views/reports.py", title="Reports", icon="📊"),
    ],
}

with st.sidebar:
    st.markdown("### 💇 Glow & Grace\nSalon & Spa Manager")
    st.caption("DBMS PBL · Project 66 · MySQL + Python")

st.navigation(pages).run()
