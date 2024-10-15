import os
import datetime
import time
import logging
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Date,
    Time,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, joinedload
from contextlib import contextmanager
import utils
from dotenv import load_dotenv

load_dotenv()

# Initialize logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", logging.INFO))
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def add_getitem(cls):
    def __getitem__(self, key):
        return getattr(self, key)

    cls.__getitem__ = __getitem__
    return cls


@add_getitem
class Apartment(Base):
    __tablename__ = "apartments"
    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, nullable=False)
    description = Column(String)
    users = relationship("User", back_populates="apartment", lazy="joined")


@add_getitem
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, nullable=False)
    role = Column(
        String, default="apartment_admin"
    )  # Can be 'apartment_admin', 'admin', or 'guest'
    creator_id = Column(String)
    apartment_id = Column(Integer, ForeignKey("apartments.id"))
    apartment = relationship("Apartment", back_populates="users", lazy="joined")
    pins = relationship("Pin", back_populates="user")
    rfids = relationship("Rfid", back_populates="user", foreign_keys="[Rfid.user_id]")
    tokens = relationship("Token", back_populates="user")
    login_codes = relationship("LoginCode", back_populates="user")
    recurring_schedule = relationship("RecurringSchedule", back_populates="user")
    one_time_access = relationship("OneTimeAccess", back_populates="user")


@add_getitem
class Rfid(Base):
    __tablename__ = "rfids"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    hashed_uuid = Column(String, nullable=False)
    last_four_digits = Column(String(4), nullable=False)
    label = Column(String)
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow
    )  # utcnow is deprecated in newer versions, but this will be likely run on an older version of python
    user = relationship(
        "User", back_populates="rfids", foreign_keys=[user_id], lazy="joined"
    )


@add_getitem
class Pin(Base):
    __tablename__ = "pins"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    hashed_pin = Column(String, nullable=False)
    label = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="pins", lazy="joined")


@add_getitem
class Token(Base):
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token_hash = Column(String, nullable=False)
    expiration = Column(Integer, nullable=False)
    user = relationship("User", back_populates="tokens", lazy="joined")


@add_getitem
class LoginCode(Base):
    __tablename__ = "login_codes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    code_hash = Column(String, nullable=False)
    expiration = Column(Integer, nullable=False)
    user = relationship("User", back_populates="login_codes", lazy="joined")


@add_getitem
class RecurringSchedule(Base):
    __tablename__ = "recurring_schedules"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day_of_week = Column(Integer)  # 0 for Monday, 6 for Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    user = relationship("User", back_populates="recurring_schedule")


@add_getitem
class OneTimeAccess(Base):
    __tablename__ = "one_time_accesses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    access_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    user = relationship("User", back_populates="one_time_access")


def init_db():
    Base.metadata.create_all(bind=engine)


def add_apartment(number, description=None):
    with get_db() as db:
        new_apartment = Apartment(number=number, description=description)
        db.add(new_apartment)
        db.commit()
        db.refresh(new_apartment)
        logger.info(f"Apartment {number} added with ID {new_apartment.id}")
        return new_apartment


def add_user(user):
    with get_db() as db:
        new_user = User(
            name=user.get("name"),
            email=user.get("email"),
            role=user.get("role", "apartment_admin"),
            creator_id=user.get("creator_id"),
            apartment_id=user.get("apartment_id"),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"User {new_user.email} added with ID {new_user.id}")

        return new_user


def get_user(identifier):
    with get_db() as db:
        user = None
        if isinstance(identifier, int):
            user = db.query(User).filter(User.id == identifier).first()
        elif isinstance(identifier, str):
            user = db.query(User).filter(User.email == identifier).first()
        return user


def get_apartment_by_number(number):
    with get_db() as db:
        return db.query(Apartment).filter(Apartment.number == number).first()


def get_apartment_users(apartment_id):
    with get_db() as db:
        apartment = db.query(Apartment).filter(Apartment.id == apartment_id).first()
        if apartment:
            return apartment.users
        return []


def save_user(user):
    with get_db() as db:
        existing_user = db.query(User).filter(User.email == user["email"]).first()
        if existing_user:
            for key, value in user.items():
                setattr(existing_user, key, value)
            db.commit()
            db.refresh(existing_user)
            logger.info(f"User {existing_user.email} updated")
            return existing_user
        else:
            return add_user(user)


def update_user_tokens(email, tokens):
    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()
        if user:
            for token_data in tokens:
                token_hash = utils.hash_secret(token_data["token"])
                expiration = token_data["expiration"]
                save_token(user.id, token_hash, expiration)
            logger.info(f"Tokens updated for user {email}")
            return user
        return None


def delete_token(token_id):
    with get_db() as db:
        token = db.query(Token).filter(Token.id == token_id).first()
        if token:
            db.delete(token)
            db.commit()
            logger.info(f"Token {token_id} deleted")
            return True
        return False


def update_user_login_codes(email, login_codes):
    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()
        if user:
            for code_data in login_codes:
                code_hash = utils.hash_secret(code_data["code"])
                expiration = code_data["expiration"]
                save_login_code(user.id, code_hash, expiration)
            logger.info(f"Login codes updated for user {email}")
            return user
        return None


def save_rfid(user_id, hashed_uuid, last_four_digits, label):
    with get_db() as db:
        new_rfid = Rfid(
            user_id=user_id,
            hashed_uuid=hashed_uuid,
            last_four_digits=last_four_digits,
            label=label,
        )
        db.add(new_rfid)
        db.commit()
        db.refresh(new_rfid)
        logger.info(f"RFID {label} registered for user {user_id}")
        return new_rfid


def delete_rfid(id):
    with get_db() as db:
        if rfid := db.query(Rfid).filter(Rfid.id == id).first():
            db.delete(rfid)
            db.commit()
            logger.info(f"RFID {rfid.label} deleted for user {rfid.user.email}")
            return True
        return False


def get_all_rfids():
    with get_db() as db:
        return db.query(Rfid).all()


def get_all_users():
    with get_db() as db:
        return db.query(User).all()


def get_user_by_login_code(login_code):
    code_hash = utils.hash_secret(login_code)
    current_time = int(time.time())

    with get_db() as db:
        user = (
            db.query(User)
            .join(LoginCode)
            .filter(
                LoginCode.code_hash == code_hash, LoginCode.expiration > current_time
            )
            .options(joinedload(User.apartment))
            .first()
        )

        return user


def is_login_code_expired(user_id, login_code, current_time):
    code_hash = utils.hash_secret(login_code)

    with get_db() as db:
        login_code = (
            db.query(LoginCode)
            .filter(LoginCode.user_id == user_id, LoginCode.code_hash == code_hash)
            .first()
        )

        return login_code is None or current_time > login_code.expiration


def remove_login_code(user_id, login_code):
    code_hash = utils.hash_secret(login_code)
    with get_db() as db:
        login_code = (
            db.query(LoginCode)
            .filter(LoginCode.user_id == user_id, LoginCode.code_hash == code_hash)
            .first()
        )
        if login_code:
            db.delete(login_code)
            db.commit()
            logger.info(f"Login code removed for user {user_id}")
            return True
        return False


def get_user_by_token(token):
    token_hash = utils.hash_secret(token)
    current_time = int(time.time())

    with get_db() as db:
        user = (
            db.query(User)
            .join(Token)
            .filter(Token.token_hash == token_hash, Token.expiration > current_time)
            .first()
        )

        return user


def update_user_login_and_tokens(email, login_codes, tokens):
    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()
        if user:
            update_user_login_codes(email, login_codes)
            update_user_tokens(email, tokens)
            logger.info(f"Login codes and tokens updated for user {email}")
            return user
        return None


def save_token(user_id, token_hash, expiration):
    with get_db() as db:
        new_token = Token(user_id=user_id, token_hash=token_hash, expiration=expiration)
        db.add(new_token)
        db.commit()
        db.refresh(new_token)
        logger.info(f"Token added for user {user_id}")
        return new_token


def save_login_code(user_id, code_hash, expiration):
    with get_db() as db:
        new_code = LoginCode(
            user_id=user_id, code_hash=code_hash, expiration=expiration
        )
        db.add(new_code)
        db.commit()
        db.refresh(new_code)
        logger.info(f"Login code added for user {user_id}")
        return new_code


def save_pin(user_id, hashed_pin, label):
    with get_db() as db:
        new_pin = Pin(user_id=user_id, hashed_pin=hashed_pin, label=label)
        db.add(new_pin)
        db.commit()
        db.refresh(new_pin)
        logger.info(f"Pin {label} added for user {user_id}")
        return new_pin


def update_pin(pin_id, hashed_pin, label):
    with get_db() as db:
        pin = db.query(Pin).filter(Pin.id == pin_id).first()
        if pin:
            pin.hashed_pin = hashed_pin
            pin.label = label
            db.commit()
            db.refresh(pin)
            logger.info(f"Pin {label} updated for pin {pin_id}")
            return pin
        return None


def remove_pin(pin_id):
    with get_db() as db:
        pin = db.query(Pin).filter(Pin.id == pin_id).first()
        if pin:
            db.delete(pin)
            db.commit()
            logger.info(f"Pin {pin.label} removed for pin {pin_id}")
            return True
        return False


def get_pins_by_user(user_id):
    with get_db() as db:
        return db.query(Pin).filter(Pin.user_id == user_id).all()


def get_pins_by_apartment(apartment_id):
    with get_db() as db:
        return db.query(Pin).join(User).filter(User.apartment_id == apartment_id).all()


def get_all_pins():
    with get_db() as db:
        return db.query(Pin).all()


def remove_user(user_id):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
            logger.info(f"User {user.email} deleted")
            return True
        return False


def get_all_apartments():
    with get_db() as db:
        return db.query(Apartment).all()


def update_apartment(apartment_id, updated_data):
    with get_db() as db:
        apartment = db.query(Apartment).filter(Apartment.id == apartment_id).first()
        if apartment:
            for key, value in updated_data.items():
                setattr(apartment, key, value)
            db.commit()
            db.refresh(apartment)
            logger.info(f"Apartment {apartment.number} updated")
            return apartment
        return None


def remove_apartment(apartment_id):
    with get_db() as db:
        apartment = db.query(Apartment).filter(Apartment.id == apartment_id).first()
        if apartment:
            db.delete(apartment)
            db.commit()
            logger.info(f"Apartment {apartment.number} deleted")
            return True
        return False


def get_apartment_pins(apartment_id):
    with get_db() as db:
        return db.query(Pin).join(User).filter(User.apartment_id == apartment_id).all()


def get_user_pins(user_id):
    with get_db() as db:
        return db.query(Pin).filter(Pin.user_id == user_id).all()


def get_apartment_rfids(apartment_id):
    with get_db() as db:
        return db.query(Rfid).join(User).filter(User.apartment_id == apartment_id).all()


def get_user_rfids(user_id):
    with get_db() as db:
        return db.query(Rfid).filter(Rfid.user_id == user_id).all()


def add_recurring_schedule(user_id, day_of_week, start_time, end_time):
    with get_db() as db:
        new_schedule = RecurringSchedule(
            user_id=user_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
        )
        db.add(new_schedule)
        db.commit()
        db.refresh(new_schedule)
        logger.info(f"Recurring guest schedule added for user {user_id}")
        return new_schedule


def add_one_time_access(user_id, access_date, start_time, end_time):
    with get_db() as db:
        new_access = OneTimeAccesses(
            user_id=user_id,
            access_date=access_date,
            start_time=start_time,
            end_time=end_time,
        )
        db.add(new_access)
        db.commit()
        db.refresh(new_access)
        logger.info(f"One-time guest access added for user {user_id}")
        return new_access


def get_one_time_accesses_by_user(user_id):
    with get_db() as db:
        return (
            db.query(OneTimeAccesses).filter(OneTimeAccesses.user_id == user_id).all()
        )


def get_recurring_schedules_by_user(user_id):
    with get_db() as db:
        return (
            db.query(RecurringSchedule)
            .filter(RecurringSchedule.user_id == user_id)
            .all()
        )


def get_recurring_schedule(schedule_id):
    with get_db() as db:
        return (
            db.query(RecurringSchedule)
            .filter(RecurringSchedule.id == schedule_id)
            .first()
        )


def get_one_time_access(access_id):
    with get_db() as db:
        return db.query(OneTimeAccesses).filter(OneTimeAccesses.id == access_id).first()


def remove_recurring_schedule(schedule_id):
    with get_db() as db:
        schedule = (
            db.query(RecurringSchedule)
            .filter(RecurringSchedule.id == schedule_id)
            .first()
        )
        if schedule:
            db.delete(schedule)
            db.commit()
            logger.info(f"Recurring guest schedule {schedule_id} removed")
            return True
        return False


def remove_one_time_access(access_id):
    with get_db() as db:
        access = (
            db.query(OneTimeAccesses).filter(OneTimeAccesses.id == access_id).first()
        )
        if access:
            db.delete(access)
            db.commit()
            logger.info(f"One-time guest access {access_id} removed")
            return True
        return False


def is_user_allowed_access(user_id):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.role == "guest":
            now = datetime.datetime.now()
            current_time = now.time()
            current_date = now.date()
            current_day = now.weekday()

            # Check recurring schedule
            recurring_access = (
                db.query(RecurringSchedule)
                .filter(
                    RecurringSchedule.user_id == user_id,
                    RecurringSchedule.day_of_week == current_day,
                    RecurringSchedule.start_time <= current_time,
                    RecurringSchedule.end_time >= current_time,
                )
                .first()
            )

            if recurring_access:
                return True

            # Check one-time access
            one_time_access = (
                db.query(OneTimeAccesses)
                .filter(
                    OneTimeAccesses.user_id == user_id,
                    OneTimeAccesses.access_date == current_date,
                    OneTimeAccesses.start_time <= current_time,
                    OneTimeAccesses.end_time >= current_time,
                )
                .first()
            )

            return one_time_access is not None

        return True  # Non-guest users are always allowed access
