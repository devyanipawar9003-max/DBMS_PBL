"""
Fills the official DBMS PBL report template with the project content.
Usage: python build_report.py <template.docx> <out.docx> [pages.json]
pages.json (optional) maps heading/caption text -> page number (2nd pass for TOC).
"""
import copy, json, os, re, sys
import mysql.connector
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image

TPL, OUT = sys.argv[1], sys.argv[2]
PAGES = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else {}
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHOT = os.path.join(ROOT, "screenshots", "cropped")

d = Document(TPL)
body = d.element.body
TITLE = "Design and Implementation of a Database Management System for Salon and Spa Appointment Management System"
REPO = "https://github.com/<your-username>/salon-spa-dbms"

db = mysql.connector.connect(user=os.getenv("SALON_DB_USER", "salon"), password=os.getenv("SALON_DB_PASSWORD", "salon123"), database="salon_spa_db")
cur = db.cursor()


def q(sql):
    cur.execute(sql)
    return cur.fetchall()


# ------------------------------------------------------------------ helpers
def P(el):
    return Paragraph(el, d)


def paras():
    return [P(e) for e in body.iterchildren() if e.tag == qn("w:p")]


def find(text, start=None, exact=False):
    for p in paras():
        t = p.text.strip()
        if (t == text) if exact else t.startswith(text):
            return p
    raise KeyError(text)


def remove(el):
    el.getparent().remove(el)


def new_p(text="", style="Normal", align="justify", size=12, bold=False, italic=False, spacing=1.5, after=6, font="Times New Roman"):
    p = d.add_paragraph(style=style)
    if text:
        add_runs(p, text, size=size, bold=bold, italic=italic, font=font)
    pf = p.paragraph_format
    pf.alignment = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY, "center": WD_ALIGN_PARAGRAPH.CENTER, "left": WD_ALIGN_PARAGRAPH.LEFT}[align]
    pf.line_spacing = spacing
    pf.space_after = Pt(after)
    return p


def add_runs(p, text, size=12, bold=False, italic=False, font="Times New Roman"):
    """**bold** segments supported; [[x]] = yellow-highlighted placeholder."""
    for part in re.split(r"(\*\*.+?\*\*|\[\[.+?\]\])", text):
        if not part:
            continue
        b, hl = bold, False
        if part.startswith("**"):
            part, b = part[2:-2], True
        elif part.startswith("[["):
            part, hl = "[" + part[2:-2] + "]", True
        r = p.add_run(part)
        r.font.size, r.font.bold, r.font.italic, r.font.name = Pt(size), b, italic, font
        r._element.rPr.rFonts.set(qn("w:eastAsia"), font)
        if hl:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return p


def set_text(p, text, **kw):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    for h in p._element.findall(qn("w:hyperlink")):
        remove(h)
    add_runs(p, text, **kw)
    return p


class Cursor:
    """Inserts elements one after another, starting after an anchor element."""
    def __init__(self, anchor):
        self.el = anchor._element if hasattr(anchor, "_element") else anchor

    def put(self, obj):
        el = obj._element if hasattr(obj, "_element") else obj._tbl if hasattr(obj, "_tbl") else obj
        if isinstance(obj, Table):
            el = obj._tbl
        self.el.addnext(el)
        self.el = el
        return obj

    def para(self, text, **kw):
        return self.put(new_p(text, **kw))

    def bullets(self, items, size=12):
        for it in items:
            p = new_p(it, style="List Bullet", size=size)
            p.paragraph_format.line_spacing = 1.5
            p.paragraph_format.space_after = Pt(3)
            self.put(p)

    def code(self, text, size=8):
        lines = text.strip("\n").split("\n")
        for i, line in enumerate(lines):
            p = new_p(line.replace(" ", " ") if line else " ", align="left", size=size, spacing=1.0, after=0, font="Courier New")
            pPr = p._element.get_or_add_pPr()
            shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "F2F2F2")
            pPr.append(shd)
            if i == len(lines) - 1:
                p.paragraph_format.space_after = Pt(8)
            self.put(p)

    def image(self, path, width_in, max_h_in=None):
        w, h = Image.open(path).size
        width = width_in
        if max_h_in and width_in * h / w > max_h_in:
            width = max_h_in * w / h
        p = new_p(align="center", spacing=1.0, after=2)
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(path, width=Inches(width))
        return self.put(p)

    def caption(self, text):
        p = d.add_paragraph(style="Caption")
        add_runs(p, text, size=11, bold=True)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if text.startswith("Table"):
            p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_after = Pt(10)
        return self.put(p)


# ---- numbering of tables and figures (in document order)
TCOUNT, FCOUNT = [0], [0]
TABLES, FIGURES = [], []


def tcap(title):
    TCOUNT[0] += 1
    TABLES.append((TCOUNT[0], title))
    return f"Table {TCOUNT[0]}. {title}"


def fcap(title):
    FCOUNT[0] += 1
    FIGURES.append((FCOUNT[0], title))
    return f"Figure {FCOUNT[0]}. {title}"


def caption_para(p, text):
    """Rewrite an existing template caption."""
    set_text(p, text, size=11, bold=True)
    p.paragraph_format.keep_with_next = True


def cell_text(cell, text, size=10, bold=None, align=None, hl=False):
    p = cell.paragraphs[0]
    for extra in cell.paragraphs[1:]:
        remove(extra._element)
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    run = p.add_run(str(text))
    run.font.size = Pt(size)
    run.font.name = "Times New Roman"
    if bold is not None:
        run.font.bold = bold
    if hl:
        run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(0)
    if align:
        p.paragraph_format.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER}[align]


def strip_vmerge(tr):
    for vm in tr.iter(qn("w:vMerge")):
        vm.getparent().remove(vm)


def fill(table, rows, size=10, header=None, proto_idx=1):
    """Replace all data rows of a template table with `rows`."""
    trs = table._tbl.findall(qn("w:tr"))
    proto = copy.deepcopy(trs[proto_idx])
    strip_vmerge(proto)
    for tr in trs[1:]:
        table._tbl.remove(tr)
    if header:
        hdr = Table(table._tbl, table._parent).rows[0]
        for c, h in zip(hdr.cells, header):
            cell_text(c, h, size=size, bold=True, align="center")
    for r in rows:
        tr = copy.deepcopy(proto)
        table._tbl.append(tr)
        row = Table(table._tbl, table._parent).rows[-1]
        for c, v in zip(row.cells, r):
            cell_text(c, v, size=size, bold=False, align="left")
    return table


def clone_table(table):
    return Table(copy.deepcopy(table._tbl), table._parent)


def table_after(cursor, template_table, rows, header, size=10, widths=None):
    t = clone_table(template_table)
    fill(t, rows, size=size, header=header)
    if widths:
        set_widths(t, widths)
    cursor.put(t)
    return t


def set_widths(table, widths_in):
    tblPr = table._tbl.tblPr
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW"); tblPr.append(tblW)
    tblW.set(qn("w:w"), str(int(sum(widths_in) * 1440))); tblW.set(qn("w:type"), "dxa")
    lay = tblPr.find(qn("w:tblLayout"))
    if lay is None:
        lay = OxmlElement("w:tblLayout"); tblPr.append(lay)
    lay.set(qn("w:type"), "fixed")
    grid = table._tbl.find(qn("w:tblGrid"))
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths_in):
        gc.set(qn("w:w"), str(int(w * 1440)))
    for tr in table._tbl.findall(qn("w:tr")):
        for tc, w in zip(tr.findall(qn("w:tc")), widths_in):
            tcPr = tc.get_or_add_tcPr()
            tcW = tcPr.find(qn("w:tcW"))
            if tcW is None:
                tcW = OxmlElement("w:tcW"); tcPr.insert(0, tcW)
            tcW.set(qn("w:w"), str(int(w * 1440))); tcW.set(qn("w:type"), "dxa")


def tbl_after(p):
    el = p._element.getnext()
    while el is not None and el.tag != qn("w:tbl"):
        el = el.getnext()
    return Table(el, d._body)


def page_break_before(p):
    p.paragraph_format.page_break_before = True


# =====================================================================
# 0. Remove guidelines page and the blank spacer paragraphs
# =====================================================================
children = list(body.iterchildren())
first_tbl = next(i for i, e in enumerate(children) if e.tag == qn("w:tbl"))
for e in children[:first_tbl]:
    remove(e)

# remove instruction (italic guidance) paragraphs
GUIDE = ["Use this common structure", "Update this list after", "Retain only the acronyms", "Write the abstract as one",
         "Provide 4-6 specific keywords", "This chapter should", "Describe the current problem", "State 3-5 measurable",
         "Explain how the proposed solution", "Insert the approved ER", "List every relation", "Include PRIMARY KEY, FOREIGN",
         "List the important functional", "[Example format", "Prepare the data dictionary", "Mention the DBMS used",
         "[Insert representative DDL", "Briefly explain the users", "Explain how the application prevents", "Insert the important application",
         "Summarize the key results", "Summarize the problem addressed", "Mention genuine limitations", "Use IEEE reference style",
         "Attach the complete DDL", "Provide the source-code", "Include any additional test", "Reference-writing notes"]
for p in paras():
    if any(p.text.strip().startswith(g) for g in GUIDE):
        remove(p._element)
# abstract guidance table
abs_h = find("ABSTRACT", exact=True)
remove(tbl_after(abs_h)._tbl)
# IEEE guideline sub-sections (5.1 / 5.2 and their content) up to the appendices heading
start = find("5.1 IEEE In-Text Citation Guidelines")
stop = find("APPENDICES", exact=True)._element
el = start._element
while el is not None and el is not stop:
    nxt = el.getnext()
    remove(el)
    el = nxt

# delete empty paragraphs outside the cover page (cover ends at the "Submitted by" table)
cover_end = find("Submitted by")._element
seen_cover = False
for e in list(body.iterchildren()):
    if e is cover_end:
        seen_cover = True
        continue
    if not seen_cover or e.tag != qn("w:p"):
        continue
    p = P(e)
    if not p.text.strip() and "graphic" not in e.xml and "w:sectPr" not in e.xml:
        if 'w:type="page"' in e.xml and False:
            continue
        remove(e)

# =====================================================================
# 1. Cover, acknowledgement, undertaking
# =====================================================================
tables = d.tables
title_tbl = tables[1]
cell_text(title_tbl.rows[0].cells[0], TITLE.upper() + "\n(PROJECT 66)", size=14, bold=True, align="center")
info = tables[2]
vals = ["B.Tech – Computer Science and Engineering (AI & ML)", "AIML Rhinos", "[[Faculty name]]", "[[DD]] October 2026", "2026 – 27"]
for row, v in zip(info.rows, vals):
    hl = v.startswith("[[")
    cell_text(row.cells[1], v.replace("[[", "").replace("]]", ""), size=12, hl=hl)
sub = tables[3]
for c, v, hl in zip(sub.rows[1].cells, ["25WU0102069", "Devyani Pawar", "Mobile", "University email"], [False, False, True, True]):
    cell_text(c, v, size=11, align="center", hl=hl)

ack = find("I thank my course faculty")
set_text(ack, "I thank my course faculty, [[Faculty name]], for the guidance, suggestions, and support throughout the design and development of this project. The guidance helped me understand the practical application of database concepts such as ER modelling, relational schema design, normalization, SQL, constraints, queries, and database application development.")
und = find("I hereby declare that the project entitled")
set_text(und, f"I hereby declare that the project entitled **“{TITLE}”**, submitted as part of the Project-Based Learning activity for the **Database Management Systems (DBMS)** course, is my individual work carried out under the guidance of the course faculty.")
for p in (ack, und):
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
sig = tables[4]
cells = {(0, 4): None}
cell_text(sig.rows[2].cells[2], "Hyderabad", size=12)
cell_text(sig.rows[1].cells[4], "Devyani Pawar", size=12)
cell_text(sig.rows[2].cells[4], "25WU0102069", size=12)
cell_text(sig.rows[3].cells[4], "B.Tech CSE (AI & ML)", size=12)

# =====================================================================
# 2. Abstract, keywords
# =====================================================================
ABSTRACT = ("Salons and spas still commonly run their day on a paper appointment book, which cannot detect when a stylist is "
    "double-booked, when a service is given to someone without the right skill, how many prepaid package sessions a client "
    "has left, how much stock was consumed, or which bills are only partly paid. The objective of this project is to design and "
    "implement a relational database, with a small application on top of it, that manages the complete salon workflow from "
    "booking to payment while enforcing these rules automatically. The conceptual design identifies 14 entities and 16 "
    "relationships, which were mapped to 18 relations and normalized to Third Normal Form. The database was implemented in "
    "MySQL 8 with 85 declarative constraints, five triggers backed by a validation procedure, seven reporting views and seven "
    "secondary indexes, and populated with realistic data for 603 appointments. A Python application built with Streamlit "
    "provides customer registration, skilled-staff booking, package redemption, product issue, billing with membership discounts "
    "and GST, partial payments and six management reports. Testing showed that every invalid operation, including overlapping "
    "bookings, skill mismatches and over-payments, is rejected by the database itself, giving a dependable and practical system "
    "for small salons.")
p = find("[Write the final abstract here.]")
set_text(p, ABSTRACT)
p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
p.paragraph_format.line_spacing = 1.5
kw = find("Keywords:")
set_text(kw, "**Keywords:** Relational Database, ER Modelling, Normalization (3NF), MySQL Triggers, Python Streamlit, Salon Appointment Scheduling")

# acronyms
acr = [("1NF / 2NF / 3NF", "First / Second / Third Normal Form"), ("BCNF", "Boyce–Codd Normal Form"), ("CRUD", "Create, Read, Update, Delete"),
       ("CSV", "Comma-Separated Values"), ("DBMS", "Database Management System"), ("DDL", "Data Definition Language"),
       ("DML", "Data Manipulation Language"), ("ER / ERD", "Entity–Relationship / Entity–Relationship Diagram"), ("FD", "Functional Dependency"),
       ("FK", "Foreign Key"), ("FR", "Functional Requirement"), ("GST", "Goods and Services Tax"), ("GUI", "Graphical User Interface"),
       ("INR", "Indian Rupee"), ("PBL", "Project-Based Learning"), ("PK", "Primary Key"), ("SQL", "Structured Query Language"),
       ("TC", "Test Case"), ("UPI", "Unified Payments Interface")]
fill(tbl_after(find("LIST OF ACRONYMS", exact=True)), acr, size=11)

# =====================================================================
# 3. Chapter 1
# =====================================================================
h = find("1.1 Problem Statement")
c = Cursor(h)
c.para("A typical neighbourhood salon and spa offers 20 or more services across hair, skin, nails, massage, makeup and grooming, "
       "performed by staff who each hold only some of the required skills and work different weekly shifts. Customers buy prepaid "
       "packages and annual memberships, products such as hair colour and facial kits are consumed during services, and bills are "
       "often settled in more than one payment. In most small salons all of this is still recorded in a paper appointment book, "
       "separate package cards and a cash register.")
c.para("This manual process has clear failures. The book cannot see that a stylist is already busy, so two clients are booked into "
       "overlapping slots; it does not know who is trained for which service, so a barber can be booked for a facial; package "
       "sessions are over-used or disputed; product consumption is never linked to services; and partly paid bills are forgotten. "
       "The receptionist, the salon manager, the service staff and ultimately the customer are all affected. A database-driven "
       "application is needed that stores this information once, enforces the salon's business rules at the moment of entry and "
       "produces reliable reports on appointments, staff utilization, service popularity, package balances, product use and revenue.")
remove(find("[Problem statement")._element)

h = find("1.2 Objectives")
for p in paras():
    if p.text.strip().startswith("[Objective"):
        remove(p._element)
c = Cursor(h)
c.bullets([
    "**Design** a normalized (3NF) relational database that covers all twelve required areas: customers, services, categories, staff, skills, schedules, appointments, packages, memberships, product usage, bills and payments.",
    "**Implement** the five core business rules inside MySQL – no overlapping staff appointments, skill match, package-session limits, valid appointment times and payment limits – so that no client can bypass them.",
    "**Populate** the database with realistic sample data (40 customers, 10 staff, 600+ appointments) and write at least 20 SQL queries and 6 views for the required reports.",
    "**Develop** a Python application that performs registration, booking with skilled-staff assignment, package use, product issue, billing, payment and reporting on the live database.",
    "**Validate** the system with at least 15 positive and negative test cases and record a five-minute demonstration.",
])

Cursor(find("1.3 Scope and Assumptions")).para("Table 1 defines what the system covers and the assumptions made about the salon.")
t = tbl_after(find("Table 1. Scope and Assumptions"))
caption_para(find("Table 1. Scope and Assumptions"), tcap("Scope and Assumptions"))
fill(t, [
    ["In Scope", "Customer registration and search; service categories and services; staff, skills with proficiency and weekly schedules; multi-service appointments with staff assignment; rescheduling, cancellation, completion and no-show; packages and package redemption; memberships and discounts; product stock and product issue; bills with discount and GST; full and partial payments; six management reports."],
    ["Out of Scope / Exclusions", "Online self-booking portal, SMS/WhatsApp reminders, payroll and commissions, supplier purchase orders, multi-branch operation, user login and role-based access control."],
    ["Assumptions", "Single branch open 09:00–21:00 every day; prices in INR; GST at 18% on the discounted amount; one bill per visit; a customer can hold at most one active membership; package sessions are redeemable only by the buyer before expiry; time slots in 15-minute steps."],
], size=10.5)

h = find("1.4 Proposed Solution Strategy")
c = Cursor(h)
c.para("The solution follows the standard database design life-cycle – requirements, conceptual ER design, logical relational design, "
       "normalization and physical implementation [1]. Business rules that involve only one row are declared as CHECK, UNIQUE, NOT NULL "
       "and FOREIGN KEY constraints; rules that need other rows (overlaps, skills, package balances, payment totals) are enforced by "
       "BEFORE INSERT/UPDATE triggers, so the database itself rejects invalid data. A Python application then provides the screens "
       "used at the front desk. Table 2 summarises the strategy.")
caption_para(find("Table 2. Proposed Solution Strategy"), tcap("Proposed Solution Strategy"))
fill(tbl_after(find("Table 2. Proposed Solution Strategy")), [
    ["Primary Users / Roles", "Receptionist (registration, booking, billing, payments); Salon manager (staff, skills, schedules, packages, stock, reports); Stylist / therapist (performs services, issues products); Customer (indirect user)."],
    ["Major Application Modules", "Dashboard, Customers, Book Appointment, Manage Appointments, Packages & Memberships, Products & Stock, Billing & Payments, Staff & Services, Reports."],
    ["Proposed Workflow", "Register customer → book one or more services, choosing only skilled, on-shift and free staff (or redeem a package session) → complete the visit and issue products → generate the bill with membership discount and GST → record one or more payments → review reports."],
    ["Important Business Rules", "No overlapping staff appointments; staff must hold the skill a service requires; slot = service duration and inside the staff shift and 09:00–21:00; package redemptions within sessions and validity, only by the owner; total payments ≤ bill total; bill only completed visits; stock never negative."],
    ["Expected Reports / Outputs", "Daily appointment sheet and appointment statistics, staff utilization, service popularity and category revenue, package balances, product consumption with re-order alerts, monthly billed vs collected revenue and outstanding dues."],
], size=10.5)

Cursor(find("1.5 Functional Requirements")).para("The twelve functional requirements in Table 3 were derived from the problem statement and the project brief.")
caption_para(find("Table 3. Functional Requirements"), tcap("Functional Requirements"))
fill(tbl_after(find("Table 3. Functional Requirements")), [
    ["FR-01", "Register, search, update and delete customers with input validation", "High"],
    ["FR-02", "Maintain service categories, services, durations and prices", "High"],
    ["FR-03", "Maintain staff, staff skills with proficiency, and weekly schedules", "High"],
    ["FR-04", "Book an appointment containing one or more services and time slots", "High"],
    ["FR-05", "Assign only staff who have the required skill, are on shift and are free", "High"],
    ["FR-06", "Reschedule, cancel, complete or mark an appointment as no-show", "High"],
    ["FR-07", "Sell packages and redeem sessions within limits and validity", "High"],
    ["FR-08", "Enrol customers in membership plans and apply plan discounts on bills", "Medium"],
    ["FR-09", "Issue products against performed services, update stock, flag re-order", "Medium"],
    ["FR-10", "Generate a bill (subtotal, discount, GST, total) for a completed visit", "High"],
    ["FR-11", "Record full or partial payments without exceeding the bill total", "High"],
    ["FR-12", "Produce reports: appointments, staff utilization, service popularity, package balances, product use and revenue", "High"],
], size=10.5)

h = find("1.6 Entity-Relationship Diagram (ERD)")
c = Cursor(h)
c.para("The conceptual model was drawn using Chen-style ER notation [2]. Figure 1 shows the 14 entities with their key attributes and the "
       "16 relationships with cardinalities. Weak entities (STAFF_SCHEDULE, APPOINTMENT_SERVICE and PAYMENT) have a double border and "
       "total participation is shown by a double line. Many-to-many relationships carry their own attributes – for example "
       "HAS_SKILL carries proficiency_level and CONTAINS carries sessions_included. A full-page version is given in Appendix C.")
ph = find("[Insert approved ER diagram here]")
cc = Cursor(ph)
cc.image(os.path.join(ROOT, "docs", "er_diagram.png"), 6.3)
remove(ph._element)
caption_para(find("Figure 1. Entity-Relationship Diagram"), fcap("Entity-Relationship Diagram of the Proposed System"))
find("Figure 1.").paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

h = find("1.7 Entity and Relationship Summary")
c = Cursor(h)
c.para("Table 4 summarises each relationship, its cardinality and the rule it represents.")
caption_para(find("Table 4. Entity and Relationship Summary"), tcap("Entity and Relationship Summary"))
fill(tbl_after(find("Table 4. Entity and Relationship Summary")), [
    ["BELONGS_TO (Service – Service_Category)", "N : 1, total on Service", "Every service belongs to exactly one category."],
    ["REQUIRES (Service – Skill)", "N : 1, total on Service", "Each service needs one skill; basis of the skill-match rule."],
    ["HAS_SKILL (Staff – Skill)", "M : N; proficiency_level", "A staff member may hold many skills, rated 1–5."],
    ["WORKS_ON (Staff – Staff_Schedule)", "1 : N, weak entity", "Weekly shift per working day; validates appointment times."],
    ["BOOKS (Customer – Appointment)", "1 : N", "A visit belongs to one customer on one date."],
    ["INCLUDES (Appointment – Appointment_Service)", "1 : N, weak entity", "A visit contains one or more timed services."],
    ["FOR_SERVICE / PERFORMED_BY", "N : 1 each", "Each booked service line has one service and one staff member."],
    ["CONTAINS (Package – Service)", "M : N; sessions_included", "Defines what a prepaid package offers."],
    ["BUYS / OF_PACKAGE (Customer – Customer_Package – Package)", "1 : N, N : 1", "A customer's purchased package with validity."],
    ["REDEEMS (Appointment_Service – Customer_Package)", "N : 1, optional", "A service line may consume one package session."],
    ["SUBSCRIBES (Customer – Membership_Plan)", "M : N; start_date, end_date", "Membership gives a discount on bills."],
    ["USES_PRODUCT (Appointment_Service – Product)", "M : N; quantity_used", "Product consumed by a performed service."],
    ["BILLED_AS (Appointment – Bill)", "1 : 1", "One bill per completed visit."],
    ["SETTLED_BY (Bill – Payment)", "1 : N, weak entity", "A bill may be paid in several parts."],
], size=10)

# =====================================================================
# 4. Chapter 2
# =====================================================================
h = find("2.1 Relational Schema")
c = Cursor(h)
c.para("The ER model was mapped to relations using the standard rules of the relational model [3]: each strong entity became a table "
       "with a surrogate primary key, weak entities received the owner's key as a foreign key, 1:N relationships became foreign keys on "
       "the N side, and every M:N relationship became its own table (staff_skill, package_item, customer_membership, product_usage). "
       "Table 5 lists the 18 relations and Figure 2 shows how they are linked.")
caption_para(find("Table 5. Relational Schema"), tcap("Relational Schema"))
schema = [
    ("service_category", "category_id (PK), category_name, description"),
    ("skill", "skill_id (PK), skill_name"),
    ("service", "service_id (PK), category_id (FK), required_skill_id (FK), service_name, duration_min, price, is_active"),
    ("customer", "customer_id (PK), first_name, last_name, phone, email, gender, date_of_birth, registered_on"),
    ("staff", "staff_id (PK), full_name, phone, email, designation, hire_date, status"),
    ("staff_skill", "staff_id (PK, FK), skill_id (PK, FK), proficiency_level"),
    ("staff_schedule", "schedule_id (PK), staff_id (FK), day_of_week, shift_start, shift_end"),
    ("membership_plan", "plan_id (PK), plan_name, annual_fee, discount_pct"),
    ("customer_membership", "membership_id (PK), customer_id (FK), plan_id (FK), start_date, end_date"),
    ("package", "package_id (PK), package_name, price, validity_days, is_active"),
    ("package_item", "package_id (PK, FK), service_id (PK, FK), sessions_included"),
    ("customer_package", "customer_package_id (PK), customer_id (FK), package_id (FK), purchase_date, expiry_date, amount_paid, status"),
    ("appointment", "appointment_id (PK), customer_id (FK), appointment_date, status, booked_at, notes"),
    ("appointment_service", "appt_service_id (PK), appointment_id (FK), service_id (FK), staff_id (FK), start_time, end_time, price_charged, customer_package_id (FK)"),
    ("product", "product_id (PK), product_name, brand, unit, unit_cost, stock_qty, reorder_level"),
    ("product_usage", "usage_id (PK), appt_service_id (FK), product_id (FK), quantity_used, issued_at"),
    ("bill", "bill_id (PK), appointment_id (FK, UNIQUE), bill_date, subtotal, discount_amount, tax_amount, total_amount (generated)"),
    ("payment", "payment_id (PK), bill_id (FK), amount, method, paid_at, reference_no"),
]
fill(tbl_after(find("Table 5. Relational Schema")), [[i + 1, n, a] for i, (n, a) in enumerate(schema)], size=10,
     header=["S.No.", "Table Name", "Attributes (PK / FK)"])
t5 = tbl_after(find("Table 5. Relational Schema"))
set_widths(t5, [0.6, 1.8, 3.9])
c = Cursor(t5._tbl)
c.para("", spacing=1.0, after=2)
c.image(os.path.join(ROOT, "docs", "schema_diagram.png"), 6.0, max_h_in=6.6)
c.caption(fcap("Relational Schema Diagram (foreign keys point to referenced primary keys)"))

h = find("2.2 Keys and Integrity Constraints")
c = Cursor(h)
c.para("Table 6 lists the keys and constraints of every table. In total the schema declares 18 primary keys, 20 foreign keys, 12 UNIQUE "
       "constraints, 35 CHECK constraints, 17 DEFAULT values and 88 NOT NULL columns. Foreign keys use ON DELETE RESTRICT for history "
       "that must not be lost (a customer with appointments cannot be deleted), CASCADE for dependent detail rows (deleting a staff "
       "member removes his or her schedule and skills) and SET NULL for the optional package link.")
caption_para(find("Table 6. Keys and Integrity Constraints"), tcap("Keys and Integrity Constraints"))
keys = [
    ["service_category", "PK; UNIQUE", "category_id; category_name", "Each category listed once"],
    ["skill", "PK; UNIQUE", "skill_id; skill_name", "Each skill listed once"],
    ["service", "PK; FK; UNIQUE", "service_id; category_id, required_skill_id; service_name", "Service belongs to a category and needs a skill"],
    ["service", "CHECK; DEFAULT", "duration_min 10–300, price > 0; is_active = 1", "Realistic duration and price"],
    ["customer", "PK; UNIQUE; NOT NULL", "customer_id; phone, email; first_name, last_name, phone", "No duplicate customers"],
    ["customer", "CHECK; DEFAULT", "phone ^[6-9][0-9]{9}$, email pattern, gender F/M/O; registered_on = now", "Valid Indian mobile number"],
    ["staff", "PK; UNIQUE; CHECK; DEFAULT", "staff_id; phone, email; status in (ACTIVE, ON_LEAVE, INACTIVE); status = ACTIVE", "Only active staff can be booked"],
    ["staff_skill", "PK; FK; CHECK; DEFAULT", "(staff_id, skill_id); → staff CASCADE, → skill; level 1–5; 3", "Skill match source"],
    ["staff_schedule", "PK; FK; UNIQUE; CHECK", "schedule_id; staff_id; (staff_id, day_of_week); day 1–7, end > start, 09:00–21:00", "One shift per staff per weekday"],
    ["membership_plan", "PK; UNIQUE; CHECK", "plan_id; plan_name; fee ≥ 0, discount 0–50%", "Bounded discounts"],
    ["customer_membership", "PK; FK; CHECK", "membership_id; customer_id, plan_id; end_date > start_date", "Valid membership period"],
    ["package", "PK; UNIQUE; CHECK", "package_id; package_name; price > 0, validity 7–730 days", "Valid packages"],
    ["package_item", "PK; FK; CHECK", "(package_id, service_id); sessions 1–50", "Package-session limit source"],
    ["customer_package", "PK; FK; CHECK; DEFAULT", "customer_package_id; customer_id, package_id; expiry > purchase, status list; ACTIVE", "Package validity"],
    ["appointment", "PK; FK; CHECK; DEFAULT", "appointment_id; customer_id (RESTRICT); status list; BOOKED, booked_at = now", "Visit lifecycle"],
    ["appointment_service", "PK; FK; CHECK", "appt_service_id; appointment (CASCADE), service, staff, customer_package (SET NULL); end > start, 09:00–21:00, price ≥ 0", "Valid appointment times"],
    ["appointment_service", "TRIGGER", "trg_appt_service_bi / _bu → sp_validate_appt_service", "No overlap, skill match, shift, duration, package limit"],
    ["product", "PK; UNIQUE; CHECK; DEFAULT", "product_id; product_name; cost ≥ 0, stock ≥ 0, unit ml/g/pcs; unit = ml, stock = 0", "Stock never negative"],
    ["product_usage", "PK; FK; CHECK; TRIGGER", "usage_id; appt_service_id, product_id; quantity > 0; trg_product_usage_bi", "Issue only available stock"],
    ["bill", "PK; FK + UNIQUE; CHECK; TRIGGER", "bill_id; appointment_id; discount ≤ subtotal, tax ≥ 0; trg_bill_bi", "One bill per completed visit"],
    ["payment", "PK; FK; CHECK; DEFAULT; TRIGGER", "payment_id; bill_id; amount > 0, method list; UPI, paid_at = now; trg_payment_bi", "Payment limit"],
]
fill(tbl_after(find("Table 6. Keys and Integrity Constraints")), keys, size=9.5)

h = find("2.3 Functional Dependencies")
c = Cursor(h)
c.para("The important functional dependencies are listed below. In every case the determinant is a candidate key of its relation, which is the condition for BCNF.")
c.code("""customer_id             -> first_name, last_name, phone, email, gender,
                           date_of_birth, registered_on
phone                   -> customer_id                         (alternate key)
category_id             -> category_name, description
skill_id                -> skill_name
service_id              -> category_id, required_skill_id, service_name,
                           duration_min, price, is_active
staff_id                -> full_name, phone, email, designation, hire_date, status
{staff_id, skill_id}    -> proficiency_level
schedule_id             -> staff_id, day_of_week, shift_start, shift_end
{staff_id, day_of_week} -> schedule_id, shift_start, shift_end (alternate key)
plan_id                 -> plan_name, annual_fee, discount_pct
membership_id           -> customer_id, plan_id, start_date, end_date
package_id              -> package_name, price, validity_days, is_active
{package_id,service_id} -> sessions_included
customer_package_id     -> customer_id, package_id, purchase_date, expiry_date,
                           amount_paid, status
appointment_id          -> customer_id, appointment_date, status, booked_at, notes
appt_service_id         -> appointment_id, service_id, staff_id, start_time,
                           end_time, price_charged, customer_package_id
product_id              -> product_name, brand, unit, unit_cost, stock_qty,
                           reorder_level
usage_id                -> appt_service_id, product_id, quantity_used, issued_at
bill_id                 -> appointment_id, bill_date, subtotal, discount_amount,
                           tax_amount
appointment_id          -> bill_id                             (1:1, UNIQUE)
payment_id              -> bill_id, amount, method, paid_at, reference_no""")

h = find("2.4 Normalization")
set_text(h, "2.4 Normalization up to Third Normal Form (3NF)", size=14, bold=True)
c = Cursor(h)
c.para("Normalization was carried out on the paper booking slip, which in unnormalized form holds the customer's details, the date, a "
       "repeating group of {service, staff, staff skills, time, price}, the package used, the bill and a repeating group of payments [4].")
c.bullets([
    "**1NF:** repeating groups were removed – one row per service per visit (appointment_service), one row per payment (payment) and one row per staff skill (staff_skill); every attribute became atomic.",
    "**2NF:** partial dependencies on composite keys were removed – service_name, duration and price depend only on service_id, and customer details only on customer_id, so they moved to service and customer.",
    "**3NF:** transitive dependencies were removed – category_name depends on category_id, skill_name on skill_id and the membership discount on plan_id, so service_category, skill and membership_plan were split out.",
])
c.para("Three attributes look derivable but are stored deliberately as historical snapshots: price_charged and end_time in "
       "appointment_service (service price and duration can change after booking) and expiry_date in customer_package (package "
       "validity can change after purchase). Over time these are not functionally determined by the current service or package, so "
       "they do not violate 3NF. bill.total_amount is a generated column, and amount paid, balance and payment status are not stored "
       "at all but computed in the view v_bill_summary. Table 7 gives the final status.")
caption_para(find("Table 7. Normalization Status up to 3NF"), tcap("Normalization Status up to 3NF"))
nf = [
    ["service_category, skill", "✓", "✓", "✓", "✓", "Single-attribute PK; names are alternate keys"],
    ["service", "✓", "✓", "✓", "✓", "Category and skill names moved out (3NF)"],
    ["customer, staff", "✓", "✓", "✓", "✓", "Phone and email are alternate keys"],
    ["staff_skill", "✓", "✓", "✓", "✓", "From staff's repeating skills (1NF); composite PK"],
    ["staff_schedule", "✓", "✓", "✓", "✓", "UNIQUE(staff_id, day_of_week) candidate key"],
    ["membership_plan, customer_membership", "✓", "✓", "✓", "✓", "Discount depends on plan only (3NF split)"],
    ["package, package_item", "✓", "✓", "✓", "✓", "M:N decomposed; sessions depend on full key"],
    ["customer_package", "✓", "✓", "✓", "✓", "expiry_date frozen at purchase"],
    ["appointment", "✓", "✓", "✓", "✓", "Header of the booking slip"],
    ["appointment_service", "✓", "✓", "✓", "✓", "Repeating service group (1NF); price/end time snapshots"],
    ["product, product_usage", "✓", "✓", "✓", "✓", "Usage separated from stock master"],
    ["bill, payment", "✓", "✓", "✓", "✓", "Repeating payments split (1NF); total generated"],
]
fill(tbl_after(find("Table 7. Normalization Status up to 3NF")), nf, size=10)

# data dictionary from information_schema
h = find("2.5 Data Dictionary")
c = Cursor(h)
c.para("Table 8 is the data dictionary for all 18 tables, generated from the implemented schema.")
caption_para(find("Table 8. Data Dictionary"), tcap("Data Dictionary"))
DESC = {
    "category_id": "Category identifier", "category_name": "Name of the category", "description": "Short description",
    "skill_id": "Skill identifier", "skill_name": "Name of the skill", "service_id": "Service identifier",
    "required_skill_id": "Skill needed to perform the service", "service_name": "Service name", "duration_min": "Duration in minutes",
    "price": "Price in INR", "is_active": "1 = available for sale", "customer_id": "Customer identifier", "first_name": "First name",
    "last_name": "Last name", "phone": "10-digit mobile number", "email": "Email address", "gender": "F / M / O",
    "date_of_birth": "Date of birth", "registered_on": "Registration timestamp", "staff_id": "Staff identifier", "full_name": "Full name",
    "designation": "Job title", "hire_date": "Date of joining", "status": "Current status", "proficiency_level": "Skill level 1–5",
    "schedule_id": "Schedule row identifier", "day_of_week": "1 = Sunday … 7 = Saturday", "shift_start": "Shift start time",
    "shift_end": "Shift end time", "plan_id": "Plan identifier", "plan_name": "Silver / Gold / Platinum", "annual_fee": "Fee per year (INR)",
    "discount_pct": "Discount on bills (%)", "membership_id": "Membership identifier", "start_date": "Membership start",
    "end_date": "Membership end", "package_id": "Package identifier", "package_name": "Package name", "validity_days": "Validity after purchase",
    "sessions_included": "Sessions of the service in the package", "customer_package_id": "Purchased package identifier",
    "purchase_date": "Date of purchase", "expiry_date": "Last date to redeem", "amount_paid": "Price paid (INR)",
    "appointment_id": "Visit identifier", "appointment_date": "Date of visit", "booked_at": "When the booking was made",
    "notes": "Optional remarks", "appt_service_id": "Booked service line identifier", "start_time": "Slot start", "end_time": "Slot end",
    "price_charged": "Price at booking (0 if from package)", "product_id": "Product identifier", "product_name": "Product name",
    "brand": "Brand", "unit": "ml / g / pcs", "unit_cost": "Cost per unit (INR)", "stock_qty": "Quantity in stock",
    "reorder_level": "Re-order threshold", "usage_id": "Usage identifier", "quantity_used": "Quantity issued", "issued_at": "Issue timestamp",
    "bill_id": "Bill identifier", "bill_date": "Bill date", "subtotal": "Sum of service prices", "discount_amount": "Membership discount",
    "tax_amount": "GST (18%)", "total_amount": "subtotal − discount + tax (generated)", "payment_id": "Payment identifier",
    "amount": "Amount paid", "method": "CASH / CARD / UPI / WALLET", "paid_at": "Payment timestamp", "reference_no": "UPI / card reference",
}
DESC_T = {("customer_package", "status"): "ACTIVE / EXHAUSTED / EXPIRED / CANCELLED", ("appointment", "status"): "BOOKED / COMPLETED / CANCELLED / NO_SHOW",
          ("staff", "status"): "ACTIVE / ON_LEAVE / INACTIVE", ("package", "price"): "Package price (INR)"}
fks = {(t, c): rt for t, c, rt in q("select table_name, column_name, referenced_table_name from information_schema.key_column_usage where table_schema='salon_spa_db' and referenced_table_name is not null")}
uniq = {(t, c) for t, c in q("select k.table_name, k.column_name from information_schema.table_constraints tc join information_schema.key_column_usage k using(constraint_schema, constraint_name, table_name) where tc.table_schema='salon_spa_db' and tc.constraint_type='UNIQUE'")}
order = [s[0] for s in schema]
cols = q("select table_name, column_name, column_type, column_key, is_nullable, column_default, extra from information_schema.columns where table_schema='salon_spa_db' and table_name in (%s) order by field(table_name,%s), ordinal_position" % (",".join("'%s'" % o for o in order), ",".join("'%s'" % o for o in order)))
dd = []
for t, col, ctype, ckey, nul, cdef, extra in cols:
    k = []
    if ckey == "PRI":
        k.append("PK")
    if (t, col) in fks:
        k.append(f"FK → {fks[(t, col)]}")
    if (t, col) in uniq and ckey != "PRI":
        k.append("UNIQUE")
    if nul == "NO" and ckey != "PRI":
        k.append("NOT NULL")
    if cdef is not None:
        k.append(f"DEFAULT {cdef}")
    if "auto_increment" in extra:
        k.append("AUTO_INCREMENT")
    if "STORED GENERATED" in extra.upper() or "VIRTUAL GENERATED" in extra.upper():
        k.append("GENERATED")
    dd.append([t, col, ctype.upper(), ", ".join(k), DESC_T.get((t, col), DESC.get(col, ""))])
ddt = tbl_after(find(f"Table {TCOUNT[0]}. Data Dictionary"))
fill(ddt, dd, size=9)

h = find("2.6 Implementation of Logical Design")
c = Cursor(h)
c.para("The design was implemented in MySQL 8.0, whose reference manual was followed for CHECK constraints, generated columns, "
       "triggers and SIGNAL [5]. The scripts are split into six files (Appendix A) and also run unchanged on MariaDB 10.11. Table 9 "
       "summarises the implementation environment.")
caption_para(find("Table 9. Database Implementation Environment"), tcap("Database Implementation Environment"))
cnt = dict(q("select 'x', 1"))
counts = {t: q(f"select count(*) from {t}")[0][0] for t in order}
total_rows = sum(counts.values())
envt = tbl_after(find(f"Table {TCOUNT[0]}. Database Implementation Environment"))
fill(envt, [
    ["DBMS", "MySQL Community Server (InnoDB storage engine)"],
    ["DBMS Version", "8.0 (tested on 8.0.46; also verified on MariaDB 10.11)"],
    ["Number of Tables", "18 tables, 7 views, 5 triggers, 1 stored procedure, 7 secondary indexes"],
    ["Sample Data", f"{total_rows:,} rows: 40 customers, 10 staff, 22 services, 603 appointments with 892 service lines, 674 product issues, 427 bills, 419 payments (Aug–Oct 2026)"],
], size=10.5)
c = Cursor(envt._tbl)
c.para("A representative CREATE TABLE statement, for the central appointment_service relation, is shown below. Every constraint is named so that error messages identify the rule that failed.", after=4)
c.code("""CREATE TABLE appointment_service (
    appt_service_id     INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id      INT          NOT NULL,
    service_id          INT          NOT NULL,
    staff_id            INT          NOT NULL,
    start_time          TIME         NOT NULL,
    end_time            TIME         NOT NULL,
    price_charged       DECIMAL(8,2) NOT NULL,
    customer_package_id INT          NULL,
    CONSTRAINT fk_as_appt    FOREIGN KEY (appointment_id)
        REFERENCES appointment(appointment_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_as_service FOREIGN KEY (service_id) REFERENCES service(service_id),
    CONSTRAINT fk_as_staff   FOREIGN KEY (staff_id)   REFERENCES staff(staff_id),
    CONSTRAINT fk_as_cpkg    FOREIGN KEY (customer_package_id)
        REFERENCES customer_package(customer_package_id) ON DELETE SET NULL,
    CONSTRAINT chk_as_order CHECK (end_time > start_time),
    CONSTRAINT chk_as_hours CHECK (start_time >= '09:00:00'
                                   AND end_time <= '21:00:00'),
    CONSTRAINT chk_as_price CHECK (price_charged >= 0)
) ENGINE=InnoDB;""")
c.para("The rules that depend on other rows are checked in one stored procedure called by the BEFORE INSERT and BEFORE UPDATE triggers. The overlap check uses the interval-overlap condition (start A < end B and start B < end A):", after=4)
c.code("""SELECT COUNT(*) INTO v_cnt
  FROM appointment_service s
  JOIN appointment a ON a.appointment_id = s.appointment_id
 WHERE s.staff_id = p_staff_id AND a.appointment_date = v_date
   AND a.status NOT IN ('CANCELLED','NO_SHOW')
   AND s.appt_service_id <> p_self_id          -- ignore the row being updated
   AND s.start_time < p_end AND p_start < s.end_time;
IF v_cnt > 0 THEN
   SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT =
        'Staff conflict: staff member already has an overlapping appointment';
END IF;""")
c.para("Sample data was produced by a seeded Python generator that schedules every visit with the same rules, and it was loaded through the triggers, so every stored row is valid. Table 10 shows the number of rows per table and Table 11 shows representative records.", after=4)
rows = [[t, counts[t]] for t in order]
half = (len(rows) + 1) // 2
rows2 = [[a[0], a[1], b[0] if b else "", b[1] if b else ""] for a, b in zip(rows[:half], rows[half:] + [None])]
c.caption(tcap("Sample Data Summary"))
tsd = table_after(c, tbl_after(find("Table 11. Application Module-to-Database Mapping")), rows2, ["Table", "Rows", "Table", "Rows"], size=10)
set_widths(tsd, [2.1, 1.0, 2.1, 1.0])
c.para("", spacing=1.0, after=2)
c.caption(tcap("Representative Records from v_appointment_details"))
recs = q("select appointment_date, time_format(start_time,'%H:%i'), customer_name, service_name, staff_name, price_charged, status from v_appointment_details where appointment_date='2026-10-05' order by start_time limit 6")
tgrid = d.add_table(rows=1, cols=7)
tgrid.style = d.tables[5].style
for cc_, hh in zip(tgrid.rows[0].cells, ["Date", "Start", "Customer", "Service", "Staff", "Price ₹", "Status"]):
    cell_text(cc_, hh, size=9.5, bold=True, align="center")
    tcPr = cc_._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "DEEAF6"); tcPr.append(shd)
for r in recs:
    cells_ = tgrid.add_row().cells
    for cc_, v in zip(cells_, [str(r[0]), r[1], r[2], r[3], r[4], f"{r[5]:.0f}", r[6]]):
        cell_text(cc_, v, size=9.5)
set_widths(tgrid, [0.95, 0.55, 1.2, 1.45, 1.15, 0.6, 0.95])
tgrid.alignment = 1
c.put(tgrid)

# =====================================================================
# 5. Chapter 3
# =====================================================================
h = find("3.1 Application Overview")
c = Cursor(h)
c.para("The application, branded “Glow & Grace Salon Manager” for the demonstration, is a browser-based Python program used at the "
       "front desk by the receptionist and by the salon manager. It has nine screens grouped as Front desk (Dashboard, Customers, "
       "Book Appointment, Manage Appointments), Operations (Packages & Memberships, Products & Stock, Billing & Payments, Staff & "
       "Services) and Insights (Reports). Every screen reads and writes the tables and views designed in Chapter 2 through a single "
       "data-access module; there is no static data in the program. Input format is validated in Python before the database is "
       "called, and all business rules are enforced again by the database, whose error messages are shown to the user unchanged.")
remove(find("[Application overview")._element)

caption_para(find("Table 10. Application Development Environment"), tcap("Application Development Environment"))
fill(tbl_after(find(f"Table {TCOUNT[0]}. Application Development Environment")), [
    ["Programming Language", "Python 3.11+"],
    ["DBMS", "MySQL 8.0"],
    ["IDE / Framework / GUI Toolkit", "VS Code; Streamlit (browser-based GUI written in Python) [7]; pandas for tabular data"],
    ["Database Connector / Driver", "mysql-connector-python (official Oracle driver) [6]; parameterised queries, explicit transactions"],
    ["Operating Environment", "Linux (Arch Linux) / Windows; runs locally at http://localhost:8501"],
    ["Repository Link", REPO],
], size=10.5)
h = find("3.2 Development Environment and Database Connectivity")
c = Cursor(h)
c.para("Connectivity is handled by db.py. It opens a connection with autocommit disabled, runs every statement with %s parameters, "
       "and exposes a transaction() context manager that issues START TRANSACTION, COMMIT on success and ROLLBACK on any error. "
       "MySQL errors are translated into readable messages: SQLSTATE 45000 messages raised by triggers are passed through, duplicate "
       "keys, foreign-key violations and CHECK failures get their own wording. Connection settings are read from environment "
       "variables (SALON_DB_HOST, SALON_DB_USER, SALON_DB_PASSWORD, SALON_DB_NAME). Table 12 lists the environment.")

Cursor(find("3.3 Application Modules and Database Mapping")).para("Table 13 maps each screen of the application to the tables and views it uses.")
caption_para(find("Table 11. Application Module-to-Database Mapping"), tcap("Application Module-to-Database Mapping"))
fill(tbl_after(find(f"Table {TCOUNT[0]}. Application Module-to-Database Mapping")), [
    ["Dashboard", "Daily snapshot", "appointment, bill, v_appointment_details, v_bill_summary, v_product_usage", "Read, aggregate"],
    ["Customers", "Registration and profile", "customer, customer_membership", "Create, search, update, delete"],
    ["Book Appointment", "Multi-service booking", "appointment, appointment_service, service, staff_skill, staff_schedule, v_package_balance", "Insert in one transaction"],
    ["Manage Appointments", "Lifecycle and reschedule", "appointment, appointment_service", "Search, update status/time/staff"],
    ["Packages & Memberships", "Sell and track", "package, package_item, customer_package, membership_plan, customer_membership", "Insert, read balances"],
    ["Products & Stock", "Issue and restock", "product, product_usage", "Insert usage, update stock"],
    ["Billing & Payments", "Bill and settle", "bill, payment, v_bill_summary", "Insert bill, insert payments"],
    ["Staff & Services", "Masters", "staff, skill, staff_skill, staff_schedule, service", "Read, update status/price, upsert skill"],
    ["Reports", "Six reports", "seven views", "Read, aggregate, CSV export"],
], size=9.5)

Cursor(find("3.4 CRUD Operations")).para("Table 14 shows where each create, read, update and delete operation is performed.")
caption_para(find("Table 12. CRUD Operations"), tcap("CRUD Operations"))
fill(tbl_after(find(f"Table {TCOUNT[0]}. CRUD Operations")), [
    ["Create", "Register customer; book appointment; sell package; enrol membership; issue product; add product; generate bill; record payment", "customer, appointment, appointment_service, customer_package, customer_membership, product_usage, product, bill, payment", "Figures 4, 5, 9, 10"],
    ["Read / Search", "Customer search by name/phone/email; appointment search by date, status, customer; bill viewer; reports", "all tables and views", "Figures 3, 12, 13"],
    ["Update", "Edit customer; complete/cancel/no-show; reschedule time or staff; restock; change service price; staff status", "customer, appointment, appointment_service, product, service, staff", "Figures 7–8"],
    ["Delete / Controlled Removal", "Delete customer only after confirmation and only if no history (FK RESTRICT); remove a line from the booking cart before saving", "customer", "Test case TC-16"],
], size=9.5)

h = find("3.5 Business Rules, Validation and Error Handling")
c = Cursor(h)
c.para("Validation works in two layers. The application checks input format before contacting the database (names, a 10-digit mobile "
       "number starting with 6–9, email pattern, non-future birth date, positive amounts, a reference number for UPI and card). It also "
       "prevents most rule violations by design: time-slot lists only offer slots that end by 21:00, and the staff list shows only "
       "staff with the right skill who are on shift and free. The database is the second and final layer – triggers and constraints "
       "reject anything that still breaks a rule, for example when the staff filter is switched off or two receptionists book the same "
       "slot at once. All SQL uses bound parameters, which prevents SQL injection [8]. Destructive actions need a confirmation tick, and "
       "multi-statement operations run in a transaction that is rolled back on error. Table 15 lists the rules.")
caption_para(find("Table 13. Business Rules, Validation and Error Handling"), tcap("Business Rules, Validation and Error Handling"))
fill(tbl_after(find(f"Table {TCOUNT[0]}. Business Rules, Validation and Error Handling")), [
    ["No overlapping staff appointments", "Staff list excludes busy staff; trigger sp_validate_appt_service (insert and update)", "“Staff conflict: staff member already has an overlapping appointment” (Figure 8)"],
    ["Skill match", "Staff list joined with staff_skill; trigger re-check", "“Skill mismatch: staff member does not have the skill required for this service” (Figure 6)"],
    ["Valid appointment times", "Slot list 09:00–21:00 in 15-min steps; CHECK chk_as_hours; trigger checks duration and staff shift", "“Invalid time slot: this service takes 30 minutes” / “not on shift”"],
    ["Package-session limit", "Redeem option shown only with sessions left; trigger checks owner, validity, coverage, count", "“Package session limit reached for this service”"],
    ["Payment limit", "Amount defaults to balance; trigger trg_payment_bi", "“Payment exceeds balance: outstanding amount is Rs. …” (Figure 11)"],
    ["Stock and billing rules", "trg_product_usage_bi, trg_bill_bi, CHECK stock_qty ≥ 0", "“Insufficient stock: only 13.00 available”; “Bill can be generated only for a completed appointment”"],
    ["Input format and uniqueness", "Python regex checks; CHECK chk_customer_phone; UNIQUE phone/email", "“Phone must be a 10-digit Indian mobile number…” (Figure 4); “Duplicate value: this phone already exists.”"],
], size=9.5)

Cursor(find("3.6 Reports and Database Operations")).para("The six required reports, the SQL concepts behind them and their output are listed in Table 16. Each report can be exported as CSV.")
caption_para(find("Table 14. Reports and Database Operations"), tcap("Reports and Database Operations"))
fill(tbl_after(find(f"Table {TCOUNT[0]}. Reports and Database Operations")), [
    ["Appointments", "v_appointment_details (5-table join); COUNT(DISTINCT CASE …) per day; correlated subquery for last visit", "Daily totals by status, line chart, CSV"],
    ["Staff utilization", "v_staff_utilization: derived tables, CROSS JOIN, SUM of minutes ÷ shift minutes", "Utilization % per staff (Figure 12)"],
    ["Service popularity", "v_service_popularity: LEFT JOIN with IN-subquery, GROUP BY; category revenue share", "Bookings, package use and revenue per service"],
    ["Package balances", "v_package_balance: correlated subquery counting sessions used", "Included / used / left per customer package"],
    ["Product use", "v_product_usage: SUM, CASE re-order flag; average material cost per service", "Consumption cost and re-order alerts"],
    ["Revenue", "v_monthly_revenue, v_bill_summary: GROUP BY month, billed vs collected, outstanding", "Monthly bar chart and dues (Figure 13)"],
], size=9.5)

# 3.7 screens
h = find("3.7 Application Screens")
for p in paras():
    if p.text.strip().startswith("[Insert application screenshot") or re.match(r"Figure [2-5]\. \[Application", p.text.strip()):
        remove(p._element)
c = Cursor(h)
c.para("Figures 3 to 13 show the main screens running on the sample database.")
SCREENS = [
    ("01_dashboard.png", "Dashboard with daily schedule and key figures"),
    ("02_register_validation.png", "Customer registration rejecting an invalid phone number and email"),
    ("05_booking_skilled_staff.png", "Booking screen offering only skilled, on-shift and free staff"),
    ("08_booking_rejected_skill.png", "Booking rejected by the database for a skill mismatch and rolled back"),
    ("10_marked_completed.png", "Manage Appointments – appointment marked completed"),
    ("28_reschedule_conflict.png", "Reschedule rejected for an overlapping staff appointment"),
    ("30_package_redeemed_cart.png", "Package session redeemed at no charge during booking"),
    ("31_member_discount_bill.png", "Bill preview with Gold membership discount and GST"),
    ("13_payment_over_limit.png", "Payment above the outstanding balance rejected"),
    ("23_report_staff_utilisation.png", "Staff utilization report"),
    ("27_report_revenue.png", "Monthly revenue report – billed vs collected"),
]
for f, title in SCREENS:
    c.image(os.path.join(SHOT, f), 5.6, max_h_in=4.0)
    c.caption(fcap(title))

# 3.8 testing
h = find("3.8 Testing and Results")
h.style = d.styles["Heading 2"]
set_text(h, "3.8 Testing and Results", size=14, bold=True)
h.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
c = Cursor(h)
c.para("Testing combined a database-level script (database/06_test_business_rules.sql, run in a transaction that is rolled back) and "
       "manual tests through the application. Table 17 lists the main positive and negative cases with the observed results.")
caption_para(find("Table 15. Test Cases"), tcap("Test Cases"))
tests = [
    ["TC-01", "Booking (DB)", "Valid Swedish massage 13:00–14:00 for Rohan", "Row inserted", "1 row inserted", "Pass"],
    ["TC-02", "Overlap rule", "Second booking for Rohan 13:30–14:30", "Rejected", "Staff conflict error", "Pass"],
    ["TC-03", "Overlap rule", "Back-to-back booking 14:00–15:00", "Accepted", "Inserted", "Pass"],
    ["TC-04", "Skill match", "Bridal makeup assigned to the barber", "Rejected", "Skill mismatch error", "Pass"],
    ["TC-05", "Valid times", "30-min haircut booked for 45 min", "Rejected", "Invalid time slot error", "Pass"],
    ["TC-06", "Valid times", "Massage at 10:00, before the 12:00 shift", "Rejected", "Not on shift error", "Pass"],
    ["TC-07", "Package limit", "Redeem another customer's package", "Rejected", "Package does not belong error", "Pass"],
    ["TC-08", "Package limit", "Redeem 4th of 4, then a 5th manicure", "4th at ₹0; 5th rejected", "₹0.00, then limit error", "Pass"],
    ["TC-09", "Billing rule", "Bill a BOOKED appointment", "Rejected", "Completed-only error", "Pass"],
    ["TC-10", "Payment limit", "Pay balance + 100, then exact balance", "First rejected, then PAID", "Error, then status PAID", "Pass"],
    ["TC-11", "Stock rule", "Issue 500 gold facial kits", "Rejected", "Insufficient stock error", "Pass"],
    ["TC-12", "Registration (app)", "Phone 12345, email meera.iyer@gmail", "Two validation errors", "Both errors shown (Fig. 4)", "Pass"],
    ["TC-13", "Booking (app)", "Facial 17:00 + threading 18:00 for new customer", "Booked with skilled staff", "Confirmation shown", "Pass"],
    ["TC-14", "Reschedule (app)", "Move threading to 15:30 onto a facial slot", "Rejected", "Staff conflict (Fig. 8)", "Pass"],
    ["TC-15", "Billing (app)", "₹600 haircut for Gold member", "₹60 off, GST ₹97.20, total ₹637.20", "As expected (Fig. 10)", "Pass"],
    ["TC-16", "Delete (app)", "Delete customer who has appointments", "Blocked by FK", "“Cannot delete …” message", "Pass"],
    ["TC-17", "Uniqueness", "Register a duplicate phone number", "Rejected", "Duplicate value message", "Pass"],
    ["TC-18", "Check constraint", "Discount larger than subtotal", "Rejected", "chk_bill_discount violated", "Pass"],
]
fill(tbl_after(find(f"Table {TCOUNT[0]}. Test Cases")), tests, size=9)
kr = find("[Key results and observations.]")
set_text(kr, "All 18 test cases produced the expected result. Every invalid operation was stopped by the database even when the "
         "application's own filters were bypassed, and multi-statement bookings were rolled back completely on error, so no partial "
         "data was left behind. Valid edge cases – such as back-to-back appointments and redeeming the last package session – were "
         "accepted. The application therefore uses the designed database correctly and enforces all of the important business rules.")
kr.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
kr.paragraph_format.line_spacing = 1.5

# =====================================================================
# 6. Chapter 4, references, appendices
# =====================================================================
for txt in ("CHAPTER 4", "CONCLUSION"):
    p = find(txt, exact=True)
    p.style = d.styles["Heading 1"]
    set_text(p, txt, size=16, bold=True)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
cp = find("[Conclusion")
set_text(cp, "This project replaced the error-prone paper appointment book of a salon and spa with a relational database and a Python "
         "application. Starting from the requirements, an ER model of 14 entities and 16 relationships was designed and converted into "
         "18 relations in Third Normal Form. The MySQL implementation uses 85 declarative constraints, five triggers, seven views and "
         "seven indexes, so that overlapping staff bookings, skill mismatches, invalid times, package over-use and over-payment are "
         "rejected by the database itself. The Streamlit application supports the full workflow from registration to payment and "
         "produces the six required reports.")
cp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
cp.paragraph_format.line_spacing = 1.5
c = Cursor(cp)
c.para("The main learning was that placing business rules inside the database, rather than only in the user interface, keeps the data "
       "correct no matter which program or person changes it, and that careful normalization made the reports simple to write as views.")
for p in paras():
    if p.text.strip().startswith("[Limitation"):
        remove(p._element)
c = Cursor(find("4.1 Limitations and Future Enhancements"))
c.bullets([
    "There is no login yet; role-based access for receptionist, manager and staff can be added with a user table and permissions.",
    "The design assumes one branch; adding branch_id to staff, appointments and stock would support a chain of salons.",
    "Appointment reminders, a customer self-booking portal and online payment links are not implemented.",
    "Staff utilization uses scheduled shift time only; leave and holidays could be modelled for more accurate utilization.",
])

refs = [
    "A. Silberschatz, H. F. Korth, and S. Sudarshan, Database System Concepts, 7th ed. New York, NY, USA: McGraw-Hill Education, 2020.",
    "P. P. Chen, “The entity-relationship model—Toward a unified view of data,” ACM Trans. Database Syst., vol. 1, no. 1, pp. 9–36, Mar. 1976, doi: 10.1145/320434.320440.",
    "E. F. Codd, “A relational model of data for large shared data banks,” Commun. ACM, vol. 13, no. 6, pp. 377–387, Jun. 1970, doi: 10.1145/362384.362685.",
    "R. Elmasri and S. B. Navathe, Fundamentals of Database Systems, 7th ed. Boston, MA, USA: Pearson, 2016.",
    "Oracle Corporation, MySQL 8.0 Reference Manual. Accessed: Oct. 8, 2026. [Online]. Available: https://dev.mysql.com/doc/refman/8.0/en/",
    "Oracle Corporation, MySQL Connector/Python Developer Guide. Accessed: Oct. 8, 2026. [Online]. Available: https://dev.mysql.com/doc/connector-python/en/",
    "Snowflake Inc., Streamlit Documentation. Accessed: Oct. 8, 2026. [Online]. Available: https://docs.streamlit.io/",
    "OWASP Foundation, “SQL injection prevention cheat sheet,” OWASP Cheat Sheet Series. Accessed: Oct. 8, 2026. [Online]. Available: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
]
rp = [p for p in paras() if p.text.strip().startswith("[Replace with an actual source")]
refs = [f"[{i + 1}] {r}" for i, r in enumerate(refs)]
for p in rp:
    pPr = p._element.pPr
    if pPr is not None and pPr.numPr is not None:
        pPr.remove(pPr.numPr)
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.first_line_indent = Inches(-0.4)
for p, r in zip(rp, refs):
    set_text(p, r, size=12)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
c = Cursor(rp[-1])
for r in refs[len(rp):]:
    p = copy.deepcopy(rp[-1]._element)
    c.put(p)
    set_text(P(p), r, size=12)

ap = find("[Database script / file reference]")
set_text(ap, f"The complete script is submitted in the repository folder database/ ({REPO}). Run the single file salon_spa_full.sql, or the parts in order:")
c = Cursor(ap)
c.bullets(["01_schema.sql – database, 18 tables, constraints and indexes (DDL)",
           "02_triggers.sql – validation procedure and five business-rule triggers",
           "03_sample_data.sql – sample data (DML), generated by generate_sample_data.py",
           "04_views.sql – seven reporting views",
           "05_queries.sql – 20 retrieval queries: joins, subqueries, aggregation, views",
           "06_test_business_rules.sql – 18 positive / negative rule tests (rolled back)"], size=11)
bp = find("[Source-code / repository reference]")
set_text(bp, f"Repository: {REPO}. The application is in the app/ folder: streamlit_app.py (entry point and navigation), db.py "
         "(connection, parameterised queries, transactions, error mapping), ui.py (validation and shared widgets) and views/ (one file per "
         "screen). Run: pip install -r requirements.txt, then streamlit run app/streamlit_app.py. The five-minute demonstration video "
         "link is in video/VIDEO_LINK.md.")
cp2 = find("[Additional supporting material]")
set_text(cp2, "Output of the business-rule test script on MySQL 8.0 (abridged):")
c = Cursor(cp2)
c.code("""TC-01 valid booking                                    rows_ok = 1
ERROR 1644 (45000): Staff conflict: staff member already has an overlapping appointment
ERROR 1644 (45000): Skill mismatch: staff member does not have the required skill
ERROR 1644 (45000): Invalid time slot: this service takes 30 minutes
ERROR 1644 (45000): Invalid time: staff member is not on shift for this slot
ERROR 1644 (45000): Package does not belong to this customer
TC-09 package redemption                               price_charged = 0.00
ERROR 1644 (45000): Package session limit reached for this service
ERROR 1644 (45000): Bill can be generated only for a completed appointment
ERROR 1644 (45000): Payment exceeds balance: outstanding amount is Rs. 1888.00
TC-13 settle bill                         payment_status = PAID, balance = 0.00
ERROR 1644 (45000): Insufficient stock: only 17.00 available
ERROR 3819 (HY000): Check constraint 'chk_customer_phone' is violated.
ERROR 1062 (23000): Duplicate entry '9374481727' for key 'customer.phone'
ERROR 1451 (23000): Cannot delete or update a parent row: a foreign key ... fails
ERROR 3819 (HY000): Check constraint 'chk_bill_discount' is violated.
All tests finished - transaction rolled back""")
c.para("Figure 14 is the full-page ER diagram (rotated) and Figure 15 the package-balance report.")
rot = os.path.join(ROOT, "report", "_er_rotated.png")
Image.open(os.path.join(ROOT, "docs", "er_diagram.png")).rotate(90, expand=True).save(rot)
pb = new_p(align="center", spacing=1.0, after=2)
pb.paragraph_format.page_break_before = True
pb.add_run().add_picture(rot, height=Inches(8.6))
c.put(pb)
c.caption(fcap("Full-page Entity-Relationship Diagram"))
c.image(os.path.join(SHOT, "25_report_package_balances.png"), 5.6, max_h_in=4.0)
c.caption(fcap("Package balances report"))

# =====================================================================
# 7. Headings: sizes, page breaks
# =====================================================================
NEWPAGE = ["ACKNOWLEDGEMENT", "UNDERTAKING", "TABLE OF CONTENTS", "LIST OF TABLES", "LIST OF FIGURES", "LIST OF ACRONYMS", "ABSTRACT",
           "CHAPTER 1", "CHAPTER 2", "CHAPTER 3", "CHAPTER 4", "REFERENCES", "APPENDICES"]
for p in paras():
    t = p.text.strip()
    if p.style.name == "Heading 1" and t:
        for r in p.runs:
            r.font.size = Pt(16); r.font.name = "Times New Roman"; r.font.bold = True
        if t in NEWPAGE:
            page_break_before(p)
            # remove any manual page break run left in the previous paragraph
    if p.style.name == "Heading 2" and t:
        for r in p.runs:
            r.font.size = Pt(14); r.font.name = "Times New Roman"; r.font.bold = True
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(12)
# strip manual page breaks (we use page_break_before)
for p in paras():
    for br in p._element.iter(qn("w:br")):
        if br.get(qn("w:type")) == "page":
            br.getparent().remove(br)
# keep the cover's own page break before acknowledgement handled by NEWPAGE

# =====================================================================
# 8. Lists of tables / figures and TOC (page numbers from pass 1)
# =====================================================================
def pg(key):
    return str(PAGES.get(key, ""))


fill(tbl_after(find("LIST OF TABLES", exact=True)), [[f"Table {n}", t, pg(f"Table {n}. {t}")] for n, t in TABLES], size=10.5)
fill(tbl_after(find("LIST OF FIGURES", exact=True)), [[f"Figure {n}", t, pg(f"Figure {n}. {t}")] for n, t in FIGURES], size=10.5)
toc = tbl_after(find("TABLE OF CONTENTS", exact=True))
for row in toc.rows[1:]:
    label = row.cells[0].text.strip()
    key = {"1. PROBLEM STATEMENT, SOLUTION STRATEGY AND ER DIAGRAM": "CHAPTER 1", "2. LOGICAL DATABASE DESIGN": "CHAPTER 2",
           "3. APPLICATION DEVELOPMENT USING LOGICAL DATABASE DESIGN": "CHAPTER 3", "4. CONCLUSION": "CHAPTER 4",
           "5. REFERENCES": "REFERENCES", "6. APPENDICES": "APPENDICES", "Abstract": "ABSTRACT"}.get(label, label)
    cell_text(row.cells[1], pg(key), size=11, align="center")

WIDTHS = {"Scope and Assumptions": [1.6, 4.67], "Proposed Solution Strategy": [1.7, 4.57], "Functional Requirements": [0.8, 4.4, 1.07],
          "Entity and Relationship Summary": [2.3, 1.7, 2.27], "Keys and Integrity Constraints": [1.35, 1.3, 2.2, 1.42],
          "Normalization Status up to 3NF": [2.0, 0.45, 0.45, 0.45, 0.5, 2.42], "Data Dictionary": [1.3, 1.35, 1.0, 1.4, 1.22],
          "Database Implementation Environment": [1.6, 4.67], "Application Development Environment": [1.8, 4.47],
          "Application Module-to-Database Mapping": [1.3, 1.2, 2.4, 1.37], "CRUD Operations": [1.0, 2.3, 2.0, 0.97],
          "Business Rules, Validation and Error Handling": [1.5, 2.3, 2.47], "Reports and Database Operations": [1.3, 3.0, 1.97],
          "Test Cases": [0.55, 1.0, 1.65, 1.2, 1.3, 0.57]}
for n, t in TABLES:
    if t in WIDTHS:
        set_widths(tbl_after(find(f"Table {n}. {t}")), WIDTHS[t])
set_widths(tbl_after(find("LIST OF TABLES", exact=True)), [0.9, 4.5, 0.87])
set_widths(tbl_after(find("LIST OF FIGURES", exact=True)), [0.9, 4.5, 0.87])
set_widths(tbl_after(find("LIST OF ACRONYMS", exact=True)), [1.5, 4.77])
json.dump({"tables": TABLES, "figures": FIGURES}, open(os.path.join(ROOT, "report", "_captions.json"), "w"))
d.core_properties.author = "Devyani Pawar"
d.core_properties.title = TITLE
d.save(OUT)
print("saved", OUT, "tables", len(TABLES), "figures", len(FIGURES))
