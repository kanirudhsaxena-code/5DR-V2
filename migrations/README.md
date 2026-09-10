# 5DR V2 Database Migrations

Canonical production database: Neon PostgreSQL database `five_dr`.

Migration policy: prepare on temporary branch, validate, obtain approval, apply to parent, preserve model-version history. Never include credentials.
