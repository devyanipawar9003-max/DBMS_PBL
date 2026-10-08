from datetime import date, timedelta

import streamlit as st

from db import execute, query_df
from ui import customer_picker, page_header, rupees, run_safely

page_header("Packages & Memberships", "Sell prepaid packages and memberships; track remaining sessions.")

tab_cat, tab_sell, tab_bal, tab_mem = st.tabs(
    ["📦 Package catalogue", "🛒 Sell package", "📊 Package balances", "⭐ Memberships"])

with tab_cat:
    cat = query_df(
        """SELECT p.package_name AS Package, p.price AS `Price ₹`, p.validity_days AS `Valid (days)`,
                  GROUP_CONCAT(CONCAT(pi.sessions_included,' × ',s.service_name) SEPARATOR ', ') AS Includes,
                  SUM(pi.sessions_included * s.price) AS `Worth ₹`
             FROM package p JOIN package_item pi ON pi.package_id = p.package_id
             JOIN service s ON s.service_id = pi.service_id
            WHERE p.is_active = 1
            GROUP BY p.package_id, p.package_name, p.price, p.validity_days""")
    cat["You save ₹"] = cat["Worth ₹"] - cat["Price ₹"]
    st.dataframe(cat, hide_index=True, width="stretch")

with tab_sell:
    cid = customer_picker("pkg")
    pk = query_df("SELECT package_id, package_name, price, validity_days FROM package WHERE is_active=1")
    pid = st.selectbox("Package", pk.package_id.tolist(),
                       format_func=lambda i: f"{pk[pk.package_id == i].iloc[0].package_name} – "
                                             f"{rupees(pk[pk.package_id == i].iloc[0].price)}")
    p = pk[pk.package_id == pid].iloc[0]
    buy = st.date_input("Purchase date", date.today(), max_value=date.today())
    exp = buy + timedelta(days=int(p.validity_days))
    st.caption(f"Valid until **{exp:%d %b %Y}**")
    if cid and st.button("Sell package", type="primary"):
        run_safely(lambda: execute(
            """INSERT INTO customer_package (customer_id, package_id, purchase_date, expiry_date, amount_paid)
               VALUES (%s,%s,%s,%s,%s)""", (cid, int(pid), buy, exp, float(p.price))),
            "Package sold (customer package #{result}).", rerun=True)

with tab_bal:
    term = st.text_input("Filter by customer name")
    only_active = st.checkbox("Active packages only", value=True)
    bal = query_df(
        f"""SELECT customer_package_id AS `Pkg #`, customer_name AS Customer, package_name AS Package,
                   service_name AS Service, sessions_included AS Included, sessions_used AS Used,
                   sessions_included - sessions_used AS `Left`, expiry_date AS Expires, status AS Status
              FROM v_package_balance
             WHERE customer_name LIKE %s {"AND status='ACTIVE'" if only_active else ""}
             ORDER BY expiry_date""", (f"%{term}%",))
    st.dataframe(bal, hide_index=True, width="stretch")

with tab_mem:
    plans = query_df("SELECT plan_id, plan_name, annual_fee, discount_pct FROM membership_plan")
    st.dataframe(plans.rename(columns={"plan_name": "Plan", "annual_fee": "Annual fee ₹",
                                       "discount_pct": "Discount %"}).drop(columns="plan_id"),
                 hide_index=True)
    cid2 = customer_picker("mem")
    plan = st.selectbox("Plan", plans.plan_id.tolist(),
                        format_func=lambda i: plans[plans.plan_id == i].iloc[0].plan_name)
    start = st.date_input("Start date", date.today(), key="mstart")
    if cid2 and st.button("Enrol member", type="primary"):
        active = query_df("""SELECT 1 FROM customer_membership WHERE customer_id=%s
                              AND %s BETWEEN start_date AND end_date""", (cid2, start))
        if not active.empty:
            st.error("This customer already has an active membership on that date.")
        else:
            run_safely(lambda: execute(
                """INSERT INTO customer_membership (customer_id, plan_id, start_date, end_date)
                   VALUES (%s,%s,%s,%s)""", (cid2, int(plan), start, start + timedelta(days=365))),
                "Membership created.", rerun=True)
