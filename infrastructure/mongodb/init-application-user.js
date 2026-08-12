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
