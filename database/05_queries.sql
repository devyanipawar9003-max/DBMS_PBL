-- =====================================================================
--  Salon & Spa Appointment Management System
--  File 05 : Retrieval queries and reports
--  Demonstrates: joins, aggregate functions + GROUP BY/HAVING, nested
--  (scalar, IN, correlated, EXISTS) subqueries, derived tables, views.
-- =====================================================================
USE salon_spa_db;

-- ---------------------------------------------------------------
-- A. APPOINTMENTS
-- ---------------------------------------------------------------
-- Q1 (JOIN, 5 tables) Day sheet: everything booked for a given date
SELECT s.start_time, s.end_time, CONCAT(c.first_name,' ',c.last_name) AS customer,
       sv.service_name, st.full_name AS staff, a.status
FROM appointment a
JOIN customer c            ON c.customer_id = a.customer_id
JOIN appointment_service s ON s.appointment_id = a.appointment_id
JOIN service sv            ON sv.service_id = s.service_id
JOIN staff st              ON st.staff_id = s.staff_id
WHERE a.appointment_date = '2026-10-10'
ORDER BY s.start_time, st.full_name;

-- Q2 (VIEW) Upcoming appointments of one customer (searched by phone)
SELECT appointment_date, start_time, service_name, staff_name, status
FROM v_appointment_details
WHERE customer_phone = (SELECT phone FROM customer WHERE customer_id = 8)
  AND appointment_date >= CURDATE()
ORDER BY appointment_date, start_time;

-- Q3 (AGGREGATE) Appointment count by status for the current month
SELECT status, COUNT(*) AS appointments
FROM appointment
WHERE DATE_FORMAT(appointment_date,'%Y-%m') = '2026-09'
GROUP BY status;

-- Q4 (LEFT JOIN + IS NULL) Registered customers who have never booked
SELECT c.customer_id, c.first_name, c.last_name, c.phone
FROM customer c
LEFT JOIN appointment a ON a.customer_id = c.customer_id
WHERE a.appointment_id IS NULL;

-- Q5 (CORRELATED SUBQUERY) Each customer's most recent completed visit
SELECT c.customer_id, CONCAT(c.first_name,' ',c.last_name) AS customer,
       (SELECT MAX(a.appointment_date) FROM appointment a
         WHERE a.customer_id = c.customer_id AND a.status = 'COMPLETED') AS last_visit
FROM customer c
ORDER BY last_visit DESC;

-- ---------------------------------------------------------------
-- B. STAFF UTILISATION
-- ---------------------------------------------------------------
-- Q6 (VIEW) Utilisation of every staff member
SELECT full_name, designation, services_done, minutes_worked,
       revenue_generated, utilization_pct
FROM v_staff_utilization
ORDER BY utilization_pct DESC;

-- Q7 (JOIN + GROUP BY + HAVING) Staff who handled more than 50 completed services
SELECT st.full_name, COUNT(*) AS services
FROM staff st
JOIN appointment_service s ON s.staff_id = st.staff_id
JOIN appointment a         ON a.appointment_id = s.appointment_id
WHERE a.status = 'COMPLETED'
GROUP BY st.staff_id, st.full_name
HAVING COUNT(*) > 50
ORDER BY services DESC;

-- Q8 (EXISTS) Staff qualified to do a 'Gold Facial' who are free on
--     2026-10-10 between 15:00 and 16:15
SELECT st.staff_id, st.full_name
FROM staff st
WHERE st.status = 'ACTIVE'
  AND EXISTS (SELECT 1 FROM staff_skill ss
                JOIN service sv ON sv.required_skill_id = ss.skill_id
               WHERE ss.staff_id = st.staff_id AND sv.service_name = 'Gold Facial')
  AND EXISTS (SELECT 1 FROM staff_schedule sc
               WHERE sc.staff_id = st.staff_id
                 AND sc.day_of_week = DAYOFWEEK('2026-10-10')
                 AND sc.shift_start <= '15:00:00' AND sc.shift_end >= '16:15:00')
  AND NOT EXISTS (SELECT 1 FROM appointment_service s
                    JOIN appointment a ON a.appointment_id = s.appointment_id
                   WHERE s.staff_id = st.staff_id
                     AND a.appointment_date = '2026-10-10'
                     AND a.status NOT IN ('CANCELLED','NO_SHOW')
                     AND s.start_time < '16:15:00' AND '15:00:00' < s.end_time);

-- ---------------------------------------------------------------
-- C. SERVICE POPULARITY
-- ---------------------------------------------------------------
-- Q9 (VIEW) Top 10 services by bookings
SELECT service_name, category_name, times_booked, via_package, revenue
FROM v_service_popularity
ORDER BY times_booked DESC
LIMIT 10;

-- Q10 (AGGREGATE by category) Revenue share of each category
SELECT sc.category_name, COUNT(*) AS services_done, SUM(s.price_charged) AS revenue,
       ROUND(100 * SUM(s.price_charged) /
             (SELECT SUM(s2.price_charged) FROM appointment_service s2
                JOIN appointment a2 ON a2.appointment_id = s2.appointment_id
               WHERE a2.status = 'COMPLETED'), 1) AS revenue_pct
FROM appointment_service s
JOIN appointment a      ON a.appointment_id = s.appointment_id
JOIN service sv         ON sv.service_id = s.service_id
JOIN service_category sc ON sc.category_id = sv.category_id
WHERE a.status = 'COMPLETED'
GROUP BY sc.category_name
ORDER BY revenue DESC;

-- Q11 (NOT IN subquery) Services never booked
SELECT service_name, price FROM service
WHERE service_id NOT IN (SELECT DISTINCT service_id FROM appointment_service);

-- ---------------------------------------------------------------
-- D. PACKAGE BALANCES
-- ---------------------------------------------------------------
-- Q12 (VIEW + derived column) Remaining sessions of active packages
SELECT customer_name, package_name, service_name, sessions_included,
       sessions_used, sessions_included - sessions_used AS sessions_left, expiry_date
FROM v_package_balance
WHERE status = 'ACTIVE'
ORDER BY expiry_date;

-- Q13 Active packages expiring in the next 30 days with sessions still unused
SELECT DISTINCT customer_name, package_name, expiry_date
FROM v_package_balance
WHERE status = 'ACTIVE'
  AND expiry_date BETWEEN CURDATE() AND CURDATE() + INTERVAL 30 DAY
  AND sessions_used < sessions_included;

-- ---------------------------------------------------------------
-- E. PRODUCT USE
-- ---------------------------------------------------------------
-- Q14 (VIEW) Product consumption and re-order alert
SELECT product_name, brand, total_used, unit, consumption_cost, stock_qty, stock_status
FROM v_product_usage
ORDER BY consumption_cost DESC;

-- Q15 (JOIN + AGGREGATE) Product cost per service (material cost of a service)
SELECT sv.service_name, COUNT(DISTINCT u.appt_service_id) AS times_performed,
       ROUND(SUM(u.quantity_used * pr.unit_cost) / COUNT(DISTINCT u.appt_service_id), 2)
           AS avg_material_cost
FROM product_usage u
JOIN product pr             ON pr.product_id = u.product_id
JOIN appointment_service s  ON s.appt_service_id = u.appt_service_id
JOIN service sv             ON sv.service_id = s.service_id
GROUP BY sv.service_name
ORDER BY avg_material_cost DESC;

-- ---------------------------------------------------------------
-- F. REVENUE & BILLING
-- ---------------------------------------------------------------
-- Q16 (VIEW) Month-wise revenue: billed vs collected
SELECT * FROM v_monthly_revenue ORDER BY month;

-- Q17 (AGGREGATE) Collections by payment method
SELECT method, COUNT(*) AS payments, SUM(amount) AS amount
FROM payment GROUP BY method ORDER BY amount DESC;

-- Q18 (VIEW + filter) Outstanding bills
SELECT bill_id, customer_name, bill_date, total_amount, amount_paid, balance_due
FROM v_bill_summary
WHERE payment_status <> 'PAID'
ORDER BY balance_due DESC;

-- Q19 (SCALAR SUBQUERY) Customers whose total spend is above the average
SELECT customer_name, SUM(total_amount) AS lifetime_spend
FROM v_bill_summary
GROUP BY customer_id, customer_name
HAVING SUM(total_amount) > (SELECT AVG(t.spend) FROM
                              (SELECT SUM(total_amount) AS spend
                                 FROM bill b JOIN appointment a ON a.appointment_id = b.appointment_id
                                GROUP BY a.customer_id) t)
ORDER BY lifetime_spend DESC;

-- Q20 Membership benefit: discount given to each plan's members
SELECT mp.plan_name, COUNT(DISTINCT cm.customer_id) AS members,
       COALESCE(SUM(b.discount_amount),0) AS total_discount
FROM membership_plan mp
LEFT JOIN customer_membership cm ON cm.plan_id = mp.plan_id
LEFT JOIN appointment a ON a.customer_id = cm.customer_id
LEFT JOIN bill b ON b.appointment_id = a.appointment_id
GROUP BY mp.plan_id, mp.plan_name;
