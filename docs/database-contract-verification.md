# Database contract verification

API models describe public data, not SQL rows. `PostgresRepository` maps internal
BIGINT keys to public UUID strings, SQL names to API names, and `chat_turn` rows
to ordered message records. Verify those mappings against the migrated database,
not just `init/02_schema.sql`.

`rawberry-api/tests/test_schema_contract.py` strictly validates repository results
against the public Pydantic models. It covers documents, chunks, metadata, binary
contents, preferences, conversation timestamps, and pending/completed/failed turns.
The existing PostgreSQL integration tests cover ownership, rollback, persistence,
vector retrieval, and recovery. Their fixture applies migrations 001–003 twice
to test repeatability and preserves seeded legacy records.

## Run against a disposable local database

Start Docker Desktop first. From the repository root in PowerShell:

```powershell
docker run --detach --name rawberry-contract-db --publish 127.0.0.1:55432:5432 --env POSTGRES_DB=rawberry_test --env POSTGRES_USER=postgres --env POSTGRES_PASSWORD=contract-local-only pgvector/pgvector:pg16
docker exec rawberry-contract-db pg_isready -U postgres -d rawberry_test
```

Wait for `pg_isready` to report that PostgreSQL is accepting connections, then:

```powershell
python -m pip install -r rawberry-api/requirements.txt
$env:TEST_DATABASE_URL = 'postgresql://postgres:contract-local-only@localhost:55432/rawberry_test'
python -X utf8 -B -m pytest tests rawberry-api/tests -p no:cacheprovider
Remove-Item Env:TEST_DATABASE_URL
docker rm --force rawberry-contract-db
```

The fixture creates and drops uniquely named schemas. Use only a disposable
database: it also enables the vector extension. Never point `TEST_DATABASE_URL`
at the shared cloud database. Model/embedding calls are mocked for these tests.
Database tests must pass, rather than skip, to establish live compatibility.

## Check compatibility with main

Fetch `origin/main` and compare the models, repository, schema, migrations, and
tests before making changes. Use a separate worktree for integration checks so
the working branch remains untouched. Test the combined changes there; a clean
text merge alone does not establish runtime compatibility.

Prefer new test files and forward migrations. Do not rewrite existing migrations
to make models resemble tables. Coordinate new migration numbers with main.
The existing `.github/workflows/tests.yml` supplies a disposable pgvector service
and `TEST_DATABASE_URL`, so this contract test runs in CI automatically.
