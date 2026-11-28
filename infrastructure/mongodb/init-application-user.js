const databaseName = process.env.MONGO_INITDB_DATABASE;
const applicationUsername = process.env.MONGO_APP_USERNAME;
const applicationPassword = process.env.MONGO_APP_PASSWORD;
const recoveryDatabaseName = process.env.MONGO_RECOVERY_DATABASE;
const recoveryUsername = process.env.MONGO_RECOVERY_USERNAME;
const recoveryPassword = process.env.MONGO_RECOVERY_PASSWORD;

if (!databaseName || !applicationUsername || !applicationPassword) {
  throw new Error("MongoDB application user environment is incomplete.");
}

if (!recoveryDatabaseName || !recoveryUsername || !recoveryPassword) {
  throw new Error("MongoDB recovery user environment is incomplete.");
}

const applicationDatabase = db.getSiblingDB(databaseName);
if (!applicationDatabase.getUser(applicationUsername)) {
  applicationDatabase.createUser({
    user: applicationUsername,
    pwd: applicationPassword,
    roles: [{ role: "readWrite", db: databaseName }],
  });
}

const recoveryDatabase = db.getSiblingDB(recoveryDatabaseName);
if (!recoveryDatabase.getUser(recoveryUsername)) {
  recoveryDatabase.createUser({
    user: recoveryUsername,
    pwd: recoveryPassword,
    roles: [{ role: "readWrite", db: recoveryDatabaseName }],
  });
}

// Security intelligence: its own database and principal, so analytics cannot
// read or change identity, recovery or ledger data. Optional for older stacks.
const intelDatabaseName = process.env.MONGO_INTEL_DATABASE;
const intelUsername = process.env.MONGO_INTEL_USERNAME;
const intelPassword = process.env.MONGO_INTEL_PASSWORD;
if (intelDatabaseName && intelUsername && intelPassword) {
  const intelDatabase = db.getSiblingDB(intelDatabaseName);
  if (!intelDatabase.getUser(intelUsername)) {
    intelDatabase.createUser({
      user: intelUsername,
      pwd: intelPassword,
      roles: [{ role: "readWrite", db: intelDatabaseName }],
    });
  }
}

// Revocation ledger: a separate database whose application principal can read
// and append but has no update or delete action, so the database itself refuses
// a rewrite of history. Optional, to keep older deployments working.
const ledgerDatabaseName = process.env.MONGO_LEDGER_DATABASE;
const ledgerUsername = process.env.MONGO_LEDGER_USERNAME;
const ledgerPassword = process.env.MONGO_LEDGER_PASSWORD;
if (ledgerDatabaseName && ledgerUsername && ledgerPassword) {
  const ledgerDatabase = db.getSiblingDB(ledgerDatabaseName);
  if (!ledgerDatabase.getRole("ledgerAppender")) {
    ledgerDatabase.createRole({
      role: "ledgerAppender",
      privileges: [
        {
          resource: { db: ledgerDatabaseName, collection: "" },
          actions: ["find", "insert", "listCollections", "listIndexes", "createCollection", "createIndex"],
        },
      ],
      roles: [],
    });
  }
  if (!ledgerDatabase.getUser(ledgerUsername)) {
    ledgerDatabase.createUser({
      user: ledgerUsername,
      pwd: ledgerPassword,
      roles: [{ role: "ledgerAppender", db: ledgerDatabaseName }],
    });
  }
}

// Read-only principal so backups can cover the recovery database.
const backupUsername = process.env.MONGO_BACKUP_READER_USERNAME;
const backupPassword = process.env.MONGO_BACKUP_READER_PASSWORD;
if (backupUsername && backupPassword && !recoveryDatabase.getUser(backupUsername)) {
  recoveryDatabase.createUser({
    user: backupUsername,
    pwd: backupPassword,
    roles: [{ role: "read", db: recoveryDatabaseName }],
  });
}
