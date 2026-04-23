import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.db.models.asset_model import IdempotencyModel
from app.db.session import SessionLocal


@dataclass
class IdempotencyRecord:
    payload_hash: str
    response: dict[str, Any] | None
    status: str = "processing"


class IdempotencyService:
    @staticmethod
    def compute_payload_hash(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get_record(self, request_id: str) -> IdempotencyRecord | None:
        if SessionLocal is None:
            return None

        with SessionLocal() as db:
            row = db.get(IdempotencyModel, request_id)
            if row is None:
                return None
            return IdempotencyRecord(payload_hash=row.payload_hash, response=row.response_json, status=row.status)

    def assert_or_create(self, request_id: str, payload_hash: str) -> IdempotencyRecord | None:
        if SessionLocal is None:
            return None

        with SessionLocal() as db:
            try:
                db.add(
                    IdempotencyModel(
                        request_id=request_id,
                        payload_hash=payload_hash,
                        status="processing",
                        response_json=None,
                    )
                )
                db.commit()
            except IntegrityError:
                db.rollback()
                current = db.get(IdempotencyModel, request_id)
                if current is None:
                    return None
                return IdempotencyRecord(payload_hash=current.payload_hash, response=current.response_json, status=current.status)
            return None

    def set_response(self, request_id: str, payload_hash: str, response: dict[str, Any]) -> None:
        if SessionLocal is None:
            return

        with SessionLocal() as db:
            row = db.get(IdempotencyModel, request_id)
            if row is None:
                row = IdempotencyModel(
                    request_id=request_id,
                    payload_hash=payload_hash,
                    status="completed",
                    response_json=response,
                )
                db.add(row)
            else:
                row.payload_hash = payload_hash
                row.status = "completed"
                row.response_json = response
            db.commit()


idempotency_service = IdempotencyService()
