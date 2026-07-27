# Infrastructure

The root Compose file defines local development. MongoDB initialization creates
a database-scoped application user from development-only environment
placeholders in
[`mongodb/init-application-user.js`](mongodb/init-application-user.js).

The script runs only for an empty Mongo data volume. Production deployment,
TLS, managed secrets, backup/restore, observability, and database operations
remain planned.
