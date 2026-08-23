from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import User

DEFAULT_USER_EMAIL = "local@papertrail.dev"
DEFAULT_USER_NAME = "Local User"


def get_or_create_default_user(db: Session) -> User:
    """Return the single local user, creating it on first use.

    Papertrail has no auth layer, so every request lazily resolves the same
    user row. Concurrent requests can reach this together on a fresh database
    (the frontend loads /papers/ and /discover/ in parallel), and sync FastAPI
    endpoints run on separate threadpool threads with their own sessions.
    A plain check-then-insert therefore races and one caller loses on the
    users.email unique constraint. Let the database arbitrate instead: attempt
    the insert, and treat a uniqueness violation as "another request already
    created it" and re-read the winner.
    """
    user = db.query(User).filter(User.email == DEFAULT_USER_EMAIL).first()
    if user:
        return user

    user = User(email=DEFAULT_USER_EMAIL, name=DEFAULT_USER_NAME)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(User).filter(User.email == DEFAULT_USER_EMAIL).one()

    db.refresh(user)
    return user
