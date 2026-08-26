from fastapi import APIRouter, Body, HTTPException

from app.diagnostics import build_health_details
from app.services.app_settings import (
    SettingsValidationError,
    describe_settings,
    reset_settings,
    update_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings():
    return describe_settings()


@router.put("")
def put_settings(patch: dict = Body(...)):
    """A partial update. An absent field is unchanged; null on a workflow
    model means that step should follow the chat model."""
    try:
        return update_settings(patch)
    except SettingsValidationError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=f"The settings file could not be written: {error}",
        )


@router.post("/reset")
def post_reset_settings():
    try:
        return reset_settings()
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=f"The settings file could not be removed: {error}",
        )


@router.post("/verify")
def verify_credentials():
    """Send one minimal request to each configured provider.

    This is the only way to tell a well-formed credential from a working one.
    It costs a few tokens, so it never runs on its own.
    """
    return build_health_details(probe=True)
