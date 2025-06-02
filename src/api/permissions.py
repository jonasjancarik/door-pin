"""
Centralized permission system for the door-pin API.
"""

from enum import Enum
from typing import Dict, List, Set, Optional
from functools import wraps
from fastapi import HTTPException
from .models import User


class Permission(Enum):
    # User management
    USERS_CREATE = "users:create"
    USERS_LIST_ALL = "users:list_all"
    USERS_LIST_APARTMENT = "users:list_apartment"
    USERS_VIEW_OTHER = "users:view_other"
    USERS_VIEW_OWN = "users:view_own"
    USERS_UPDATE_OTHER = "users:update_other"
    USERS_UPDATE_OWN = "users:update_own"
    USERS_DELETE_OTHER = "users:delete_other"

    # PIN management
    PINS_CREATE_OTHER = "pins:create_other"
    PINS_CREATE_OWN = "pins:create_own"
    PINS_LIST_ALL = "pins:list_all"
    PINS_LIST_APARTMENT = "pins:list_apartment"
    PINS_VIEW_OWN = "pins:view_own"
    PINS_UPDATE_OTHER = "pins:update_other"
    PINS_UPDATE_OWN = "pins:update_own"
    PINS_DELETE_OTHER = "pins:delete_other"
    PINS_DELETE_OWN = "pins:delete_own"

    # RFID management
    RFIDS_CREATE_OTHER = "rfids:create_other"
    RFIDS_CREATE_OWN = "rfids:create_own"
    RFIDS_LIST_ALL = "rfids:list_all"
    RFIDS_LIST_APARTMENT = "rfids:list_apartment"
    RFIDS_VIEW_OWN = "rfids:view_own"
    RFIDS_DELETE_OTHER = "rfids:delete_other"
    RFIDS_DELETE_OWN = "rfids:delete_own"

    # API key management
    API_KEYS_CREATE_OTHER = "api_keys:create_other"
    API_KEYS_CREATE_OWN = "api_keys:create_own"
    API_KEYS_LIST_ALL = "api_keys:list_all"
    API_KEYS_LIST_APARTMENT = "api_keys:list_apartment"
    API_KEYS_LIST_OWN = "api_keys:list_own"
    API_KEYS_DELETE_OTHER = "api_keys:delete_other"
    API_KEYS_DELETE_OWN = "api_keys:delete_own"

    # Guest management
    GUESTS_MANAGE_SCHEDULES = "guests:manage_schedules"
    GUESTS_VIEW_SCHEDULES = "guests:view_schedules"

    # System
    READER_CONTROL = "reader:control"
    LOGS_VIEW = "logs:view"


class Role(Enum):
    ADMIN = "admin"
    APARTMENT_ADMIN = "apartment_admin"
    USER = "user"
    GUEST = "guest"


# Permission matrix - centralized definition of what each role can do
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Admins can do everything
        Permission.USERS_CREATE,
        Permission.USERS_LIST_ALL,
        Permission.USERS_LIST_APARTMENT,
        Permission.USERS_VIEW_OTHER,
        Permission.USERS_VIEW_OWN,
        Permission.USERS_UPDATE_OTHER,
        Permission.USERS_UPDATE_OWN,
        Permission.USERS_DELETE_OTHER,
        Permission.PINS_CREATE_OTHER,
        Permission.PINS_CREATE_OWN,
        Permission.PINS_LIST_ALL,
        Permission.PINS_LIST_APARTMENT,
        Permission.PINS_VIEW_OWN,
        Permission.PINS_UPDATE_OTHER,
        Permission.PINS_UPDATE_OWN,
        Permission.PINS_DELETE_OTHER,
        Permission.PINS_DELETE_OWN,
        Permission.RFIDS_CREATE_OTHER,
        Permission.RFIDS_CREATE_OWN,
        Permission.RFIDS_LIST_ALL,
        Permission.RFIDS_LIST_APARTMENT,
        Permission.RFIDS_VIEW_OWN,
        Permission.RFIDS_DELETE_OTHER,
        Permission.RFIDS_DELETE_OWN,
        Permission.API_KEYS_CREATE_OTHER,
        Permission.API_KEYS_CREATE_OWN,
        Permission.API_KEYS_LIST_ALL,
        Permission.API_KEYS_LIST_APARTMENT,
        Permission.API_KEYS_LIST_OWN,
        Permission.API_KEYS_DELETE_OTHER,
        Permission.API_KEYS_DELETE_OWN,
        Permission.GUESTS_MANAGE_SCHEDULES,
        Permission.GUESTS_VIEW_SCHEDULES,
        Permission.READER_CONTROL,
        Permission.LOGS_VIEW,
    },
    Role.APARTMENT_ADMIN: {
        # Can manage apartment and users within apartment
        Permission.USERS_CREATE,
        Permission.USERS_LIST_APARTMENT,
        Permission.USERS_VIEW_OTHER,  # within apartment
        Permission.USERS_VIEW_OWN,
        Permission.USERS_UPDATE_OTHER,  # within apartment
        Permission.USERS_UPDATE_OWN,
        Permission.USERS_DELETE_OTHER,  # within apartment
        Permission.PINS_CREATE_OTHER,  # within apartment
        Permission.PINS_CREATE_OWN,
        Permission.PINS_LIST_APARTMENT,
        Permission.PINS_VIEW_OWN,
        Permission.PINS_UPDATE_OTHER,  # within apartment
        Permission.PINS_UPDATE_OWN,
        Permission.PINS_DELETE_OTHER,  # within apartment
        Permission.PINS_DELETE_OWN,
        Permission.RFIDS_CREATE_OTHER,  # within apartment
        Permission.RFIDS_CREATE_OWN,
        Permission.RFIDS_LIST_APARTMENT,
        Permission.RFIDS_VIEW_OWN,
        Permission.RFIDS_DELETE_OTHER,  # within apartment
        Permission.RFIDS_DELETE_OWN,
        Permission.API_KEYS_CREATE_OTHER,  # within apartment
        Permission.API_KEYS_CREATE_OWN,
        Permission.API_KEYS_LIST_APARTMENT,
        Permission.API_KEYS_LIST_OWN,
        Permission.API_KEYS_DELETE_OTHER,  # within apartment
        Permission.API_KEYS_DELETE_OWN,
        Permission.GUESTS_MANAGE_SCHEDULES,  # within apartment
        Permission.GUESTS_VIEW_SCHEDULES,  # within apartment
    },
    Role.USER: {
        # Regular users - can only manage their own resources
        Permission.USERS_VIEW_OWN,
        Permission.USERS_UPDATE_OWN,
        Permission.PINS_CREATE_OWN,
        Permission.PINS_VIEW_OWN,
        Permission.PINS_UPDATE_OWN,
        Permission.PINS_DELETE_OWN,
        Permission.RFIDS_CREATE_OWN,
        Permission.RFIDS_VIEW_OWN,
        Permission.RFIDS_DELETE_OWN,
        Permission.API_KEYS_CREATE_OWN,
        Permission.API_KEYS_LIST_OWN,
        Permission.API_KEYS_DELETE_OWN,
    },
    Role.GUEST: {
        # Guests - very limited permissions
        Permission.USERS_VIEW_OWN,
        Permission.PINS_VIEW_OWN,
        Permission.PINS_DELETE_OWN,
        Permission.RFIDS_VIEW_OWN,
        Permission.RFIDS_DELETE_OWN,
        Permission.API_KEYS_LIST_OWN,
        Permission.API_KEYS_DELETE_OWN,
        Permission.GUESTS_VIEW_SCHEDULES,  # own schedules only
    },
}


class PermissionChecker:
    """Centralized permission checking logic."""

    @staticmethod
    def has_permission(user: User, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        try:
            user_role = Role(user.role)
            return permission in ROLE_PERMISSIONS.get(user_role, set())
        except ValueError:
            # Unknown role
            return False

    @staticmethod
    def can_access_user_resource(
        current_user: User, target_user_id: int, target_user: Optional[User] = None
    ) -> bool:
        """Check if current user can access another user's resources."""
        # Users can always access their own resources
        if current_user.id == target_user_id:
            return True

        # Admins can access anyone's resources
        if current_user.role == "admin":
            return True

        # Apartment admins can access resources within their apartment
        if current_user.role == "apartment_admin" and target_user:
            return current_user.apartment_id == target_user.apartment_id

        return False

    @staticmethod
    def can_create_for_user(
        current_user: User, target_user: User, permission: Permission
    ) -> bool:
        """Check if current user can create resources for target user."""
        # Check base permission first
        if not PermissionChecker.has_permission(current_user, permission):
            return False

        # Admins can create for anyone
        if current_user.role == "admin":
            return True

        # Apartment admins can create for users in their apartment
        if current_user.role == "apartment_admin":
            return current_user.apartment_id == target_user.apartment_id

        # Regular users and guests can only create for themselves
        return current_user.id == target_user.id


def require_permission(permission: Permission):
    """Decorator to require a specific permission."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Find the current_user parameter
            current_user = kwargs.get("current_user")
            if not current_user:
                # Look in args for User object
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break

            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")

            if not PermissionChecker.has_permission(current_user, permission):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(*permissions: Permission):
    """Decorator to require any of the specified permissions."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break

            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")

            if not any(
                PermissionChecker.has_permission(current_user, p) for p in permissions
            ):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience functions for common permission patterns
def check_user_management_permission(
    current_user: User, action: str = "manage"
) -> bool:
    """Check if user can manage other users."""
    if action == "create":
        return PermissionChecker.has_permission(current_user, Permission.USERS_CREATE)
    elif action == "list":
        return PermissionChecker.has_permission(
            current_user, Permission.USERS_LIST_ALL
        ) or PermissionChecker.has_permission(
            current_user, Permission.USERS_LIST_APARTMENT
        )
    return False


def check_resource_access(
    current_user: User, resource_owner_id: int, resource_owner: Optional[User] = None
) -> bool:
    """Check if user can access a specific resource."""
    return PermissionChecker.can_access_user_resource(
        current_user, resource_owner_id, resource_owner
    )
