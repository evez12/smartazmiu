from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import SessionDep
from app.core.errors import COMMON_ERROR_RESPONSES
from app.core.rbac import CurrentUserDep
from app.modules.grades.schemas import FinishedCourseListOut
from app.modules.grades.service import GradeService

router = APIRouter(prefix="/me/grades", tags=["grades"], responses=COMMON_ERROR_RESPONSES)


def get_grades(session: SessionDep) -> GradeService:
    return GradeService(session)


GradesDep = Annotated[GradeService, Depends(get_grades)]


@router.get(
    "",
    response_model=FinishedCourseListOut,
    operation_id="listMyGrades",
    summary="My finished courses with their final scores, for the ÜOMG calculator",
)
async def my_grades(user: CurrentUserDep, service: GradesDep) -> FinishedCourseListOut:
    return FinishedCourseListOut(items=await service.mine(user))
