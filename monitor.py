#!/usr/bin/env python3
"""Offline, heuristic transaction monitor for JSON Lines transaction data.

This tool is read-only: it does not connect to a blockchain, sign transactions,
move funds, or treat its heuristic alerts as proof of fraud.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601 (for example 2026-01-31T12:00:00Z)") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_transactions(path: str) -> list[dict[str, Any]]:
    transactions = []
    stream = sys.stdin if path == "-" else Path(path).open(encoding="utf-8")
    try:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                tx = json.loads(line)
                if not isinstance(tx, dict):
                    raise ValueError("each line must contain a JSON object")
                tx["_time"] = parse_time(tx.get("timestamp"))
                tx["_amount"] = Decimal(str(tx.get("amount", "")))
                if not tx["_amount"].is_finite() or tx["_amount"] < 0:
                    raise ValueError("amount must be a finite, non-negative number")
                for field in ("tx_hash", "from", "to", "currency"):
                    if not isinstance(tx.get(field), str) or not tx[field].strip():
                        raise ValueError(f"{field} must be a non-empty string")
                transactions.append(tx)
            except (json.JSONDecodeError, InvalidOperation, ValueError) as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc
    finally:
        if stream is not sys.stdin:
            stream.close()
    return sorted(transactions, key=lambda tx: (tx["_time"], tx["tx_hash"]))


def analyze(transactions: list[dict[str, Any]], *, large_transfer: Decimal,
            burst_count: int, window: timedelta, watched: set[str]) -> list[dict[str, Any]]:
    # Use prior observed transactions only, so a recipient is considered new
    # the first time it appears in the supplied chronological data.
    seen_recipients: set[str] = set()
    recent_by_sender: dict[str, deque[datetime]] = defaultdict(deque)
    alerts = []
    for tx in transactions:
        sender, recipient = tx["from"], tx["to"]
        now = tx["_time"]
        history = recent_by_sender[sender]
        while history and history[0] < now - window:
            history.popleft()
        reasons = []
        score = 0
        if tx["_amount"] >= large_transfer:
            reasons.append(f"large transfer (>= {large_transfer})")
            score += 2
        if len(history) + 1 >= burst_count:
            reasons.append(f"transfer burst ({len(history) + 1} from sender within {window})")
            score += 2
        if recipient not in seen_recipients:
            reasons.append("recipient not previously seen in this input")
            score += 1
        if sender.lower() in watched or recipient.lower() in watched:
            reasons.append("address appears in local watchlist")
            score += 3
        history.append(now)
        seen_recipients.add(recipient)
        if reasons:
            alerts.append({
                "tx_hash": tx["tx_hash"],
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "from": sender,
                "to": recipient,
                "amount": str(tx["_amount"]),
                "currency": tx["currency"],
                "score": score,
                "severity": "high" if score >= 4 else "medium" if score >= 2 else "low",
                "reasons": reasons,
            })
    return alerts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON Lines file, or - to read stdin")
    parser.add_argument("--large-transfer", default="100", help="amount threshold; interpreted in each transaction's currency (default: 100)")
    parser.add_argument("--burst-count", type=int, default=5, help="flag sender's Nth transfer inside the time window (default: 5)")
    parser.add_argument("--window-minutes", type=int, default=10, help="burst window in minutes (default: 10)")
    parser.add_argument("--watchlist", help="optional text file with one address per line")
    args = parser.parse_args()
    try:
        threshold = Decimal(args.large_transfer)
        if not threshold.is_finite() or threshold < 0:
            raise ValueError("--large-transfer must be a finite, non-negative number")
        if args.burst_count < 1 or args.window_minutes < 1:
            raise ValueError("--burst-count and --window-minutes must be positive")
        watched = set()
        if args.watchlist:
            watched = {line.strip().lower() for line in Path(args.watchlist).read_text(encoding="utf-8").splitlines()
                       if line.strip() and not line.lstrip().startswith("#")}
        txs = load_transactions(args.input)
        for alert in analyze(txs, large_transfer=threshold, burst_count=args.burst_count,
                             window=timedelta(minutes=args.window_minutes), watched=watched):
            print(json.dumps(alert, separators=(",", ":")))
    except (OSError, ValueError, InvalidOperation) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
