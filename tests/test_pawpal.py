from datetime import date, datetime, time

from pawpal_system import CareRoutine, CareTask, Frequency, Pet


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
