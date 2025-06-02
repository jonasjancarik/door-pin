from fastapi import APIRouter, status, Response, Depends
from ..models import (
    RecurringScheduleCreate,
    OneTimeAccessCreate,
    GuestSchedulesResponse,
    User,
)
from ..exceptions import APIException
from ..dependencies import get_current_user
from ..permissions import (
    Permission,
    require_permission,
    require_any_permission,
    PermissionChecker,
)
import src.db as db

router = APIRouter(prefix="/guests", tags=["guests"])


@router.post("/{user_id}/recurring-schedules", status_code=status.HTTP_201_CREATED)
@require_permission(Permission.GUESTS_MANAGE_SCHEDULES)
def create_recurring_schedule(
    user_id: int,
    schedule: RecurringScheduleCreate,
    current_user: User = Depends(get_current_user),
):
    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    # Check if current user can access the guest user's resources
    if not PermissionChecker.can_access_user_resource(
        current_user, user_id, guest_user
    ):
        raise APIException(
            status_code=403,
            detail="Cannot modify schedule for guests from other apartments",
        )

    new_schedule = db.add_recurring_schedule(
        user_id, schedule.day_of_week, schedule.start_time, schedule.end_time
    )
    return {"status": "Recurring schedule created", "schedule_id": new_schedule.id}


@router.post("/{user_id}/one-time-accesses", status_code=status.HTTP_201_CREATED)
@require_permission(Permission.GUESTS_MANAGE_SCHEDULES)
def create_one_time_access(
    user_id: int,
    access: OneTimeAccessCreate,
    current_user: User = Depends(get_current_user),
):
    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    # Check if current user can access the guest user's resources
    if not PermissionChecker.can_access_user_resource(
        current_user, user_id, guest_user
    ):
        raise APIException(
            status_code=403,
            detail="Cannot modify access for guests from other apartments",
        )

    if access.start_date > access.end_date:
        raise APIException(
            status_code=400,
            detail="Start date must be before or equal to end date",
        )

    new_access = db.add_one_time_access(
        user_id,
        access.start_date,
        access.end_date,
        access.start_time,
        access.end_time,
    )
    return {"status": "One-time access created", "access_id": new_access.id}


@router.get("/{user_id}/schedules", status_code=status.HTTP_200_OK)
@require_any_permission(
    Permission.GUESTS_MANAGE_SCHEDULES, Permission.GUESTS_VIEW_SCHEDULES
)
def list_guest_schedules(user_id: int, current_user: User = Depends(get_current_user)):
    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    # Check if current user can access the guest user's resources
    if not PermissionChecker.can_access_user_resource(
        current_user, user_id, guest_user
    ):
        raise APIException(
            status_code=403,
            detail="Cannot view schedules for guests from other apartments",
        )

    recurring_schedules = db.get_recurring_schedules_by_user(user_id)
    one_time_access = db.get_one_time_accesses_by_user(user_id)

    return GuestSchedulesResponse(
        recurring_schedules=[
            {
                "id": schedule.id,
                "day_of_week": schedule.day_of_week,
                "start_time": schedule.start_time.isoformat(),
                "end_time": schedule.end_time.isoformat(),
            }
            for schedule in recurring_schedules
        ],
        one_time_access=[
            {
                "id": access.id,
                "start_date": access.start_date.isoformat(),
                "end_date": access.end_date.isoformat(),
                "start_time": access.start_time.isoformat(),
                "end_time": access.end_time.isoformat(),
            }
            for access in one_time_access
        ],
    )


@router.delete(
    "/recurring-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT
)
@require_permission(Permission.GUESTS_MANAGE_SCHEDULES)
def delete_recurring_schedule(
    schedule_id: int, current_user: User = Depends(get_current_user)
):
    schedule = db.get_recurring_schedule(schedule_id)
    if not schedule:
        raise APIException(status_code=404, detail="Schedule not found")

    # Check if current user can access the guest user's resources
    guest_user = db.get_user(schedule.user_id)
    if not PermissionChecker.can_access_user_resource(
        current_user, schedule.user_id, guest_user
    ):
        raise APIException(
            status_code=403,
            detail="Cannot remove schedules for guests from other apartments",
        )

    if db.remove_recurring_schedule(schedule_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete recurring schedule")


@router.delete("/one-time-accesses/{access_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission(Permission.GUESTS_MANAGE_SCHEDULES)
def delete_one_time_access(
    access_id: int, current_user: User = Depends(get_current_user)
):
    access = db.get_one_time_access(access_id)
    if not access:
        raise APIException(status_code=404, detail="One-time access not found")

    # Check if current user can access the guest user's resources
    guest_user = db.get_user(access.user_id)
    if not PermissionChecker.can_access_user_resource(
        current_user, access.user_id, guest_user
    ):
        raise APIException(
            status_code=403,
            detail="Cannot remove access for guests from other apartments",
        )

    if db.remove_one_time_access(access_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete one-time access")
