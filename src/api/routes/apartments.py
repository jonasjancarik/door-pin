from fastapi import APIRouter, Depends, status, Response
from ..models import ApartmentCreate, ApartmentResponse, ApartmentUpdate
from ..exceptions import APIException
from ..dependencies import authenticate_user
from ..utils import apartment_return_format
import src.db as db

router = APIRouter(prefix="/apartments", tags=["apartments"])


@router.get("", status_code=status.HTTP_200_OK)
def list_apartments(user: db.User = Depends(authenticate_user)):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    return [apartment_return_format(apartment) for apartment in db.get_all_apartments()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_apartment(
    apartment: ApartmentCreate, user: db.User = Depends(authenticate_user)
):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    new_apartment = db.add_apartment(apartment.number, apartment.description)
    return apartment_return_format(new_apartment)


@router.put("/{apartment_id}", status_code=status.HTTP_200_OK)
def update_apartment(
    apartment_id: int,
    updated_apartment: ApartmentUpdate,
    user: db.User = Depends(authenticate_user),
):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    apartment = db.update_apartment(
        apartment_id, updated_apartment.dict(exclude_unset=True)
    )
    if apartment:
        return apartment_return_format(apartment)
    raise APIException(status_code=404, detail="Apartment not found")


@router.delete("/{apartment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_apartment(apartment_id: int, user: db.User = Depends(authenticate_user)):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    if db.remove_apartment(apartment_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=404, detail="Apartment not found")
