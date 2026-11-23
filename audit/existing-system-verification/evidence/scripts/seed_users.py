"""Adds synthetic accounts to the ISOLATED wp31 database only."""
import json
import os
import sys

from bson import ObjectId
from pymongo import MongoClient

from app.domain.permissions import Role
from app.domain.persistence import PersistedUser
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.persistence.repositories import MongoUserRepository

client = MongoClient(os.environ["IDENTITY_MONGO_URI"], tz_aware=True)
assert client.address[0] == "mongodb"
assert os.environ["IDENTITY_MONGO_DATABASE"] == "secure_identity"
repository = MongoUserRepository(client["secure_identity"]["users"])
hasher = Argon2PasswordHasher()
for username, spec in json.load(sys.stdin).items():
    if repository.get_by_username(username) is None:
        repository.add(
            PersistedUser(
                id=str(ObjectId()),
                username=username,
                display_name=spec["name"],
                roles=(Role(spec["role"]),),
                enabled=True,
                password_hash=hasher.hash_password(spec["password"]),
            )
        )
        print("created", username)
