-- =====================================================================
--  Salon & Spa Appointment Management System
--  File 02 : Business-rule triggers
--  Rules that a CHECK constraint cannot express (they need other rows
--  or other tables) are enforced here, inside the database, so that no
--  client - the Python app, MySQL Workbench or a script - can bypass them.
--  All violations raise SQLSTATE '45000' with a readable message.
-- =====================================================================
USE salon_spa_db;

DROP TRIGGER IF EXISTS trg_appt_service_bi;
DROP TRIGGER IF EXISTS trg_appt_service_bu;
DROP TRIGGER IF EXISTS trg_product_usage_bi;
DROP TRIGGER IF EXISTS trg_bill_bi;
DROP TRIGGER IF EXISTS trg_payment_bi;
DROP PROCEDURE IF EXISTS sp_validate_appt_service;

DELIMITER $$

-- ---------------------------------------------------------------------
-- One procedure holds every rule for a booked service line, so that the
-- INSERT and UPDATE triggers apply exactly the same checks.
--   R1  valid appointment time  (end = start + service duration, inside the
--       staff member's shift for that weekday)
--   R2  skill match             (staff holds the skill the service needs)
--   R3  no overlapping staff appointments
--   R4  package-session limit   (package valid, belongs to customer, covers
--       the service, sessions remaining)
-- p_self_id = the row being updated (0 on insert) so it is not compared
-- with itself in the overlap / session counts.
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_validate_appt_service(
    IN p_self_id      INT,
    IN p_appt_id      INT,
    IN p_service_id   INT,
    IN p_staff_id     INT,
    IN p_start        TIME,
    IN p_end          TIME,
    IN p_cpkg_id      INT)
BEGIN
    DECLARE v_date        DATE;
    DECLARE v_customer    INT;
    DECLARE v_appt_status VARCHAR(10);
    DECLARE v_duration    INT;
    DECLARE v_skill       INT;
    DECLARE v_svc_active  INT;
    DECLARE v_staff_stat  VARCHAR(10);
    DECLARE v_cnt         INT;
    DECLARE v_pkg_cust    INT;
    DECLARE v_pkg_status  VARCHAR(10);
    DECLARE v_pkg_expiry  DATE;
    DECLARE v_pkg_id      INT;
    DECLARE v_sessions    INT;
    DECLARE v_msg         VARCHAR(255);

    SELECT appointment_date, customer_id, status
      INTO v_date, v_customer, v_appt_status
      FROM appointment WHERE appointment_id = p_appt_id;

    IF v_appt_status IN ('CANCELLED','NO_SHOW') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot add services to a cancelled / no-show appointment';
    END IF;

    SELECT duration_min, required_skill_id, is_active
      INTO v_duration, v_skill, v_svc_active
      FROM service WHERE service_id = p_service_id;

    IF v_svc_active = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Service is inactive and cannot be booked';
    END IF;

    -- R1a : slot length must equal the service duration
    IF TIME_TO_SEC(TIMEDIFF(p_end, p_start)) <> v_duration * 60 THEN
        SET v_msg = CONCAT('Invalid time slot: this service takes ', v_duration, ' minutes');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
    END IF;

    -- staff must be active
    SELECT status INTO v_staff_stat FROM staff WHERE staff_id = p_staff_id;
    IF v_staff_stat <> 'ACTIVE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Selected staff member is not active';
    END IF;

    -- R2 : skill match
    SELECT COUNT(*) INTO v_cnt FROM staff_skill
     WHERE staff_id = p_staff_id AND skill_id = v_skill;
    IF v_cnt = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Skill mismatch: staff member does not have the skill required for this service';
    END IF;

    -- R1b : inside the staff member's shift for that weekday
    SELECT COUNT(*) INTO v_cnt FROM staff_schedule
     WHERE staff_id = p_staff_id
       AND day_of_week = DAYOFWEEK(v_date)
       AND p_start >= shift_start AND p_end <= shift_end;
    IF v_cnt = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid time: staff member is not on shift for this slot';
    END IF;

    -- R3 : no overlapping appointments for the same staff member
    --      two intervals overlap when  startA < endB  AND  startB < endA
    SELECT COUNT(*) INTO v_cnt
      FROM appointment_service s
      JOIN appointment a ON a.appointment_id = s.appointment_id
     WHERE s.staff_id = p_staff_id
       AND a.appointment_date = v_date
       AND a.status NOT IN ('CANCELLED','NO_SHOW')
       AND s.appt_service_id <> p_self_id
       AND s.start_time < p_end
       AND p_start < s.end_time;
    IF v_cnt > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Staff conflict: staff member already has an overlapping appointment';
    END IF;

    -- R4 : package-session limit
    IF p_cpkg_id IS NOT NULL THEN
        SELECT customer_id, status, expiry_date, package_id
          INTO v_pkg_cust, v_pkg_status, v_pkg_expiry, v_pkg_id
          FROM customer_package WHERE customer_package_id = p_cpkg_id;

        IF v_pkg_cust <> v_customer THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Package does not belong to this customer';
        END IF;
        IF v_pkg_status <> 'ACTIVE' OR v_date > v_pkg_expiry THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Package is not active or has expired';
        END IF;

        SET v_sessions = NULL;
        SELECT sessions_included INTO v_sessions FROM package_item
         WHERE package_id = v_pkg_id AND service_id = p_service_id;
        IF v_sessions IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This service is not included in the customer''s package';
        END IF;

        SELECT COUNT(*) INTO v_cnt
          FROM appointment_service s
          JOIN appointment a ON a.appointment_id = s.appointment_id
         WHERE s.customer_package_id = p_cpkg_id
           AND s.service_id = p_service_id
           AND a.status NOT IN ('CANCELLED','NO_SHOW')
           AND s.appt_service_id <> p_self_id;
        IF v_cnt >= v_sessions THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Package session limit reached for this service';
        END IF;
    END IF;
END$$

CREATE TRIGGER trg_appt_service_bi
BEFORE INSERT ON appointment_service
FOR EACH ROW
BEGIN
    CALL sp_validate_appt_service(0, NEW.appointment_id, NEW.service_id, NEW.staff_id,
                                  NEW.start_time, NEW.end_time, NEW.customer_package_id);
    -- a service redeemed from a package is not charged again
    IF NEW.customer_package_id IS NOT NULL THEN
        SET NEW.price_charged = 0;
    END IF;
END$$

CREATE TRIGGER trg_appt_service_bu
BEFORE UPDATE ON appointment_service
FOR EACH ROW
BEGIN
    CALL sp_validate_appt_service(OLD.appt_service_id, NEW.appointment_id, NEW.service_id,
                                  NEW.staff_id, NEW.start_time, NEW.end_time,
                                  NEW.customer_package_id);
    IF NEW.customer_package_id IS NOT NULL THEN
        SET NEW.price_charged = 0;
    END IF;
END$$

-- ---------------------------------------------------------------------
-- R5 : product issue - enough stock must exist; stock is reduced in the
--      same statement, so usage and stock can never disagree.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_product_usage_bi
BEFORE INSERT ON product_usage
FOR EACH ROW
BEGIN
    DECLARE v_stock DECIMAL(10,2);
    DECLARE v_msg   VARCHAR(255);
    SELECT stock_qty INTO v_stock FROM product WHERE product_id = NEW.product_id FOR UPDATE;
    IF v_stock < NEW.quantity_used THEN
        SET v_msg = CONCAT('Insufficient stock: only ', v_stock, ' available');
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
    END IF;
    UPDATE product SET stock_qty = stock_qty - NEW.quantity_used
     WHERE product_id = NEW.product_id;
END$$

-- ---------------------------------------------------------------------
-- R6 : a bill can only be raised for a COMPLETED appointment
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_bill_bi
BEFORE INSERT ON bill
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(10);
    SELECT status INTO v_status FROM appointment WHERE appointment_id = NEW.appointment_id;
    IF v_status <> 'COMPLETED' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bill can be generated only for a completed appointment';
    END IF;
END$$

-- ---------------------------------------------------------------------
-- R7 : payment limit - total paid can never exceed the bill total
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_payment_bi
BEFORE INSERT ON payment
FOR EACH ROW
BEGIN
    DECLARE v_total DECIMAL(10,2);
    DECLARE v_paid  DECIMAL(10,2);
    DECLARE v_msg   VARCHAR(255);
    SELECT total_amount INTO v_total FROM bill WHERE bill_id = NEW.bill_id FOR UPDATE;
    SELECT COALESCE(SUM(amount),0) INTO v_paid FROM payment WHERE bill_id = NEW.bill_id;
    IF v_paid + NEW.amount > v_total THEN
        SET v_msg = CONCAT('Payment exceeds balance: outstanding amount is Rs. ', v_total - v_paid);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
    END IF;
END$$

DELIMITER ;
