#!/usr/bin/env python3
"""
Expired Domain Agent – Main Entry Point

Automates daily scraping of ExpiredDomains.net, AI scoring, Excel report
generation, and email delivery. Includes a feedback learning system that
adapts to your preferences over time.

Usage:
    python run.py                  # Run once immediately
    python run.py --schedule       # Run every day at configured time
    python run.py --feedback       # Show preference summary
    python run.py --feedback BUY example.com  # Record feedback
"""
import argparse
import logging
import sys
from datetime import datetime

import schedule
import time

from config import settings
from database import init_db, insert_domain, insert_daily_report, insert_report_domains
from database import get_today_report, insert_feedback
from scraper import scrape_domains, scrape_threeword_domains, scrape_threeletter_domains, login_interactive
from ai_scoring import score_domains
from report_generator import generate_both_reports, generate_threeword_report, generate_threeletter_report, export_summary_text
from email_sender import send_daily_report
from feedback_learner import (
    update_investor_profile,
    adjust_score_with_profile,
    get_preference_summary,
)
from domain_classifier import analyze_domain, generate_rankings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging() -> None:
    log_path = settings.log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # File handler
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)


logger = logging.getLogger("run")


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------
def run_pipeline(run_date: str | None = None) -> None:
    """Execute the full daily pipeline: scrape → score → report → email."""
    logger.info("=" * 60)
    logger.info("STARTING DAILY PIPELINE")
    logger.info("=" * 60)

    today = run_date or datetime.now().strftime("%Y-%m-%d")

    # Check if already run today
    existing = get_today_report(today)
    if existing:
        logger.info("Report for %s already exists – file=%s", today, existing["excel_filename"])

    # 1. Scrape
    try:
        domains = scrape_domains(headless=True, pages=settings.scrape_pages)
    except Exception:
        logger.exception("Scraping step failed – aborting pipeline")
        return

    if not domains:
        logger.warning("No domains found – aborting")
        return

    logger.info("Scraped %d raw domains", len(domains))

    # Limit domains to analyze (score all, but cap for performance)
    max_analyze = settings.max_domains_to_analyze
    if len(domains) > max_analyze:
        logger.info("Limiting to %d domains for analysis (from %d)", max_analyze, len(domains))
        domains = domains[:max_analyze]

    # 2. Score with AI
    try:
        scored = score_domains(domains, enabled=settings.ai_scoring_enabled)
    except Exception:
        logger.exception("AI scoring step failed – aborting")
        return

    logger.info("Scored %d domains", len(scored))

    # 3. Apply feedback learning adjustment
    try:
        update_investor_profile()
        for d in scored:
            adjustment = adjust_score_with_profile(d)
            d["final_score"] = round(d.get("final_score", 0) + adjustment, 2)
    except Exception:
        logger.warning("Feedback profile adjustment failed (non-fatal)")

    # 4. Sort and pick top N
    scored.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    # 5. Apply domain classification & rankings
    rankings = generate_rankings(scored)
    investor_top = rankings["overall"]

    logger.info("Top domain: %s (score=%.2f)", investor_top[0]["domain"], investor_top[0]["final_score"])

    # 6. Save to database
    try:
        analyzed_date = today
        for d in scored:
            d["analyzed_date"] = analyzed_date
            insert_domain(d)

        report_date = today
        top_score = investor_top[0]["final_score"]
        best_domain = investor_top[0]["domain"]

        # 7. Generate TWO Excel reports
        report_paths = generate_both_reports(scored, investor_top)
        available_filename = report_paths[0].name
        investor_filename = report_paths[1].name

        # 8. Save report metadata
        insert_daily_report(report_date, len(scored), top_score, best_domain, investor_filename)
        report_domains_data = [
            {
                "report_date": report_date,
                "rank": i + 1,
                **{k: d.get(k, "") for k in (
                    "domain", "category", "final_score",
                    "estimated_wholesale_price", "estimated_end_user_price",
                    "probability_of_sale", "reason_for_selection",
                )},
            }
            for i, d in enumerate(investor_top)
        ]
        insert_report_domains(report_date, report_domains_data)

        logger.info("Database updated for %s", report_date)
    except Exception:
        logger.exception("Database/Excel step failed – continuing to email")

    # 9. Send email with both attachments
    try:
        send_daily_report(
            attachment_paths=report_paths,
            total_analyzed=len(scored),
            top_score=top_score,
            best_domain=best_domain,
            top_domains=investor_top,
        )
        logger.info("Email sent successfully")
    except Exception:
        logger.exception("Email step failed – reports saved locally at %s", report_paths)

    # 10. Scrape 3-word hyphenated domains and generate report
    threeword_domains = []
    try:
        logger.info("--- Starting 3-word domain scrape ---")
        threeword_domains = scrape_threeword_domains(headless=True, pages=5)
        if threeword_domains:
            threeword_path = generate_threeword_report(threeword_domains)
            report_paths.append(threeword_path)
            logger.info("3-word report added: %s (%d domains)", threeword_path.name, len(threeword_domains))
        else:
            logger.info("No 3-word domains found")
    except Exception:
        logger.exception("3-word domain step failed (non-fatal)")

    # 11. Scrape available 3-letter .com domains
    threeletter_domains = []
    try:
        logger.info("--- Starting 3-letter domain scrape ---")
        threeletter_domains = scrape_threeletter_domains(headless=True, pages=5)
        if threeletter_domains:
            threeletter_path = generate_threeletter_report(threeletter_domains)
            report_paths.append(threeletter_path)
            logger.info("3-letter report added: %s (%d domains)", threeletter_path.name, len(threeletter_domains))
        else:
            logger.info("No 3-letter domains found")
    except Exception:
        logger.exception("3-letter domain step failed (non-fatal)")

    # 12. Print summary
    print(export_summary_text(investor_top))
    if threeword_domains:
        print(f"\n3-Word Domains found: {len(threeword_domains)}")
    if threeletter_domains:
        print(f"\n3-Letter Domains found: {len(threeletter_domains)}")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------
def handle_feedback(args: argparse.Namespace) -> None:
    if args.rating and args.domain:
        insert_feedback(args.domain, args.rating.upper())
        update_investor_profile()
        print(f"Feedback recorded: {args.rating.upper()} – {args.domain}")
        print(get_preference_summary())
    else:
        print(get_preference_summary())


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
def run_scheduler() -> None:
    hour = settings.daily_run_hour
    minute = settings.daily_run_minute
    schedule_time = f"{hour:02d}:{minute:02d}"
    schedule.every().day.at(schedule_time).do(run_pipeline)

    logger.info("Scheduler started – next run at %s daily", schedule_time)
    print(f"Scheduler running. Pipeline will execute daily at {schedule_time}.")
    print("Press Ctrl+C to stop.")

    # Run once immediately on start
    run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    setup_logging()
    init_db()

    parser = argparse.ArgumentParser(
        description="Expired Domain Agent – AI-powered domain investing tool"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run continuously and execute daily at configured time",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Interactive login to save session cookies for future runs",
    )
    parser.add_argument(
        "--feedback",
        nargs="?",
        const="summary",
        metavar="RATING",
        help="Record feedback: BUY|GOOD|BAD|SKIP domain.com (or omit for summary)",
    )
    parser.add_argument("domain", nargs="?", help="Domain name for feedback")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Run pipeline for a specific date (YYYY-MM-DD). Defaults to today.",
    )

    args = parser.parse_args()

    if args.login:
        login_interactive()
    elif args.feedback:
        if args.feedback != "summary":
            # --feedback RATING domain
            handle_feedback(
                argparse.Namespace(
                    rating=args.feedback,
                    domain=args.domain,
                )
            )
        else:
            # --feedback alone = show summary
            handle_feedback(
                argparse.Namespace(rating=None, domain=None)
            )
    elif args.schedule:
        run_scheduler()
    else:
        run_pipeline(run_date=args.date)


if __name__ == "__main__":
    main()
