"""Routes parse and delegate; they hold no rules. The request-bound dependencies
live here, so nothing below `services/` needs the web framework."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from ..clock import Clock, get_clock
from ..db import get_session

SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]
