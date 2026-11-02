from fastapi import APIRouter

from ..schemas import SettingsOut
from . import SettingsDep

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsOut, summary="The rules in force (read-only)")
def get_settings_(settings: SettingsDep) -> SettingsOut:
    return SettingsOut(inspection_required_for=settings.inspection_types,
                       stall_after_minutes=settings.stall_after_minutes)


