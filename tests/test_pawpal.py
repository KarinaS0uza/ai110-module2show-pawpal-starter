import json
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from itertools import count
from pathlib import Path

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


def test_explicit_time_sort_returns_tasks_in_chronological_order(today, scheduler):
    """Keep time sorting available independently of the default priority schedule."""
    luna, mochi = scheduler.owner.pets
    tomorrow = add_routine(luna, today + timedelta(days=1), "Breakfast", time(8))
    evening = add_routine(luna, today, "Dinner", time(18), priority=Priority.HIGH)
    morning = add_routine(mochi, today, "Walk", time(8), priority=Priority.LOW)
    midday = add_routine(mochi, today, "Play", time(12))

    tasks = scheduler.sort_by_time()

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


def test_default_schedule_sorts_priority_before_time_across_pets(today, scheduler):
    luna, mochi = scheduler.owner.pets
    low = add_routine(luna, today, "Brush", time(7), priority=Priority.LOW).tasks[0]
    high_late = add_routine(mochi, today, "Evening care", time(18), priority=Priority.HIGH).tasks[0]
    medium = add_routine(luna, today, "Breakfast", time(8)).tasks[0]
    high_early = add_routine(luna, today, "Medication", time(9), priority=Priority.HIGH).tasks[0]
    high_tomorrow = add_routine(
        mochi, today + timedelta(days=1), "Morning care", time(8), priority=Priority.HIGH,
    ).tasks[0]
    expected_today = [high_early, high_late, medium, low]
    supplied = [low, high_late, medium, high_early]

    assert scheduler.get_tasks() == [high_early, high_late, high_tomorrow, medium, low]
    assert scheduler.tasks_on(today) == expected_today
    assert scheduler.todays_tasks() == expected_today
    assert scheduler.owner.view_todays_tasks() == expected_today
    assert scheduler.filter_tasks(pet_name="Luna") == [high_early, medium, low]
    assert scheduler.sort_by_priority(supplied) == expected_today
    assert supplied == [low, high_late, medium, high_early]
    assert scheduler.sort_by_priority([]) == []


def test_daily_plan_keeps_priority_order_and_completed_history(today, scheduler):
    pet = scheduler.owner.pets[0]
    low = add_routine(pet, today, "Brush", time(7), priority=Priority.LOW).tasks[0]
    completed = add_routine(pet, today, "Breakfast", time(8)).tasks[0]
    completed.set_completion_status(True)
    high_late = add_routine(pet, today, "Evening care", time(18), priority=Priority.HIGH).tasks[0]
    high_early = add_routine(pet, today, "Medication", time(9), priority=Priority.HIGH).tasks[0]

    plan = scheduler.generate_schedule(today)

    assert plan.included == [high_early, high_late, completed, low]
    assert plan.excluded == []
    assert plan.completed_minutes == 30
    assert plan.planned_minutes == 90
    assert plan.reasons[completed.task_id] == "Already completed."
    assert low.scheduled_date_time == datetime.combine(today, time(7))
    assert high_late.scheduled_date_time == datetime.combine(today, time(18))


def test_excluded_tasks_also_keep_priority_order(today, scheduler):
    pet = scheduler.owner.pets[0]
    low = add_routine(pet, today, "Brush", time(7), priority=Priority.LOW).tasks[0]
    high = add_routine(pet, today, "Medication", time(18), priority=Priority.HIGH).tasks[0]
    medium = add_routine(pet, today, "Walk", time(8)).tasks[0]
    scheduler.owner.set_preferences(daily_care_minutes=0)

    plan = scheduler.build_daily_plan(today)

    assert plan.included == []
    assert plan.excluded == [high, medium, low]
    assert scheduler.get_tasks() == [high, medium, low]


def test_mixed_priorities_preserve_chronological_conflict_and_gap_scans(today, scheduler):
    pet = scheduler.owner.pets[0]
    low = add_routine(pet, today, "Walk", time(9), duration_minutes=60, priority=Priority.LOW).tasks[0]
    high = add_routine(pet, today, "Medication", time(11), priority=Priority.HIGH).tasks[0]
    assert scheduler.get_tasks() == [high, low]
    assert scheduler.find_conflicts() == []
    medium = add_routine(pet, today, "Play", time(9, 30), duration_minutes=15).tasks[0]

    assert scheduler.find_conflicts() == [[low, medium]]
    assert scheduler.next_free_slot(30, datetime.combine(today, time(8, 45))) == datetime.combine(today, time(10))
    assert scheduler.next_free_slot(
        30, datetime.combine(today, time(8, 45)), exclude_task_id=low.task_id,
    ) == datetime.combine(today, time(8, 45))


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
        pet, today, "Walk", time(18), duration_minutes=30, priority=Priority.HIGH
    ).get_tasks()[0]
    play = add_routine(
        pet, today, "Play", time(8), duration_minutes=20, priority=Priority.LOW
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


def test_json_round_trip_preserves_profiles_recurring_history_and_reschedules(today, scheduler, tmp_path):
    owner = scheduler.owner
    pet = owner.pets[0]
    pet.update_profile({
        "birthday": date(2022, 4, 10), "breed": "Siamese", "photo": "luna.png",
        "pet_needs": "Daily play", "care_instructions": "Gentle brushing",
    })
    owner.set_preferences(time(7), time(20), daily_care_minutes=120)
    routine = add_routine(
        pet, today, "Café breakfast", time(8), frequency=Frequency.DAILY,
        interval=2, end_date=today + timedelta(days=30), duration_minutes=15,
        priority=Priority.HIGH, category="Meal",
    )
    successor = scheduler.mark_task_complete(routine.tasks[0])
    successor.reschedule(successor.scheduled_date_time + timedelta(hours=1))
    old_routine = add_routine(owner.pets[1], today, "Walk", time(9))
    old_routine.tasks[0].set_completion_status(True)
    owner.pets[1].remove_routine(old_routine)
    saved_file = tmp_path / "data.json"

    owner.save_to_json(saved_file)
    restored = PetOwner.load_from_json(saved_file)

    assert restored == owner
    assert restored.pets[0].routines[0].tasks[1].is_rescheduled is True
    assert restored.get_pet_for_task(restored.get_all_tasks()[0]) is restored.pets[0]
    saved = json.loads(saved_file.read_text())
    assert saved["pets"][0]["birthday"] == "2022-04-10"
    assert saved["pets"][0]["routines"][0]["frequency"] == "daily"
    assert saved["pets"][0]["routines"][0]["tasks"][0]["completion_status"] is True


def test_loading_does_not_generate_tasks_for_empty_or_completed_routines(today, tmp_path, monkeypatch):
    pet = Pet(name="Luna", species="cat")
    empty = CareRoutine(
        title="Walk", frequency=Frequency.DAILY, scheduled_time=time(8),
        start_date=today, pet_id=pet.pet_id,
    )
    completed = CareRoutine(
        title="Play", frequency=Frequency.DAILY, scheduled_time=time(9),
        start_date=today, pet_id=pet.pet_id,
        tasks=[CareTask(title="Play", scheduled_date_time=datetime.combine(today, time(9)), completion_status=True)],
    )
    pet.routines.extend([empty, completed])
    owner = PetOwner(name="Alex", email="alex@example.com", pets=[pet])
    saved_file = tmp_path / "data.json"
    owner.save_to_json(saved_file)

    def unexpected_generation(*args, **kwargs):
        pytest.fail("Loading must not generate new task occurrences")

    monkeypatch.setattr(CareRoutine, "generate_tasks", unexpected_generation)
    assert PetOwner.load_from_json(saved_file) == owner


def test_loaded_ids_remain_unique_after_a_new_process_starts(today, tmp_path):
    task = CareTask(task_id=700, title="Walk", scheduled_date_time=datetime.combine(today, time(8)))
    routine = CareRoutine(
        routine_id=500, pet_id=300, title="Walk", frequency=Frequency.DAILY,
        scheduled_time=time(8), start_date=today, tasks=[task],
    )
    pet = Pet(pet_id=300, name="Luna", species="cat", routines=[routine])
    owner = PetOwner(owner_id=900, name="Alex", email="alex@example.com", pets=[pet])
    saved_file = tmp_path / "data.json"
    owner.save_to_json(saved_file)
    script = """
import sys
from datetime import date, datetime, time
from pawpal_system import CareRoutine, CareTask, Frequency, Pet, PetOwner
owner = PetOwner.load_from_json(sys.argv[1])
assert owner.owner_id == 900
assert PetOwner(name="New", email="new@example.com").owner_id > 900
assert Pet(name="Mochi", species="dog").pet_id > 300
assert CareRoutine(title="Play", frequency=Frequency.ONCE, scheduled_time=time(9), start_date=date.today()).routine_id > 500
assert CareTask(title="Play", scheduled_date_time=datetime.now()).task_id > 700
"""
    subprocess.run(
        [sys.executable, "-c", script, str(saved_file)],
        cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True,
    )


def test_loading_does_not_rewind_existing_id_counters(today, scheduler, tmp_path, monkeypatch):
    routine = add_routine(scheduler.owner.pets[0], today, "Walk", time(8))
    saved_file = tmp_path / "data.json"
    scheduler.owner.save_to_json(saved_file)
    for name in ("_owner_ids", "_pet_ids", "_routine_ids", "_task_ids"):
        monkeypatch.setattr(f"pawpal_system.{name}", count(10000))

    PetOwner.load_from_json(saved_file)

    assert PetOwner(name="New", email="new@example.com").owner_id >= 10000
    assert Pet(name="New", species="cat").pet_id >= 10000
    assert CareRoutine(title="New", frequency=Frequency.ONCE, scheduled_time=time(8), start_date=today).routine_id >= 10000
    assert routine.add_task(datetime.combine(today + timedelta(days=1), time(8))).task_id >= 10000


@pytest.mark.parametrize("reload_mode", ["reload", "fresh-import"])
def test_backend_reload_preserves_unique_ids_for_retained_owner(tmp_path, reload_mode):
    """Keep a live owner's care intact when Streamlit reloads its backend module."""
    script = """
import importlib
import sys
from datetime import date, datetime, time
import pawpal_system as ps

owner = ps.PetOwner(name="Alex", email="alex@example.com")
pet = ps.Pet(name="Luna", species="cat")
owner.add_pet(pet)
routine = ps.CareRoutine(
    title="Breakfast", frequency=ps.Frequency.ONCE,
    scheduled_time=time(8), start_date=date.today(),
)
pet.add_routine(routine)
original_task = routine.tasks[0]

if sys.argv[2] == "reload":
    ps = importlib.reload(ps)
else:
    del sys.modules["pawpal_system"]
    ps = importlib.import_module("pawpal_system")
    ps.PetOwner.sync_id_counters(owner)

assert ps.PetOwner(name="New", email="new@example.com").owner_id > owner.owner_id
new_pet = ps.Pet(name="Mochi", species="dog")
assert new_pet.pet_id > pet.pet_id
new_routine = ps.CareRoutine(
    title="Walk", frequency=ps.Frequency.ONCE,
    scheduled_time=time(9), start_date=date.today(),
)
assert new_routine.routine_id > routine.routine_id
new_pet.add_routine(new_routine)
assert new_routine.tasks[0].task_id > original_task.task_id
owner.add_pet(new_pet)
owner.save_to_json(sys.argv[1])
restored = ps.PetOwner.load_from_json(sys.argv[1])
assert [pet.name for pet in restored.pets] == ["Luna", "Mochi"]
assert len(restored.get_all_tasks()) == 2
assert restored.get_all_tasks()[0].task_id == original_task.task_id
assert restored.get_all_tasks()[0].scheduled_date_time == original_task.scheduled_date_time
"""
    subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "data.json"), reload_mode],
        cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True,
    )


@pytest.mark.parametrize("duplicate_kind", ["pet", "routine", "task"])
def test_saving_duplicate_ids_preserves_previous_data(today, scheduler, tmp_path, duplicate_kind):
    """A damaged live session must not replace a valid saved care file."""
    owner = scheduler.owner
    pet = owner.pets[0]
    routine = add_routine(pet, today, "Walk", time(8))
    saved_file = tmp_path / "data.json"
    owner.save_to_json(saved_file)
    previous = saved_file.read_bytes()
    if duplicate_kind == "pet":
        owner.pets.append(Pet(pet_id=pet.pet_id, name="Duplicate", species="dog"))
    elif duplicate_kind == "routine":
        pet.routines.append(routine)
    else:
        routine.tasks.append(routine.tasks[0])

    with pytest.raises(ValueError, match="Duplicate IDs"):
        owner.save_to_json(saved_file)

    assert saved_file.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [saved_file]


@pytest.mark.parametrize("content", ["{broken", "[]", "{}"])
def test_invalid_json_is_rejected_without_changing_the_file(tmp_path, content):
    saved_file = tmp_path / "data.json"
    saved_file.write_text(content)

    with pytest.raises(ValueError):
        PetOwner.load_from_json(saved_file)

    assert saved_file.read_text() == content


@pytest.mark.parametrize("problem", ["duplicate-id", "wrong-pet", "invalid-date", "invalid-status"])
def test_invalid_saved_objects_are_rejected(today, scheduler, tmp_path, problem):
    routine = add_routine(scheduler.owner.pets[0], today, "Walk", time(8))
    routine.add_task(datetime.combine(today + timedelta(days=1), time(8)))
    saved_file = tmp_path / "data.json"
    scheduler.owner.save_to_json(saved_file)
    data = json.loads(saved_file.read_text())
    saved_routine = data["pets"][0]["routines"][0]
    if problem == "duplicate-id":
        saved_routine["tasks"][1]["task_id"] = saved_routine["tasks"][0]["task_id"]
    elif problem == "wrong-pet":
        saved_routine["pet_id"] = data["pets"][1]["pet_id"]
    elif problem == "invalid-date":
        saved_routine["tasks"][0]["scheduled_date_time"] = "not a date"
    else:
        saved_routine["tasks"][0]["completion_status"] = "false"
    content = json.dumps(data)
    saved_file.write_text(content)

    with pytest.raises(ValueError, match="Invalid PawPal data"):
        PetOwner.load_from_json(saved_file)

    assert saved_file.read_text() == content


def test_failed_save_preserves_previous_data_and_removes_temporary_file(scheduler, tmp_path, monkeypatch):
    saved_file = tmp_path / "data.json"
    scheduler.owner.save_to_json(saved_file)
    previous = saved_file.read_bytes()
    scheduler.owner.name = "Changed"

    def fail_replace(*args, **kwargs):
        raise OSError("Cannot replace file")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="Cannot replace file"):
        scheduler.owner.save_to_json(saved_file)

    assert saved_file.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [saved_file]
