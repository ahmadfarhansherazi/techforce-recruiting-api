"""Throwaway profiling script for the raw import files.

Reads Data/candidates_import.csv and Data/recruiters.csv and prints what is
actually in them. Standard library only, no CLI, no application code.
Run: python3 scripts/profile_csv.py
"""

import csv
import datetime
import io
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "Data")
CANDIDATES = os.path.join(DATA_DIR, "candidates_import.csv")
RECRUITERS = os.path.join(DATA_DIR, "recruiters.csv")

EMAIL_COL = "email"
REGION_COL = "region_code"
STATUS_COL = "status"
DATE_COL = "applied_date"
SALARY_COL = "salary_expectation"
ID_COL = "candidate_id"

SQL_KEYWORDS = [
    "select", "insert", "update", "delete", "drop", "alter", "truncate",
    "union", "exec", "table", "where", "or 1=1", "--", "/*",
]
FORMULA_LEADERS = ("=", "+", "-", "@")


def rule(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def sub(title):
    print()
    print("-- %s" % title)


def show(value):
    """Render a value so invisible characters stay visible."""
    return repr(value)


def split_raw_records(text):
    """Split CSV text into raw record strings, respecting quoted newlines.

    Returns the exact source substring for each record (delimiters stripped),
    so records can be compared byte-for-byte.
    """
    records = []
    buf = []
    in_quotes = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            in_quotes = not in_quotes
            buf.append(ch)
            i += 1
            continue
        if not in_quotes and ch in "\r\n":
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
            records.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        records.append("".join(buf))
    return [r for r in records if r != ""]


# ---------------------------------------------------------------- encoding

def report_encoding(path, raw, text, rows):
    sub("Encoding / structure")
    print("file: %s" % path)
    print("size on disk: %d bytes" % len(raw))

    bom = raw[:3] == b"\xef\xbb\xbf"
    print("UTF-8 BOM present: %s" % bom)

    try:
        raw.decode("utf-8")
        print("decodes as UTF-8: yes")
    except UnicodeDecodeError as exc:
        print("decodes as UTF-8: NO -> %s" % exc)

    non_ascii = sorted({c for c in text if ord(c) > 127})
    print("non-ASCII characters present: %d distinct -> %s"
          % (len(non_ascii), "".join(non_ascii) if non_ascii else "(none)"))

    crlf = raw.count(b"\r\n")
    lone_cr = raw.count(b"\r") - crlf
    lone_lf = raw.count(b"\n") - crlf
    print("line endings: CRLF=%d  bare LF=%d  bare CR=%d" % (crlf, lone_lf, lone_cr))
    if crlf and (lone_lf or lone_cr):
        print("  WARNING: mixed line endings")
    elif crlf:
        print("  style: CRLF (Windows)")
    else:
        print("  style: LF (Unix)")

    print("physical lines in file: %d" % len(raw.splitlines()))
    print("parsed data rows (excluding header): %d" % len(rows))
    if len(raw.splitlines()) - 1 != len(rows):
        print("  NOTE: line count != row count -> some field contains an "
              "embedded newline")

    ends_newline = raw.endswith(b"\n") or raw.endswith(b"\r")
    print("file ends with a newline: %s" % ends_newline)


# ------------------------------------------------------------------ columns

def report_columns(header, rows):
    sub("Column names, exactly as they appear")
    for idx, name in enumerate(header):
        flags = []
        if name != name.strip():
            flags.append("HAS SURROUNDING WHITESPACE")
        if name != name.lower():
            flags.append("not lowercase")
        print("  [%2d] %s%s" % (idx, show(name), ("  <- " + ", ".join(flags)) if flags else ""))
    dupes = [n for n, c in Counter(header).items() if c > 1]
    if dupes:
        print("  DUPLICATE COLUMN NAMES: %s" % dupes)

    sub("Per-column null / empty counts and sample values")
    total = len(rows)
    for name in header:
        values = [r.get(name) for r in rows]
        missing = sum(1 for v in values if v is None)
        empty = sum(1 for v in values if v is not None and v.strip() == "")
        ws_only = sum(1 for v in values if v is not None and v != "" and v.strip() == "")
        padded = sum(1 for v in values if v is not None and v != v.strip() and v.strip() != "")
        distinct = []
        for v in values:
            if v is not None and v not in distinct:
                distinct.append(v)
        print()
        print("  %s" % name)
        print("    rows=%d  missing(field absent)=%d  empty-or-blank=%d  "
              "whitespace-only=%d  padded-with-whitespace=%d"
              % (total, missing, empty, ws_only, padded))
        print("    distinct values: %d" % len(distinct))
        for v in distinct[:15]:
            print("      %s" % show(v))
        if len(distinct) > 15:
            print("      ... and %d more distinct values" % (len(distinct) - 15))


# -------------------------------------------------------------------- email

def report_email(rows):
    sub("Email: case / whitespace collisions")
    groups = defaultdict(list)
    for r in rows:
        raw = r.get(EMAIL_COL) or ""
        key = raw.strip().lower()
        if key == "":
            continue
        groups[key].append((r.get(ID_COL), raw))

    colliding = {k: v for k, v in groups.items() if len(v) > 1}
    rows_involved = sum(len(v) for v in colliding.values())
    exact_dupes = sum(
        1 for v in colliding.values()
        for raw in {x[1] for x in v} if False
    )
    print("non-empty emails: %d" % sum(len(v) for v in groups.values()))
    print("distinct once trimmed + lowercased: %d" % len(groups))
    print("rows involved in a collision: %d" % rows_involved)
    print("collision groups: %d" % len(colliding))

    for key, members in sorted(colliding.items()):
        raws = {m[1] for m in members}
        kind = "IDENTICAL raw values" if len(raws) == 1 else \
               "differ only by case and/or surrounding whitespace"
        print()
        print("  normalized: %s  (%s)" % (show(key), kind))
        for cid, raw in members:
            print("    %-8s %s" % (cid, show(raw)))

    sub("Email: values that do not look like an address")
    bad = [(r.get(ID_COL), r.get(EMAIL_COL)) for r in rows
           if (r.get(EMAIL_COL) or "").strip() == ""
           or "@" not in (r.get(EMAIL_COL) or "")]
    if not bad:
        print("  (none)")
    for cid, val in bad:
        reason = "empty" if (val or "").strip() == "" else "no @"
        print("  %-8s %-32s <- %s" % (cid, show(val), reason))


# ---------------------------------------------------------- simple freq cols

def report_frequency(rows, column, label):
    sub("%s: every distinct raw value with frequency" % label)
    counts = Counter(r.get(column) for r in rows)
    for value, count in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        flags = []
        if value is None:
            flags.append("FIELD ABSENT")
        else:
            if value.strip() == "":
                flags.append("EMPTY")
            if value != value.strip():
                flags.append("PADDED")
            if value.strip() and value != value.upper() and value == value.lower():
                flags.append("lowercase")
            if value.strip() and value == value.upper() and value != value.lower():
                flags.append("UPPERCASE")
        print("  %5d  %-16s %s" % (count, show(value), ("<- " + ", ".join(flags)) if flags else ""))

    normalized = Counter((r.get(column) or "").strip().upper() for r in rows)
    variants = [k for k in normalized
                if sum(1 for v in counts if (v or "").strip().upper() == k) > 1]
    if variants:
        print()
        print("  values that merge once trimmed + uppercased:")
        for k in sorted(variants):
            raws = [v for v in counts if (v or "").strip().upper() == k]
            print("    %s <- %s" % (show(k), ", ".join(show(x) for x in raws)))


# --------------------------------------------------------------------- date

ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
DASH_SLASH = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
TEXT_MONTH = re.compile(r"^(\d{1,2})-([A-Za-z]{3,9})-(\d{4})$")


def classify_date(value):
    if value is None:
        return "FIELD ABSENT", None
    if value.strip() == "":
        return "EMPTY", None
    v = value.strip()
    if ISO.match(v):
        return "ISO YYYY-MM-DD", ISO.match(v)
    if SLASH.match(v):
        return "numeric N/N/YYYY", SLASH.match(v)
    if DASH_SLASH.match(v):
        return "numeric N-N-YYYY", DASH_SLASH.match(v)
    if TEXT_MONTH.match(v):
        return "text DD-Mon-YYYY", TEXT_MONTH.match(v)
    return "UNRECOGNIZED", None


def real_date(y, m, d):
    try:
        datetime.date(y, m, d)
        return True
    except ValueError:
        return False


def report_dates(rows):
    sub("Date: distinct raw values grouped by apparent format")
    buckets = defaultdict(Counter)
    for r in rows:
        value = r.get(DATE_COL)
        fmt, _ = classify_date(value)
        buckets[fmt][value] += 1

    ambiguous = []
    impossible = []

    for fmt in sorted(buckets):
        print()
        print("  format: %s   (%d rows, %d distinct)"
              % (fmt, sum(buckets[fmt].values()), len(buckets[fmt])))
        for value, count in sorted(buckets[fmt].items(), key=lambda kv: str(kv[0])):
            note = ""
            match = classify_date(value)[1]
            if match and fmt.startswith("numeric"):
                a, b, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if a <= 12 and b <= 12 and a != b:
                    note = "  <- AMBIGUOUS DD/MM vs MM/DD"
                    ambiguous.append(value)
                elif a <= 12 and b <= 12 and a == b:
                    note = "  <- same either way (%d/%d)" % (a, b)
                else:
                    reading = "MM/DD" if b > 12 else "DD/MM"
                    note = "  <- unambiguous, reads as %s" % reading
            if match and fmt == "ISO YYYY-MM-DD":
                y, m, d = (int(g) for g in match.groups())
                if not real_date(y, m, d):
                    note = "  <- IMPOSSIBLE CALENDAR DATE"
                    impossible.append(value)
            print("    %3d  %-20s%s" % (count, show(value), note))

    sub("Date: flags summary")
    print("ambiguous DD/MM vs MM/DD: %s" % (sorted(set(ambiguous)) or "(none)"))
    print("impossible calendar dates: %s" % (sorted(set(impossible)) or "(none)"))
    print("missing/empty dates: %d" % sum(buckets["EMPTY"].values()))
    print("unrecognized shapes: %s"
          % (sorted(str(v) for v in buckets["UNRECOGNIZED"]) or "(none)"))


# ------------------------------------------------------------------- salary

def report_salary(rows):
    sub("Salary: every distinct raw value that is not a plain integer")
    offenders = Counter()
    plain = 0
    for r in rows:
        value = r.get(SALARY_COL)
        if value is not None and re.fullmatch(r"\d+", value):
            plain += 1
        else:
            offenders[value] += 1
    print("plain-integer values: %d rows" % plain)
    print("non-plain-integer values: %d rows, %d distinct" % (sum(offenders.values()), len(offenders)))
    for value, count in sorted(offenders.items(), key=lambda kv: str(kv[0])):
        reasons = []
        if value is None:
            reasons.append("field absent")
        elif value.strip() == "":
            reasons.append("empty")
        else:
            if "$" in value:
                reasons.append("currency symbol")
            if "," in value:
                reasons.append("thousands separator")
            if re.search(r"[A-Za-z]", value):
                reasons.append("letters")
            if "." in value:
                reasons.append("decimal point")
            if value != value.strip():
                reasons.append("padded")
        print("  %3d  %-16s <- %s" % (count, show(value), ", ".join(reasons)))


# ---------------------------------------------------------------- duplicates

def report_duplicate_ids(header, rows):
    sub("candidate_id appearing more than once (full rows shown)")
    counts = Counter(r.get(ID_COL) for r in rows)
    dupes = {k: c for k, c in counts.items() if c > 1}
    if not dupes:
        print("  (none)")
        return
    print("duplicate ids: %s" % sorted(dupes))
    for cid in sorted(dupes):
        members = [(i, r) for i, r in enumerate(rows) if r.get(ID_COL) == cid]
        print()
        print("  id %s appears %d times:" % (cid, len(members)))
        for line_no, row in members:
            print("    row #%d" % (line_no + 1))
            for col in header:
                print("      %-20s %s" % (col, show(row.get(col))))
        differing = [c for c in header
                     if len({r.get(c) for _, r in members}) > 1]
        if differing:
            print("    -> fields that DIFFER across these rows: %s" % differing)
        else:
            print("    -> all fields identical (exact duplicate row)")


def report_duplicate_rows(raw_records):
    sub("Rows byte-for-byte identical to another row")
    body = raw_records[1:]
    counts = Counter(body)
    dupes = {k: c for k, c in counts.items() if c > 1}
    if not dupes:
        print("  (none)")
        return
    for record, count in dupes.items():
        positions = [i + 1 for i, r in enumerate(body) if r == record]
        print("  appears %d times at data rows %s:" % (count, positions))
        print("    %s" % show(record))


# ------------------------------------------------------------ risky content

def risky_reasons(value):
    reasons = []
    if value is None or value == "":
        return reasons
    stripped = value.strip()
    lowered = value.lower()
    hits = [k for k in SQL_KEYWORDS if k in lowered]
    if hits:
        reasons.append("sql-ish token(s): %s" % hits)
    if "'" in value:
        reasons.append("single quote")
    if '"' in value:
        reasons.append("double quote")
    if ";" in value:
        reasons.append("semicolon")
    if "<" in value or ">" in value:
        reasons.append("angle bracket")
    if stripped[:1] in FORMULA_LEADERS:
        reasons.append("leading %r (spreadsheet formula risk)" % stripped[0])
    return reasons


def report_risky(header, rows):
    sub("Values containing SQL keywords, quotes, ; <> or a leading = + - @")
    found = 0
    by_reason = Counter()
    for i, row in enumerate(rows):
        for col in header:
            value = row.get(col)
            reasons = risky_reasons(value)
            if reasons:
                found += 1
                for r in reasons:
                    by_reason[r.split(":")[0]] += 1
                print("  row #%-3d id=%-8s col=%-20s %s"
                      % (i + 1, row.get(ID_COL), col, show(value)))
                print("        -> %s" % "; ".join(reasons))
    print()
    print("total flagged values: %d" % found)
    for reason, count in by_reason.most_common():
        print("  %-45s %d" % (reason, count))


# --------------------------------------------------------------- recruiters

def report_recruiters():
    rule("recruiters.csv")
    with open(RECRUITERS, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    header = list(rows[0].keys()) if rows else []

    print("columns: %s" % [show(h) for h in header])
    print("recruiters: %d" % len(rows))

    all_regions = set()
    for row in rows:
        raw_regions = row.get("assigned_regions") or ""
        role = (row.get("role") or "").strip()
        is_admin = role.lower() == "admin"
        wildcard = raw_regions.strip() == "*"
        regions = [] if wildcard else [
            p.strip() for p in raw_regions.split("|") if p.strip()
        ]
        all_regions.update(regions)
        print()
        print("  %s  %s" % (row.get("recruiter_id"), row.get("full_name")))
        print("    email          %s" % show(row.get("email")))
        print("    role           %s" % show(row.get("role")))
        print("    admin          %s" % is_admin)
        print("    regions (raw)  %s" % show(raw_regions))
        if wildcard:
            print("    regions parsed ALL ('*' wildcard -> no region filter)")
        else:
            print("    regions parsed %s  (%d)" % (regions, len(regions)))

    print()
    print("  union of explicitly assigned regions: %s" % sorted(all_regions))
    admins = [r.get("recruiter_id") for r in rows
              if (r.get("role") or "").strip().lower() == "admin"]
    print("  admins: %s" % admins)


# --------------------------------------------------------------------- main

def main():
    rule("candidates_import.csv")
    with open(CANDIDATES, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8-sig")

    reader = csv.reader(io.StringIO(text))
    all_records = list(reader)
    header = all_records[0]
    data = all_records[1:]
    rows = [dict(zip(header, rec)) for rec in data]

    for rec, row in zip(data, rows):
        if len(rec) != len(header):
            row["__ragged__"] = "%d fields vs %d header columns" % (len(rec), len(header))

    raw_records = split_raw_records(text)

    report_encoding(CANDIDATES, raw, text, rows)

    ragged = [(i + 1, r["__ragged__"]) for i, r in enumerate(rows) if "__ragged__" in r]
    sub("Ragged rows (field count != header count)")
    if ragged:
        for line_no, msg in ragged:
            print("  row #%d: %s" % (line_no, msg))
    else:
        print("  (none)")
    for row in rows:
        row.pop("__ragged__", None)

    report_columns(header, rows)
    report_email(rows)
    report_frequency(rows, REGION_COL, "Region")
    report_frequency(rows, STATUS_COL, "Status")
    report_dates(rows)
    report_salary(rows)
    report_duplicate_ids(header, rows)
    report_duplicate_rows(raw_records)
    report_risky(header, rows)

    report_recruiters()

    rule("end of profile")


if __name__ == "__main__":
    main()
