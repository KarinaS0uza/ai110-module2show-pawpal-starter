"""PawPal+ core classes. Mirrors diagrams/uml_draft.mmd, plus a Scheduler."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from itertools import count
from typing import Iterator

# How many days ahead tasks are generated; run when a routine is added/updated and when the app opens.
GENERATION_DAYS = 90

# IDs are auto-assigned from one counter per class; nobody types them.
# Possible future improvement: save data between sessions (for example one JSON file);
# on load, each counter would restart above the highest saved ID.
_task_ids = count(1)
_routine_ids = count(1)
_pet_ids = count(1)
_owner_ids = count(1)


def _today() -> date:
    """Today's date; a single place to patch when testing."""
    return date.today()


def _add_months(start: date, months: int) -> date:
    """Add months to a date, clamping the day (Jan 31 + 1 month = Feb 28/29)."""
    year_offset, month_index = divmod(start.month - 1 + months, 12)
    year, month = start.year + year_offset, month_index + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _apply_fields(obj: object, fields: dict, allowed: set[str]) -> None:
    """Set only known attributes; unknown keys raise instead of creating bad attributes."""
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    for name, value in fields.items():
        setattr(obj, name, value)


class Frequency(Enum):
    """How often a routine repeats; combined with CareRoutine.interval."""

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Priority(Enum):
    """How important a routine's tasks are; used to order tasks at the same time."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        """Sort order: a higher number means more important."""
        return list(Priority).index(self)


@dataclass
class CareTask:
    """One dated instance of a routine, e.g. "Feed Luna today at 8 AM"."""

    task_id: int = field(default_factory=lambda: next(_task_ids), kw_only=True)
    title: str
    scheduled_date_time: datetime
    routine_id: int | None = None  # set by CareRoutine.generate_tasks()
    duration_minutes: int = 30
    priority: Priority = Priority.MEDIUM
    completion_status: bool = False
    original_date_time: datetime = field(init=False)  # never changes

    def __post_init__(self) -> None:
        """Remember the first scheduled slot so rescheduling can be detected."""
        self.original_date_time = self.scheduled_date_time

    @property
    def is_rescheduled(self) -> bool:
        """True once the user has moved this task off its original slot."""
        return self.scheduled_date_time != self.original_date_time

    @property
    def end_date_time(self) -> datetime:
        """When the task ends: its scheduled time plus its duration."""
        return self.scheduled_date_time + timedelta(minutes=self.duration_minutes)

    def set_completion_status(self, completion_status: bool) -> None:
        """Set Completed (True) or Not Completed (False); no toggling."""
        self.completion_status = completion_status

    def reschedule(self, new_date_time: datetime) -> None:
        """Move only this task: change scheduled_date_time, never original_date_time."""
        self.scheduled_date_time = new_date_time


@dataclass
class CareRoutine:
    """A recurring care activity for one pet, e.g. "Feed Luna every day at 8 AM"."""

    routine_id: int = field(default_factory=lambda: next(_routine_ids), kw_only=True)
    title: str
    frequency: Frequency
    scheduled_time: time
    start_date: date
    interval: int = 1  # "every N" days/weeks/months
    duration_minutes: int = 30
    priority: Priority = Priority.MEDIUM
    end_date: date | None = None  # None = repeats until removed
    pet_id: int | None = None  # set by Pet.add_routine()
    is_active: bool = True
    tasks: list[CareTask] = field(default_factory=list)

    _EDITABLE = {
        "title", "frequency", "scheduled_time", "start_date",
        "interval", "end_date", "is_active", "duration_minutes", "priority",
    }

    def __post_init__(self) -> None:
        """Reject an invalid interval or end_date as soon as the routine is created."""
        self._validate()

    def _validate(self) -> None:
        """Raise ValueError if interval or duration is below 1, or end_date is before start_date."""
        if self.interval < 1:
            raise ValueError("interval must be at least 1")
        if self.duration_minutes < 1:
            raise ValueError("duration_minutes must be at least 1")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")

    def _occurrence_dates(self, range_start: date, range_end: date) -> Iterator[date]:
        """Dates this routine falls on within [range_start, range_end], anchored on start_date."""
        if self.frequency is Frequency.ONCE:
            if range_start <= self.start_date <= range_end:
                yield self.start_date
        elif self.frequency in (Frequency.DAILY, Frequency.WEEKLY):
            step_days = self.interval * (1 if self.frequency is Frequency.DAILY else 7)
            steps_to_skip = 0
            if range_start > self.start_date:
                steps_to_skip = -(-(range_start - self.start_date).days // step_days)  # ceil
            current = self.start_date + timedelta(days=steps_to_skip * step_days)
            while current <= range_end:
                yield current
                current += timedelta(days=step_days)
        else:  # MONTHLY, counted from start_date so day-of-month clamping does not accumulate
            n = 0
            while True:
                current = _add_months(self.start_date, n * self.interval)
                if current > range_end:
                    return
                if current >= range_start:
                    yield current
                n += 1

    def update_routine(self, fields: dict) -> None:
        """Apply edits, then regenerate only future, incomplete, unrescheduled tasks."""
        snapshot = {name: getattr(self, name) for name in self._EDITABLE}
        try:
            _apply_fields(self, fields, self._EDITABLE)
            self._validate()
        except ValueError:
            for name, value in snapshot.items():
                setattr(self, name, value)
            raise
        now = datetime.now()
        self.tasks[:] = [
            t for t in self.tasks
            if t.completion_status or t.is_rescheduled or t.scheduled_date_time <= now
        ]
        today = _today()
        self.generate_tasks(today, today + timedelta(days=GENERATION_DAYS))

    def generate_tasks(self, range_start: date, range_end: date) -> list[CareTask]:
        """Create tasks in the clamped range, skipping slots that already exist."""
        if not self.is_active:
            return []
        # Clamp the range: never before today or start_date, never after end_date.
        range_start = max(range_start, _today(), self.start_date)
        if self.end_date is not None:
            range_end = min(range_end, self.end_date)
        existing = {t.original_date_time for t in self.tasks}
        new_tasks = []
        for day in self._occurrence_dates(range_start, range_end):
            slot = datetime.combine(day, self.scheduled_time)
            if slot in existing:
                continue
            new_tasks.append(
                CareTask(
                    title=self.title,
                    scheduled_date_time=slot,
                    routine_id=self.routine_id,
                    duration_minutes=self.duration_minutes,
                    priority=self.priority,
                )
            )
        self.tasks.extend(new_tasks)
        return new_tasks

    def get_tasks(self) -> list[CareTask]:
        """Return this routine's tasks."""
        return list(self.tasks)


@dataclass
class Pet:
    """A pet profile and its care routines."""

    pet_id: int = field(default_factory=lambda: next(_pet_ids), kw_only=True)
    name: str
    species: str
    breed: str = ""
    birthday: date | None = None
    photo: str = ""  # file path
    pet_needs: str = ""
    care_instructions: str = ""
    routines: list[CareRoutine] = field(default_factory=list)

    _EDITABLE = {
        "name", "species", "breed", "birthday", "photo", "pet_needs", "care_instructions",
    }

    def update_profile(self, fields: dict) -> None:
        """Update only the profile fields that are provided."""
        _apply_fields(self, fields, self._EDITABLE)

    def get_care_routines(self) -> list[CareRoutine]:
        """Return all routines, active and inactive."""
        return list(self.routines)

    def add_routine(self, routine: CareRoutine) -> None:
        """Attach a routine to this pet, set routine.pet_id and generate its upcoming tasks."""
        if routine.pet_id is not None and routine.pet_id != self.pet_id:
            raise ValueError("routine already belongs to another pet")
        routine.pet_id = self.pet_id
        if routine not in self.routines:
            self.routines.append(routine)
        today = _today()
        routine.generate_tasks(today, today + timedelta(days=GENERATION_DAYS))

    def remove_routine(self, routine: CareRoutine) -> None:
        """Set is_active = False and delete incomplete tasks; keep completed ones."""
        if routine not in self.routines:
            raise ValueError("routine does not belong to this pet")
        routine.is_active = False
        routine.tasks[:] = [t for t in routine.tasks if t.completion_status]


@dataclass
class PetOwner:
    """The user: owns pets and views today's and overdue tasks across all of them."""

    owner_id: int = field(default_factory=lambda: next(_owner_ids), kw_only=True)
    name: str
    email: str
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        if pet not in self.pets:
            self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner."""
        if pet not in self.pets:
            raise ValueError("pet does not belong to this owner")
        self.pets.remove(pet)

    def get_all_tasks(self) -> list[CareTask]:
        """Collect tasks across all pets' routines (including inactive routines)."""
        return [
            task
            for pet in self.pets
            for routine in pet.get_care_routines()
            for task in routine.get_tasks()
        ]

    def get_pet_for_task(self, task: CareTask) -> Pet:
        """Find a task's pet: task.routine_id -> routine.pet_id -> pet."""
        for pet in self.pets:
            for routine in pet.routines:
                if routine.routine_id == task.routine_id:
                    return pet
        raise LookupError(f"no pet found for task {task.task_id}")

    def view_todays_tasks(self) -> list[CareTask]:
        """Only tasks dated today, sorted by time."""
        return Scheduler(self).todays_tasks()

    def view_overdue_tasks(self) -> list[CareTask]:
        """Incomplete tasks dated before today, sorted by time (separate tab)."""
        return Scheduler(self).overdue_tasks()

    def clear_overdue_tasks(self) -> None:
        """Delete all overdue incomplete tasks."""
        overdue_ids = {t.task_id for t in self.view_overdue_tasks()}
        for pet in self.pets:
            for routine in pet.routines:
                routine.tasks[:] = [t for t in routine.tasks if t.task_id not in overdue_ids]


@dataclass
class Scheduler:
    """Organizes tasks across an owner's pets, getting them via PetOwner.get_all_tasks()."""

    owner: PetOwner

    @staticmethod
    def _by_time(tasks: list[CareTask]) -> list[CareTask]:
        """Sort tasks by scheduled time, then highest priority first, then title."""
        return sorted(tasks, key=lambda t: (t.scheduled_date_time, -t.priority.rank, t.title))

    def get_tasks(self) -> list[CareTask]:
        """All tasks across all pets, sorted by time."""
        return self._by_time(self.owner.get_all_tasks())

    def tasks_on(self, day: date) -> list[CareTask]:
        """Tasks dated on the given day, sorted by time."""
        return [t for t in self.get_tasks() if t.scheduled_date_time.date() == day]

    def todays_tasks(self) -> list[CareTask]:
        """Tasks dated today (completed or not), sorted by time."""
        return self.tasks_on(_today())

    def overdue_tasks(self) -> list[CareTask]:
        """Incomplete tasks dated before today, sorted by time."""
        today = _today()
        return [
            t for t in self.get_tasks()
            if not t.completion_status and t.scheduled_date_time.date() < today
        ]

    def upcoming_tasks(self, days: int = 7) -> list[CareTask]:
        """Incomplete tasks from today through the next `days` days, sorted by time."""
        today = _today()
        last = today + timedelta(days=days)
        return [
            t for t in self.get_tasks()
            if not t.completion_status and today <= t.scheduled_date_time.date() <= last
        ]

    def filter_tasks(
        self, pet_name: str | None = None, completed: bool | None = None
    ) -> list[CareTask]:
        """Tasks for one pet (by name, case-insensitive) and/or by completion status."""
        tasks = self.get_tasks()
        if pet_name is not None:
            wanted = pet_name.casefold()
            tasks = [t for t in tasks if self.owner.get_pet_for_task(t).name.casefold() == wanted]
        if completed is not None:
            tasks = [t for t in tasks if t.completion_status == completed]
        return tasks

    def find_conflicts(self) -> list[list[CareTask]]:
        """Groups of incomplete tasks whose time ranges overlap."""
        groups: list[list[CareTask]] = []
        current: list[CareTask] = []
        current_end: datetime | None = None
        for task in self.get_tasks():
            if task.completion_status:
                continue
            if current and task.scheduled_date_time < current_end:
                current.append(task)
                current_end = max(current_end, task.end_date_time)
            else:
                if len(current) > 1:
                    groups.append(current)
                current, current_end = [task], task.end_date_time
        if len(current) > 1:
            groups.append(current)
        return groups
