# Tradier Response Fixtures

These JSON files are captured from real Tradier API responses for use in the
offline `tests/test_tradier_client.py` normalization tests. The committed
fixtures are anonymized hand-edited samples that match the documented Tradier
response shapes. If you have a live token, regenerate them with the curl
commands below so the tests run against real-world byte-for-byte payloads.

## Regenerating fixtures from a live token

Set `TRADIER` to your production bearer token, then run each command. Redirect
the body into the matching fixture file.

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
curl -s "https://api.tradier.com/v1/markets/timesales?symbol=AAPL&interval=15min&start=2024-05-17%2009%3A30&end=2024-05-17%2016%3A00&session_filter=all" \
  -H "Authorization: Bearer $TRADIER" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/timesales_15min.json

# fault_auth.json -- intentionally bad token to capture the fault shape
curl -s "https://api.tradier.com/v1/markets/quotes?symbols=AAPL" \
  -H "Authorization: Bearer ThisTokenIsIntentionallyInvalid" \
  -H "Accept: application/json" \
  > tests/fixtures/tradier/fault_auth.json
```

After regenerating, re-run `uv run pytest tests/test_tradier_client.py -v` to
confirm the normalization layer still handles every shape end-to-end.
