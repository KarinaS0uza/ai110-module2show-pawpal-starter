"""CLI demo: build an owner with two pets and print today's schedule."""

from datetime import date, time

from pawpal_system import (
    PetOwner,
    Pet,
    CareRoutine,
    Frequency,
    Scheduler,
)


def build_demo_owner(today: date) -> PetOwner:
    """Build an owner with two pets and three one-time routines for today."""
    owner = PetOwner(
        name="Karina",
        email="karina@example.com",
    )

    luna = Pet(name="Luna", species="cat")
    mochi = Pet(name="Mochi", species="dog")
    owner.add_pet(luna)
    owner.add_pet(mochi)

    breakfast = CareRoutine(
        title="Breakfast",
        frequency=Frequency.ONCE,
        scheduled_time=time(8, 0),
        start_date=today,
    )
    morning_walk = CareRoutine(
        title="Morning walk",
        frequency=Frequency.ONCE,
        scheduled_time=time(9, 30),
        start_date=today,
    )
    brushing = CareRoutine(
        title="Brush fur",
        frequency=Frequency.ONCE,
        scheduled_time=time(18, 0),
        start_date=today,
    )

    luna.add_routine(breakfast)
    mochi.add_routine(morning_walk)
    luna.add_routine(brushing)

    return owner


def print_schedule(owner: PetOwner, today: date) -> None:
    """Print today's tasks for all pets, sorted by time."""
    scheduler = Scheduler(owner=owner)

    print("Today's Schedule")
    print(f"Owner: {owner.name}")
    print(f"Date: {today}")
    print("-" * 60)

    for task in scheduler.todays_tasks():
        pet = owner.get_pet_for_task(task)
        status = "Completed" if task.completion_status else "Pending"
        print(
            f"{task.scheduled_date_time:%H:%M} | "
            f"{pet.name:<8} | "
            f"{task.title:<20} | "
            f"{status}"
        )


def main() -> None:
    """Build the demo data and print today's schedule."""
    today = date.today()
    print_schedule(build_demo_owner(today), today)


if __name__ == "__main__":
    main()
