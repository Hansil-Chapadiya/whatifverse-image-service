from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import validate_internal_token
from app.schemas.responses.asset_response import JobStatusResponse, SceneAssetResponse
from app.services.scene_store import scene_store

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(validate_internal_token)])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str):
    record = scene_store.get_job(job_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": "job_id was not found",
                }
            },
        )

    return JobStatusResponse(
        job_id=job_id,
        status=record.status,
        scene_id=record.scene_id,
        result=SceneAssetResponse(**record.result) if record.result else None,
    )
