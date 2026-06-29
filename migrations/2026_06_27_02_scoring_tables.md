# Scoring Tables Notes

## Added tables

- `content_scores`
- `post_metrics`

## Main fields

- `content_scores` stores the scoring payload, base score, penalty score, total score, decision, breakdowns, and idempotency metadata.
- `post_metrics` stores post-performance snapshots and links them back to `content_scores` and published/generated posts.

## Constraints and indexes

- Decision is constrained to `publish`, `improve`, or `reject`.
- Score ranges are bounded to `0..100`.
- `content_scores` keeps idempotency and dedupe indexes on `idempotency_key` and `(topic_profile_id, content_hash, score_version, content_kind)`.
- `post_metrics` keeps idempotency and workflow indexes on topic, post linkage, metric window, and snapshot time.

## Compatibility notes

- The schema stays additive only.
- Existing tables remain untouched.
- Foreign keys are nullable where that keeps the tables usable during staged rollout.
- `content_scores` can store ad-hoc `/score` results before a candidate/generated post row exists.
