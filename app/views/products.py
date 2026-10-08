from datetime import date

import streamlit as st

from db import execute, query_df
from ui import page_header, run_safely

page_header("Products & Stock", "Issue products against services, restock and add products.")

tab_stock, tab_issue, tab_restock = st.tabs(["📦 Stock", "➖ Issue product", "➕ Restock / add"])

with tab_stock:
    df = query_df("""SELECT product_id AS ID, product_name AS Product, brand AS Brand, unit AS Unit,
                            stock_qty AS `In stock`, reorder_level AS `Reorder at`,
                            total_used AS `Used to date`, consumption_cost AS `Cost used ₹`,
                            stock_status AS Status
                       FROM v_product_usage ORDER BY stock_status DESC, product_name""")

    def _hl(row):
        return ["background-color: #fde2e2" if row.Status == "REORDER" else "" for _ in row]

    st.dataframe(df.style.apply(_hl, axis=1).format(precision=2), hide_index=True, width="stretch")

with tab_issue:
    st.caption("Products can be issued only against services of today's or past, non-cancelled appointments.")
    d = st.date_input("Appointment date", date.today(), max_value=date.today())
    lines = query_df(
        """SELECT appt_service_id, appointment_id, start_time, customer_name, service_name, staff_name
             FROM v_appointment_details
            WHERE appointment_date = %s AND status IN ('BOOKED','COMPLETED')
            ORDER BY start_time""", (d,))
    if lines.empty:
        st.info("No services on that date.")
    else:
        lid = st.selectbox("Service performed", lines.appt_service_id.tolist(),
                           format_func=lambda i: (lambda r: f"{r.start_time} · {r.customer_name} · "
                                                            f"{r.service_name} ({r.staff_name})")(
                               lines[lines.appt_service_id == i].iloc[0]))
        prods = query_df("SELECT product_id, product_name, unit, stock_qty FROM product ORDER BY product_name")
        pid = st.selectbox("Product", prods.product_id.tolist(),
                           format_func=lambda i: (lambda r: f"{r.product_name} — {r.stock_qty:g} {r.unit} left")(
                               prods[prods.product_id == i].iloc[0]))
        qty = st.number_input("Quantity", min_value=0.0, step=1.0, value=10.0)
        if st.button("Issue product", type="primary"):
            if qty <= 0:
                st.error("Quantity must be greater than zero.")
            else:
                run_safely(lambda: execute(
                    "INSERT INTO product_usage (appt_service_id, product_id, quantity_used) VALUES (%s,%s,%s)",
                    (int(lid), int(pid), qty)), "Product issued and stock reduced.", rerun=True)
        used = query_df("""SELECT p.product_name AS Product, u.quantity_used AS Qty, p.unit AS Unit,
                                  u.issued_at AS `Issued at`
                             FROM product_usage u JOIN product p ON p.product_id = u.product_id
                            WHERE u.appt_service_id = %s""", (int(lid),))
        if not used.empty:
            st.markdown("**Already issued for this service**")
            st.dataframe(used, hide_index=True)

with tab_restock:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Restock**")
        prods = query_df("SELECT product_id, product_name, unit FROM product ORDER BY product_name")
        rp = st.selectbox("Product ", prods.product_id.tolist(),
                          format_func=lambda i: prods[prods.product_id == i].iloc[0].product_name)
        rq = st.number_input("Quantity received", min_value=0.0, step=10.0)
        if st.button("Update stock"):
            if rq <= 0:
                st.error("Quantity must be greater than zero.")
            else:
                run_safely(lambda: execute("UPDATE product SET stock_qty = stock_qty + %s WHERE product_id=%s",
                                           (rq, int(rp))), "Stock updated.", rerun=True)
    with c2:
        st.markdown("**Add new product**")
        with st.form("newprod", clear_on_submit=True):
            name = st.text_input("Product name *")
            brand = st.text_input("Brand")
            unit = st.selectbox("Unit", ["ml", "g", "pcs"])
            cost = st.number_input("Unit cost ₹", min_value=0.0, step=0.5)
            stock = st.number_input("Opening stock", min_value=0.0, step=10.0)
            reorder = st.number_input("Reorder level", min_value=0.0, step=10.0)
            if st.form_submit_button("Add product"):
                if not name.strip():
                    st.error("Product name is required.")
                else:
                    run_safely(lambda: execute(
                        """INSERT INTO product (product_name, brand, unit, unit_cost, stock_qty, reorder_level)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (name.strip(), brand.strip() or None, unit, cost, stock, reorder)),
                        "Product #{result} added.")
