from fastapi import APIRouter, status, Response
from ..models import ApartmentCreate, ApartmentResponse, ApartmentUpdate, User
from ..exceptions import APIException
from ..utils import apartment_return_format
import src.db as db

router = APIRouter(prefix="/apartments", tags=["apartments"])


@router.get("", status_code=status.HTTP_200_OK, response_model=list[ApartmentResponse])
def list_apartments(current_user: User):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    return [apartment_return_format(apartment) for apartment in db.get_all_apartments()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApartmentResponse)
def create_apartment(apartment: ApartmentCreate, current_user: User):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    new_apartment = db.add_apartment(apartment.number, apartment.description)
    return apartment_return_format(new_apartment)


@router.put(
    "/{apartment_id}", status_code=status.HTTP_200_OK, response_model=ApartmentResponse
)
def update_apartment(
    apartment_id: int,
    updated_apartment: ApartmentUpdate,
    current_user: User,
):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    apartment = db.update_apartment(
        apartment_id, updated_apartment.dict(exclude_unset=True)
    )
    if apartment:
        return apartment_return_format(apartment)
    raise APIException(status_code=404, detail="Apartment not found")


@router.delete("/{apartment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_apartment(apartment_id: int, current_user: User):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    if db.remove_apartment(apartment_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=404, detail="Apartment not found")
