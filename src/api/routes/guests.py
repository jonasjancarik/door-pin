from fastapi import APIRouter, status, Response
from ..models import (
    RecurringScheduleCreate,
    OneTimeAccessCreate,
    GuestSchedulesResponse,
)
from ..exceptions import APIException
import src.db as db

router = APIRouter(prefix="/guests", tags=["guests"])


@router.post("/{user_id}/recurring-schedules", status_code=status.HTTP_201_CREATED)
def create_recurring_schedule(
    user_id: int,
    schedule: RecurringScheduleCreate,
    current_user: db.User,
):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    if (
        current_user.role == "apartment_admin"
        and guest_user.apartment_id != current_user.apartment_id
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
def create_one_time_access(
    user_id: int,
    access: OneTimeAccessCreate,
    current_user: db.User,
):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    if (
        current_user.role == "apartment_admin"
        and guest_user.apartment_id != current_user.apartment_id
    ):
        raise APIException(
            status_code=403,
            detail="Cannot modify access for guests from other apartments",
        )

    new_access = db.add_one_time_access(
        user_id, access.access_date, access.start_time, access.end_time
    )
    return {"status": "One-time access created", "access_id": new_access.id}


@router.get("/{user_id}/schedules", status_code=status.HTTP_200_OK)
def list_guest_schedules(user_id: int, current_user: db.User):
    if (
        current_user.role not in ["admin", "apartment_admin"]
        and current_user.id != user_id
    ):
        raise APIException(status_code=403, detail="Insufficient permissions")

    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    if (
        current_user.role == "apartment_admin"
        and guest_user.apartment_id != current_user.apartment_id
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
                "access_date": access.access_date.isoformat(),
                "start_time": access.start_time.isoformat(),
                "end_time": access.end_time.isoformat(),
            }
            for access in one_time_access
        ],
    )


@router.delete(
    "/recurring-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_recurring_schedule(schedule_id: int, current_user: db.User):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    schedule = db.get_recurring_schedule(schedule_id)
    if not schedule:
        raise APIException(status_code=404, detail="Schedule not found")

    if current_user.role == "apartment_admin":
        guest_user = db.get_user(schedule.user_id)
        if guest_user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot remove schedules for guests from other apartments",
            )

    if db.remove_recurring_schedule(schedule_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete recurring schedule")


@router.delete("/one-time-accesses/{access_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_one_time_access(access_id: int, current_user: db.User):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    access = db.get_one_time_access(access_id)
    if not access:
        raise APIException(status_code=404, detail="One-time access not found")

    if current_user.role == "apartment_admin":
        guest_user = db.get_user(access.user_id)
        if guest_user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot remove access for guests from other apartments",
            )

    if db.remove_one_time_access(access_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete one-time access")
