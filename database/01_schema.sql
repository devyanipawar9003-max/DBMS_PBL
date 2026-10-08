-- =====================================================================
--  Salon & Spa Appointment Management System
--  File 01 : Schema (DDL) - tables, keys, constraints, indexes
--  DBMS    : MySQL 8.0.16+  (CHECK constraints are enforced from 8.0.16)
--  Author  : Devyani Pawar (25WU0102069) - DBMS PBL, Project 66
-- =====================================================================

DROP DATABASE IF EXISTS salon_spa_db;
CREATE DATABASE salon_spa_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE salon_spa_db;

-- ---------------------------------------------------------------------
-- 1. SERVICE_CATEGORY : groups of services (Hair, Skin, Spa ...)
-- ---------------------------------------------------------------------
CREATE TABLE service_category (
    category_id     INT AUTO_INCREMENT PRIMARY KEY,
    category_name   VARCHAR(50)  NOT NULL UNIQUE,
    description     VARCHAR(200)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. SKILL : a competency a staff member can hold (Hair Cutting ...)
-- ---------------------------------------------------------------------
CREATE TABLE skill (
    skill_id        INT AUTO_INCREMENT PRIMARY KEY,
    skill_name      VARCHAR(60)  NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. SERVICE : a sellable service; needs exactly one skill
-- ---------------------------------------------------------------------
CREATE TABLE service (
    service_id        INT AUTO_INCREMENT PRIMARY KEY,
    category_id       INT          NOT NULL,
    required_skill_id INT          NOT NULL,
    service_name      VARCHAR(80)  NOT NULL UNIQUE,
    duration_min      SMALLINT     NOT NULL,
    price             DECIMAL(8,2) NOT NULL,
    is_active         TINYINT(1)   NOT NULL DEFAULT 1,
    CONSTRAINT fk_service_category FOREIGN KEY (category_id)
        REFERENCES service_category(category_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_service_skill FOREIGN KEY (required_skill_id)
        REFERENCES skill(skill_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_service_duration CHECK (duration_min BETWEEN 10 AND 300),
    CONSTRAINT chk_service_price    CHECK (price > 0),
    CONSTRAINT chk_service_active   CHECK (is_active IN (0,1))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. CUSTOMER
-- ---------------------------------------------------------------------
CREATE TABLE customer (
    customer_id     INT AUTO_INCREMENT PRIMARY KEY,
    first_name      VARCHAR(40)  NOT NULL,
    last_name       VARCHAR(40)  NOT NULL,
    phone           CHAR(10)     NOT NULL UNIQUE,
    email           VARCHAR(100) UNIQUE,
    gender          CHAR(1),
    date_of_birth   DATE,
    registered_on   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_customer_phone  CHECK (phone REGEXP '^[6-9][0-9]{9}$'),
    CONSTRAINT chk_customer_email  CHECK (email IS NULL OR email LIKE '%_@_%._%'),
    CONSTRAINT chk_customer_gender CHECK (gender IS NULL OR gender IN ('F','M','O'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. STAFF
-- ---------------------------------------------------------------------
CREATE TABLE staff (
    staff_id        INT AUTO_INCREMENT PRIMARY KEY,
    full_name       VARCHAR(80)  NOT NULL,
    phone           CHAR(10)     NOT NULL UNIQUE,
    email           VARCHAR(100) UNIQUE,
    designation     VARCHAR(40)  NOT NULL,
    hire_date       DATE         NOT NULL,
    status          VARCHAR(10)  NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT chk_staff_phone  CHECK (phone REGEXP '^[6-9][0-9]{9}$'),
    CONSTRAINT chk_staff_status CHECK (status IN ('ACTIVE','ON_LEAVE','INACTIVE'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. STAFF_SKILL : M:N between STAFF and SKILL
-- ---------------------------------------------------------------------
CREATE TABLE staff_skill (
    staff_id          INT      NOT NULL,
    skill_id          INT      NOT NULL,
    proficiency_level TINYINT  NOT NULL DEFAULT 3,
    PRIMARY KEY (staff_id, skill_id),
    CONSTRAINT fk_ss_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ss_skill FOREIGN KEY (skill_id) REFERENCES skill(skill_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_ss_level CHECK (proficiency_level BETWEEN 1 AND 5)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. STAFF_SCHEDULE : weekly working hours (day_of_week 1=Sun ... 7=Sat,
--    same convention as MySQL DAYOFWEEK())
-- ---------------------------------------------------------------------
CREATE TABLE staff_schedule (
    schedule_id     INT AUTO_INCREMENT PRIMARY KEY,
    staff_id        INT      NOT NULL,
    day_of_week     TINYINT  NOT NULL,
    shift_start     TIME     NOT NULL,
    shift_end       TIME     NOT NULL,
    CONSTRAINT fk_sched_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_sched_staff_day UNIQUE (staff_id, day_of_week),
    CONSTRAINT chk_sched_day   CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT chk_sched_order CHECK (shift_end > shift_start),
    CONSTRAINT chk_sched_hours CHECK (shift_start >= '09:00:00' AND shift_end <= '21:00:00')
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 8. MEMBERSHIP_PLAN : Silver / Gold / Platinum etc.
-- ---------------------------------------------------------------------
CREATE TABLE membership_plan (
    plan_id         INT AUTO_INCREMENT PRIMARY KEY,
    plan_name       VARCHAR(30)  NOT NULL UNIQUE,
    annual_fee      DECIMAL(8,2) NOT NULL,
    discount_pct    DECIMAL(5,2) NOT NULL DEFAULT 0,
    CONSTRAINT chk_plan_fee      CHECK (annual_fee >= 0),
    CONSTRAINT chk_plan_discount CHECK (discount_pct BETWEEN 0 AND 50)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 9. CUSTOMER_MEMBERSHIP : a customer's subscription to a plan
-- ---------------------------------------------------------------------
CREATE TABLE customer_membership (
    membership_id   INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT   NOT NULL,
    plan_id         INT   NOT NULL,
    start_date      DATE  NOT NULL,
    end_date        DATE  NOT NULL,
    CONSTRAINT fk_cm_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_cm_plan FOREIGN KEY (plan_id) REFERENCES membership_plan(plan_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_cm_dates CHECK (end_date > start_date)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 10. PACKAGE : prepaid bundle of service sessions
-- ---------------------------------------------------------------------
CREATE TABLE package (
    package_id      INT AUTO_INCREMENT PRIMARY KEY,
    package_name    VARCHAR(60)  NOT NULL UNIQUE,
    price           DECIMAL(9,2) NOT NULL,
    validity_days   SMALLINT     NOT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    CONSTRAINT chk_pkg_price    CHECK (price > 0),
    CONSTRAINT chk_pkg_validity CHECK (validity_days BETWEEN 7 AND 730)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 11. PACKAGE_ITEM : which services (and how many sessions) a package has
-- ---------------------------------------------------------------------
CREATE TABLE package_item (
    package_id        INT      NOT NULL,
    service_id        INT      NOT NULL,
    sessions_included TINYINT  NOT NULL,
    PRIMARY KEY (package_id, service_id),
    CONSTRAINT fk_pi_package FOREIGN KEY (package_id) REFERENCES package(package_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pi_service FOREIGN KEY (service_id) REFERENCES service(service_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_pi_sessions CHECK (sessions_included BETWEEN 1 AND 50)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 12. CUSTOMER_PACKAGE : a package bought by a customer
--     (expiry_date is frozen at purchase; package validity may change later)
-- ---------------------------------------------------------------------
CREATE TABLE customer_package (
    customer_package_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id         INT          NOT NULL,
    package_id          INT          NOT NULL,
    purchase_date       DATE         NOT NULL,
    expiry_date         DATE         NOT NULL,
    amount_paid         DECIMAL(9,2) NOT NULL,
    status              VARCHAR(10)  NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_cp_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cp_package FOREIGN KEY (package_id) REFERENCES package(package_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_cp_dates  CHECK (expiry_date > purchase_date),
    CONSTRAINT chk_cp_amount CHECK (amount_paid >= 0),
    CONSTRAINT chk_cp_status CHECK (status IN ('ACTIVE','EXHAUSTED','EXPIRED','CANCELLED'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 13. APPOINTMENT : one customer visit on one date (header)
-- ---------------------------------------------------------------------
CREATE TABLE appointment (
    appointment_id   INT AUTO_INCREMENT PRIMARY KEY,
    customer_id      INT          NOT NULL,
    appointment_date DATE         NOT NULL,
    status           VARCHAR(10)  NOT NULL DEFAULT 'BOOKED',
    booked_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes            VARCHAR(200),
    CONSTRAINT fk_appt_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_appt_status CHECK (status IN ('BOOKED','COMPLETED','CANCELLED','NO_SHOW'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 14. APPOINTMENT_SERVICE : each service inside a visit, with the staff
--     member doing it and the time slot. Price and end time are frozen at
--     booking time (service price / duration may change later).
-- ---------------------------------------------------------------------
CREATE TABLE appointment_service (
    appt_service_id     INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id      INT          NOT NULL,
    service_id          INT          NOT NULL,
    staff_id            INT          NOT NULL,
    start_time          TIME         NOT NULL,
    end_time            TIME         NOT NULL,
    price_charged       DECIMAL(8,2) NOT NULL,
    customer_package_id INT          NULL,
    CONSTRAINT fk_as_appt FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_as_service FOREIGN KEY (service_id) REFERENCES service(service_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_as_staff FOREIGN KEY (staff_id) REFERENCES staff(staff_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_as_cpkg FOREIGN KEY (customer_package_id)
        REFERENCES customer_package(customer_package_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT chk_as_order CHECK (end_time > start_time),
    CONSTRAINT chk_as_hours CHECK (start_time >= '09:00:00' AND end_time <= '21:00:00'),
    CONSTRAINT chk_as_price CHECK (price_charged >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 15. PRODUCT : consumables / retail stock
-- ---------------------------------------------------------------------
CREATE TABLE product (
    product_id      INT AUTO_INCREMENT PRIMARY KEY,
    product_name    VARCHAR(80)  NOT NULL UNIQUE,
    brand           VARCHAR(40),
    unit            VARCHAR(10)  NOT NULL DEFAULT 'ml',
    unit_cost       DECIMAL(8,2) NOT NULL,
    stock_qty       DECIMAL(10,2) NOT NULL DEFAULT 0,
    reorder_level   DECIMAL(10,2) NOT NULL DEFAULT 0,
    CONSTRAINT chk_prod_cost    CHECK (unit_cost >= 0),
    CONSTRAINT chk_prod_stock   CHECK (stock_qty >= 0),
    CONSTRAINT chk_prod_reorder CHECK (reorder_level >= 0),
    CONSTRAINT chk_prod_unit    CHECK (unit IN ('ml','g','pcs'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 16. PRODUCT_USAGE : product issued against a performed service
-- ---------------------------------------------------------------------
CREATE TABLE product_usage (
    usage_id         INT AUTO_INCREMENT PRIMARY KEY,
    appt_service_id  INT           NOT NULL,
    product_id       INT           NOT NULL,
    quantity_used    DECIMAL(8,2)  NOT NULL,
    issued_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pu_as FOREIGN KEY (appt_service_id)
        REFERENCES appointment_service(appt_service_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pu_product FOREIGN KEY (product_id) REFERENCES product(product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_pu_qty CHECK (quantity_used > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 17. BILL : one bill per appointment
--     total_amount is a generated (computed) column, never typed in.
-- ---------------------------------------------------------------------
CREATE TABLE bill (
    bill_id          INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id   INT           NOT NULL UNIQUE,
    bill_date        DATE          NOT NULL,
    subtotal         DECIMAL(10,2) NOT NULL,
    discount_amount  DECIMAL(10,2) NOT NULL DEFAULT 0,
    tax_amount       DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount     DECIMAL(10,2) AS (subtotal - discount_amount + tax_amount) STORED,
    CONSTRAINT fk_bill_appt FOREIGN KEY (appointment_id) REFERENCES appointment(appointment_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_bill_subtotal CHECK (subtotal >= 0),
    CONSTRAINT chk_bill_discount CHECK (discount_amount >= 0 AND discount_amount <= subtotal),
    CONSTRAINT chk_bill_tax      CHECK (tax_amount >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 18. PAYMENT : one bill may be settled in several payments
-- ---------------------------------------------------------------------
CREATE TABLE payment (
    payment_id      INT AUTO_INCREMENT PRIMARY KEY,
    bill_id         INT           NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    method          VARCHAR(10)   NOT NULL DEFAULT 'UPI',
    paid_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reference_no    VARCHAR(40),
    CONSTRAINT fk_pay_bill FOREIGN KEY (bill_id) REFERENCES bill(bill_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_pay_amount CHECK (amount > 0),
    CONSTRAINT chk_pay_method CHECK (method IN ('CASH','CARD','UPI','WALLET'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- INDEXES on frequently searched / joined attributes
-- (PK, UNIQUE and FK columns are indexed automatically by InnoDB)
-- ---------------------------------------------------------------------
CREATE INDEX idx_customer_name      ON customer (last_name, first_name);
CREATE INDEX idx_staff_name         ON staff (full_name);
CREATE INDEX idx_appt_date_status   ON appointment (appointment_date, status);
CREATE INDEX idx_as_staff_time      ON appointment_service (staff_id, start_time);
CREATE INDEX idx_bill_date          ON bill (bill_date);
CREATE INDEX idx_payment_paid_at    ON payment (paid_at);
CREATE INDEX idx_cp_customer_status ON customer_package (customer_id, status);
