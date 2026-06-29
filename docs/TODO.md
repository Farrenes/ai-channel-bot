# BotTG TODO

## critical

- Verify current runtime startup path on Windows
- Verify API reachability from n8n in the actual deployment mode
- Verify RouterAI auth and model configuration
- Confirm billing works in dev and disabled mode safely
- Confirm publish idempotency end-to-end

## backend

- Reduce duplication between `main.py` and `admin_bot.py`
- Split runtime concerns out of bot files
- Normalize API envelopes across routes
- Tighten error handling in service adapters

## bot

- Decide the long-term split between content bot and admin bot
- Clean up duplicated topic/admin command handling
- Remove remaining mojibake text in old handler strings

## database

- Decide whether legacy bootstrap tables in `database.py` stay or move fully to migrations
- Backfill compatibility columns if future cleanup needs them
- Add explicit migration runner documentation if needed

## billing

- Finish `CloudPaymentsProvider`
- Finish `RobokassaProvider`
- Finish `TelegramStarsProvider`
- Add receipt/refund/webhook completeness where required
- Validate all billing limits against real plans

## admin

- Decide if FastAPI admin billing endpoints are enough or if a UI admin layer is needed
- Add operator runbooks for manual grants, bans, and limit resets

## LLM

- Stabilize RouterAI startup checks
- Verify prompt generation paths for current style/topic workflows
- Review whether `scoring_service.py` should keep writing to DB as a side effect

## tests

- Run the full billing test subset
- Run topic profile, source validation, generation/review, and scoring contract tests
- Add a smoke test for the full n8n -> API -> publish flow

## deploy

- Document the recommended startup topology
- Decide local vs Docker runtime for API, scoring service, and bots
- Confirm required ports: `8000` and `8001`

## docs

- Keep `PROJECT_BRIEF.md` current
- Keep `PROJECT_HANDOFF.md` current
- Keep `DECISIONS.md` current
- Update `README.md` if launch topology changes again

