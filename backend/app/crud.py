import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError
from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate


async def create_user(*, db: AsyncIOMotorDatabase, user_create: UserCreate) -> User:
    user_data = user_create.model_dump(exclude={"password"})
    user_data["hashed_password"] = get_password_hash(user_create.password)

    try:
        result = await User(**user_data).save(db)
        created_user = await User.find_one(db=db, query={"_id": result.id})
        return User.model_validate(created_user)
    except ValidationError as e:
        raise ValueError(f"Invalid user data: {e}")


async def update_user(
    *, db: AsyncIOMotorDatabase, db_user: User, user_in: UserUpdate
) -> User:
    user_data = user_in.model_dump(exclude_unset=True, exclude={"password"})

    if user_in.password:
        user_data["hashed_password"] = get_password_hash(user_in.password)

    updated_data = db_user.model_copy(update=user_data)
    await updated_data.save(db)

    updated_user = await User.find_one(db, {"_id": db_user.id})
    return User.model_validate(updated_user)


async def get_user_by_email(*, db: AsyncIOMotorDatabase, email: str) -> User | None:
    user_data = await User.find_by_email(db=db, email=email)

    if not user_data:
        return None
    try:

        return User.model_validate(user_data)
    except ValidationError:
        return None


async def authenticate(
    *, db: AsyncIOMotorDatabase, email: str, password: str
) -> User | None:
    db_user = await get_user_by_email(db=db, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


async def create_item(
    *, db: AsyncIOMotorDatabase, item_in: ItemCreate, owner_id: uuid.UUID
) -> Item:
    item_data = item_in.model_dump()
    item_data["owner_id"] = owner_id

    result = await Item(**item_data).save(db)
    created_item = await Item.find_one(db, {"_id": result.inserted_id})
    return Item.model_validate(created_item)
