"""Scheduled entry point: python -m app.cleanup_conversations.

Run from rawberry-api with DATABASE_URL configured. Never falls back to memory.
Each invocation processes a bounded batch; schedule repeatedly for large backlogs.
"""
import argparse
import json

from app.config import get_settings
from app.postgres_repository import PostgresRepository


def main():
    parser = argparse.ArgumentParser(description='Delete conversations inactive for 24 hours.')
    parser.add_argument('--batch-size', type=int, default=500)
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error('--batch-size must be positive')
    database_url = get_settings().database_url
    if not database_url:
        parser.error('DATABASE_URL must be configured; cleanup does not use in-memory storage')
    repository = PostgresRepository(database_url)
    repository.check_ready()
    deleted = repository.purge_expired_conversations(args.batch_size)
    print(json.dumps({'deleted_conversations': deleted}))


if __name__ == '__main__':
    main()
