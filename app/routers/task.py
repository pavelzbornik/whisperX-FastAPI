from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db_session
from ..schemas import Response, Result, ResultTasks
from ..tasks import (
    delete_task_from_db,
    get_all_tasks_status_from_db,
    get_task_status_from_db,
)

task_router = APIRouter()


@task_router.get("/task/all", tags=["Tasks Management"])
async def get_all_tasks_status(
    session: Session = Depends(get_db_session),
) -> ResultTasks:
    return get_all_tasks_status_from_db(session)


@task_router.get("/task/{identifier}", tags=["Tasks Management"])
async def get_transcription_status(
    identifier: str,
    session: Session = Depends(get_db_session),
) -> Result:
    # Check if the identifier exists in the transcription_requests dictionary

    status = get_task_status_from_db(identifier, session)

    if status is not None:
        # If the identifier is found, return the status
        return status
    else:
        # If the identifier is not found, return a 404 response
        raise HTTPException(status_code=404, detail="Identifier not found")


@task_router.delete("/task/{identifier}/delete", tags=["Tasks Management"])
async def delete_task(
    identifier: str,
    session: Session = Depends(get_db_session),
) -> Response:
    if delete_task_from_db(identifier, session):
        return Response(identifier=identifier, message="Task deleted")
    else:
        raise HTTPException(status_code=404, detail="Task not found")
