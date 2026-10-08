"""
Database access layer for the Salon & Spa Appointment Management System.

* All SQL uses parameterised queries (%s placeholders) - no string building
  with user input, so SQL injection is not possible.
* Business-rule violations raised by MySQL triggers (SQLSTATE 45000) and
  constraint errors are converted into a readable DBError.
* `transaction()` wraps multi-statement work (e.g. booking an appointment
  with several services) in START TRANSACTION ... COMMIT / ROLLBACK.
"""
import os
import re
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal

import mysql.connector
import pandas as pd
from mysql.connector import errorcode

DB_CONFIG = {
    "host": os.getenv("SALON_DB_HOST", "localhost"),
    "port": int(os.getenv("SALON_DB_PORT", "3306")),
    "user": os.getenv("SALON_DB_USER", "salon"),
    "password": os.getenv("SALON_DB_PASSWORD", "salon123"),
    "database": os.getenv("SALON_DB_NAME", "salon_spa_db"),
}


class DBError(Exception):
    """Readable database error shown to the user."""


def _friendly(err: mysql.connector.Error) -> str:
    if err.sqlstate == "45000":                      # raised by our triggers
        return err.msg
    if err.errno == errorcode.ER_DUP_ENTRY:
        field = err.msg.split("for key")[-1].strip(" '`")
        return f"Duplicate value: this {field.split('.')[-1]} already exists."
    if err.errno in (errorcode.ER_ROW_IS_REFERENCED, errorcode.ER_ROW_IS_REFERENCED_2):
        return "Cannot delete: this record is referenced by other records (e.g. appointments or bills)."
    if err.errno in (errorcode.ER_NO_REFERENCED_ROW, errorcode.ER_NO_REFERENCED_ROW_2):
        return "Invalid reference: the related record does not exist."
    msg = str(err.msg)
    if err.errno in (3819, 4025) or ("constraint" in msg.lower() and "failed" in msg.lower()
                                      and "foreign key" not in msg.lower()):
        m = re.search(r"[`'](chk_\w+)[`']", msg)
        return f"Validation failed: value violates check constraint '{m.group(1) if m else msg}'."
    if err.errno == errorcode.CR_CONN_HOST_ERROR or err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        return "Cannot connect to the database. Check that MySQL is running and the credentials in db.py / environment variables."
    return f"Database error {err.errno}: {err.msg}"


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    """MySQL TIME -> 'HH:MM' text and DECIMAL -> float, for display/charts."""
    for col in df.columns:
        sample = df[col].dropna()
        if sample.empty:
            continue
        v = sample.iloc[0]
        if isinstance(v, timedelta):
            df[col] = df[col].map(lambda t: None if t is None else
                                  f"{int(t.total_seconds() // 3600):02d}:{int(t.total_seconds() % 3600 // 60):02d}")
        elif isinstance(v, Decimal):
            df[col] = df[col].astype(float)
    return df


def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG, autocommit=False)
    except mysql.connector.Error as e:
        raise DBError(_friendly(e)) from e


def query_df(sql: str, params=None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        return _tidy(df)
    except mysql.connector.Error as e:
        raise DBError(_friendly(e)) from e
    finally:
        conn.close()


def query_one(sql: str, params=None):
    df = query_df(sql, params)
    return None if df.empty else df.iloc[0]


def execute(sql: str, params=None) -> int:
    """Run one INSERT/UPDATE/DELETE in its own transaction. Returns lastrowid
    for inserts, otherwise rowcount."""
    with transaction() as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid or cur.rowcount


@contextmanager
def transaction():
    """Yields a cursor; commits on success, rolls back on any error."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        conn.start_transaction()
        yield cur
        conn.commit()
    except mysql.connector.Error as e:
        conn.rollback()
        raise DBError(_friendly(e)) from e
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
