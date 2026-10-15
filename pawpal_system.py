"""PawPal+ core classes (skeleton). Mirrors diagrams/uml_draft.mmd."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time


@dataclass
class CareTask:
    """One dated instance of a routine, e.g. "Feed Luna today at 8 AM"."""

    task_id: int
    routine_id: int
    title: str
    scheduled_date_time: datetime
    completion_status: bool = False

    def set_completion_status(self, completion_status: bool) -> None:
        """Set Completed (True) or Not Completed (False); no toggling."""
        pass

    def reschedule(self, new_date_time: datetime) -> None:
        """Move only this task to a new date and time."""
        pass


@dataclass
class CareRoutine:
    """A recurring care activity for one pet, e.g. "Feed Luna every day at 8 AM"."""

    routine_id: int
    pet_id: int
    title: str
    frequency: str  # user-entered; may need an interval later
    scheduled_time: time
    start_date: date
    is_active: bool = True
    tasks: list[CareTask] = field(default_factory=list)

    def update_routine(self, fields: dict) -> None:
        """Update the routine and regenerate its future incomplete tasks."""
        pass

    def generate_tasks(self, range_start: date, range_end: date) -> list[CareTask]:
        """Create tasks for the date range, skipping ones that already exist."""
        pass

    def get_tasks(self) -> list[CareTask]:
        """Return this routine's tasks."""
        pass


@dataclass
class Pet:
    """A pet profile and its care routines."""

    pet_id: int
    name: str
    species: str
    breed: str = ""
    birthday: date | None = None
    photo: str = ""  # file path
    pet_needs: str = ""
    care_instructions: str = ""
    routines: list[CareRoutine] = field(default_factory=list)

    def update_profile(self, fields: dict) -> None:
        """Update only the profile fields that are provided."""
        pass

    def get_care_routines(self) -> list[CareRoutine]:
        """Return this pet's (active) routines."""
        pass

    def add_routine(self, routine: CareRoutine) -> None:
        """Attach a routine to this pet."""
        pass

    def remove_routine(self, routine: CareRoutine) -> None:
        """Set is_active = False and delete incomplete tasks; keep completed ones."""
        pass


@dataclass
class PetOwner:
    """The user: owns pets and views today's tasks across all of them."""

    owner_id: int
    name: str
    email: str
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        pass

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner."""
        pass

    def get_all_tasks(self) -> list[CareTask]:
        """Collect tasks across all pets' routines."""
        pass

    def view_todays_tasks(self) -> list[CareTask]:
        """Today's tasks plus overdue incomplete ones, sorted by time."""
        pass
