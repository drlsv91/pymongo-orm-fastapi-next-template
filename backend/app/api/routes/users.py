from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from app import crud
from app.api.deps import (
    CurrentUser,
    DbDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    PyObjectId,
)
from app.utils import generate_new_account_email, send_email


router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
async def read_users(db: DbDep, skip: int = 0, limit: int = 100, q: str = None) -> Any:
    """
    Retrieve users.
    """

    # Add search query if provided
    base_filter = {}
    if q:

        search_filter = {
            "$or": [
                {
                    "full_name": {"$regex": q, "$options": "i"}
                },  # Case-insensitive search in name
                {
                    "email": {"$regex": q, "$options": "i"}
                },  # Case-insensitive search in email
            ]
        }

        # Combine base filter with search filter
        filter_query = {"$and": [base_filter, search_filter]}
    else:
        filter_query = base_filter

    # Get count of matching documents
    count = await User.count(db=db, query=filter_query)

    # Find matching items with pagination
    users_cursor = await User.find(
        db=db, query=filter_query, limit=limit, skip=skip, sort=[("created_at", -1)]
    )

    # Transform to Pydantic models
    users = [UserPublic(**user.model_dump()) for user in users_cursor]

    return UsersPublic(data=users, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
async def create_user(*, db: DbDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = await crud.get_user_by_email(db=db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )

    user = await crud.create_user(db=db, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    *, db: DbDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = await crud.get_user_by_email(db=db, email=user_in.email)

        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )

    update_data = user_in.model_dump(exclude_unset=True)

    await User.update_many(
        db=db, query={"_id": current_user.id}, update={"$set": update_data}
    )

    return await User.find_one(db=db, query={"_id": current_user.id})


@router.patch("/me/password", response_model=Message)
async def update_password_me(
    *, db: DbDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password"
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the current one",
        )

    hashed_password = get_password_hash(body.new_password)
    await User.update_many(
        db=db,
        query={"_id": current_user.id},
        update={"$set": {"hashed_password": hashed_password}},
    )
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
async def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
async def delete_user_me(db: DbDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super users are not allowed to delete themselves",
        )

    await current_user.delete(db)
    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: PyObjectId, db: DbDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = await User.find_one(db=db, query={"_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
async def update_user(
    *,
    db: DbDep,
    user_id: PyObjectId,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """
    db_user = await User.find_one(db, {"_id": user_id})
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )

    if user_in.email:
        existing_user = await crud.get_user_by_email(db=db, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )

    updated_user = await crud.update_user(
        db=db, db_user=User(**db_user.model_dump()), user_in=user_in
    )
    return updated_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(
    db: DbDep, current_user: CurrentUser, user_id: PyObjectId
) -> Message:
    """
    Delete a user.
    """
    user = await User.find_one(db, {"_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super users are not allowed to delete themselves",
        )

    # Delete all items owned by this user
    await user.delete(db)
    Item.delete_many(db=db, query={"owner_id": user_id})
    return Message(message="User deleted successfully")
