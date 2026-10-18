"""Demonstrate PawPal+ task scheduling, filtering, conflicts, recurring care and daily planning."""

from datetime import date, datetime, time, timedelta

from pawpal_system import (
    CareRoutine,
    CareTask,
    Frequency,
    Pet,
    PetOwner,
    Priority,
    Scheduler,
)


def build_demo_owner(today: date) -> PetOwner:
    """Build an owner with two pets and four routines added out of time order."""
    owner = PetOwner(
        name="Karina",
        email="karina@example.com",
    )

    luna = Pet(name="Luna", species="cat")
    mochi = Pet(name="Mochi", species="dog")
    owner.add_pet(luna)
    owner.add_pet(mochi)

    brushing = CareRoutine(
        title="Brush fur",
        frequency=Frequency.ONCE,
        scheduled_time=time(18, 0),
        start_date=today,
    )
    evening_walk = CareRoutine(
        title="Evening walk",
        frequency=Frequency.DAILY,
        scheduled_time=time(18, 0),
        start_date=today,
    )
    morning_walk = CareRoutine(
        title="Morning walk",
        frequency=Frequency.ONCE,
        scheduled_time=time(9, 30),
        start_date=today,
    )
    breakfast = CareRoutine(
        title="Breakfast",
        frequency=Frequency.ONCE,
        scheduled_time=time(8, 0),
        start_date=today,
    )

    luna.add_routine(brushing)
    mochi.add_routine(evening_walk)
    mochi.add_routine(morning_walk)
    luna.add_routine(breakfast)

    breakfast.tasks[0].set_completion_status(True)

    return owner


def todays(tasks: list[CareTask], today: date) -> list[CareTask]:
    return [task for task in tasks if task.scheduled_date_time.date() == today]


def print_tasks(
    owner: PetOwner, heading: str, tasks: list[CareTask], with_date: bool = False
) -> None:
    """Print readable task rows, optionally including dates for overdue care."""
    print(f"\n{heading}")
    print("-" * 60)
    if not tasks:
        print("(none)")
    for task in tasks:
        pet = owner.get_pet_for_task(task)
        status = "Completed" if task.completion_status else "Pending"
        when = f"{task.scheduled_date_time:%b %d %H:%M}" if with_date else f"{task.scheduled_date_time:%H:%M}"
        print(f"{when} | {pet.name:<8} | {task.title:<20} | {status}")


def demo_sorting_and_filtering(owner: PetOwner, scheduler: Scheduler, today: date) -> None:
    """Show insertion order, chronological order and pet/status filters."""
    added = todays(owner.get_all_tasks(), today)
    print_tasks(owner, "Added out of order", added)
    print_tasks(owner, "Today's Schedule (sorted by time)", scheduler.sort_by_time(added))
    print_tasks(owner, "Filtered by pet: Luna", todays(scheduler.filter_tasks(pet_name="Luna"), today))
    print_tasks(owner, "Filtered by status: completed", todays(scheduler.filter_tasks(completed=True), today))
    print_tasks(owner, "Filtered by status: pending", todays(scheduler.filter_tasks(completed=False), today))


def todays_conflicts(scheduler: Scheduler, today: date) -> list[list[CareTask]]:
    """Return conflict groups whose earliest task starts on the supplied day."""
    return [group for group in scheduler.find_conflicts() if group[0].scheduled_date_time.date() == today]


def demo_conflicts(owner: PetOwner, scheduler: Scheduler, today: date) -> None:
    """Show an overlap, a suggested free time, and the owner's two choices."""
    print("\nConflicts today")
    print("-" * 60)
    for group in todays_conflicts(scheduler, today):
        print(scheduler.conflict_warning(group))

        later = group[-1]
        pet = owner.get_pet_for_task(later)
        suggestion = scheduler.next_free_slot(
            later.duration_minutes, later.scheduled_date_time, exclude_task_id=later.task_id
        )
        print(f"Suggested time for {pet.name}'s {later.title}: {suggestion:%H:%M}")
        print(f"Keep as scheduled: nothing changes, conflicts still found: {len(todays_conflicts(scheduler, today))}")
        later.reschedule(suggestion)
        print(f"Reschedule: {later.title} moved to {suggestion:%H:%M}, conflicts now: {len(todays_conflicts(scheduler, today))}")


def demo_recurring_completion(scheduler: Scheduler, walk: CareRoutine, today: date) -> None:
    """Demonstrate the next daily occurrence and duplicate-completion protection."""
    print("\nCompleting a daily task")
    print("-" * 60)
    task = todays(walk.tasks, today)[0]
    count = len(walk.tasks)
    following = scheduler.mark_task_complete(task)
    print(
        f"{walk.title} on {task.original_date_time:%b %d} completed -> next: "
        f"{following.scheduled_date_time:%b %d %H:%M} (tasks: {count} -> {len(walk.tasks)})"
    )

    count = len(walk.tasks)
    scheduler.mark_task_complete(task)
    print(f"Completing the same task again creates no duplicate (tasks: {count} -> {len(walk.tasks)})")


def demo_overdue(owner: PetOwner, scheduler: Scheduler, today: date, routines: dict[str, CareRoutine]) -> None:
    """Show overdue tasks, marking one done, then deleting the rest."""
    routines["Morning walk"].add_task(datetime.combine(today - timedelta(days=1), time(9, 30)))
    routines["Breakfast"].add_task(datetime.combine(today - timedelta(days=2), time(8, 0)))

    print_tasks(owner, "Overdue tasks (two past tasks added by hand for this demo)", owner.view_overdue_tasks(), with_date=True)
    scheduler.mark_task_complete(owner.view_overdue_tasks()[0])
    print_tasks(owner, "Overdue after marking the oldest one done", owner.view_overdue_tasks(), with_date=True)
    owner.clear_overdue_tasks()
    print_tasks(owner, "Overdue after deleting all", owner.view_overdue_tasks(), with_date=True)


def demo_daily_planning(today: date) -> None:
    """Show all scheduled care for a day with explanations and minute totals."""
    owner = PetOwner(name="Karina", email="karina@example.com")
    owner.add_pet(Pet(name="Luna", species="cat"))
    owner.add_pet(Pet(name="Mochi", species="dog"))
    examples = [
        (0, "Breakfast", time(8), 15, Priority.MEDIUM, True, "Meal"),
        (0, "Medication", time(9), 20, Priority.HIGH, False, "Other"),
        (1, "Long walk", time(10), 40, Priority.MEDIUM, False, "Exercise"),
        (1, "Short walk", time(11), 25, Priority.MEDIUM, False, "Exercise"),
        (0, "Brush fur", time(18), 10, Priority.LOW, False, "Grooming"),
        (1, "Playtime", time(20), 10, Priority.HIGH, False, "Play"),
    ]
    for pet_index, title, at_time, duration, priority, completed, category in examples:
        routine = CareRoutine(
            title=title, frequency=Frequency.ONCE, scheduled_time=at_time,
            start_date=today, duration_minutes=duration, priority=priority,
            category=category,
        )
        owner.pets[pet_index].add_routine(routine)
        routine.tasks[0].set_completion_status(completed)

    plan = Scheduler(owner).build_daily_plan(today)
    print("\nDaily care plan")
    print(f"Completed: {plan.completed_minutes} min | Planned: {plan.planned_minutes} min")
    for heading, tasks in (("Today's plan", plan.included), ("Not included in this plan", plan.excluded)):
        print(f"\n{heading}")
        print("-" * 60)
        if not tasks:
            print("(none)")
        for task in tasks:
            pet = owner.get_pet_for_task(task)
            print(f"{task.scheduled_date_time:%H:%M} | {pet.name:<8} | {task.title}")
            print(f"  {plan.reasons[task.task_id]}")


def main() -> None:
    today = date.today()
    owner = build_demo_owner(today)
    scheduler = Scheduler(owner)
    routines = {routine.title: routine for pet in owner.pets for routine in pet.routines}

    print(f"Owner: {owner.name}")
    print(f"Date: {today}")

    demo_sorting_and_filtering(owner, scheduler, today)
    demo_conflicts(owner, scheduler, today)
    demo_recurring_completion(scheduler, routines["Evening walk"], today)
    demo_overdue(owner, scheduler, today, routines)
    demo_daily_planning(today)


if __name__ == "__main__":
    main()
