"""Small in-memory stand-in for the Mongo calls the intelligence store makes."""

from copy import deepcopy
from types import SimpleNamespace

from pymongo.errors import DuplicateKeyError


def _match(document, query):
    for key, expected in query.items():
        value = document.get(key)
        if isinstance(expected, dict):
            for op, operand in expected.items():
                if op == "$in" and value not in operand:
                    return False
                if op == "$ne" and value == operand:
                    return False
                if op == "$gte" and (value is None or value < operand):
                    return False
                if op == "$lte" and (value is None or value > operand):
                    return False
        elif value != expected:
            return False
    return True


class _Cursor(list):
    def sort(self, key, direction=1):
        return _Cursor(sorted(self, key=lambda d: d.get(key), reverse=direction < 0))

    def skip(self, count):
        return _Cursor(self[count:])

    def limit(self, count):
        return _Cursor(self[:count])


class FakeCollection:
    def __init__(self, unique_open=False):
        self.rows = []
        self.unique_open = unique_open

    def create_index(self, *_args, **_kwargs):
        return "ok"

    def insert_one(self, document):
        if any(r["_id"] == document["_id"] for r in self.rows):
            raise DuplicateKeyError("_id")
        if self.unique_open and document.get("open") and any(
            r.get("open") and r["dedupe_key"] == document["dedupe_key"] for r in self.rows
        ):
            raise DuplicateKeyError("dedupe")
        self.rows.append(deepcopy(document))

    def find(self, query):
        return _Cursor(deepcopy(r) for r in self.rows if _match(r, query))

    def find_one(self, query):
        return next(iter(self.find(query)), None)

    def count_documents(self, query):
        return len(self.find(query))

    def update_one(self, query, update, upsert=False):
        row = next((r for r in self.rows if _match(r, query)), None)
        inserted = row is None and upsert
        if inserted:
            row = dict(query)
            row.update(update.get("$setOnInsert", {}))
            self.rows.append(row)
        if row is None:
            return SimpleNamespace(matched_count=0)
        row.update(update.get("$set", {}))
        for key, amount in update.get("$inc", {}).items():
            row[key] = row.get(key, 0) + amount
        for key, spec in update.get("$push", {}).items():
            values = row.setdefault(key, [])
            batch = isinstance(spec, dict) and "$each" in spec
            values.extend(spec["$each"] if batch else [spec])
            if batch and "$slice" in spec:
                row[key] = values[spec["$slice"]:]
        return SimpleNamespace(matched_count=0 if inserted else 1)


class FakeDatabase(dict):
    def __missing__(self, name):
        self[name] = FakeCollection(unique_open=name == "incidents")
        return self[name]
