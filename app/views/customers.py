from datetime import date

import streamlit as st

from db import execute, query_df, query_one
from ui import customer_picker, page_header, run_safely, validate_customer

page_header("Customers", "Register, search, update and remove customers.")

tab_new, tab_find, tab_hist = st.tabs(["➕ Register", "🔍 Search & Edit", "🕘 Visit history"])

# ------------------------------------------------------------------ CREATE
with tab_new:
    with st.form("new_customer", clear_on_submit=True):
        c1, c2 = st.columns(2)
        first = c1.text_input("First name *")
        last = c2.text_input("Last name *")
        phone = c1.text_input("Mobile number *", max_chars=10, placeholder="10 digits, starts with 6-9")
        email = c2.text_input("Email")
        gender = c1.selectbox("Gender", ["F", "M", "O"], format_func={"F": "Female", "M": "Male", "O": "Other"}.get)
        dob = c2.date_input("Date of birth", value=None, min_value=date(1930, 1, 1), max_value=date.today())
        ok = st.form_submit_button("Register customer", type="primary")
    if ok:
        errs = validate_customer(first, last, phone, email, dob)
        if errs:
            for e in errs:
                st.error(e)
        else:
            run_safely(
                lambda: execute(
                    """INSERT INTO customer (first_name, last_name, phone, email, gender, date_of_birth)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (first.strip().title(), last.strip().title(), phone.strip(),
                     email.strip().lower() or None, gender, dob)),
                "Customer registered with ID #{result}.")

# ------------------------------------------------------------ READ / UPDATE / DELETE
with tab_find:
    term = st.text_input("Search by name, phone or email", key="cust_search")
    like = f"%{term.strip()}%"
    df = query_df(
        """SELECT customer_id AS ID, first_name AS `First name`, last_name AS `Last name`,
                  phone AS Phone, email AS Email, gender AS Gender, date_of_birth AS DOB,
                  DATE(registered_on) AS Registered
             FROM customer
            WHERE CONCAT(first_name,' ',last_name) LIKE %s OR phone LIKE %s OR email LIKE %s
            ORDER BY customer_id DESC""", (like, like, like))
    st.caption(f"{len(df)} customer(s) found")
    st.dataframe(df, hide_index=True, width="stretch", height=280)

    if not df.empty:
        cid = st.selectbox("Select customer to edit", df["ID"].tolist(),
                           format_func=lambda i: f"#{i} – " + " ".join(df.loc[df.ID == i, ["First name", "Last name"]].iloc[0]))
        row = query_one("SELECT * FROM customer WHERE customer_id = %s", (int(cid),))
        with st.form("edit_customer"):
            c1, c2 = st.columns(2)
            first = c1.text_input("First name", row.first_name)
            last = c2.text_input("Last name", row.last_name)
            phone = c1.text_input("Mobile number", row.phone, max_chars=10)
            email = c2.text_input("Email", row.email or "")
            save = st.form_submit_button("Save changes", type="primary")
        if save:
            errs = validate_customer(first, last, phone, email, None)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                run_safely(lambda: execute(
                    """UPDATE customer SET first_name=%s, last_name=%s, phone=%s, email=%s
                        WHERE customer_id=%s""",
                    (first.strip().title(), last.strip().title(), phone.strip(),
                     email.strip().lower() or None, int(cid))), "Customer updated.")

        with st.expander("🗑️ Delete customer"):
            st.warning("Only customers with no appointments, packages or memberships can be deleted "
                       "(the database enforces this with foreign keys).")
            sure = st.checkbox(f"Yes, permanently delete customer #{cid}")
            if st.button("Delete", disabled=not sure):
                run_safely(lambda: execute("DELETE FROM customer WHERE customer_id=%s", (int(cid),)),
                           "Customer deleted.")

# ------------------------------------------------------------------ HISTORY
with tab_hist:
    cid = customer_picker("hist")
    if cid:
        m = query_df(
            """SELECT mp.plan_name AS Plan, mp.discount_pct AS `Discount (pct)`, cm.start_date AS `From`,
                      cm.end_date AS `To`,
                      CASE WHEN CURDATE() BETWEEN cm.start_date AND cm.end_date
                           THEN 'Active' ELSE 'Expired' END AS Status
                 FROM customer_membership cm JOIN membership_plan mp ON mp.plan_id = cm.plan_id
                WHERE cm.customer_id = %s""", (cid,))
        if not m.empty:
            st.markdown("**Membership**")
            st.dataframe(m, hide_index=True)
        h = query_df(
            """SELECT appointment_id AS Appt, appointment_date AS Date, start_time AS Time,
                      service_name AS Service, staff_name AS Staff, price_charged AS `Price ₹`,
                      from_package AS Package, status AS Status
                 FROM v_appointment_details WHERE customer_id = %s
                ORDER BY appointment_date DESC, start_time""", (cid,))
        st.markdown(f"**Visits** · {h['Appt'].nunique() if not h.empty else 0} appointments")
        st.dataframe(h, hide_index=True, width="stretch")
