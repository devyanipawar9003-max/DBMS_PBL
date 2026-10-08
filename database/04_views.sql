-- =====================================================================
--  Salon & Spa Appointment Management System
--  File 04 : Views used by the reports and the application
-- =====================================================================
USE salon_spa_db;

-- ---------------------------------------------------------------------
-- V1. Appointment details - one row per booked service (multi-table join)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_appointment_details AS
SELECT  a.appointment_id,
        a.appointment_date,
        s.start_time,
        s.end_time,
        a.status,
        c.customer_id,
        CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
        c.phone                                 AS customer_phone,
        sv.service_name,
        sc.category_name,
        st.staff_id,
        st.full_name                            AS staff_name,
        s.price_charged,
        CASE WHEN s.customer_package_id IS NULL THEN 'No' ELSE 'Yes' END AS from_package,
        s.appt_service_id
FROM appointment a
JOIN customer             c  ON c.customer_id  = a.customer_id
JOIN appointment_service  s  ON s.appointment_id = a.appointment_id
JOIN service              sv ON sv.service_id  = s.service_id
JOIN service_category     sc ON sc.category_id = sv.category_id
JOIN staff                st ON st.staff_id    = s.staff_id;

-- ---------------------------------------------------------------------
-- V2. Staff utilisation - booked minutes vs available shift minutes for
--     the completed / booked work of each staff member (aggregation +
--     derived table)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_staff_utilization AS
SELECT  st.staff_id,
        st.full_name,
        st.designation,
        st.status,
        COUNT(x.appt_service_id)                       AS services_done,
        COALESCE(SUM(x.minutes), 0)                    AS minutes_worked,
        COALESCE(SUM(x.price_charged), 0)              AS revenue_generated,
        w.weekly_shift_minutes,
        ROUND(100 * COALESCE(SUM(x.minutes), 0)
              / (w.weekly_shift_minutes * per.weeks), 1) AS utilization_pct
FROM staff st
JOIN (SELECT staff_id,
             SUM(TIME_TO_SEC(TIMEDIFF(shift_end, shift_start)) / 60) AS weekly_shift_minutes
        FROM staff_schedule GROUP BY staff_id) w ON w.staff_id = st.staff_id
CROSS JOIN (SELECT GREATEST(1, (DATEDIFF(MAX(appointment_date), MIN(appointment_date)) + 1) / 7) AS weeks
              FROM appointment WHERE status = 'COMPLETED') per
LEFT JOIN (SELECT s.appt_service_id, s.staff_id, s.price_charged,
                  TIME_TO_SEC(TIMEDIFF(s.end_time, s.start_time)) / 60 AS minutes
             FROM appointment_service s
             JOIN appointment a ON a.appointment_id = s.appointment_id
            WHERE a.status = 'COMPLETED') x ON x.staff_id = st.staff_id
GROUP BY st.staff_id, st.full_name, st.designation, st.status,
         w.weekly_shift_minutes, per.weeks;

-- ---------------------------------------------------------------------
-- V3. Service popularity - how often each service is booked and its revenue
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_service_popularity AS
SELECT  sv.service_id,
        sv.service_name,
        sc.category_name,
        COUNT(s.appt_service_id)                               AS times_booked,
        SUM(CASE WHEN s.customer_package_id IS NOT NULL THEN 1 ELSE 0 END) AS via_package,
        COALESCE(SUM(s.price_charged), 0)                      AS revenue
FROM service sv
JOIN service_category sc ON sc.category_id = sv.category_id
LEFT JOIN appointment_service s ON s.service_id = sv.service_id
     AND s.appointment_id IN (SELECT appointment_id FROM appointment
                               WHERE status IN ('COMPLETED','BOOKED'))
GROUP BY sv.service_id, sv.service_name, sc.category_name;

-- ---------------------------------------------------------------------
-- V4. Package balance - sessions included / used / remaining per customer
--     package and service (correlated subquery)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_package_balance AS
SELECT  cp.customer_package_id,
        cp.customer_id,
        CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
        p.package_name,
        sv.service_id,
        sv.service_name,
        pi.sessions_included,
        (SELECT COUNT(*)
           FROM appointment_service s
           JOIN appointment a ON a.appointment_id = s.appointment_id
          WHERE s.customer_package_id = cp.customer_package_id
            AND s.service_id = pi.service_id
            AND a.status NOT IN ('CANCELLED','NO_SHOW'))          AS sessions_used,
        cp.purchase_date,
        cp.expiry_date,
        cp.status
FROM customer_package cp
JOIN customer     c  ON c.customer_id = cp.customer_id
JOIN package      p  ON p.package_id  = cp.package_id
JOIN package_item pi ON pi.package_id = cp.package_id
JOIN service      sv ON sv.service_id = pi.service_id;

-- ---------------------------------------------------------------------
-- V5. Product usage - consumption and cost per product, with stock alert
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_product_usage AS
SELECT  pr.product_id,
        pr.product_name,
        pr.brand,
        pr.unit,
        COALESCE(SUM(u.quantity_used), 0)                     AS total_used,
        COALESCE(SUM(u.quantity_used), 0) * pr.unit_cost      AS consumption_cost,
        pr.stock_qty,
        pr.reorder_level,
        CASE WHEN pr.stock_qty <= pr.reorder_level THEN 'REORDER' ELSE 'OK' END AS stock_status
FROM product pr
LEFT JOIN product_usage u ON u.product_id = pr.product_id
GROUP BY pr.product_id, pr.product_name, pr.brand, pr.unit, pr.unit_cost,
         pr.stock_qty, pr.reorder_level;

-- ---------------------------------------------------------------------
-- V6. Bill summary - amount paid, balance and payment status per bill
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_bill_summary AS
SELECT  b.bill_id,
        b.appointment_id,
        a.customer_id,
        CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
        b.bill_date,
        b.subtotal,
        b.discount_amount,
        b.tax_amount,
        b.total_amount,
        COALESCE(p.paid, 0)                          AS amount_paid,
        b.total_amount - COALESCE(p.paid, 0)         AS balance_due,
        CASE WHEN COALESCE(p.paid, 0) = 0 AND b.total_amount > 0 THEN 'UNPAID'
             WHEN COALESCE(p.paid, 0) < b.total_amount           THEN 'PARTIAL'
             ELSE 'PAID' END                         AS payment_status
FROM bill b
JOIN appointment a ON a.appointment_id = b.appointment_id
JOIN customer    c ON c.customer_id    = a.customer_id
LEFT JOIN (SELECT bill_id, SUM(amount) AS paid FROM payment GROUP BY bill_id) p
       ON p.bill_id = b.bill_id;

-- ---------------------------------------------------------------------
-- V7. Monthly revenue - billed vs collected per month
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_monthly_revenue AS
SELECT  DATE_FORMAT(b.bill_date, '%Y-%m')  AS month,
        COUNT(*)                            AS bills,
        SUM(b.subtotal)                     AS gross_sales,
        SUM(b.discount_amount)              AS discounts,
        SUM(b.tax_amount)                   AS gst,
        SUM(b.total_amount)                 AS billed,
        SUM(COALESCE(p.paid, 0))            AS collected
FROM bill b
LEFT JOIN (SELECT bill_id, SUM(amount) AS paid FROM payment GROUP BY bill_id) p
       ON p.bill_id = b.bill_id
GROUP BY DATE_FORMAT(b.bill_date, '%Y-%m');
