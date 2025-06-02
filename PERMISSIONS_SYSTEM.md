# Centralized Permission System Documentation

## Overview

This document describes the centralized Role-Based Access Control (RBAC) system for the door-pin API, designed to replace the fragmented permission checks scattered across route files.

## Problem Statement

### Before: Fragmented Permission Checks
- Permission logic scattered across 7+ route files
- Code duplication and inconsistency risks
- Hard to audit what each role can actually do
- Difficult to maintain and test
- Error-prone when adding new roles or changing permissions

### After: Centralized RBAC System
- Single source of truth for all permissions
- Clean, maintainable code with decorators
- Easy to audit and modify permissions
- Centralized testing
- Consistent permission checks across all routes

## System Architecture

### Core Components

1. **Permission Enum** - Defines all possible actions in the system
2. **Role Enum** - Defines the four user roles
3. **Permission Matrix** - Maps roles to their allowed permissions
4. **PermissionChecker** - Core logic for permission validation
5. **Decorators** - Clean route-level permission enforcement

### File Structure
```
src/api/permissions.py    # Main permission system
src/api/routes/*.py       # Route files use decorators from permissions.py
```

## Roles and Permissions

### Role Hierarchy
1. **admin** - Full system access
2. **apartment_admin** - Apartment-scoped management  
3. **user** - Self-service only
4. **guest** - Very limited, schedule-based access

### Permission Categories

#### User Management
- `USERS_CREATE` - Create new users
- `USERS_LIST_ALL` - List all users system-wide
- `USERS_LIST_APARTMENT` - List users in own apartment
- `USERS_VIEW_OTHER` - View other users' profiles
- `USERS_VIEW_OWN` - View own profile
- `USERS_UPDATE_OTHER` - Update other users
- `USERS_UPDATE_OWN` - Update own profile
- `USERS_DELETE_OTHER` - Delete other users

#### PIN Management
- `PINS_CREATE_OTHER` - Create PINs for other users
- `PINS_CREATE_OWN` - Create own PINs
- `PINS_LIST_ALL` - List all PINs system-wide
- `PINS_LIST_APARTMENT` - List PINs in apartment
- `PINS_VIEW_OWN` - View own PINs
- `PINS_UPDATE_OTHER` - Update other users' PINs
- `PINS_UPDATE_OWN` - Update own PINs
- `PINS_DELETE_OTHER` - Delete other users' PINs
- `PINS_DELETE_OWN` - Delete own PINs

#### RFID Management
- `RFIDS_CREATE_OTHER` - Create RFIDs for other users
- `RFIDS_CREATE_OWN` - Create own RFIDs
- `RFIDS_LIST_ALL` - List all RFIDs system-wide
- `RFIDS_LIST_APARTMENT` - List RFIDs in apartment
- `RFIDS_VIEW_OWN` - View own RFIDs
- `RFIDS_DELETE_OTHER` - Delete other users' RFIDs
- `RFIDS_DELETE_OWN` - Delete own RFIDs

#### API Key Management
- `API_KEYS_CREATE_OTHER` - Create API keys for other users
- `API_KEYS_CREATE_OWN` - Create own API keys
- `API_KEYS_LIST_ALL` - List all API keys system-wide
- `API_KEYS_LIST_APARTMENT` - List API keys in apartment
- `API_KEYS_LIST_OWN` - List own API keys
- `API_KEYS_DELETE_OTHER` - Delete other users' API keys
- `API_KEYS_DELETE_OWN` - Delete own API keys

#### Guest Management
- `GUESTS_MANAGE_SCHEDULES` - Create/update guest schedules
- `GUESTS_VIEW_SCHEDULES` - View guest schedules

#### System
- `READER_CONTROL` - Control door reader hardware
- `LOGS_VIEW` - View system logs

## Usage Guide

### 1. Simple Permission Check

Use the `@require_permission` decorator for endpoints that need a single permission:

```python
from src.api.permissions import Permission, require_permission

@router.get("/pins", status_code=200)
@require_permission(Permission.PINS_LIST_ALL)
def list_all_pins(current_user: User = Depends(get_current_user)):
    # Permission automatically checked by decorator
    pins = db.get_all_pins()
    return pins
```

### 2. Multiple Permission Options

Use `@require_any_permission` when a user needs any one of several permissions:

```python
from src.api.permissions import Permission, require_any_permission

@router.get("/users", status_code=200)
@require_any_permission(Permission.USERS_LIST_ALL, Permission.USERS_LIST_APARTMENT)
def list_users(current_user: User = Depends(get_current_user)):
    if PermissionChecker.has_permission(current_user, Permission.USERS_LIST_ALL):
        return db.get_all_users()
    else:
        return db.get_apartment_users(current_user.apartment_id)
```

### 3. Manual Permission Checks

For complex logic, use `PermissionChecker` directly:

```python
from src.api.permissions import PermissionChecker, Permission

def create_pin_for_user(target_user_id: int, current_user: User):
    target_user = db.get_user(target_user_id)
    
    # Check if user can create PINs for the target user
    if not PermissionChecker.can_create_for_user(
        current_user, target_user, Permission.PINS_CREATE_OTHER
    ):
        raise HTTPException(status_code=403, detail="Cannot create PIN for this user")
    
    # Proceed with PIN creation...
```

### 4. Resource Access Validation

Check if a user can access another user's resources:

```python
from src.api.permissions import PermissionChecker

def get_user_pins(user_id: int, current_user: User):
    target_user = db.get_user(user_id)
    
    if not PermissionChecker.can_access_user_resource(current_user, user_id, target_user):
        raise HTTPException(status_code=403, detail="Cannot access this user's resources")
    
    return db.get_user_pins(user_id)
```

## Permission Matrix

| Permission Category | Admin | Apartment Admin | User | Guest |
|-------------------|-------|----------------|------|--------|
| **User Management** |
| Create Users | ✅ All | ✅ Own Apartment | ❌ | ❌ |
| List Users | ✅ All | ✅ Own Apartment | ❌ | ❌ |
| View Users | ✅ All | ✅ Own Apartment | ✅ Self Only | ✅ Self Only |
| Update Users | ✅ All | ✅ Own Apartment | ✅ Self Only | ❌ |
| Delete Users | ✅ All | ✅ Own Apartment | ❌ | ❌ |
| **PIN Management** |
| Create PINs | ✅ All | ✅ Own Apartment | ✅ Self Only | ❌ |
| List PINs | ✅ All | ✅ Own Apartment | ❌ | ❌ |
| View PINs | ✅ All | ✅ Own Apartment | ✅ Self Only | ✅ Self Only |
| Update PINs | ✅ All | ✅ Own Apartment | ✅ Self Only | ❌ |
| Delete PINs | ✅ All | ✅ Own Apartment | ✅ Self Only | ✅ Self Only |
| **RFID Management** |
| Create RFIDs | ✅ All | ✅ Own Apartment | ✅ Self Only | ❌ |
| List RFIDs | ✅ All | ✅ Own Apartment | ❌ | ❌ |
| View RFIDs | ✅ All | ✅ Own Apartment | ✅ Self Only | ✅ Self Only |
| Delete RFIDs | ✅ All | ✅ Own Apartment | ✅ Self Only | ✅ Self Only |
| **API Keys** |
| Create API Keys | ✅ All | ✅ Own Apartment | ✅ Self Only | ❌ |
| List API Keys | ✅ All | ✅ Own Apartment | ✅ Self Only | ✅ Self Only |
| Delete API Keys | ✅ All | ✅ Own Apartment | ✅ Self Only | ✅ Self Only |
| **Guest Schedules** |
| Manage Schedules | ✅ All | ✅ Own Apartment | ❌ | ❌ |
| View Schedules | ✅ All | ✅ Own Apartment | ❌ | ✅ Self Only |
| **System** |
| Reader Control | ✅ | ❌ | ❌ | ❌ |
| View Logs | ✅ | ❌ | ❌ | ❌ |

## Migration Strategy

### Phase 1: New Endpoints
- Use the permission system for all new endpoints
- Test the system with new features first

### Phase 2: Gradual Refactoring
Refactor existing routes one file at a time:

1. **Start with simple routes** (logs, reader)
2. **Move to medium complexity** (guests, api_keys)  
3. **Finish with complex routes** (users, pins, rfids)

### Phase 3: Cleanup
- Remove old permission checking code
- Add comprehensive tests for the permission system
- Update documentation

### Example Migration

**Before:**
```python
@router.delete("/{pin_id}")
def delete_pin(pin_id: int, current_user: User = Depends(get_current_user)):
    pin = db.get_pin(pin_id)
    if not pin:
        raise APIException(status_code=404, detail="PIN not found")

    if current_user.role == "admin":
        # Admins can delete any PIN
        pass
    elif current_user.role == "apartment_admin":
        # Apartment admins can only delete PINs from their apartment
        if pin.user.apartment_id != current_user.apartment_id:
            raise APIException(status_code=403, detail="Cannot delete PINs for users from other apartments")
    elif current_user.role in ["guest", "user"]:
        # Guests and users can only delete their own PINs
        if pin.user_id != current_user.id:
            raise APIException(status_code=403, detail="Guests and users can only delete their own PINs")
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    if db.delete_pin(pin_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete PIN")
```

**After:**
```python
@router.delete("/{pin_id}")
@require_any_permission(Permission.PINS_DELETE_OTHER, Permission.PINS_DELETE_OWN)
def delete_pin(pin_id: int, current_user: User = Depends(get_current_user)):
    pin = db.get_pin(pin_id)
    if not pin:
        raise APIException(status_code=404, detail="PIN not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(current_user, pin.user_id, pin.user):
        raise APIException(status_code=403, detail="Cannot access this PIN")

    if db.delete_pin(pin_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete PIN")
```

## Testing Strategy

### Unit Tests for Permission System
```python
def test_admin_has_all_permissions():
    admin_user = User(role="admin")
    for permission in Permission:
        assert PermissionChecker.has_permission(admin_user, permission)

def test_user_cannot_create_for_others():
    user = User(id=1, role="user", apartment_id=1)
    other_user = User(id=2, role="user", apartment_id=1)
    
    assert not PermissionChecker.can_create_for_user(
        user, other_user, Permission.PINS_CREATE_OTHER
    )

def test_apartment_admin_can_manage_own_apartment():
    apt_admin = User(id=1, role="apartment_admin", apartment_id=1)
    apt_user = User(id=2, role="user", apartment_id=1)
    
    assert PermissionChecker.can_access_user_resource(apt_admin, 2, apt_user)
```

### Integration Tests for Routes
```python
def test_create_pin_requires_permission():
    # Test that endpoints properly enforce permissions
    response = client.post("/pins", json={...}, headers=guest_headers)
    assert response.status_code == 403
```

## Benefits

### ✅ **Maintainability**
- Single file to modify for permission changes
- Clear role capabilities at a glance
- Consistent patterns across all routes

### ✅ **Security**
- Centralized permission logic reduces security bugs
- Easy to audit what each role can do
- Consistent enforcement across all endpoints

### ✅ **Developer Experience**
- Clean, readable route code
- Easy to add new permissions or roles
- Self-documenting permission matrix

### ✅ **Testing**
- Test permissions centrally instead of in each route
- Easier to verify security requirements
- Better test coverage

## Future Enhancements

### Possible Extensions
1. **Dynamic Permissions** - Load permissions from database
2. **Resource-Based Permissions** - Fine-grained resource access
3. **Audit Logging** - Track permission checks and failures
4. **Permission Caching** - Cache permission checks for performance
5. **Permission Dependencies** - Define permission hierarchies

### Adding New Roles
To add a new role:

1. Add the role to the `Role` enum
2. Define its permissions in `ROLE_PERMISSIONS`
3. Update documentation and tests
4. No changes needed in route files!

### Adding New Permissions
To add a new permission:

1. Add to the `Permission` enum
2. Assign to appropriate roles in `ROLE_PERMISSIONS`
3. Use in route decorators or manual checks
4. Add tests for the new permission

## Conclusion

The centralized permission system provides a clean, maintainable, and secure foundation for access control in the door-pin API. By moving from scattered permission checks to a centralized RBAC system, we achieve better code quality, easier maintenance, and improved security posture. 