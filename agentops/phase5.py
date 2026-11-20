"""Phase 5 governance primitives: leases, strict schema validation, immutable versions."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class Phase5Error(RuntimeError):
    pass


class LeaseLedger:
    """SQLite lease store with monotonically increasing fencing tokens.

    A worker must present both owner and fencing token on heartbeat/release.
    Expired leases can be acquired by a new owner; each takeover increments token.
    """
    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS leases(
            resource TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            lease_until REAL NOT NULL,
            fencing_token INTEGER NOT NULL,
            updated REAL NOT NULL
        )""")

    def close(self):
        self.db.close()

    def acquire(self, resource: str, owner: str, ttl_seconds: float, now: float | None = None):
        if not resource or not owner or ttl_seconds <= 0:
            raise Phase5Error("resource, owner and positive ttl_seconds are required")
        now = time.time() if now is None else float(now)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM leases WHERE resource=?", (resource,)).fetchone()
            if row and row["lease_until"] > now:
                self.db.execute("COMMIT")
                return {"acquired": False, "reason": "lease_active", "lease": dict(row)}
            token = (row["fencing_token"] + 1) if row else 1
            until = now + ttl_seconds
            self.db.execute("""INSERT INTO leases(resource,owner,lease_until,fencing_token,updated)
                VALUES(?,?,?,?,?) ON CONFLICT(resource) DO UPDATE SET
                owner=excluded.owner,lease_until=excluded.lease_until,
                fencing_token=excluded.fencing_token,updated=excluded.updated""",
                (resource, owner, until, token, now))
            self.db.execute("COMMIT")
            return {"acquired": True, "lease": {
                "resource": resource, "owner": owner, "lease_until": until,
                "fencing_token": token, "updated": now}}
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def heartbeat(self, resource: str, owner: str, fencing_token: int,
                  ttl_seconds: float, now: float | None = None):
        if ttl_seconds <= 0:
            raise Phase5Error("positive ttl_seconds required")
        now = time.time() if now is None else float(now)
        cur = self.db.execute("""UPDATE leases SET lease_until=?,updated=?
            WHERE resource=? AND owner=? AND fencing_token=? AND lease_until>?""",
            (now + ttl_seconds, now, resource, owner, fencing_token, now))
        return cur.rowcount == 1

    def release(self, resource: str, owner: str, fencing_token: int):
        # Preserve the row and fencing counter. Deleting it would reset the next
        # acquisition to token 1 and could let a stale downstream worker appear current.
        cur = self.db.execute("""UPDATE leases SET lease_until=0,updated=?
            WHERE resource=? AND owner=? AND fencing_token=?""",
            (time.time(), resource, owner, fencing_token))
        return cur.rowcount == 1

    def get(self, resource: str):
        row = self.db.execute("SELECT * FROM leases WHERE resource=?", (resource,)).fetchone()
        return dict(row) if row else None


class SchemaValidationError(Phase5Error):
    pass


class JsonSchemaValidator:
    """A deliberately small JSON Schema subset. Unknown keywords fail closed."""
    _SUPPORTED = {
        "type", "required", "properties", "additionalProperties", "enum",
        "items", "minLength", "maxLength", "minItems", "maxItems",
        "minimum", "maximum",
    }

    @classmethod
    def _check_schema(cls, schema: dict[str, Any], path: str = "$") -> None:
        """Validate schema structure recursively, including unreachable branches."""
        if not isinstance(schema, dict):
            raise SchemaValidationError(f"{path}: schema must be an object")
        unknown = set(schema) - cls._SUPPORTED
        if unknown:
            raise SchemaValidationError(f"{path}: unsupported schema keywords: {sorted(unknown)}")
        if "type" in schema:
            allowed_types={"object","array","string","integer","number","boolean","null"}
            if schema["type"] not in allowed_types:
                raise SchemaValidationError(f"{path}: unsupported type: {schema['type']}")
        if "enum" in schema and (not isinstance(schema["enum"],list) or not schema["enum"]):
            raise SchemaValidationError(f"{path}: enum must be a non-empty array")
        if "required" in schema:
            req=schema["required"]
            if not isinstance(req,list) or not all(isinstance(x,str) for x in req) or len(req)!=len(set(req)):
                raise SchemaValidationError(f"{path}: required must contain unique strings")
        if "properties" in schema:
            props=schema["properties"]
            if not isinstance(props,dict) or not all(isinstance(k,str) for k in props):
                raise SchemaValidationError(f"{path}: properties must be an object with string keys")
            for key, sub in props.items():
                cls._check_schema(sub,f"{path}.properties.{key}")
        if "additionalProperties" in schema:
            additional=schema["additionalProperties"]
            if isinstance(additional,dict):
                cls._check_schema(additional,f"{path}.additionalProperties")
            elif not isinstance(additional,bool):
                raise SchemaValidationError(f"{path}: additionalProperties must be boolean or schema")
        if "items" in schema:
            cls._check_schema(schema["items"],f"{path}.items")
        for key in ("minLength","maxLength","minItems","maxItems"):
            if key in schema and (type(schema[key]) is not int or schema[key] < 0):
                raise SchemaValidationError(f"{path}: {key} must be a non-negative integer")
        for low,high in (("minLength","maxLength"),("minItems","maxItems")):
            if low in schema and high in schema and schema[low] > schema[high]:
                raise SchemaValidationError(f"{path}: {low} cannot exceed {high}")
        for key in ("minimum","maximum"):
            if key in schema and (isinstance(schema[key],bool) or not isinstance(schema[key],(int,float))):
                raise SchemaValidationError(f"{path}: {key} must be numeric")
        if ("minimum" in schema and "maximum" in schema and
            schema["minimum"] > schema["maximum"]):
            raise SchemaValidationError(f"{path}: minimum cannot exceed maximum")

    @classmethod
    def validate(cls, value: Any, schema: dict[str, Any]) -> None:
        cls._check_schema(schema)
        if "enum" in schema and value not in schema["enum"]:
            raise SchemaValidationError("value is not in enum")

        expected = schema.get("type")
        type_map = {
            "object": dict, "array": list, "string": str,
            "integer": int, "number": (int, float),
            "boolean": bool, "null": type(None),
        }
        if expected is not None:
            typ = type_map[expected]
            valid = isinstance(value, typ)
            if expected in {"integer", "number"}:
                valid = valid and not isinstance(value, bool)
            if not valid:
                raise SchemaValidationError(f"expected {expected}")

        if isinstance(value, dict):
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            missing = set(required) - set(value)
            if missing:
                raise SchemaValidationError(f"missing required properties: {sorted(missing)}")
            additional = schema.get("additionalProperties", True)
            extras = set(value) - set(properties)
            if additional is False and extras:
                raise SchemaValidationError(f"additional properties not allowed: {sorted(extras)}")
            if isinstance(additional, dict):
                for key in extras:
                    cls.validate(value[key], additional)
            for key, subschema in properties.items():
                if key in value:
                    cls.validate(value[key], subschema)

        if isinstance(value, list):
            if "items" in schema:
                for item in value:
                    cls.validate(item, schema["items"])
            if len(value) < schema.get("minItems", 0):
                raise SchemaValidationError("array shorter than minItems")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                raise SchemaValidationError("array longer than maxItems")

        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                raise SchemaValidationError("string shorter than minLength")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                raise SchemaValidationError("string longer than maxLength")

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                raise SchemaValidationError("number below minimum")
            if "maximum" in schema and value > schema["maximum"]:
                raise SchemaValidationError("number above maximum")



class VersionRegistry:
    """Append-only prompt/policy registry with canonical SHA-256 digests."""
    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS versions(
            kind TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,
            content TEXT NOT NULL, digest TEXT NOT NULL, created REAL NOT NULL,
            PRIMARY KEY(kind,name,version)
        )""")

    def close(self):
        self.db.close()

    @staticmethod
    def _canonical(content: str | dict[str, Any]) -> str:
        if isinstance(content, str):
            return content
        return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def register(self, kind: str, name: str, version: str, content: str | dict[str, Any]):
        if kind not in {"PROMPT", "POLICY"} or not name or not version:
            raise Phase5Error("kind must be PROMPT or POLICY; name/version are required")
        canonical = self._canonical(content)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        existing = self.db.execute(
            "SELECT * FROM versions WHERE kind=? AND name=? AND version=?",
            (kind, name, version)).fetchone()
        if existing:
            if existing["digest"] != digest:
                raise Phase5Error("version is immutable; content differs from registered digest")
            return dict(existing)
        created = time.time()
        self.db.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)",
                        (kind, name, version, canonical, digest, created))
        return dict(self.db.execute(
            "SELECT * FROM versions WHERE kind=? AND name=? AND version=?",
            (kind, name, version)).fetchone())

    def get(self, kind: str, name: str, version: str):
        row = self.db.execute(
            "SELECT * FROM versions WHERE kind=? AND name=? AND version=?",
            (kind, name, version)).fetchone()
        return dict(row) if row else None

    def list_versions(self, kind: str, name: str):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM versions WHERE kind=? AND name=? ORDER BY created,version",
            (kind, name))]
