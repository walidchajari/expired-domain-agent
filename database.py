import sqlite3
import datetime
from typing import Optional

from config import settings

CREATE_DOMAINS_TABLE = """
CREATE TABLE IF NOT EXISTS domains (
    domain          TEXT PRIMARY KEY,
    length          INTEGER,
    bl              TEXT,
    dp              TEXT,
    wby             TEXT,
    aby             TEXT,
    acr             TEXT,
    mmgr            TEXT,
    reg             INTEGER,
    rdt             TEXT,
    status          TEXT,
    brandability    REAL DEFAULT 0,
    resale_potential REAL DEFAULT 0,
    pronounceability REAL DEFAULT 0,
    memorability    REAL DEFAULT 0,
    startup_potential REAL DEFAULT 0,
    final_score     REAL DEFAULT 0,
    ai_raw_response TEXT,
    analyzed_date   TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
)
"""

CREATE_DAILY_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date     TEXT UNIQUE,
    total_analyzed  INTEGER,
    top_score       REAL,
    best_domain     TEXT,
    excel_filename  TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
)
"""

CREATE_REPORT_DOMAINS_TABLE = """
CREATE TABLE IF NOT EXISTS report_domains (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date     TEXT,
    rank            INTEGER,
    domain          TEXT,
    final_score     REAL,
    category        TEXT,
    estimated_wholesale_price TEXT,
    estimated_end_user_price TEXT,
    probability_of_sale REAL,
    reason_for_selection TEXT,
    FOREIGN KEY (report_date) REFERENCES daily_reports(report_date)
)
"""

CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain          TEXT,
    rating          TEXT CHECK(rating IN ('BUY','GOOD','BAD','SKIP')),
    feedback_date   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (domain) REFERENCES domains(domain)
)
"""

CREATE_INVESTOR_PROFILE_TABLE = """
CREATE TABLE IF NOT EXISTS investor_profile (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature         TEXT UNIQUE,
    weight          REAL DEFAULT 0.0,
    importance      TEXT DEFAULT 'neutral',
    updated_at      TEXT DEFAULT (datetime('now'))
)
"""

CREATE_DOMAIN_CATEGORIES_TABLE = """
CREATE TABLE IF NOT EXISTS domain_categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain          TEXT,
    category        TEXT,
    confidence      REAL DEFAULT 1.0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (domain) REFERENCES domains(domain)
)
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(CREATE_DOMAINS_TABLE)
        conn.execute(CREATE_DAILY_REPORTS_TABLE)
        conn.execute(CREATE_REPORT_DOMAINS_TABLE)
        conn.execute(CREATE_FEEDBACK_TABLE)
        conn.execute(CREATE_INVESTOR_PROFILE_TABLE)
        conn.execute(CREATE_DOMAIN_CATEGORIES_TABLE)

        # Migration: add new report_domains columns if missing
        for col in ("category", "estimated_wholesale_price", "estimated_end_user_price",
                     "probability_of_sale", "reason_for_selection"):
            try:
                conn.execute(f"ALTER TABLE report_domains ADD COLUMN {col} TEXT")
            except Exception:
                pass


def domain_exists(domain: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM domains WHERE domain = ?", (domain,)
        ).fetchone() is not None


def insert_domain(data: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO domains
            (domain, length, bl, dp, wby, aby, acr, mmgr, reg, rdt, status,
             brandability, resale_potential, pronounceability, memorability,
             startup_potential, final_score, ai_raw_response, analyzed_date)
            VALUES (:domain, :length, :bl, :dp, :wby, :aby, :acr, :mmgr, :reg,
                    :rdt, :status, :brandability, :resale_potential,
                    :pronounceability, :memorability, :startup_potential,
                    :final_score, :ai_raw_response, :analyzed_date)
            """,
            data,
        )


def insert_daily_report(
    report_date: str,
    total_analyzed: int,
    top_score: float,
    best_domain: str,
    excel_filename: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_reports
            (report_date, total_analyzed, top_score, best_domain, excel_filename)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_date, total_analyzed, top_score, best_domain, excel_filename),
        )


def insert_report_domains(report_date: str, domains: list[dict]) -> None:
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO report_domains
            (report_date, rank, domain, final_score, category,
             estimated_wholesale_price, estimated_end_user_price,
             probability_of_sale, reason_for_selection)
            VALUES (:report_date, :rank, :domain, :final_score, :category,
                    :estimated_wholesale_price, :estimated_end_user_price,
                    :probability_of_sale, :reason_for_selection)
            """,
            domains,
        )


def insert_feedback(domain: str, rating: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO feedback (domain, rating) VALUES (?, ?)", (domain, rating)
        )


def get_feedback_history() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.*, d.brandability, d.resale_potential, d.pronounceability,
                   d.memorability, d.startup_potential, d.final_score, d.length, d.reg
            FROM feedback f
            LEFT JOIN domains d ON f.domain = d.domain
            ORDER BY f.feedback_date DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_investor_profile() -> dict:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM investor_profile").fetchall()
        return {r["feature"]: r["weight"] for r in rows}


def upsert_investor_profile(feature: str, weight: float, importance: str = "neutral") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO investor_profile (feature, weight, importance, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(feature) DO UPDATE SET
                weight = excluded.weight,
                importance = excluded.importance,
                updated_at = datetime('now')
            """,
            (feature, weight, importance),
        )


def get_previous_top_domains(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT d.*
            FROM domains d
            INNER JOIN report_domains rd ON d.domain = rd.domain
            WHERE d.final_score > 0
            ORDER BY rd.report_date DESC, rd.rank ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_report_dates(limit: int = 30) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT report_date FROM daily_reports ORDER BY report_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["report_date"] for r in rows]


def get_today_report(report_date: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_reports WHERE report_date = ?", (report_date,)
        ).fetchone()
        return dict(row) if row else None
