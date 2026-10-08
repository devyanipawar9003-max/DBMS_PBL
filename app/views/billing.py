from datetime import date

import streamlit as st

from db import execute, query_df, query_one, transaction, DBError
from ui import GST_RATE, page_header, rupees, run_safely

page_header("Billing & Payments", "Raise bills for completed appointments and record payments.")

tab_bill, tab_pay, tab_view = st.tabs(["🧾 Generate bill", "💳 Record payment", "📄 View bill"])

# ------------------------------------------------------------------ BILL
with tab_bill:
    pending = query_df(
        """SELECT a.appointment_id, a.appointment_date, CONCAT(c.first_name,' ',c.last_name) AS customer,
                  a.customer_id
             FROM appointment a JOIN customer c ON c.customer_id = a.customer_id
            WHERE a.status = 'COMPLETED'
              AND NOT EXISTS (SELECT 1 FROM bill b WHERE b.appointment_id = a.appointment_id)
            ORDER BY a.appointment_date DESC""")
    if pending.empty:
        st.success("All completed appointments are billed. Mark an appointment completed to bill it.")
    else:
        aid = st.selectbox("Completed appointment without a bill", pending.appointment_id.tolist(),
                           format_func=lambda i: (lambda r: f"#{i} – {r.customer} – {r.appointment_date}")(
                               pending[pending.appointment_id == i].iloc[0]))
        r = pending[pending.appointment_id == aid].iloc[0]
        lines = query_df("""SELECT service_name AS Service, staff_name AS Staff,
                                   from_package AS `Package`, price_charged AS `Amount ₹`
                              FROM v_appointment_details WHERE appointment_id = %s""", (int(aid),))
        st.dataframe(lines, hide_index=True)
        mem = query_one(
            """SELECT mp.plan_name, mp.discount_pct FROM customer_membership cm
                 JOIN membership_plan mp ON mp.plan_id = cm.plan_id
                WHERE cm.customer_id = %s AND %s BETWEEN cm.start_date AND cm.end_date
                ORDER BY mp.discount_pct DESC LIMIT 1""", (int(r.customer_id), r.appointment_date))
        subtotal = float(lines["Amount ₹"].sum())
        pct = float(mem.discount_pct) if mem is not None else 0.0
        discount = round(subtotal * pct / 100, 2)
        tax = round((subtotal - discount) * GST_RATE, 2)
        total = round(subtotal - discount + tax, 2)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Subtotal", rupees(subtotal))
        c2.metric(f"Discount ({mem.plan_name} {pct:g}%)" if mem is not None else "Discount", rupees(discount))
        c3.metric("GST 18%", rupees(tax))
        c4.metric("Total", rupees(total))
        if st.button("Generate bill", type="primary"):
            run_safely(lambda: execute(
                """INSERT INTO bill (appointment_id, bill_date, subtotal, discount_amount, tax_amount)
                   VALUES (%s,%s,%s,%s,%s)""", (int(aid), date.today(), subtotal, discount, tax)),
                "Bill #{result} generated.", rerun=True)

# ------------------------------------------------------------------ PAYMENT
with tab_pay:
    due = query_df("""SELECT bill_id, customer_name, bill_date, total_amount, amount_paid, balance_due
                        FROM v_bill_summary WHERE balance_due > 0 ORDER BY bill_date DESC""")
    if due.empty:
        st.success("No outstanding bills.")
    else:
        bid = st.selectbox("Bill with balance due", due.bill_id.tolist(),
                           format_func=lambda i: (lambda r: f"Bill #{i} – {r.customer_name} – balance {rupees(r.balance_due)}")(
                               due[due.bill_id == i].iloc[0]))
        b = due[due.bill_id == bid].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Bill total", rupees(b.total_amount))
        c2.metric("Paid so far", rupees(b.amount_paid))
        c3.metric("Balance due", rupees(b.balance_due))
        with st.form("pay"):
            amt = st.number_input("Amount ₹", min_value=0.0, value=float(b.balance_due), step=50.0)
            method = st.radio("Method", ["UPI", "CARD", "CASH", "WALLET"], horizontal=True)
            ref = st.text_input("Transaction reference (UPI/card)")
            go = st.form_submit_button("Record payment", type="primary")
        if go:
            if amt <= 0:
                st.error("Amount must be greater than zero.")
            elif method in ("UPI", "CARD") and not ref.strip():
                st.error("A transaction reference is required for UPI / card payments.")
            else:
                # the trigger trg_payment_bi blocks any amount above the balance
                run_safely(lambda: execute(
                    "INSERT INTO payment (bill_id, amount, method, reference_no) VALUES (%s,%s,%s,%s)",
                    (int(bid), amt, method, ref.strip() or None)), "Payment recorded.", rerun=True)

# ------------------------------------------------------------------ VIEW
with tab_view:
    bills = query_df("""SELECT bill_id, customer_name, bill_date, payment_status FROM v_bill_summary
                         ORDER BY bill_id DESC LIMIT 500""")
    bid = st.selectbox("Bill", bills.bill_id.tolist(),
                       format_func=lambda i: (lambda r: f"#{i} – {r.customer_name} – {r.bill_date} – {r.payment_status}")(
                           bills[bills.bill_id == i].iloc[0]))
    s = query_one("SELECT * FROM v_bill_summary WHERE bill_id=%s", (int(bid),))
    st.markdown(f"### Glow & Grace Salon and Spa\n**Bill #{s.bill_id}** · {s.bill_date} · "
                f"Customer: **{s.customer_name}** · Appointment #{s.appointment_id}")
    st.dataframe(query_df("""SELECT service_name AS Service, staff_name AS Staff, price_charged AS `Amount ₹`
                               FROM v_appointment_details WHERE appointment_id=%s""", (int(s.appointment_id),)),
                 hide_index=True)
    st.markdown(f"Subtotal {rupees(s.subtotal)} · Discount −{rupees(s.discount_amount)} · "
                f"GST +{rupees(s.tax_amount)}  \n**Total {rupees(s.total_amount)}** · Paid {rupees(s.amount_paid)} · "
                f"**Balance {rupees(s.balance_due)}** · `{s.payment_status}`")
    pays = query_df("""SELECT payment_id AS `#`, paid_at AS `Paid at`, method AS Method, amount AS `Amount ₹`,
                              reference_no AS Reference FROM payment WHERE bill_id=%s""", (int(bid),))
    if not pays.empty:
        st.dataframe(pays, hide_index=True)
