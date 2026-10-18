"""PawPal+ core classes and scheduling logic, matching diagrams/uml_final.mmd."""

from __future__ import annotations

import calendar
from copy import copy
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from itertools import count
from typing import Iterator

CARE_CATEGORIES = ("Other", "Exercise", "Play", "Training", "Grooming", "Meal")

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
    """Apply allowed fields and raise ValueError for unknown names."""
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
    routine_id: int | None = None  # assigned when attached to a routine
    duration_minutes: int = 30
    priority: Priority = Priority.MEDIUM
    completion_status: bool = False
    original_date_time: datetime = field(init=False)  # never changes

    def __post_init__(self) -> None:
        """Validate task values and remember the first scheduled slot."""
        if isinstance(self.duration_minutes, bool) or not isinstance(self.duration_minutes, int):
            raise ValueError("duration_minutes must be a whole number")
        if self.duration_minutes < 1:
            raise ValueError("duration_minutes must be at least 1")
        if not isinstance(self.priority, Priority):
            raise ValueError("priority must be a Priority value")
        self.original_date_time = self.scheduled_date_time

    @property
    def is_rescheduled(self) -> bool:
        """Return whether the scheduled time differs from the original slot."""
        return self.scheduled_date_time != self.original_date_time

    @property
    def end_date_time(self) -> datetime:
        """When the task ends: its scheduled time plus its duration."""
        return self.scheduled_date_time + timedelta(minutes=self.duration_minutes)

    def set_completion_status(self, completion_status: bool) -> None:
        """Set completion directly without generating another occurrence."""
        self.completion_status = completion_status

    def reschedule(self, new_date_time: datetime) -> None:
        """Move this occurrence while preserving its original scheduled slot."""
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
    pet_id: int | None = None  # assigned when attached to a pet
    is_active: bool = True
    tasks: list[CareTask] = field(default_factory=list)
    category: str = "Other"

    _EDITABLE = {
        "title", "frequency", "scheduled_time", "start_date",
        "interval", "end_date", "is_active", "duration_minutes", "priority", "category",
    }

    def __post_init__(self) -> None:
        """Validate the routine and link any supplied tasks without replacing them."""
        self._validate()
        self.tasks = list(self.tasks)
        for task in self.tasks:
            if not isinstance(task, CareTask):
                raise ValueError("tasks must contain CareTask instances")
            if task.routine_id is not None and task.routine_id != self.routine_id:
                raise ValueError("task already belongs to another routine")
        for task in self.tasks:
            task.routine_id = self.routine_id

    def _validate(self) -> None:
        """Validate recurrence, duration and care classification."""
        if not isinstance(self.title, str):
            raise ValueError("title must be a string")
        if not isinstance(self.frequency, Frequency):
            raise ValueError("frequency must be a Frequency value")
        if not isinstance(self.scheduled_time, time):
            raise ValueError("scheduled_time must be a time")
        if not isinstance(self.start_date, date) or isinstance(self.start_date, datetime):
            raise ValueError("start_date must be a date without a time")
        if self.end_date is not None and (
            not isinstance(self.end_date, date) or isinstance(self.end_date, datetime)
        ):
            raise ValueError("end_date must be a date without a time, or None")
        if isinstance(self.interval, bool) or not isinstance(self.interval, int):
            raise ValueError("interval must be a whole number")
        if self.interval < 1:
            raise ValueError("interval must be at least 1")
        if isinstance(self.duration_minutes, bool) or not isinstance(self.duration_minutes, int):
            raise ValueError("duration_minutes must be a whole number")
        if self.duration_minutes < 1:
            raise ValueError("duration_minutes must be at least 1")
        if not isinstance(self.priority, Priority):
            raise ValueError("priority must be a Priority value")
        if not isinstance(self.is_active, bool):
            raise ValueError("is_active must be a boolean")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        if self.category not in CARE_CATEGORIES:
            raise ValueError("Choose a supported care category.")

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
        """Apply edits and replace future pending tasks; keep history, overdue tasks and reschedules."""
        updated = copy(self)
        _apply_fields(updated, fields, self._EDITABLE)
        updated._validate()
        now = datetime.now()
        updated.tasks = [
            t for t in self.tasks
            if t.completion_status or t.is_rescheduled or t.scheduled_date_time <= now
        ]
        updated.generate_tasks(_today(), date.max)
        # Commit only after validation and task generation have both succeeded.
        for name in fields:
            setattr(self, name, getattr(updated, name))
        self.tasks[:] = updated.tasks

    def generate_tasks(
        self, range_start: date, range_end: date, *, first_only: bool = True
    ) -> list[CareTask]:
        """Seed one pending task, or fill a bounded calendar range when first_only is False."""
        if not self.is_active or (
            first_only and any(not task.completion_status for task in self.tasks)
        ):
            return []
        # Clamp the range: never before today or start_date, never after end_date.
        range_start = max(range_start, _today(), self.start_date)
        if self.end_date is not None:
            range_end = min(range_end, self.end_date)
        existing = {t.original_date_time for t in self.tasks}
        created = []
        for day in self._occurrence_dates(range_start, range_end):
            slot = datetime.combine(day, self.scheduled_time)
            if slot in existing:
                continue
            created.append(self._create_task(slot))
            existing.add(slot)
            if first_only:
                break
        return created

    def add_task(self, scheduled_date_time: datetime) -> CareTask:
        """Add one task at an exact date and time, even in the past; reuses a task already in that slot."""
        if not self.is_active:
            raise ValueError("cannot add a task to an inactive routine")
        for task in self.tasks:
            if task.original_date_time == scheduled_date_time:
                return task
        return self._create_task(scheduled_date_time)

    def _create_task(self, scheduled_date_time: datetime) -> CareTask:
        """Create and store a task without checking for an existing occurrence."""
        task = CareTask(
            title=self.title,
            scheduled_date_time=scheduled_date_time,
            routine_id=self.routine_id,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
        )
        self.tasks.append(task)
        return task

    def complete_task(self, task: CareTask) -> CareTask | None:
        """Complete a task and create or reuse its successor; reject early recurring care."""
        if not any(t is task for t in self.tasks):
            raise ValueError("task does not belong to this routine")
        today = _today()
        if (
            self.frequency is not Frequency.ONCE
            and not task.completion_status
            and task.scheduled_date_time.date() > today
        ):
            raise ValueError("Repeating tasks can only be completed on their scheduled date or later.")
        was_completed = task.completion_status
        task.set_completion_status(True)
        if not self.is_active or self.frequency is Frequency.ONCE:
            return None

        if self.frequency is Frequency.MONTHLY:
            next_date = _add_months(today, self.interval)
        else:
            days = self.interval * (1 if self.frequency is Frequency.DAILY else 7)
            next_date = today + timedelta(days=days)
        if next_date < self.start_date or (self.end_date is not None and next_date > self.end_date):
            return None

        slot = datetime.combine(next_date, self.scheduled_time)
        successor = next(
            (
                t for t in self.tasks
                if t is not task and not t.completion_status and t.original_date_time == slot
            ),
            None,
        )
        if was_completed or successor is not None:
            return successor
        # An earlier reschedule can leave the completed task's original slot here.
        return self._create_task(slot)

    def get_tasks(self) -> list[CareTask]:
        """Return a copy of the routine's task list."""
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

    def __post_init__(self) -> None:
        """Validate and attach supplied routines using the usual attachment rules."""
        initial_routines = list(self.routines)
        for routine in initial_routines:
            if not isinstance(routine, CareRoutine):
                raise ValueError("routines must contain CareRoutine instances")
            if routine.pet_id is not None and routine.pet_id != self.pet_id:
                raise ValueError("routine already belongs to another pet")
        self.routines = []
        for routine in initial_routines:
            self.add_routine(routine)

    def update_profile(self, fields: dict) -> None:
        """Apply provided profile fields, rejecting unknown names."""
        _apply_fields(self, fields, self._EDITABLE)

    def get_care_routines(self) -> list[CareRoutine]:
        """Return a copy of all routines, including inactive ones."""
        return list(self.routines)

    def add_routine(self, routine: CareRoutine) -> None:
        """Attach a routine to this pet, set routine.pet_id and generate its first pending task."""
        if routine.pet_id is not None and routine.pet_id != self.pet_id:
            raise ValueError("routine already belongs to another pet")
        routine.pet_id = self.pet_id
        if routine not in self.routines:
            self.routines.append(routine)
        routine.generate_tasks(_today(), date.max)

    def remove_routine(self, routine: CareRoutine) -> None:
        """Set is_active = False and delete incomplete tasks; keep completed ones."""
        if routine not in self.routines:
            raise ValueError("routine does not belong to this pet")
        routine.is_active = False
        routine.tasks[:] = [t for t in routine.tasks if t.completion_status]


@dataclass
class PetOwner:
    """The user: owns pets and stores optional care time limits."""

    owner_id: int = field(default_factory=lambda: next(_owner_ids), kw_only=True)
    name: str
    email: str
    pets: list[Pet] = field(default_factory=list)
    available_start: time | None = None
    available_end: time | None = None
    daily_care_minutes: int | None = None

    def __post_init__(self) -> None:
        self.set_preferences(self.available_start, self.available_end, self.daily_care_minutes)

    def set_preferences(
        self,
        available_start: time | None = None,
        available_end: time | None = None,
        daily_care_minutes: int | None = None,
    ) -> None:
        """Validate and replace optional time limits without partial updates."""
        if (available_start is None) != (available_end is None):
            raise ValueError("Set both the availability start and end time, or leave both unset.")
        if available_start is not None:
            if not isinstance(available_start, time) or not isinstance(available_end, time):
                raise ValueError("Availability start and end must be times.")
            if available_end <= available_start:
                raise ValueError("Availability end must be after the start on the same day.")
        if daily_care_minutes is not None and (
            isinstance(daily_care_minutes, bool)
            or not isinstance(daily_care_minutes, int)
            or daily_care_minutes < 0
        ):
            raise ValueError("Daily care time must be a nonnegative whole number of minutes.")
        self.available_start = available_start
        self.available_end = available_end
        self.daily_care_minutes = daily_care_minutes

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet unless it is already listed."""
        if pet not in self.pets:
            self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove an owned pet or raise ValueError if it is not listed."""
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
        """Find the pet whose routines contain the task's routine ID."""
        for pet in self.pets:
            for routine in pet.routines:
                if routine.routine_id == task.routine_id:
                    return pet
        raise LookupError(f"no pet found for task {task.task_id}")

    def get_routine_for_task(self, task: CareTask) -> CareRoutine:
        """Find a routine by the task's routine ID or raise LookupError."""
        for pet in self.pets:
            for routine in pet.routines:
                if routine.routine_id == task.routine_id:
                    return routine
        raise LookupError(f"no routine found for task {task.task_id}")

    def view_todays_tasks(self) -> list[CareTask]:
        """Only tasks dated today, sorted by time."""
        return Scheduler(self).todays_tasks()

    def view_overdue_tasks(self) -> list[CareTask]:
        """Return incomplete tasks from earlier dates in schedule order."""
        return Scheduler(self).overdue_tasks()

    def clear_overdue_tasks(self) -> None:
        """Delete overdue incomplete tasks and restart affected active repeating routines today or later."""
        overdue_ids = {t.task_id for t in self.view_overdue_tasks()}
        for pet in self.pets:
            for routine in pet.routines:
                removed = any(t.task_id in overdue_ids for t in routine.tasks)
                routine.tasks[:] = [t for t in routine.tasks if t.task_id not in overdue_ids]
                if removed and routine.frequency is not Frequency.ONCE:
                    routine.generate_tasks(_today(), date.max)


@dataclass
class DailyPlan:
    """One day's selections, explanations and minute totals; None means no care time limit."""

    included: list[CareTask] = field(default_factory=list)
    excluded: list[CareTask] = field(default_factory=list)
    reasons: dict[int, str] = field(default_factory=dict)
    completed_minutes: int = 0
    planned_minutes: int = 0
    remaining_minutes: int | None = None


@dataclass
class Scheduler:
    """Organizes tasks across an owner's pets, getting them via PetOwner.get_all_tasks()."""

    owner: PetOwner

    def sort_by_time(self, tasks: list[CareTask] | None = None) -> list[CareTask]:
        """Sort supplied or owner-wide tasks by datetime, then priority (high first), then title."""
        if tasks is None:
            tasks = self.owner.get_all_tasks()
        return sorted(tasks, key=lambda t: (t.scheduled_date_time, -t.priority.rank, t.title))

    def get_tasks(self) -> list[CareTask]:
        """Return all pets' tasks in schedule order, including completed care."""
        return self.sort_by_time()

    def _sorted_where(self, keep) -> list[CareTask]:
        return self.sort_by_time([t for t in self.owner.get_all_tasks() if keep(t)])

    def tasks_on(self, day: date) -> list[CareTask]:
        """Return pending and completed tasks dated on the given day in schedule order."""
        return self._sorted_where(lambda t: t.scheduled_date_time.date() == day)

    def todays_tasks(self) -> list[CareTask]:
        """Tasks dated today (completed or not), sorted by time."""
        return self.tasks_on(_today())

    def generate_schedule(self, day: date) -> DailyPlan:
        """Create missing occurrences for the selected day, then build its explained plan."""
        for pet in self.owner.pets:
            for routine in pet.routines:
                routine.generate_tasks(day, day, first_only=False)
        return self.build_daily_plan(day)

    def build_daily_plan(self, day: date) -> DailyPlan:
        """Explain all existing care for a day, applying the owner's optional time limits."""
        tasks = self.tasks_on(day)
        completed = [task for task in tasks if task.completion_status]
        completed_minutes = sum(task.duration_minutes for task in completed)
        care_time_limit = self.owner.daily_care_minutes
        plan = DailyPlan(
            included=list(completed),
            reasons={task.task_id: "Already completed." for task in completed},
            completed_minutes=completed_minutes,
            remaining_minutes=None if care_time_limit is None else max(0, care_time_limit - completed_minutes),
        )
        window_start = window_end = None
        if self.owner.available_start is not None:
            window_start = datetime.combine(day, self.owner.available_start)
            window_end = datetime.combine(day, self.owner.available_end)

        pending = sorted(
            (task for task in tasks if not task.completion_status),
            key=lambda task: (-task.priority.rank, task.scheduled_date_time, task.title, task.task_id),
        )
        for task in pending:
            if window_start is not None and not (
                window_start <= task.scheduled_date_time and task.end_date_time <= window_end
            ):
                plan.excluded.append(task)
                plan.reasons[task.task_id] = (
                    f"Outside your available hours ({window_start:%H:%M}–{window_end:%H:%M}); "
                    f"the full {task.duration_minutes}-minute task must fit."
                )
                continue
            if plan.remaining_minutes is not None and task.duration_minutes > plan.remaining_minutes:
                plan.excluded.append(task)
                plan.reasons[task.task_id] = (
                    f"Needs {task.duration_minutes} minutes, but only {plan.remaining_minutes} minutes "
                    "remain in your daily care time limit."
                )
                continue

            reasons = [f"{task.priority.value.title()} priority", "scheduled care"]
            if window_start is not None:
                reasons.append(f"within your available hours ({window_start:%H:%M}–{window_end:%H:%M})")
            if plan.remaining_minutes is not None:
                reasons.append(
                    f"fits the remaining {plan.remaining_minutes} minutes ({task.duration_minutes} minutes needed)"
                )
            plan.reasons[task.task_id] = "; ".join(reasons) + "."
            plan.included.append(task)
            plan.planned_minutes += task.duration_minutes
            if plan.remaining_minutes is not None:
                plan.remaining_minutes -= task.duration_minutes

        plan.included = self.sort_by_time(plan.included)
        plan.excluded = self.sort_by_time(plan.excluded)
        return plan

    def overdue_tasks(self) -> list[CareTask]:
        """Incomplete tasks dated before today, sorted by time."""
        today = _today()
        return self._sorted_where(
            lambda t: not t.completion_status and t.scheduled_date_time.date() < today
        )

    def upcoming_tasks(self, days: int = 7) -> list[CareTask]:
        """Incomplete tasks from today through the next `days` days, sorted by time."""
        today = _today()
        last = today + timedelta(days=days)
        return self._sorted_where(
            lambda t: not t.completion_status and today <= t.scheduled_date_time.date() <= last
        )

    def filter_tasks(
        self, pet_name: str | None = None, completed: bool | None = None
    ) -> list[CareTask]:
        """Tasks for one pet (by name, case-insensitive) and/or by completion status."""
        wanted = pet_name.casefold() if pet_name is not None else None
        pet_of_routine = {
            routine.routine_id: pet.name.casefold()
            for pet in self.owner.pets
            for routine in pet.routines
        }

        def keep(task: CareTask) -> bool:
            if wanted is not None and pet_of_routine.get(task.routine_id) != wanted:
                return False
            return completed is None or task.completion_status == completed

        return self._sorted_where(keep)

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

    def conflict_warning(self, group: list[CareTask]) -> str:
        """Describe a detected conflict group with each pet, task and start time."""
        names = ", ".join(
            f"{self.owner.get_pet_for_task(task).name}: {task.title} ({task.scheduled_date_time:%H:%M})"
            for task in group
        )
        return f"Time conflict: {names}"

    def next_free_slot(
        self,
        duration: int,
        after: datetime,
        exclude_task_id: int | None = None,
    ) -> datetime:
        """Suggest the earliest start at or after `after` with `duration` free minutes; changes no tasks."""
        if duration <= 0:
            raise ValueError("duration must be greater than zero")

        needed = timedelta(minutes=duration)
        busy_tasks = [
            t for t in self.get_tasks()
            if not t.completion_status and t.task_id != exclude_task_id
        ]

        slot_start = after
        for task in busy_tasks:
            if task.end_date_time <= slot_start:
                continue
            if slot_start + needed <= task.scheduled_date_time:
                break
            slot_start = task.end_date_time
        return slot_start

    def mark_task_complete(self, task: CareTask) -> CareTask | None:
        """Complete care through its routine and return the next occurrence, if any."""
        return self.owner.get_routine_for_task(task).complete_task(task)
