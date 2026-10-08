-- =====================================================================
--  Salon & Spa Appointment Management System
--  File 06 : Business-rule test script (positive + negative cases)
--  Run with:  mysql -u root -p --force salon_spa_db < 06_test_business_rules.sql
--  (--force keeps going after the expected errors).  Everything runs in
--  one transaction that is ROLLED BACK at the end, so data is unchanged.
-- =====================================================================
USE salon_spa_db;
START TRANSACTION;

-- Test fixtures: 30-Oct-2026 is a Friday (DAYOFWEEK = 6)
INSERT INTO appointment (customer_id, appointment_date) VALUES (1, '2026-10-30');
SET @a1 = LAST_INSERT_ID();
INSERT INTO appointment (customer_id, appointment_date) VALUES (8, '2026-10-30');
SET @a8 = LAST_INSERT_ID();

-- TC-01 POSITIVE: valid booking - Swedish massage (60 min) with Rohan (staff 6,
--        massage skill, shift 12:00-21:00)            => 1 row inserted
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged)
VALUES (@a1, 14, 6, '13:00:00', '14:00:00', 2200);
SELECT 'TC-01 valid booking' AS test, COUNT(*) AS rows_ok FROM appointment_service WHERE appointment_id = @a1;

-- TC-02 NEGATIVE: overlapping appointment for the same staff (13:30-14:30)
--        => ERROR 1644: Staff conflict: staff member already has an overlapping appointment
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged)
VALUES (@a8, 14, 6, '13:30:00', '14:30:00', 2200);

-- TC-03 POSITIVE: back-to-back slot (14:00-15:00) is NOT an overlap => inserted
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged)
VALUES (@a8, 14, 6, '14:00:00', '15:00:00', 2200);

-- TC-04 NEGATIVE: skill mismatch - Bridal Makeup (18) given to Barber Arjun (8)
--        => ERROR 1644: Skill mismatch ...
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged)
VALUES (@a1, 18, 8, '15:00:00', '18:00:00', 15000);

-- TC-05 NEGATIVE: slot length does not match service duration (30-min haircut booked for 45 min)
--        => ERROR 1644: Invalid time slot: this service takes 30 minutes
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged)
VALUES (@a1, 2, 8, '15:00:00', '15:45:00', 350);

-- TC-06 NEGATIVE: outside staff shift (Rohan starts at 12:00)
--        => ERROR 1644: Invalid time: staff member is not on shift for this slot
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged)
VALUES (@a1, 16, 6, '10:00:00', '10:30:00', 700);

-- TC-07 NEGATIVE: outside salon hours (08:00). Rejected by the trigger (no shift
--        covers 08:00); CHECK chk_as_hours (09:00-21:00) is a second line of defence.
--        => ERROR 1644: Invalid time: staff member is not on shift for this slot
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged)
VALUES (@a1, 20, 4, '08:00:00', '08:15:00', 80);

-- TC-08 NEGATIVE: package belongs to another customer (package 3 is customer 8's)
--        => ERROR 1644: Package does not belong to this customer
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged, customer_package_id)
VALUES (@a1, 11, 7, '11:00:00', '11:45:00', 700, 3);

-- TC-09 POSITIVE: package redemption - customer 8 has used 3 of 4 manicures
--        => inserted, price_charged forced to 0 by the trigger
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged, customer_package_id)
VALUES (@a8, 11, 7, '11:00:00', '11:45:00', 700, 3);
SELECT 'TC-09 package redemption' AS test, price_charged FROM appointment_service
 WHERE appointment_id = @a8 AND service_id = 11;

-- TC-10 NEGATIVE: package-session limit - all 4 manicures are now used
--        => ERROR 1644: Package session limit reached for this service
INSERT INTO appointment_service (appointment_id, service_id, staff_id, start_time, end_time, price_charged, customer_package_id)
VALUES (@a8, 11, 7, '16:00:00', '16:45:00', 700, 3);

-- TC-11 NEGATIVE: bill for an appointment that is not completed
--        => ERROR 1644: Bill can be generated only for a completed appointment
INSERT INTO bill (appointment_id, bill_date, subtotal, tax_amount) VALUES (@a1, '2026-10-30', 2200, 396);

-- pick a partly paid bill and remember its balance
SELECT bill_id, balance_due INTO @pb, @bal FROM v_bill_summary
 WHERE payment_status = 'PARTIAL' ORDER BY bill_id LIMIT 1;

-- TC-12 NEGATIVE: payment larger than the outstanding balance
--        => ERROR 1644: Payment exceeds balance: outstanding amount is Rs. <balance>
INSERT INTO payment (bill_id, amount, method) VALUES (@pb, @bal + 100, 'UPI');

-- TC-13 POSITIVE: exact balance payment => inserted, bill becomes PAID
INSERT INTO payment (bill_id, amount, method) VALUES (@pb, @bal, 'UPI');
SELECT 'TC-13 settle bill' AS test, bill_id, payment_status, balance_due FROM v_bill_summary WHERE bill_id = @pb;

-- TC-14 NEGATIVE: product issue larger than stock => ERROR 1644: Insufficient stock ...
INSERT INTO product_usage (appt_service_id, product_id, quantity_used) VALUES (1, 7, 500);

-- TC-15 NEGATIVE: invalid phone number - CHECK chk_customer_phone
INSERT INTO customer (first_name, last_name, phone) VALUES ('Test', 'User', '12345');

-- TC-16 NEGATIVE: duplicate phone number - UNIQUE  => ERROR 1062 Duplicate entry
INSERT INTO customer (first_name, last_name, phone)
SELECT 'Dup', 'User', phone FROM customer WHERE customer_id = 1;

-- TC-17 NEGATIVE: delete a customer that has appointments - FK RESTRICT => ERROR 1451
DELETE FROM customer WHERE customer_id = 1;

-- TC-18 NEGATIVE: discount larger than subtotal - CHECK chk_bill_discount
UPDATE bill SET discount_amount = subtotal + 1 WHERE bill_id = 1;

ROLLBACK;
SELECT 'All tests finished - transaction rolled back' AS result;
