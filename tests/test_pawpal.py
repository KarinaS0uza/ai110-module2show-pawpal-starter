from datetime import date, datetime, time, timedelta

import pytest

from pawpal_system import CareRoutine, CareTask, Frequency, Pet, PetOwner, Priority, Scheduler


def task_count(pet):
    """Total tasks across all of a pet's routines."""
    return sum(len(routine.get_tasks()) for routine in pet.get_care_routines())


def test_task_completion_changes_status():
    """Setting a task to completed changes its status."""
    task = CareTask(title="Feed", scheduled_date_time=datetime.now())
    assert task.completion_status is False

    task.set_completion_status(True)

    assert task.completion_status is True


def test_adding_routine_increases_pet_task_count():
    """Adding a routine to a pet adds its generated tasks to the pet's task count."""
    pet = Pet(name="Luna", species="cat")
    assert task_count(pet) == 0

    routine = CareRoutine(
        title="Breakfast",
        frequency=Frequency.DAILY,
        scheduled_time=time(8),
        start_date=date.today(),
        end_date=date.today(),  # one day only, so exactly 1 task
    )
    pet.add_routine(routine)

    assert task_count(pet) == 1


@pytest.fixture
def today(monkeypatch):
    """Keep date-dependent tests repeatable, regardless of when they run."""
    fixed_date = date(2026, 10, 17)
    monkeypatch.setattr("pawpal_system._today", lambda: fixed_date)
    return fixed_date


@pytest.fixture
def scheduler():
    owner = PetOwner(name="Alex", email="alex@example.com")
    owner.add_pet(Pet(name="Luna", species="cat"))
    owner.add_pet(Pet(name="Mochi", species="dog"))
    return Scheduler(owner)


def add_routine(pet, start_date, title, scheduled_time, *, frequency=Frequency.ONCE, **options):
    """Attach a routine through the same public method used by the app."""
    routine = CareRoutine(
        title=title,
        frequency=frequency,
        scheduled_time=scheduled_time,
        start_date=start_date,
        **options,
    )
    pet.add_routine(routine)
    return routine


def test_tasks_are_returned_in_chronological_order(today, scheduler):
    """Combine pets' tasks in date-and-time order, regardless of insertion order."""
    luna, mochi = scheduler.owner.pets
    tomorrow = add_routine(luna, today + timedelta(days=1), "Breakfast", time(8))
    evening = add_routine(luna, today, "Dinner", time(18), priority=Priority.HIGH)
    morning = add_routine(mochi, today, "Walk", time(8), priority=Priority.LOW)
    midday = add_routine(mochi, today, "Play", time(12))

    tasks = scheduler.get_tasks()

    assert tasks == [
        morning.get_tasks()[0],
        midday.get_tasks()[0],
        evening.get_tasks()[0],
        tomorrow.get_tasks()[0],
    ]


def test_tasks_at_same_time_sort_by_priority_then_title(today, scheduler):
    pet = scheduler.owner.pets[0]
    walk = add_routine(pet, today, "Walk", time(9), priority=Priority.HIGH)
    feeding = add_routine(pet, today, "Feeding", time(9), priority=Priority.MEDIUM)
    brushing = add_routine(pet, today, "Brushing", time(9), priority=Priority.HIGH)
    grooming = add_routine(pet, today, "Grooming", time(9), priority=Priority.LOW)

    assert scheduler.get_tasks() == [
        brushing.get_tasks()[0],
        walk.get_tasks()[0],
        feeding.get_tasks()[0],
        grooming.get_tasks()[0],
    ]


@pytest.mark.parametrize(
    "frequency,next_day",
    [
        pytest.param(Frequency.DAILY, date(2026, 10, 19), id="every-two-days"),
        pytest.param(Frequency.WEEKLY, date(2026, 10, 31), id="every-two-weeks"),
        pytest.param(Frequency.MONTHLY, date(2026, 12, 17), id="every-two-months"),
    ],
)
def test_routine_links_to_pet_and_generates_next_scheduled_occurrence(
    today, scheduler, frequency, next_day
):
    pet = scheduler.owner.pets[0]
    routine = add_routine(pet, today, "Care", time(8), frequency=frequency, interval=2)

    first_task, = routine.get_tasks()
    assert routine.pet_id == pet.pet_id
    assert first_task.routine_id == routine.routine_id
    assert scheduler.owner.get_pet_for_task(first_task) is pet
    assert first_task.scheduled_date_time == datetime.combine(today, time(8))
    assert first_task.completion_status is False

    plan = scheduler.generate_schedule(next_day)

    assert len(routine.get_tasks()) == 2
    next_task, = plan.included
    assert next_task.routine_id == routine.routine_id
    assert next_task.scheduled_date_time == datetime.combine(next_day, time(8))
    assert next_task.completion_status is False
    assert scheduler.owner.pets[1].get_care_routines() == []


def test_completing_daily_task_creates_task_for_following_day(today, scheduler):
    routine = add_routine(
        scheduler.owner.pets[0], today, "Breakfast", time(8), frequency=Frequency.DAILY
    )
    task, = routine.get_tasks()

    next_task = scheduler.mark_task_complete(task)

    assert task.completion_status is True
    assert next_task is not None
    assert next_task.scheduled_date_time == datetime.combine(today + timedelta(days=1), time(8))
    assert next_task.completion_status is False
    assert next_task.task_id != task.task_id
    assert next_task.routine_id == routine.routine_id
    assert next_task.title == "Breakfast"
    assert routine.get_tasks() == [task, next_task]


def test_pet_and_status_filters_return_matching_tasks(today, scheduler):
    luna, mochi = scheduler.owner.pets
    breakfast = add_routine(luna, today, "Breakfast", time(8)).get_tasks()[0]
    play = add_routine(luna, today, "Play", time(12)).get_tasks()[0]
    walk = add_routine(mochi, today, "Walk", time(9)).get_tasks()[0]
    scheduler.mark_task_complete(breakfast)

    assert scheduler.filter_tasks(pet_name="Luna") == [breakfast, play]
    assert scheduler.filter_tasks(pet_name="Mochi") == [walk]
    assert scheduler.filter_tasks(completed=True) == [breakfast]
    assert scheduler.filter_tasks(completed=False) == [walk, play]
    assert scheduler.filter_tasks(pet_name="Luna", completed=False) == [play]


def test_daily_plan_calculates_completed_and_planned_minutes(today, scheduler):
    pet = scheduler.owner.pets[0]
    breakfast = add_routine(pet, today, "Breakfast", time(8), duration_minutes=20).get_tasks()[0]
    play = add_routine(pet, today, "Play", time(10), duration_minutes=30).get_tasks()[0]
    scheduler.mark_task_complete(breakfast)
    scheduler.owner.set_preferences(time(8), time(18), daily_care_minutes=60)

    plan = scheduler.build_daily_plan(today)

    assert plan.included == [breakfast, play]
    assert plan.excluded == []
    assert plan.completed_minutes == 20
    assert plan.planned_minutes == 30
    assert plan.remaining_minutes == 10
    assert plan.reasons[breakfast.task_id] == "Already completed."
    assert "scheduled care" in plan.reasons[play.task_id]


def test_daily_plan_explains_exclusion_from_optional_time_limit(today, scheduler):
    pet = scheduler.owner.pets[0]
    walk = add_routine(
        pet, today, "Walk", time(9), duration_minutes=30, priority=Priority.HIGH
    ).get_tasks()[0]
    play = add_routine(
        pet, today, "Play", time(10), duration_minutes=20, priority=Priority.LOW
    ).get_tasks()[0]
    scheduler.owner.set_preferences(daily_care_minutes=40)

    plan = scheduler.build_daily_plan(today)

    assert plan.included == [walk]
    assert plan.excluded == [play]
    assert plan.planned_minutes == 30
    assert plan.remaining_minutes == 10
    assert "Needs 20 minutes" in plan.reasons[play.task_id]
    assert "only 10 minutes remain" in plan.reasons[play.task_id]
    assert scheduler.get_tasks() == [walk, play]


def test_scheduler_flags_tasks_with_duplicate_times(today, scheduler):
    luna, mochi = scheduler.owner.pets
    breakfast = add_routine(luna, today, "Breakfast", time(9)).get_tasks()[0]
    walk = add_routine(mochi, today, "Walk", time(9)).get_tasks()[0]
    add_routine(mochi, today, "Play", time(11))

    conflicts = scheduler.find_conflicts()

    assert conflicts == [[breakfast, walk]]


def test_rescheduling_resolves_conflict_and_preserves_original_occurrence(today, scheduler):
    luna, mochi = scheduler.owner.pets
    breakfast = add_routine(luna, today, "Breakfast", time(9)).get_tasks()[0]
    walk = add_routine(mochi, today, "Walk", time(9, 15)).get_tasks()[0]
    original_time = walk.original_date_time
    original_id = walk.task_id
    assert scheduler.find_conflicts() == [[breakfast, walk]]

    walk.reschedule(datetime.combine(today, time(10)))

    assert scheduler.find_conflicts() == []
    assert walk.scheduled_date_time == datetime.combine(today, time(10))
    assert walk.original_date_time == original_time
    assert walk.task_id == original_id
    assert walk.is_rescheduled is True
    assert scheduler.get_tasks() == [breakfast, walk]


def test_overdue_cleanup_preserves_history_and_restarts_active_routine(today, scheduler):
    pet = scheduler.owner.pets[0]
    completed = CareTask(
        title="Breakfast",
        scheduled_date_time=datetime.combine(today - timedelta(days=2), time(8)),
        completion_status=True,
    )
    overdue = CareTask(
        title="Breakfast",
        scheduled_date_time=datetime.combine(today - timedelta(days=1), time(8)),
    )
    routine = CareRoutine(
        title="Breakfast",
        frequency=Frequency.DAILY,
        scheduled_time=time(8),
        start_date=today - timedelta(days=2),
        tasks=[completed, overdue],
    )
    pet.add_routine(routine)
    todays_task = add_routine(pet, today, "Play", time(12)).get_tasks()[0]
    assert scheduler.overdue_tasks() == [overdue]

    scheduler.owner.clear_overdue_tasks()

    assert scheduler.overdue_tasks() == []
    assert completed in routine.get_tasks()
    assert completed.completion_status is True
    assert overdue not in scheduler.get_tasks()
    assert todays_task in scheduler.get_tasks()
    pending = [task for task in routine.get_tasks() if not task.completion_status]
    assert len(pending) == 1
    assert pending[0].scheduled_date_time == datetime.combine(today, time(8))
    assert pending[0].routine_id == routine.routine_id
    assert pending[0].task_id != overdue.task_id
