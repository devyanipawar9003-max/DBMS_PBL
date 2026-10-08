import json, subprocess, sys, re
pdf = sys.argv[1]; cap = json.load(open("_captions.json"))
n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
pages = [subprocess.run(["pdftotext", "-layout", "-f", str(i), "-l", str(i), pdf, "-"], capture_output=True, text=True).stdout for i in range(1, n + 1)]
norm = lambda s: re.sub(r"\s+", " ", s).strip()
lines = [[norm(l) for l in p.splitlines() if norm(l)] for p in pages]
out = {}
front = ["ACKNOWLEDGEMENT", "UNDERTAKING", "TABLE OF CONTENTS", "LIST OF TABLES", "LIST OF FIGURES", "LIST OF ACRONYMS", "ABSTRACT",
         "CHAPTER 1", "CHAPTER 2", "CHAPTER 3", "CHAPTER 4", "REFERENCES", "APPENDICES"]
for k in front:
    for i, L in enumerate(lines):
        if L and L[0] == k:
            out[k] = i + 1; break
start = out.get("ABSTRACT", 1)
subs = ["1.1 Problem Statement", "1.2 Objectives", "1.3 Scope and Assumptions", "1.4 Proposed Solution Strategy", "1.5 Functional Requirements",
        "1.6 Entity-Relationship Diagram (ERD)", "1.7 Entity and Relationship Summary", "2.1 Relational Schema", "2.2 Keys and Integrity Constraints",
        "2.3 Functional Dependencies", "2.4 Normalization up to Third Normal Form (3NF)", "2.5 Data Dictionary",
        "2.6 Implementation of Logical Design: DDL and Sample Data", "3.1 Application Overview", "3.2 Development Environment and Database Connectivity",
        "3.3 Application Modules and Database Mapping", "3.4 CRUD Operations", "3.5 Business Rules, Validation and Error Handling",
        "3.6 Reports and Database Operations", "3.7 Application Screens", "3.8 Testing and Results", "4.1 Limitations and Future Enhancements"]
keys = subs + [f"Table {a}. {b}" for a, b in cap["tables"]] + [f"Figure {a}. {b}" for a, b in cap["figures"]]
for k in keys:
    probe = norm(k)[:45]
    for i in range(start, len(lines)):
        if any(l.startswith(probe) for l in lines[i]):
            out[k] = i + 1; break
missing = [k for k in front + keys if k not in out]
print("missing:", missing)
json.dump(out, open("pages.json", "w"), indent=1)
