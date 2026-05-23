# Tradier Response Fixtures

These JSON files are captured from real Tradier API responses and used by the
offline `tests/test_tradier_client.py` normalization tests. Six of the seven
JSON fixtures are byte-faithful production captures; the remaining one
(`fault_auth.json`) is a synthetic example of the documented JSON-fault shape
and is described separately below.

## Regenerating fixtures from a live token

Set `TRADIER` to your production bearer token, then run each command. Pipe the
body into the matching fixture file, or paste the response into the file by
hand if you want to verify the shape before saving.

```bash
export TRADIER=<your-production-token>

# quote_single.json  -- single-symbol GET (object shape)
curl -s "https://api.tradier.com/v1/markets/quotes?symbols=AAPL&greeks=false" \
  -H "Authorization: Bearer $TRADIER" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/quote_single.json

# quote_batch.json -- multi-symbol GET (array shape)
curl -s "https://api.tradier.com/v1/markets/quotes?symbols=SPY,QQQ,IWM&greeks=false" \
  -H "Authorization: Bearer $TRADIER" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/quote_batch.json

# quote_unmatched.json -- bad ticker (unmatched_symbols shape)
curl -s "https://api.tradier.com/v1/markets/quotes?symbols=BADTICKER123&greeks=false" \
  -H "Authorization: Bearer $TRADIER" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/quote_unmatched.json

# history_daily.json  -- multi-day history (day = array shape)
# Tradier history endpoints support years of daily/weekly/monthly data;
# any 5-trading-day window will produce the array shape.
curl -s "https://api.tradier.com/v1/markets/history?symbol=AAPL&interval=daily&start=2024-05-13&end=2024-05-17" \
  -H "Authorization: Bearer $TRADIER" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/history_daily.json

# history_single_day.json -- one-day history (day = object shape)
curl -s "https://api.tradier.com/v1/markets/history?symbol=AAPL&interval=daily&start=2024-05-17&end=2024-05-17" \
  -H "Authorization: Bearer $TRADIER" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/history_single_day.json

# timesales_15min.json -- intraday 15min bars
# IMPORTANT: Tradier's timesales endpoint enforces a rolling history window
# of roughly 60 days. Pick a `start` date within the window or the request
# fails with "Invalid parameter, start: must be on or after YYYY-MM-DD".
# The end parameter is inclusive (capturing 09:30 to 11:30 yields 9 bars,
# not 8); the test fixture trims the final bar to keep exactly 8.
curl -s "https://api.tradier.com/v1/markets/timesales?symbol=AAPL&interval=15min&start=2026-05-21%2009%3A30&end=2026-05-21%2011%3A30&session_filter=open" \
  -H "Authorization: Bearer $TRADIER" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/timesales_15min.json
```

After regenerating, re-run `uv run pytest tests/test_tradier_client.py -v` to
confirm the normalization layer still handles every shape end-to-end. If the
captured OHLCV differs from what the test asserts, update the assertions in
`tests/test_tradier_client.py` to match (the test purpose is to validate the
*shape*, not any specific market moment).

## Notes on capture quirks

### Intraday timestamp format

Tradier's timesales endpoint returns bar timestamps as ISO 8601 with a `T`
separator and seconds suffix (e.g., `"2026-05-21T09:30:00"`), not the
space-separated `"YYYY-MM-DD HH:MM"` form an earlier fixture used.
`_normalize_intraday_timestamp` in `tradier_client.py` uses
`datetime.fromisoformat`, which handles both forms.

### `fault_auth.json` is synthetic

The committed `fault_auth.json` is a hand-authored example of the JSON fault
shape (`{"fault": {"faultstring": "..."}}`) documented in Tradier's developer
materials. In practice, invalid bearer tokens yield a different response
shape: `HTTP 401` with `Content-Type: plain/text` and the literal body
`"Invalid Access Token"` (no JSON envelope, no fault payload). The `_request`
non-200 branch handles that path already; the synthetic JSON fixture covers
the documented shape for non-auth faults such as quota / rate-limit responses
which may still emit JSON.

If you want to verify Tradier's plain-text 401 behavior directly:

```bash
curl -i -s "https://api.tradier.com/v1/markets/quotes?symbols=AAPL" \
  -H "Authorization: Bearer ThisTokenIsIntentionallyInvalid" \
  -H "Accept: application/json"
```

The returned body is plain text; do not save it as a `.json` fixture.

### `history_empty.json` is synthetic

There is no public way to query a date range that guarantees an empty
history response without depending on market-calendar awareness (a holiday
gap or a future date works, both fragile). The committed `history_empty.json`
hand-encodes the `{"history": null}` shape that real Tradier returns when a
range produces zero trading days, so the `_extract_history_days` empty branch
remains under test.
