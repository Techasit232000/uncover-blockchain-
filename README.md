# Uncover Blockchain — Transaction Monitor

A small, read-only command-line app for reviewing transaction records and flagging suspicious patterns. It is designed to open and run in Visual Studio Code using Python. The monitor works on local JSON Lines data; it does not connect to a blockchain, sign or submit transactions, or move funds. Alerts are heuristic signals for human review, not proof of fraud.

## Requirements

- Python 3.9 or newer
- Visual Studio Code with the Microsoft Python extension (recommended)
- No third-party Python packages

## Open and run in VS Code

1. Clone this repository and open its folder in VS Code.
2. If prompted, select a Python 3.9+ interpreter.
3. Open **Run and Debug** and select **Run transaction monitor**, or use the integrated terminal:

   ```sh
   python3 monitor.py sample-transactions.jsonl
   ```

   On Windows, use `python monitor.py sample-transactions.jsonl` if `python3` is unavailable.

The sample input is for demonstration only. To analyze your own data, provide a JSON Lines file with one transaction per line.

## Input format

Each line must be a JSON object with non-empty `tx_hash`, `timestamp`, `from`, `to`, `amount`, and `currency` fields. Timestamps use ISO-8601; UTC `Z` is recommended. Amount must be a finite, non-negative number.

```json
{"tx_hash":"0xabc123","timestamp":"2026-01-31T12:00:00Z","from":"0xSender","to":"0xRecipient","amount":"125.5","currency":"TOKEN"}
```

## Options

```sh
python3 monitor.py transactions.jsonl --large-transfer 500 --burst-count 4 --window-minutes 15 --watchlist watchlist.txt
```

- `--large-transfer`: amount threshold (default `100`). The threshold is interpreted in each transaction's currency, so configure it for your input.
- `--burst-count`: flag the sender's Nth transaction in the time window (default `5`).
- `--window-minutes`: sender activity window (default `10`).
- `--watchlist`: optional text file with one address per line. Blank lines and lines beginning with `#` are ignored.
- Use `-` instead of a filename to read JSON Lines from standard input.

Alerts are emitted as JSON Lines on standard output. The monitor flags large amounts, rapid sender activity, recipients not previously seen in the supplied input, and watchlist matches. It does not validate chain data or determine address ownership. Protect sensitive transaction data and verify alerts independently before acting.
