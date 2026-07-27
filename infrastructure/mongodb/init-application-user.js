const databaseName = process.env.MONGO_INITDB_DATABASE;
const applicationUsername = process.env.MONGO_APP_USERNAME;
const applicationPassword = process.env.MONGO_APP_PASSWORD;

if (!databaseName || !applicationUsername || !applicationPassword) {
  throw new Error("MongoDB application user environment is incomplete.");
}

const applicationDatabase = db.getSiblingDB(databaseName);
if (!applicationDatabase.getUser(applicationUsername)) {
  applicationDatabase.createUser({
    user: applicationUsername,
    pwd: applicationPassword,
    roles: [{ role: "readWrite", db: databaseName }],
  });
}
