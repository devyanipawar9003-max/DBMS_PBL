"""
Generates 03_sample_data.sql - realistic, rule-consistent sample data for the
Salon & Spa Appointment Management System.

Every generated appointment respects the same rules the triggers enforce
(skill match, staff shift, no overlap, package-session limits, payment limit),
so the file loads cleanly through the triggers.  Re-run to regenerate:
    python generate_sample_data.py > 03_sample_data.sql
"""
import random
from datetime import date, datetime, time, timedelta

random.seed(66)
TODAY = date(2026, 10, 8)
START = date(2026, 8, 3)
END = date(2026, 10, 24)
out = []
w = out.append


def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def insert(table, cols, rows):
    w(f"INSERT INTO {table} ({', '.join(cols)}) VALUES")
    w(",\n".join("  (" + ", ".join(q(v) for v in r) + ")" for r in rows) + ";\n")


# ---------------------------------------------------------------- masters
categories = [
    (1, "Hair", "Cuts, styling, colouring and hair treatments"),
    (2, "Skin & Facial", "Facials, clean-ups, de-tan and skin care"),
    (3, "Nails", "Manicure, pedicure and nail art"),
    (4, "Spa & Massage", "Body massages and relaxation therapies"),
    (5, "Makeup", "Party and bridal makeup"),
    (6, "Grooming", "Waxing, threading and men's grooming"),
]
skills = [
    (1, "Hair Cutting & Styling"), (2, "Hair Colouring"), (3, "Hair Treatment"),
    (4, "Facial & Skin Care"), (5, "Waxing & Threading"), (6, "Manicure & Pedicure"),
    (7, "Nail Art"), (8, "Body Massage"), (9, "Makeup Artistry"), (10, "Beard & Shaving"),
]
# id, cat, skill, name, minutes, price
services = [
    (1, 1, 1, "Women's Haircut", 45, 600), (2, 1, 1, "Men's Haircut", 30, 350),
    (3, 1, 1, "Blow Dry & Styling", 30, 450), (4, 1, 2, "Global Hair Colour", 120, 3200),
    (5, 1, 2, "Root Touch-Up", 60, 1200), (6, 1, 3, "Hair Spa", 60, 1500),
    (7, 1, 3, "Keratin Treatment", 180, 6500),
    (8, 2, 4, "Classic Facial", 60, 1400), (9, 2, 4, "Gold Facial", 75, 2500),
    (10, 2, 4, "De-Tan Clean-Up", 45, 900),
    (11, 3, 6, "Classic Manicure", 45, 700), (12, 3, 6, "Spa Pedicure", 60, 1100),
    (13, 3, 7, "Gel Nail Art", 60, 1500),
    (14, 4, 8, "Swedish Massage (60 min)", 60, 2200), (15, 4, 8, "Deep Tissue Massage", 90, 3200),
    (16, 4, 8, "Head & Shoulder Massage", 30, 700),
    (17, 5, 9, "Party Makeup", 75, 3000), (18, 5, 9, "Bridal Makeup", 180, 15000),
    (19, 6, 5, "Full Arms Waxing", 30, 500), (20, 6, 5, "Eyebrow Threading", 15, 80),
    (21, 6, 10, "Beard Trim & Styling", 20, 250), (22, 6, 10, "Classic Shave", 30, 300),
]
svc = {s[0]: s for s in services}

staff = [
    (1, "Ananya Reddy", "9848012345", "ananya.r@glowandgrace.in", "Senior Stylist", "2021-06-14"),
    (2, "Mohammed Irfan", "9849023456", "irfan.m@glowandgrace.in", "Stylist", "2022-03-01"),
    (3, "Kavya Sharma", "9866034567", "kavya.s@glowandgrace.in", "Colour Specialist", "2020-11-20"),
    (4, "Lakshmi Prasanna", "9885045678", "lakshmi.p@glowandgrace.in", "Beautician", "2023-01-09"),
    (5, "Priya Naidu", "9908056789", "priya.n@glowandgrace.in", "Skin Therapist", "2022-07-18"),
    (6, "Rohan Verma", "9959067890", "rohan.v@glowandgrace.in", "Spa Therapist", "2021-09-05"),
    (7, "Sneha Kulkarni", "9963078901", "sneha.k@glowandgrace.in", "Nail Technician", "2024-02-12"),
    (8, "Arjun Rao", "9989089012", "arjun.r@glowandgrace.in", "Barber", "2023-08-21"),
    (9, "Fatima Begum", "9700090123", "fatima.b@glowandgrace.in", "Makeup Artist", "2020-04-15"),
    (10, "Deepika Goud", "9701101234", "deepika.g@glowandgrace.in", "Beautician", "2025-01-06"),
]
staff_status = {10: "ON_LEAVE"}
# staff -> {skill: level}
staff_skills = {
    1: {1: 5, 2: 4, 3: 4}, 2: {1: 4, 10: 4, 3: 3}, 3: {2: 5, 3: 4, 1: 3},
    4: {5: 4, 4: 3, 6: 3}, 5: {4: 5, 5: 3}, 6: {8: 5}, 7: {6: 5, 7: 5},
    8: {10: 5, 1: 3}, 9: {9: 5, 4: 3}, 10: {5: 3, 6: 3},
}
# weekly off (DAYOFWEEK: 1=Sun..7=Sat) and shift
shift_def = {
    1: (3, "10:00", "19:00"), 2: (4, "12:00", "21:00"), 3: (2, "10:00", "19:00"),
    4: (5, "11:00", "20:00"), 5: (3, "10:00", "19:00"), 6: (4, "12:00", "21:00"),
    7: (2, "11:00", "20:00"), 8: (6, "10:00", "19:00"), 9: (2, "10:00", "19:00"),
    10: (5, "10:00", "19:00"),
}

first_f = ["Aditi", "Bhavana", "Charitha", "Divya", "Harika", "Ishita", "Keerthi", "Meghana",
           "Nikhitha", "Pooja", "Ritu", "Sahithi", "Tanvi", "Varsha", "Yamini", "Zoya",
           "Shreya", "Mounika"]
first_m = ["Aakash", "Karthik", "Nikhil", "Rahul", "Sai Teja", "Varun", "Vikram", "Imran",
           "Pranav", "Siddharth", "Manoj", "Rakesh"]
lasts = ["Reddy", "Rao", "Sharma", "Gupta", "Naidu", "Patel", "Iyer", "Khan", "Varma", "Jain",
         "Chowdary", "Menon", "Agarwal", "Kapoor", "Desai", "Mishra", "Pillai", "Yadav"]
customers = []
used_phones = set()
used_names = set()
for cid in range(1, 41):
    g = "F" if cid % 10 not in (3, 7, 0) else "M"
    while True:
        fn = random.choice(first_f if g == "F" else first_m)
        ln = random.choice(lasts)
        if (fn, ln) not in used_names:
            used_names.add((fn, ln))
            break
    while True:
        ph = str(random.choice([6, 7, 8, 9])) + "".join(random.choice("0123456789") for _ in range(9))
        if ph not in used_phones:
            used_phones.add(ph)
            break
    email = f"{fn.lower().replace(' ', '')}.{ln.lower()}{cid}@gmail.com"
    dob = date(random.randint(1975, 2006), random.randint(1, 12), random.randint(1, 28))
    reg = START - timedelta(days=random.randint(0, 400)) if cid <= 30 else START + timedelta(days=random.randint(5, 60))
    customers.append((cid, fn, ln, ph, email, g, dob.isoformat(), f"{reg.isoformat()} 1{random.randint(0,8)}:{random.randint(10,59)}:00"))
cust_gender = {c[0]: c[5] for c in customers}
cust_reg = {c[0]: date.fromisoformat(c[7][:10]) for c in customers}

plans = [(1, "Silver", 999, 5), (2, "Gold", 2499, 10), (3, "Platinum", 4999, 15)]
memberships = []
mid = 1
for cid in [2, 5, 8, 11, 14, 17, 21, 24, 27, 33]:
    plan = random.choice([1, 1, 2, 2, 3])
    sd = max(cust_reg[cid], START - timedelta(days=random.randint(0, 200)))
    memberships.append((mid, cid, plan, sd.isoformat(), (sd + timedelta(days=365)).isoformat()))
    mid += 1

packages = [
    (1, "Glow Facial Pack", 3600, 90, [(8, 3)]),
    (2, "Hair Spa Combo", 4800, 120, [(6, 4)]),
    (3, "Mani-Pedi Monthly", 6200, 60, [(11, 4), (12, 4)]),
    (4, "Bridal Prep Package", 19500, 60, [(9, 2), (18, 1), (19, 2), (20, 2)]),
    (5, "Relax & Unwind", 9000, 180, [(14, 5)]),
    (6, "Gentleman's Grooming", 1500, 90, [(2, 3), (21, 3)]),
]
pkg = {p[0]: p for p in packages}

cust_pkgs = []  # id, cust, pkg, purchase, expiry, amount, status
cpid = 1
for cid, pid, d in [(2, 1, "2026-08-05"), (5, 2, "2026-08-10"), (8, 3, "2026-09-01"),
                    (14, 5, "2026-08-04"), (11, 1, "2026-09-12"), (19, 4, "2026-09-20"),
                    (3, 6, "2026-08-08"), (24, 3, "2026-09-15"), (27, 2, "2026-06-01"), (30, 5, "2026-09-25"), (33, 1, "2026-10-01"), (9, 2, "2026-09-28"), (36, 3, "2026-10-03"),
                    (21, 1, "2026-05-02")]:
    pd = date.fromisoformat(d)
    cust_pkgs.append([cpid, cid, pid, d, (pd + timedelta(days=pkg[pid][3])).isoformat(), pkg[pid][2], "ACTIVE"])
    cpid += 1

products = [
    (1, "L'Oreal Professional Shampoo", "L'Oreal", "ml", 1.10, 6000, 1000),
    (2, "Matrix Conditioner", "Matrix", "ml", 1.30, 5000, 800),
    (3, "Majirel Hair Colour", "L'Oreal", "g", 9.50, 1800, 300),
    (4, "Developer 20 Vol", "L'Oreal", "ml", 0.60, 4000, 600),
    (5, "Hair Spa Cream", "Schwarzkopf", "g", 2.20, 3000, 500),
    (6, "Keratin Smoothing Solution", "GK Hair", "ml", 14.00, 600, 300),
    (7, "VLCC Gold Facial Kit", "VLCC", "pcs", 420.00, 25, 5),
    (8, "Lotus Fruit Facial Kit", "Lotus Herbals", "pcs", 260.00, 75, 10),
    (9, "De-Tan Pack", "O3+", "g", 3.00, 2500, 400),
    (10, "Rica Liposoluble Wax", "Rica", "g", 1.60, 4000, 600),
    (11, "OPI Gel Polish", "OPI", "ml", 18.00, 600, 100),
    (12, "Pedicure Soak Salt", "Spa Ceylon", "g", 0.90, 9000, 1500),
    (13, "Aroma Massage Oil", "Kama Ayurveda", "ml", 2.40, 7000, 1000),
    (14, "MAC Foundation", "MAC", "ml", 95.00, 110, 40),
    (15, "Shaving Cream", "Gillette", "g", 0.80, 1500, 300),
]
# service -> list of (product, qty_low, qty_high)
svc_products = {
    1: [(1, 20, 30), (2, 15, 25)], 2: [(1, 10, 15)], 3: [(1, 15, 20)],
    4: [(3, 60, 90), (4, 60, 90), (1, 25, 30)], 5: [(3, 30, 40), (4, 30, 40)],
    6: [(5, 40, 60), (1, 20, 25)], 7: [(6, 40, 70), (1, 30, 40)],
    8: [(8, 1, 1)], 9: [(7, 1, 1)], 10: [(9, 30, 50)],
    11: [(12, 40, 60)], 12: [(12, 80, 120)], 13: [(11, 4, 6)],
    14: [(13, 40, 60)], 15: [(13, 60, 80)], 16: [(13, 15, 20)],
    17: [(14, 3, 5)], 18: [(14, 6, 8)], 19: [(10, 40, 60)], 22: [(15, 15, 20)],
}
stock = {p[0]: p[5] for p in products}

# ------------------------------------------------------------ scheduling
def dow(d):  # MySQL DAYOFWEEK: 1=Sun..7=Sat
    return (d.weekday() + 1) % 7 + 1


def tmin(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


busy = {}  # (staff, date) -> list of (start,end)


def free(staff_id, d, s, e):
    off, ss, se = shift_def[staff_id]
    if dow(d) == off or s < tmin(ss) or e > tmin(se):
        return False
    return all(e <= bs or s >= be for bs, be in busy.get((staff_id, d), []))


def capable(service_id):
    sk = svc[service_id][2]
    return [sid for sid, sks in staff_skills.items() if sk in sks and staff_status.get(sid) != "ON_LEAVE"]


popular = [1, 1, 2, 2, 3, 5, 6, 8, 8, 10, 11, 12, 12, 13, 14, 14, 16, 19, 20, 20, 20, 21, 4, 9, 15, 17, 22, 7]
male_ok = {2, 6, 10, 14, 15, 16, 21, 22, 8, 12}
combos_f = [[20, 8], [11, 12], [1, 3], [6, 1], [19, 20], [10, 20], [14, 16]]

appointments, lines, usage, bills, payments = [], [], [], [], []
pkg_used = {}
aid = lid = uid = bid = pid_ = 1


def fmt(m):
    return f"{m // 60:02d}:{m % 60:02d}:00"


d = START
while d <= END:
    n = random.randint(10, 14) if dow(d) in (1, 7) else random.randint(5, 9)
    for _ in range(n):
        cid = random.randint(1, 40)
        if cust_reg[cid] > d:
            continue
        g = cust_gender[cid]
        # package redemption first if the customer owns a usable package
        wanted, from_pkg = [], {}
        for cp in cust_pkgs:
            if cp[1] == cid and date.fromisoformat(cp[3]) <= d <= date.fromisoformat(cp[4]) and random.random() < 0.3:
                for (s_id, n_s) in pkg[cp[2]][4]:
                    if pkg_used.get((cp[0], s_id), 0) < n_s and s_id not in wanted and len(wanted) < 2:
                        if s_id == 18:  # bridal makeup only once near the end
                            continue
                        wanted.append(s_id)
                        from_pkg[s_id] = cp[0]
                break
        if not wanted:
            if g == "F" and random.random() < 0.4:
                wanted = list(random.choice(combos_f))
            else:
                k = random.choice([1, 1, 2])
                pool = [s for s in popular if (g == "F" and s not in (2, 21, 22)) or (g == "M" and s in male_ok)]
                wanted = list(dict.fromkeys(random.sample(pool, k)))
        cursor = random.choice(range(tmin("10:00"), tmin("18:30"), 15))
        booked = []
        for s_id in wanted:
            dur = svc[s_id][4]
            placed = False
            for tries in range(16):
                s = cursor + tries * 15
                e = s + dur
                if e > tmin("21:00"):
                    break
                cands = [st for st in capable(s_id) if free(st, d, s, e)]
                if cands:
                    st = random.choice(cands)
                    busy.setdefault((st, d), []).append((s, e))
                    booked.append((s_id, st, s, e))
                    cursor = e
                    placed = True
                    break
            if not placed:
                continue
        if not booked:
            continue
        if d < TODAY:
            status = random.choices(["COMPLETED", "CANCELLED", "NO_SHOW"], [90, 7, 3])[0]
        elif d == TODAY:
            status = "BOOKED"
        else:
            status = random.choices(["BOOKED", "CANCELLED"], [93, 7])[0]
        booked_at = d - timedelta(days=random.randint(0, 6))
        appointments.append((aid, cid, d.isoformat(), status,
                             f"{booked_at.isoformat()} {random.randint(9, 20):02d}:{random.randint(0, 59):02d}:00",
                             None))
        appt_lines = []
        for s_id, st, s, e in booked:
            cp = from_pkg.get(s_id) if status not in ("CANCELLED", "NO_SHOW") else None
            if cp:
                pkg_used[(cp, s_id)] = pkg_used.get((cp, s_id), 0) + 1
            price = 0 if cp else svc[s_id][5]
            lines.append((lid, aid, s_id, st, fmt(s), fmt(e), price, cp))
            appt_lines.append((lid, s_id, price))
            if status == "COMPLETED":
                for (p, lo, hi) in svc_products.get(s_id, []):
                    qty = random.randint(lo, hi) if hi > 1 else 1
                    if stock[p] >= qty:
                        stock[p] -= qty
                        usage.append((uid, lid, p, qty, f"{d.isoformat()} {fmt(e)}"))
                        uid += 1
            lid += 1
        if status == "COMPLETED":
            sub = sum(p for _, _, p in appt_lines)
            disc_pct = 0
            for m in memberships:
                if m[1] == cid and date.fromisoformat(m[3]) <= d <= date.fromisoformat(m[4]):
                    disc_pct = plans[m[2] - 1][3]
            disc = round(sub * disc_pct / 100, 2)
            tax = round((sub - disc) * 0.18, 2)
            total = round(sub - disc + tax, 2)
            bills.append((bid, aid, d.isoformat(), sub, disc, tax))
            if total > 0:
                r = random.random()
                when = f"{d.isoformat()} {fmt(booked[-1][3])}"
                if r < 0.78 or d < TODAY - timedelta(days=14):
                    payments.append((pid_, bid, total, random.choice(["UPI", "UPI", "UPI", "CARD", "CASH"]), when, f"TXN{100000 + pid_}"))
                    pid_ += 1
                elif r < 0.92:  # split payment
                    part = round(total * 0.4, 2)
                    payments.append((pid_, bid, part, "CASH", when, None)); pid_ += 1
                    payments.append((pid_, bid, round(total - part, 2), "UPI", when, f"TXN{100000 + pid_}")); pid_ += 1
                else:  # partially paid -> outstanding balance
                    payments.append((pid_, bid, round(total * 0.5, 2), "CASH", when, None)); pid_ += 1
            bid += 1
        aid += 1
    d += timedelta(days=1)

# package status: exhausted / expired
for cp in cust_pkgs:
    items = pkg[cp[2]][4]
    if all(pkg_used.get((cp[0], s), 0) >= n for s, n in items):
        cp[6] = "EXHAUSTED"
    elif date.fromisoformat(cp[4]) < TODAY:
        cp[6] = "EXPIRED"

# ---------------------------------------------------------------- output
w("-- =====================================================================")
w("--  Salon & Spa Appointment Management System")
w("--  File 03 : Sample data  (generated by generate_sample_data.py, seed 66)")
w("--  Salon: 'Glow & Grace Salon and Spa', Hyderabad (fictional)")
w("-- =====================================================================")
w("USE salon_spa_db;\nSET NAMES utf8mb4;\n")
insert("service_category", ["category_id", "category_name", "description"], categories)
insert("skill", ["skill_id", "skill_name"], skills)
insert("service", ["service_id", "category_id", "required_skill_id", "service_name", "duration_min", "price"], services)
insert("staff", ["staff_id", "full_name", "phone", "email", "designation", "hire_date", "status"],
       [s + (staff_status.get(s[0], "ACTIVE"),) for s in staff])
insert("staff_skill", ["staff_id", "skill_id", "proficiency_level"],
       [(sid, sk, lv) for sid, sks in staff_skills.items() for sk, lv in sks.items()])
sched = []
scid = 1
for sid, (off, ss, se) in shift_def.items():
    for dw in range(1, 8):
        if dw != off:
            sched.append((scid, sid, dw, ss + ":00", se + ":00")); scid += 1
insert("staff_schedule", ["schedule_id", "staff_id", "day_of_week", "shift_start", "shift_end"], sched)
insert("customer", ["customer_id", "first_name", "last_name", "phone", "email", "gender", "date_of_birth", "registered_on"], customers)
insert("membership_plan", ["plan_id", "plan_name", "annual_fee", "discount_pct"], plans)
insert("customer_membership", ["membership_id", "customer_id", "plan_id", "start_date", "end_date"], memberships)
insert("package", ["package_id", "package_name", "price", "validity_days"], [p[:4] for p in packages])
insert("package_item", ["package_id", "service_id", "sessions_included"],
       [(p[0], s, n) for p in packages for s, n in p[4]])
# customer packages are inserted ACTIVE so the triggers accept the redemptions;
# their final status is set after the appointments are loaded.
insert("customer_package", ["customer_package_id", "customer_id", "package_id", "purchase_date", "expiry_date", "amount_paid", "status"],
       [cp[:6] + ["ACTIVE"] for cp in cust_pkgs])
insert("product", ["product_id", "product_name", "brand", "unit", "unit_cost", "stock_qty", "reorder_level"], products)
# appointments: insert as BOOKED first so that lines can be attached, then set final status
insert("appointment", ["appointment_id", "customer_id", "appointment_date", "status", "booked_at", "notes"],
       [(a[0], a[1], a[2], "BOOKED", a[4], a[5]) for a in appointments])
for i in range(0, len(lines), 60):
    insert("appointment_service", ["appt_service_id", "appointment_id", "service_id", "staff_id", "start_time", "end_time", "price_charged", "customer_package_id"],
           lines[i:i + 60])
for st in ("COMPLETED", "CANCELLED", "NO_SHOW"):
    ids = [str(a[0]) for a in appointments if a[3] == st]
    if ids:
        w(f"UPDATE appointment SET status = '{st}' WHERE appointment_id IN ({', '.join(ids)});\n")
for st in ("EXHAUSTED", "EXPIRED"):
    ids = [str(cp[0]) for cp in cust_pkgs if cp[6] == st]
    if ids:
        w(f"UPDATE customer_package SET status = '{st}' WHERE customer_package_id IN ({', '.join(ids)});\n")
for i in range(0, len(usage), 80):
    insert("product_usage", ["usage_id", "appt_service_id", "product_id", "quantity_used", "issued_at"], usage[i:i + 80])
insert("bill", ["bill_id", "appointment_id", "bill_date", "subtotal", "discount_amount", "tax_amount"], bills)
insert("payment", ["payment_id", "bill_id", "amount", "method", "paid_at", "reference_no"], payments)

import sys
print("\n".join(out))
print(f"-- rows: customers={len(customers)} appointments={len(appointments)} services={len(lines)} "
      f"usage={len(usage)} bills={len(bills)} payments={len(payments)}", file=sys.stderr)
