# PawPal+

**PawPal+** is a Streamlit pet-care planner with a Python scheduling backend. It helps an owner organize care across multiple pets, complete recurring tasks, and manage overlapping schedules.

## Scenario

A busy pet owner needs a clear view of walks, feeding, medications, grooming and appointments across their pets. PawPal+ keeps each pet's routines together and shows dated tasks in chronological order.

## Features

- Enter an owner name and add pets by name and species.
- Schedule one-time, daily, weekly or monthly care with a time, duration, priority and optional end date.
- View a day's tasks sorted by time, with priority breaking ties, and filter by pet or completion status.
- Generate a daily plan containing all scheduled care, with explanations and completed/planned minute totals.
- Complete recurring care on its scheduled day or later to create or reuse the next occurrence from the completion date.
- Review red overlap warnings, choose a new date and time, or keep both tasks and dismiss that overlap.
- Complete or delete overdue tasks, with active repeating routines continuing after deletion.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the app and CLI demo

```bash
streamlit run app.py
```

```bash
python main.py
```

Pets and tasks stay in the Streamlit browser session. A new session starts empty; there is no file persistence yet.

## 🧩 Implementation Summary

The backend lives in `pawpal_system.py` as five main classes plus a `DailyPlan` result dataclass, and `main.py` is a CLI demo that uses them.

The current working architecture is in `diagrams/uml_draft.mmd`.

| Class | What it does |
|---|---|
| `PetOwner` | Owns the pets and collects every task through `get_all_tasks()`. Optional time limits remain available to direct Python callers. |
| `Pet` | Holds a pet's profile and its care routines. |
| `CareRoutine` | A recurring activity that generates tasks and stores its care category. |
| `CareTask` | One dated occurrence of a routine, which can be completed or rescheduled. |
| `Scheduler` | Organizes tasks across all pets, builds explained daily plans, sorts and filters tasks, detects conflicts, suggests free times and completes tasks. |
| `DailyPlan` | Holds included and excluded tasks, reasons keyed by task ID, and completed, planned and remaining minutes. |

**How they work together**

1. A `PetOwner` has many `Pet`s, a `Pet` has many `CareRoutine`s, and a `CareRoutine` generates many `CareTask`s.
2. Adding a routine with `Pet.add_routine()` links it to the pet and generates its first pending task on or after today and its start date. A routine repeats once, daily, weekly or monthly, every N units, between a start date and an optional end date. Each routine also has a duration in minutes and a priority (low, medium or high), which its tasks inherit.
3. The `Scheduler` gets all tasks from `PetOwner.get_all_tasks()`, which walks pets, then routines, then tasks. It sorts and filters them, so the today view, the overdue view and conflict detection (tasks whose times overlap) all start from that one list.
4. `Scheduler.build_daily_plan(day)` includes that day's existing tasks across all pets by default and keeps completed history visible. Results are displayed chronologically, and pet/status filters are applied afterward. Direct Python callers can still set optional time limits; within those limits pending tasks are considered by priority, then time, title and ID. The Streamlit app clears earlier saved limits and includes all scheduled care.

**Behaviors worth knowing**

- All scheduled care is treated as required. Each routine defaults to category **Other**; categories are Other, Exercise, Play, Training, Grooming and Meal. Categories label care without affecting inclusion, and titles are not interpreted automatically. The app renames General categories left in an existing browser session to Other.
- `PetOwner.set_preferences()` retains optional available-hours and daily-care-time limits for direct Python callers. Available hours need both times, with the end later on the same day; daily care time is a nonnegative whole number of minutes. Completed care consumes any time allowance. Invalid updates change nothing. The app clears saved limits from earlier versions, so every task for the selected day is included before display filters.
- Every included or excluded task has an explanation. Tasks outside the plan remain saved with their original times and completion controls. `build_daily_plan()` selects existing tasks without changing them. The app calls `generate_schedule()` first to create any missing occurrences for the selected day, then applies the same planning rules.
- Task selection uses a simple priority-first greedy algorithm when time limits are set, so it does not guarantee the largest number of tasks or the best possible use of every minute. Overlapping tasks can both be included; each task's duration counts separately, and the existing conflict controls leave the final decision with the owner.
- Tasks are only generated from today forward, so a deleted overdue task never comes back.
- A task the user rescheduled is never overwritten when its routine is updated. Routine edits replace future pending tasks, keeping completed history and overdue tasks, and generate at most one pending occurrence.
- Removing a routine deletes its pending tasks but keeps completed ones as history.
- Invalid edits (an unknown field, an interval below 1) raise an error instead of silently changing data.
- Completing a daily, weekly or monthly task creates the next occurrence (`Scheduler.mark_task_complete()`) using the completion date: today + interval days, today + 7 × interval days, or today + interval months (clamping the day for shorter months). The routine's scheduled time is kept, even when the completed task was overdue or rescheduled. Nothing is created before the start date, past the end date, for one-time tasks or for a removed routine. Repeating the completion creates no duplicate, and reopening a task keeps its next occurrence.
- Future recurring occurrences cannot be completed early: the backend rejects early completion before changing task status. Each future pending recurring row has its own disabled Done checkbox, while one-time tasks can still be completed early.
- **Generate schedule** fills the selected day using each routine's start date, repeat interval and optional end date. Daily, weekly and monthly tasks appear even if earlier tasks are still pending. Monthly dates clamp to the last day of shorter months without shifting later months. Repeated generation preserves completed and rescheduled tasks without duplicates. If an overdue task is deleted, an active repeating routine gets a fresh pending occurrence today or later on its routine schedule; one-time tasks stay deleted.
- Overlaps can be intentional, such as walking two dogs together. The app lets the owner reschedule a task manually or choose **Keep both**, which dismisses that pair's warning and clears its conflict markers without changing either task. Acceptance lasts for those occurrences at their current times and durations in the browser session. Changed or new overlaps need review again. The backend still detects all actual overlaps; `conflict_warning()` provides shared readable text, and `next_free_slot()` remains available for Python callers and the CLI demo.

**Design note**

Frequency is stored on `CareRoutine`, and each `CareTask` is one dated occurrence of its routine. `generate_tasks()` seeds at most one pending occurrence by default; `first_only=False` fills a bounded date range for calendar scheduling. `Scheduler.generate_schedule(day)` fills only the selected day and then calls `build_daily_plan(day)`. `complete_task()` creates or reuses its successor from the completion date. The classes use more specific names than a generic owner, pet and task model: `PetOwner`, `CareRoutine` and `CareTask`. Marking a task complete is `CareTask.set_completion_status()`, and `Scheduler.mark_task_complete()` completes it and creates the routine's next occurrence.

**Streamlit app**

`app.py` connects the Streamlit forms and controls to the backend. Its `filter_plan_tasks()` helper applies pet and status filters after planning, preserving task order. `show_plan_tasks()` renders compact table-style rows using native Streamlit columns and a final Done checkbox. `set_done()` handles completion and reopening through the existing methods. Escaped HTML supplies small theme-aware priority and overlap badges, and `format_time_range()` shows each task's start and end in AM/PM form. `find_unaccepted_overlaps()` identifies actual overlapping pairs needing review and removes stale acceptance records. `accept_overlap()` remembers a pair's current IDs, times and durations in session state. `begin_rescheduling()` opens the usual task form with prefilled values; a small fixed navigation script scrolls to that form and back to the plan. Run the app with `streamlit run app.py`.

- Forms add pets (`PetOwner.add_pet()`) and tasks (`Pet.add_routine()`).
- **Schedule a Task** creates routines with a care category, defaulting to Other and a 30-minute duration. In reschedule mode, the same form is prefilled for a selected task occurrence. The owner can choose either overlapping task, change its Time and Start date, and click **Reschedule task** or **Cancel**. Pet, title, duration, priority, recurrence and category stay visible but read-only, so rescheduling moves only that occurrence. Saving or canceling returns to the plan. The original **Scenario** and **What you need to build** sections remain above the forms.
- **Pets and Tasks** lists pets with a count of care routines, followed by each routine's repeat pattern, time, duration, priority, category and active status.
- **Build Schedule** includes all care for the selected day. **Today's plan** has Time, Pet, Task, Priority, Overlap and Done columns. Times show full ranges such as **8:15–8:45AM**. High priority has a purple badge, Medium a warm gold badge and Low a neutral badge. Red Overlap badges mark tasks needing review. Done remains the last column, with a native checkbox for each occurrence. The **Not included in this plan** table appears only when there are excluded results and also ends with Done checkboxes. Completed/planned minute totals appear above the table. Pet and status filters change only the view; the plan and totals still cover all pets.
- Each unaccepted overlap has a small red badge showing the exact overlapping interval, followed by **Reschedule a task** and **Keep both**. Reschedule a task scrolls to the prefilled Schedule a Task form. Keep both removes that pair's warning and badges immediately; other unaccepted overlaps remain visible. Reviews include all pending care occupying that day, including hidden tasks and care continuing from the previous day. The former Schedule overview grid has been removed.
- **Overdue Tasks** lists incomplete tasks from earlier days, where they can be marked done or all deleted. To try it without waiting a day, start the app with `PAWPAL_TESTING=1 streamlit run app.py`. A testing-only section then appears that adds sample overdue tasks for a chosen pet. It is hidden for normal use, since real tasks are never created in the past.

Run the tests with `python -m pytest`.

The Python backend also supports editing pet profiles and routines and removing routines. The current Streamlit interface exposes pet and routine creation, task completion, conflict rescheduling and overdue cleanup.

## 🖥️ Sample Output

Running `python main.py` walks through sorting and filtering, conflicts and rescheduling, recurring completion, overdue cleanup, and a daily plan containing all scheduled care with explanations. Sample dates reflect the run shown below:

```
Owner: Karina
Date: 2026-10-17

Added out of order
------------------------------------------------------------
18:00 | Luna     | Brush fur            | Pending
08:00 | Luna     | Breakfast            | Completed
18:00 | Mochi    | Evening walk         | Pending
09:30 | Mochi    | Morning walk         | Pending

Today's Schedule (sorted by time)
------------------------------------------------------------
08:00 | Luna     | Breakfast            | Completed
09:30 | Mochi    | Morning walk         | Pending
18:00 | Luna     | Brush fur            | Pending
18:00 | Mochi    | Evening walk         | Pending

Filtered by pet: Luna
------------------------------------------------------------
08:00 | Luna     | Breakfast            | Completed
18:00 | Luna     | Brush fur            | Pending

Filtered by status: completed
------------------------------------------------------------
08:00 | Luna     | Breakfast            | Completed

Filtered by status: pending
------------------------------------------------------------
09:30 | Mochi    | Morning walk         | Pending
18:00 | Luna     | Brush fur            | Pending
18:00 | Mochi    | Evening walk         | Pending

Conflicts today
------------------------------------------------------------
Time conflict: Luna: Brush fur (18:00), Mochi: Evening walk (18:00)
Suggested time for Mochi's Evening walk: 18:30
Keep as scheduled: nothing changes, conflicts still found: 1
Reschedule: Evening walk moved to 18:30, conflicts now: 0

Completing a daily task
------------------------------------------------------------
Evening walk on Oct 17 completed -> next: Oct 18 18:00 (tasks: 1 -> 2)
Completing the same task again creates no duplicate (tasks: 2 -> 2)

Overdue tasks (two past tasks added by hand for this demo)
------------------------------------------------------------
Oct 15 08:00 | Luna     | Breakfast            | Pending
Oct 16 09:30 | Mochi    | Morning walk         | Pending

Overdue after marking the oldest one done
------------------------------------------------------------
Oct 16 09:30 | Mochi    | Morning walk         | Pending

Overdue after deleting all
------------------------------------------------------------
(none)

Daily care plan
Completed: 15 min | Planned: 105 min

Today's plan
------------------------------------------------------------
08:00 | Luna     | Breakfast
  Already completed.
09:00 | Luna     | Medication
  High priority; scheduled care.
10:00 | Mochi    | Long walk
  Medium priority; scheduled care.
11:00 | Mochi    | Short walk
  Medium priority; scheduled care.
18:00 | Luna     | Brush fur
  Low priority; scheduled care.
20:00 | Mochi    | Playtime
  High priority; scheduled care.

Not included in this plan
------------------------------------------------------------
(none)
```

## Testing PawPal+

After completing **Setup** and activating the virtual environment, run the automated tests from the project root:

```bash
python -m pytest
```

The backend suite in `tests/test_pawpal.py` covers:

- Task completion status and task creation when a routine is added to a pet.
- Chronological sorting, with priority and title breaking ties.
- Pet/routine/task links and daily, weekly and monthly schedule generation.
- Creating the next day's task when daily care is completed.
- Filtering by pet, completion status or both.
- Daily-plan minute totals and explanations for exclusions under optional Python time limits.
- Overlap detection and rescheduling while preserving the original occurrence's identity.
- Overdue cleanup that preserves completed history and restarts an active recurring routine.

Terminal output from a successful `python -m pytest` run (local path omitted):

```text
======================== test session starts ========================
platform darwin -- Python 3.13.9, pytest-9.1.1, pluggy-1.7.0
plugins: anyio-4.15.1
collected 14 items

tests/test_pawpal.py ..............                           [100%]

======================== 14 passed in 0.07s =========================
```

**Confidence Level: ★★★★☆ (4/5 stars)**

All 14 automated tests passed, giving confidence in the core backend workflows: scheduling, completion, filtering, daily-plan totals, conflict handling and overdue cleanup. The fifth star would require broader coverage, including automated Streamlit interface tests and edge cases such as month-end recurrence and repeated completion.

For manual checks of the Streamlit interface, run `streamlit run app.py` and try these workflows:

1. Add two pets and schedule several tasks, including two with overlapping times. Generate a schedule and check task order, time ranges and minute totals.
2. Apply the pet and status filters. Confirm the visible rows change while the plan's totals still cover all pets.
3. Complete a daily task scheduled for today. Confirm it appears completed and its next occurrence appears tomorrow. Future recurring tasks should have disabled Done checkboxes.
4. Review an overlap using **Reschedule a task** and move one task to a free time. For another overlap, choose **Keep both** and confirm its warning clears without changing the tasks.
5. To exercise overdue care, restart with `PAWPAL_TESTING=1 streamlit run app.py`, use the testing-only section to add sample overdue tasks, then try completing and deleting them in **Overdue Tasks**.

These interface workflows are manual checks; the retained pytest suite tests the Python backend.

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()` | By scheduled time, then highest priority first, then title. |
| Optional Python time limits | `PetOwner.set_preferences()` | Direct Python callers can set same-day availability and care-time limits. Invalid changes leave saved limits unchanged. The app clears these limits to include all care. |
| Daily care and explanations | `Scheduler.build_daily_plan(day)` | Returns a `DailyPlan` containing all of the day's care by default, including completed history. Any limits set by direct Python callers use priority, time, title and ID to choose pending care. Every inclusion or exclusion has a reason. Planning changes no tasks. |
| Filtering | `Scheduler.filter_tasks()`, `tasks_on()`, `overdue_tasks()`, `upcoming_tasks()`; `filter_plan_tasks()` in `app.py` | Backend queries filter before sorting. Streamlit filters the existing plan lists by pet (case-insensitive) and/or completion status after planning, preserving their order and the shared plan selection. |
| Conflict handling | `Scheduler.find_conflicts()`, `Scheduler.conflict_warning()`, `CareTask.reschedule()`; UI acceptance in `app.py` | Finds tasks whose time ranges overlap. The UI highlights pairs needing review and lets the owner reschedule manually or choose Keep both. Acceptance clears that pair's warning and markers for its current occurrences, times and durations. The backend's `next_free_slot()` remains available to the CLI and Python callers. |
| Recurring tasks | `CareRoutine.generate_tasks()`, `Scheduler.generate_schedule()`, `CareRoutine.complete_task()`, `Scheduler.mark_task_complete()` | One pending occurrence when added; generating a schedule creates missing occurrences for the selected day even if earlier care is incomplete. Completing a repeating task on its scheduled day or later creates or reuses its successor from today's date: +interval days, +7 × interval days or +interval months, at the routine's scheduled time. Future repeating tasks cannot be completed early, and duplicate completions are safe. |
| Overdue tasks | `PetOwner.view_overdue_tasks()`, `clear_overdue_tasks()` | Incomplete tasks from earlier days, kept out of today's list. They can be marked done or all deleted. Deleting one restarts its active repeating routine with a fresh occurrence today or later. |

## 📸 Demo Walkthrough

Follow this workflow in the Streamlit app. The CLI output in **Sample Output** above demonstrates sorting, filters, conflicts, rescheduling, recurrence, overdue cleanup and explained planning.

1. Activate the virtual environment and run `streamlit run app.py`.
2. **Add a pet:** enter a name and species, then click **Add pet**.
3. **Schedule a task:** choose the pet, a title, duration, priority, time, repeat pattern, start date and care category. Click **Add task** to create its first pending occurrence.
4. **See a day's plan:** under **Build Schedule**, pick a day and click **Generate schedule**. **Today's plan** shows all care for that selected day. Recurring tasks appear on their matching dates even if earlier tasks are incomplete. Review the completed/planned minute totals above the table. Pet and status filters affect only which results you see.
5. **Complete a task:** check the last **Done** column. The plan recalculates immediately, and completed care remains visible unless a display filter hides it. Future recurring care cannot be completed early. For a daily task with interval 1, a new task is created for tomorrow at the routine's scheduled time. Weekly and monthly tasks use the same completion-date rule with their interval. Uncheck it to reopen the task; its successor is kept, and checking it again creates no duplicate.
6. **Handle a conflict:** red **Overlap** badges identify care needing review. Choose **Reschedule a task** to return to the prefilled **Schedule a Task** form. Choose which task to move, change **Time** or **Start date**, then click **Reschedule task**. Or choose **Keep both** to dismiss that pair's warning without moving or completing its tasks. Its badges disappear unless another overlap still needs review. Changed or new overlaps get flagged again. Pending tasks hidden by display filters are still considered.
7. **Review overdue tasks:** the **Overdue Tasks** tab lists incomplete tasks from earlier days, where they can be marked done or all deleted. To try it without waiting a day, start the app with `PAWPAL_TESTING=1 streamlit run app.py` and use the testing-only section.

**Screenshot or video** *(optional)*: not included.
