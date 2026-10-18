"""Streamlit interface for managing pets, care routines, daily plans and overdue tasks."""

import os
from datetime import date, datetime, time, timedelta
from html import escape
from itertools import combinations

import streamlit as st

from pawpal_system import (
    CARE_CATEGORIES,
    CareRoutine,
    CareTask,
    Frequency,
    Pet,
    PetOwner,
    Priority,
    Scheduler,
)

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

if "owner" not in st.session_state:
    st.session_state.owner = PetOwner(name="Jordan", email="jordan@example.com")

owner = st.session_state.owner
# Clear limits saved by earlier versions so every scheduled task stays included.
owner.set_preferences()
for pet in owner.pets:
    for routine in pet.routines:
        if routine.category == "General":
            routine.category = "Other"

color_scheme = st.context.theme.type or st.get_option("theme.base") or "light"
st.html("""
<style>
[class*="st-key-plan_table_"] { overflow-x: auto; gap: 0; }
[class*="st-key-plan_table_"] [data-testid="stHorizontalBlock"] { min-width: 600px; }
[class*="st-key-plan_table_"] [data-testid="stColumn"] { min-width: 0; }
[class*="st-key-plan_row_"], [class*="st-key-plan_header_"] {
    border-bottom: 1px solid color-mix(in srgb, currentColor 20%, transparent);
    padding: 16px 0;
}
[class*="st-key-plan_header_"] { opacity: 0.7; padding-top: 0; }
[class*="st-key-plan_table_"] [data-testid="stMarkdownContainer"] p {
    font-size: 13px; line-height: 1.5;
}
[class*="st-key-plan_table_"] [data-testid="stMarkdownContainer"] span {
    font-size: 13px; border-radius: 4px;
}
[class*="st-key-plan_table_"] .plan-time { white-space: nowrap; font-variant-numeric: tabular-nums; }
.care-badge {
    color-scheme: PAWPAL_SCHEME;
    display: inline-block; padding: 3px 8px; border-radius: 4px;
    font-size: 13px; line-height: 1.5; white-space: nowrap;
}
.care-badge.high { background: light-dark(#eee8fc, #33234c); color: light-dark(#6330a0, #e2ccff); }
.care-badge.medium { background: light-dark(#f3f0e7, #373125); color: light-dark(#725b24, #e5d6ac); }
.care-badge.low { background: light-dark(#f0f2f6, #262730); color: light-dark(#626671, #c2c5ce); }
.care-badge.overlap { background: light-dark(#fee8e8, #49242b); color: light-dark(#8c2430, #ffc6cb); }
[class*="st-key-care_total_"] [data-testid="stMetric"] {
    color-scheme: PAWPAL_SCHEME;
    padding: 0;
    border-radius: 10px;
}
[class*="st-key-care_total_"] [data-testid="stMetric"] > div {
    padding: 12px 16px;
}
[class*="st-key-care_total_"] [data-testid="stMetricLabel"] {
    color: inherit;
    font-size: 13px;
}
[class*="st-key-care_total_"] [data-testid="stMetricValue"] {
    color: inherit;
    font-size: 26px;
    font-weight: 600;
}
.st-key-care_total_completed [data-testid="stMetric"] {
    background: light-dark(#edf7f1, #192f26);
    border-color: light-dark(#c5e3d2, #355b49);
    color: light-dark(#286344, #b9e4cc);
}
.st-key-care_total_planned [data-testid="stMetric"] {
    background: light-dark(#f3effb, #2c243d);
    border-color: light-dark(#ddd0ef, #514066);
    color: light-dark(#65428c, #ddc9f4);
}
</style>
""".replace("PAWPAL_SCHEME", color_scheme))


def describe_repeat(routine: CareRoutine) -> str:
    """Plain-language repeat pattern, such as "Every 2 weeks"."""
    # Session routines can retain enum instances from before a code reload.
    frequency = Frequency(routine.frequency.value)
    if frequency is Frequency.ONCE:
        return f"Once on {routine.start_date}"
    unit = {Frequency.DAILY: "day", Frequency.WEEKLY: "week", Frequency.MONTHLY: "month"}[frequency]
    return f"Every {unit}" if routine.interval == 1 else f"Every {routine.interval} {unit}s"


def move_task(task: CareTask, new_start: datetime) -> None:
    """Reschedule one occurrence and require review of its changed overlaps."""
    if new_start == task.scheduled_date_time:
        return
    task.reschedule(new_start)
    st.session_state.accepted_overlaps = {
        key for key in st.session_state.get("accepted_overlaps", set())
        if all(slot[0] != task.task_id for slot in key)
    }


def overlap_key(tasks: list[CareTask]) -> tuple:
    """Identify an overlap by its task IDs, scheduled times and durations."""
    return tuple(
        (task.task_id, task.scheduled_date_time, task.duration_minutes)
        for task in sorted(tasks, key=lambda task: task.task_id)
    )


def accept_overlap(tasks: list[CareTask]) -> None:
    """Dismiss this overlap for the current task occurrences and times."""
    st.session_state.setdefault("accepted_overlaps", set()).add(overlap_key(tasks))
    if set(st.session_state.get("reschedule_task_ids", [])) == {task.task_id for task in tasks}:
        st.session_state.pop("reschedule_task_ids", None)


def begin_rescheduling(tasks: list[CareTask]) -> None:
    """Open the usual task form for one of the overlapping occurrences."""
    st.session_state.reschedule_task_ids = [task.task_id for task in tasks]
    st.session_state.reschedule_task_id = tasks[-1].task_id
    st.session_state.scroll_target = "schedule-a-task"


def find_unaccepted_overlaps(scheduler: Scheduler, day: date) -> list[list[CareTask]]:
    """Return actual overlapping pairs needing review on the selected day."""
    pairs = [
        list(pair)
        for group in scheduler.find_conflicts()
        for pair in combinations(group, 2)
        if max(task.scheduled_date_time for task in pair) < min(task.end_date_time for task in pair)
    ]
    accepted = st.session_state.setdefault("accepted_overlaps", set())
    accepted.intersection_update(overlap_key(pair) for pair in pairs)
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)
    return [
        pair for pair in pairs
        if overlap_key(pair) not in accepted
        and max(day_start, *(task.scheduled_date_time for task in pair))
        < min(day_end, *(task.end_date_time for task in pair))
    ]


def set_done(task: CareTask, key: str) -> None:
    """Complete care through its routine, or reopen it without removing its successor."""
    if st.session_state[key]:
        try:
            Scheduler(st.session_state.owner).mark_task_complete(task)
        except ValueError as error:
            st.session_state[key] = task.completion_status
            st.warning(str(error))
    else:
        task.set_completion_status(False)


def format_time_range(start: datetime, end: datetime) -> str:
    """Format a compact AM/PM range, noting care that finishes on a later day."""
    first = start.strftime("%I:%M%p" if start.minute else "%I%p").lstrip("0")
    last = end.strftime("%I:%M%p" if end.minute else "%I%p").lstrip("0")
    label = f"{first[:-2]}–{last}" if first[-2:] == last[-2:] else f"{first}–{last}"
    days = (end.date() - start.date()).days
    return label if not days else f"{label} (+{days} day{'s' if days > 1 else ''})"


def badge_html(label: str, kind: str, description: str = "") -> str:
    """Return an escaped priority or overlap badge matching the plan's style."""
    return f'<span class="care-badge {escape(kind)}" title="{escape(description or label)}">{escape(label)}</span>'


def show_plan_tasks(
    owner: PetOwner, tasks: list[CareTask], conflict_ids: set[int] | None = None, *, key: str = "included",
) -> None:
    """Show compact task rows with priority badges, overlap badges and final Done checkboxes."""
    headers = ["Time", "Pet", "Task", "Priority"]
    widths = [1.6, 1, 1.8, 1]
    if conflict_ids is not None:
        headers.append("Overlap")
        widths.append(1)
    headers.append("Done")
    widths.append(0.45)
    with st.container(key=f"plan_table_{key}"):
        with st.container(key=f"plan_header_{key}"):
            for column, label in zip(st.columns(widths, wrap=False), headers):
                column.markdown(label)
        for task in tasks:
            pet = owner.get_pet_for_task(task)
            with st.container(key=f"plan_row_{key}_{task.task_id}"):
                columns = st.columns(widths, vertical_alignment="center", wrap=False)
                columns[0].markdown(
                    f'<span class="plan-time">{format_time_range(task.scheduled_date_time, task.end_date_time)}</span>',
                    unsafe_allow_html=True,
                )
                columns[1].markdown(escape(pet.name), unsafe_allow_html=True)
                columns[2].markdown(escape(task.title), unsafe_allow_html=True)
                columns[3].markdown(
                    badge_html(task.priority.value.title(), task.priority.value), unsafe_allow_html=True,
                )
                if conflict_ids is not None and task.task_id in conflict_ids:
                    columns[4].markdown(badge_html("Overlap", "overlap"), unsafe_allow_html=True)
                done_key = f"plan_done_{task.task_id}"
                st.session_state[done_key] = task.completion_status
                future_repeat = (
                    not task.completion_status and task.scheduled_date_time.date() > date.today()
                    and owner.get_routine_for_task(task).frequency.value != Frequency.ONCE.value
                )
                columns[-1].checkbox(
                    f"Done: {pet.name} {task.title}", key=done_key, label_visibility="collapsed",
                    disabled=future_repeat, on_change=set_done, args=(task, done_key),
                    help="Repeating tasks can be completed on their scheduled day or later." if future_repeat else None,
                )


def add_sample_overdue() -> None:
    """Add two sample overdue tasks for the selected pet in testing mode."""
    pet = st.session_state.owner.pets[st.session_state.sample_pet]
    today = date.today()
    for days_ago, title, at_time in ((2, "Morning walk", time(8, 0)), (1, "Evening feeding", time(18, 0))):
        routine = CareRoutine(
            title=title,
            frequency=Frequency.ONCE,
            scheduled_time=at_time,
            start_date=today - timedelta(days=days_ago),
        )
        pet.add_routine(routine)
        routine.add_task(datetime.combine(routine.start_date, at_time))
    st.toast(f"Added 2 sample overdue tasks for {pet.name}.")


st.title("🐾 PawPal+")

st.markdown(
    """
PawPal+ helps a pet owner plan recurring care for their pets: add pets, schedule routines,
and see today's tasks.
"""
)

st.caption("Your pets and tasks are kept in this browser session.")

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)

st.subheader("Add a Pet")
with st.form("add_pet_form", clear_on_submit=True):
    pet_name = st.text_input("Pet name")
    species = st.selectbox("Species", ["dog", "cat", "other"])
    if st.form_submit_button("Add pet"):
        if pet_name.strip():
            owner.add_pet(Pet(name=pet_name.strip(), species=species))
            st.success(f"Added {pet_name.strip()}.")
        else:
            st.error("Please enter a pet name.")

st.subheader("Schedule a Task", anchor="schedule-a-task")
if not owner.pets:
    st.info("Add a pet first, then schedule its tasks here.")
else:
    reschedule_tasks = {
        task.task_id: task for task in owner.get_all_tasks()
        if task.task_id in st.session_state.get("reschedule_task_ids", []) and not task.completion_status
    }
    if not reschedule_tasks:
        st.session_state.pop("reschedule_task_ids", None)
    editing_task = None
    editing_routine = None
    if reschedule_tasks:
        if st.session_state.get("reschedule_task_id") not in reschedule_tasks:
            st.session_state.reschedule_task_id = next(iter(reschedule_tasks))
        task_id = st.selectbox(
            "Task to reschedule", list(reschedule_tasks), key="reschedule_task_id",
            format_func=lambda task_id: (
                f"{owner.get_pet_for_task(reschedule_tasks[task_id]).name}: {reschedule_tasks[task_id].title}"
            ),
        )
        editing_task = reschedule_tasks[task_id]
        editing_routine = owner.get_routine_for_task(editing_task)
    form_key = f"reschedule_task_{editing_task.task_id}" if editing_task else "add_routine_form"
    with st.form(form_key, clear_on_submit=editing_task is None):
        pet_index = st.selectbox(
            "Pet", range(len(owner.pets)), format_func=lambda i: owner.pets[i].name,
            index=owner.pets.index(owner.get_pet_for_task(editing_task)) if editing_task else 0,
            disabled=editing_task is not None,
        )
        title_col, category_col = st.columns(2)
        with title_col:
            task_title = st.text_input(
                "Task title", value=editing_task.title if editing_task else "Morning walk",
                disabled=editing_task is not None,
            )
        with category_col:
            care_category = st.selectbox(
                "Care category", CARE_CATEGORIES,
                index=CARE_CATEGORIES.index(editing_routine.category) if editing_routine else 0,
                disabled=editing_task is not None,
            )

        start_col, end_col = st.columns(2)
        with start_col:
            start_date = st.date_input(
                "Start date", value=editing_task.scheduled_date_time.date() if editing_task else date.today(),
            )
        with end_col:
            end_date = st.date_input(
                "End date (optional)", value=editing_routine.end_date if editing_routine else None,
                disabled=editing_task is not None,
            )

        time_col, duration_col = st.columns(2)
        with time_col:
            scheduled_time = st.time_input("Time", value=editing_task.scheduled_date_time.time() if editing_task else time(8))
        with duration_col:
            duration = st.number_input(
                "Duration (minutes)", min_value=1, max_value=max(240, editing_task.duration_minutes) if editing_task else 240,
                value=editing_task.duration_minutes if editing_task else 30, disabled=editing_task is not None,
            )

        repeat_col, interval_col, priority_col = st.columns(3)
        with repeat_col:
            frequency = st.selectbox(
                "Repeats", list(Frequency), format_func=lambda f: f.value.title(),
                index=list(Frequency).index(Frequency(editing_routine.frequency.value)) if editing_routine else 0,
                disabled=editing_task is not None,
            )
        with interval_col:
            interval = st.number_input(
                "Every N", min_value=1,
                value=editing_routine.interval if editing_routine else 1, disabled=editing_task is not None,
                help="Days, weeks or months, based on the repeat pattern.",
            )
        with priority_col:
            priority = st.selectbox(
                "Priority", list(Priority), format_func=lambda p: p.value.title(),
                index=list(Priority).index(Priority(editing_task.priority.value)) if editing_task else 1,
                disabled=editing_task is not None,
            )

        submit = st.form_submit_button("Reschedule task" if editing_task else "Add task")
        cancel = st.form_submit_button("Cancel") if editing_task else False
        if cancel:
            st.session_state.pop("reschedule_task_ids", None)
            st.session_state.scroll_target = "todays-plan"
            st.rerun()
        if submit:
            if editing_task:
                move_task(editing_task, datetime.combine(start_date, scheduled_time))
                st.session_state.pop("reschedule_task_ids", None)
                st.session_state.scroll_target = "todays-plan"
                st.rerun()
            if not task_title.strip():
                st.error("Please enter a task title.")
            else:
                pet = owner.pets[pet_index]
                try:
                    routine = CareRoutine(
                        title=task_title.strip(),
                        frequency=frequency,
                        scheduled_time=scheduled_time,
                        start_date=start_date,
                        interval=int(interval),
                        end_date=end_date,
                        duration_minutes=int(duration),
                        priority=priority,
                        category=care_category,
                    )
                    pet.add_routine(routine)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.success(f"Scheduled '{routine.title}' for {pet.name}.")
                    if not routine.tasks:
                        st.warning("No upcoming tasks: the start or end date is already in the past.")

st.subheader("Pets and Tasks")
if owner.pets:
    st.table(
        [
            {"Name": p.name, "Species": p.species, "Care routines": len(p.get_care_routines())}
            for p in owner.pets
        ]
    )
    routine_rows = [
        {
            "Pet": pet.name,
            "Routine": routine.title,
            "Repeats": describe_repeat(routine),
            "Time": routine.scheduled_time.strftime("%H:%M"),
            "Minutes": routine.duration_minutes,
            "Priority": routine.priority.value,
            "Category": routine.category,
            "Active": "Yes" if routine.is_active else "No",
        }
        for pet in owner.pets
        for routine in pet.get_care_routines()
    ]
    if routine_rows:
        st.table(routine_rows)
    else:
        st.info("No tasks scheduled yet. Add one above.")
else:
    st.info("No pets yet. Add one above.")

st.divider()

schedule_tab, overdue_tab = st.tabs(["Build Schedule", "Overdue Tasks"])

with schedule_tab:
    st.subheader("Build Schedule")
    st.caption("Choose a day to view your pets' care.")
    selected_day = st.date_input("Day", value=date.today(), key="schedule_day")
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        pet_choice = st.selectbox(
            "Show pet",
            ["All pets"] + list(dict.fromkeys(p.name for p in owner.pets)),
            key="schedule_pet",
        )
    with filter_col2:
        status_choice = st.selectbox("Show status", ["All", "Pending", "Completed"], key="schedule_status")

    if st.button("Generate schedule"):
        st.session_state.show_schedule = True

    if st.session_state.get("show_schedule"):
        scheduler = Scheduler(owner)
        plan = scheduler.generate_schedule(selected_day)
        pet_name = None if pet_choice == "All pets" else pet_choice
        completed = {"All": None, "Pending": False, "Completed": True}[status_choice]
        visible_ids = {task.task_id for task in scheduler.filter_tasks(pet_name, completed)}
        included = [task for task in plan.included if task.task_id in visible_ids]
        excluded = [task for task in plan.excluded if task.task_id in visible_ids]
        day_conflicts = find_unaccepted_overlaps(scheduler, selected_day)
        conflict_ids = {task.task_id for group in day_conflicts for task in group}
        st.markdown(f"**Tasks for {selected_day:%A, %B %d, %Y}**")
        totals = st.columns(2)
        with totals[0].container(key="care_total_completed"):
            st.metric("Completed care", f"{plan.completed_minutes} min", border=True)
        with totals[1].container(key="care_total_planned"):
            st.metric("Planned care", f"{plan.planned_minutes} min", border=True)
        st.subheader("Today's plan", anchor="todays-plan")
        st.caption(
            f"Showing {len(included)} of {len(plan.included)} tasks, sorted by time, then priority and title. "
            "Filters only change visible rows; care totals and overlap reviews still cover all pets."
        )

        for pair in day_conflicts:
            key = overlap_key(pair)
            overlap_start = max(datetime.combine(selected_day, time.min), *(task.scheduled_date_time for task in pair))
            overlap_end = min(datetime.combine(selected_day + timedelta(days=1), time.min), *(task.end_date_time for task in pair))
            st.warning(
                f"**Overlapping care: {format_time_range(overlap_start, overlap_end)}**\n\n"
                f"{scheduler.conflict_warning(pair)}\n\n"
                "Choose **Reschedule a task** to move one occurrence, or **Keep both** "
                "if you can do this care together. Keeping both acknowledges the overlap without moving either task.",
                icon="⚠️",
            )
            with st.container(horizontal=True):
                st.button(
                    "Reschedule a task", key=f"edit_{key}", on_click=begin_rescheduling, args=(pair,),
                )
                st.button("Keep both", key=f"keep_{key}", on_click=accept_overlap, args=(pair,))

        if not day_conflicts and (plan.included or plan.excluded):
            st.success("No overlaps need review for this day.")

        if included:
            show_plan_tasks(owner, included, conflict_ids)
        else:
            st.info("No tasks in this view.")

        if excluded:
            st.subheader("Not included in this plan")
            show_plan_tasks(owner, excluded, key="excluded")


with overdue_tab:
    st.subheader("Overdue Tasks")
    st.caption(
        "Incomplete tasks from earlier days. Mark them done, or delete them all. "
        "Deleting them gives active repeating routines a fresh task today or later."
    )
    overdue_tasks = owner.view_overdue_tasks()
    if overdue_tasks:
        header = st.columns([2, 2, 3, 2, 2])
        for column, label in zip(header, ["Due", "Pet", "Task", "Priority", "Done"]):
            column.markdown(f"**{label}**")
        for task in overdue_tasks:
            pet = owner.get_pet_for_task(task)
            done_key = f"overdue_done_{task.task_id}"
            st.session_state[done_key] = task.completion_status
            due_col, pet_col, task_col, priority_col, done_col = st.columns([2, 2, 3, 2, 2])
            due_col.write(f"{task.scheduled_date_time:%b %d, %H:%M}")
            pet_col.write(pet.name)
            task_col.write(f"{task.title} ({task.duration_minutes} min)")
            priority_col.write(task.priority.value)
            done_col.checkbox(
                f"Done: {pet.name} {task.title}",
                key=done_key,
                label_visibility="collapsed",
                on_change=set_done,
                args=(task, done_key),
            )
        with st.popover(f"Delete all {len(overdue_tasks)} overdue tasks"):
            st.write("This permanently deletes every overdue task that is not completed.")
            st.button("Yes, delete them", key="confirm_clear_overdue", on_click=owner.clear_overdue_tasks)
    else:
        st.info("No overdue tasks.")

    if os.environ.get("PAWPAL_TESTING") == "1":
        with st.expander("Testing only: sample overdue tasks"):
            st.warning(
                "**For testing only.** In PawPal+, tasks are only created from today forward, so a task "
                "normally becomes overdue after its day passes. This button adds two sample tasks dated "
                "1 and 2 days ago to the pet you choose, so you can try the Overdue tab right away. "
                "They are not real tasks. Use \"Delete all overdue tasks\" to remove them. "
                "Nothing is saved when you close or refresh the page."
            )
            if owner.pets:
                st.selectbox(
                    "Add sample tasks for",
                    range(len(owner.pets)),
                    format_func=lambda i: owner.pets[i].name,
                    key="sample_pet",
                )
                st.button(
                    "Add sample overdue tasks",
                    key="add_sample_overdue",
                    on_click=add_sample_overdue,
                )
            else:
                st.info("Add a pet first, then choose it here.")

scroll_target = st.session_state.pop("scroll_target", None)
if scroll_target in {"schedule-a-task", "todays-plan"}:
    st.html(
        f'''<script>requestAnimationFrame(() => {{
            document.getElementById("{scroll_target}")?.scrollIntoView({{behavior: "smooth", block: "start"}});
        }});</script>''',
        unsafe_allow_javascript=True,
    )
