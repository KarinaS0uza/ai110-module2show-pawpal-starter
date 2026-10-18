# PawPal+

**A pet-care planner for owners managing everyday care across multiple pets.**

PawPal+ combines a Streamlit interface with scheduling logic for everyday pet care. Organize feeding, walks, medication, grooming and appointments; track completed care; and review overlapping tasks in one daily plan.

> **Local JSON storage:** owner details, pets, routines and tasks are saved automatically to `data.json` beside `app.py` and restored in new sessions and after server restarts. Overlap acknowledgments and display settings remain in the current browser session.

## Contents

- [Features](#features)
- [Getting started](#getting-started)
- [Data persistence](#data-persistence)
- [User guide](#user-guide)
- [Scheduling rules](#scheduling-rules)
- [Professional UI and output formatting (Challenge 4)](#professional-ui-and-output-formatting-challenge-4)
- [Implementation summary](#implementation-summary)
- [Demo Walkthrough](#demo-walkthrough)
- [Testing PawPal+](#testing-pawpal)
- [Troubleshooting](#troubleshooting)
- [Current limitations](#current-limitations)

## Features

- **Data persistence:** automatically save pet profiles, routines, task completion and rescheduled occurrences to a local `data.json` file.
- **Priority-based scheduling:** combine tasks across pets and sort High → Medium → Low first, then by scheduled date and time. Title and task ID break remaining ties. Explicit chronological sorting remains available through `Scheduler.sort_by_time()`.
- **Filtering by pet and status:** match pet names without case sensitivity and filter by pending/completed status. Interface filters preserve plan order and totals for all pets.
- **Conflict warnings:** detect overlapping time ranges among incomplete tasks and show the affected pets, tasks and overlapping interval. Tasks that only touch at an endpoint do not conflict.
- **Manual conflict resolution:** move one occurrence while preserving its ID and original slot, or choose **Keep both** to acknowledge an intentional overlap for its current times and durations.
- **Daily, weekly and monthly recurrence:** completing repeating care creates or reuses its next occurrence from the completion date, using the repeat interval and routine's usual time. Monthly dates clamp to the last valid day of shorter months; future repeating tasks cannot be completed early.
- **Calendar schedule generation:** create missing occurrences for a selected day from each routine's start date, repeat interval and optional end date, even if earlier care is incomplete. Existing original slots prevent duplicate generation and preserve rescheduled tasks.
- **Daily plan totals and explanations:** include all scheduled care by default and sum completed and pending care minutes separately. The backend and CLI provide reasons for each task's inclusion or exclusion.
- **Optional care-time limits (backend only):** use a greedy algorithm to select pending care by priority, then time, title and ID, subject to availability and remaining care minutes. Completed care consumes the allowance; excluded tasks stay saved.
- **Free-slot suggestions (backend and CLI):** scan pending tasks in time order to find the earliest gap long enough for a task at or after a requested start time.
- **Overdue detection and cleanup:** identify incomplete tasks dated before today. Completing or deleting them preserves completed history; deleting overdue care lets active repeating routines generate a fresh occurrence today or later.

## Getting started

### Prerequisites

- A local Python environment with pip. Verified environment: **Python 3.13.9**, **Streamlit 1.66.0** and **pytest 9.1.1**.
- A terminal opened in this repository's root directory, where `app.py` and `requirements.txt` are located.

No API keys, database setup or external service accounts are required. Dependencies are listed in [requirements.txt](requirements.txt).

### 1. Create and activate a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

With the environment activated:

```bash
python -m pip install --upgrade -r requirements.txt
```

The upgrade flag also updates older installations. The interface uses Streamlit APIs newer than the minimum declared in `requirements.txt`; the verified version above is a reference if an older environment fails.

### 3. Start the app

```bash
python -m streamlit run app.py
```

Open the local URL printed in the terminal, normally [http://localhost:8501](http://localhost:8501). Stop the server with **Ctrl+C**.

To run the terminal demonstration instead:

```bash
python main.py
```

The CLI creates its own sample data and demonstrates sorting, filtering, conflicts, rescheduling, recurring completion, overdue cleanup and explained planning. It does not share data with the browser app.

## Data persistence

**Challenge 2** uses the built-in `json` module and custom dictionary conversion, with no additional dependency. `PetOwner` contains all pets, routines and tasks, so saving the owner saves the complete care history.

1. When a new browser session opens, the app calls `PetOwner.load_from_json()` to read `data.json` beside `app.py`. If the file is missing, the owner name and email start blank, with no pets. An empty first visit does not create a saved file.
2. After you enter an owner name or add a pet, `owner.save_to_json()` saves the current data at the end of each successful app run. Adding pets or routines, generating schedules, completing or reopening tasks, deleting overdue tasks and editing the owner's name are saved this way. Rescheduling also saves immediately before its explicit rerun.
3. Closing or refreshing the browser and restarting the server preserve the saved data. The next session rebuilds the owner, pets, routines and tasks from the file.

Saving uses `dataclasses.asdict()` to produce nested dictionaries. Dates, times and datetimes become ISO-format strings, and enum values become strings such as `"daily"` and `"high"`. Loading reverses these conversions and preserves object IDs, parent links, completion status and each task's original and current scheduled times. It does not generate extra occurrences while rebuilding routines. ID counters continue above saved IDs and any IDs already assigned in the running process. Counters survive module reloads, and `PetOwner.sync_id_counters()` reserves the current session's IDs before forms create more care. Saving rejects duplicate IDs before replacing the existing file.

To save and load an existing `owner` directly:

```python
from pawpal_system import PetOwner

owner.save_to_json("data.json")
restored_owner = PetOwner.load_from_json("data.json")
```

Both methods default to `data.json` in the caller's working directory. The Streamlit app explicitly uses the file beside `app.py`, regardless of where it is launched. `main.py` remains a separate sample-data demonstration.

The JSON methods also preserve the backend's optional availability window and daily care-minute allowance. On each run, the Streamlit app clears those limits so all scheduled care stays included, then saves the owner with the limits unset.

Saving writes a temporary file in the same directory, then replaces `data.json` after writing finishes. If loading fails, the app shows an error and stops without replacing the saved file. If saving fails, the app reports that the latest changes could not be saved. Keep a copy of `data.json` to back up your care records; invalid data must be repaired or moved aside before starting fresh. Generated data and temporary save files are ignored by Git.

Files modified for this feature:

| File | Change |
|---|---|
| `pawpal_system.py` | Adds `PetOwner.save_to_json()` and `PetOwner.load_from_json()`, JSON conversion and ID counter restoration. |
| `app.py` | Loads at session startup, autosaves changes, handles file errors and updates storage messages. |
| `.gitignore` | Excludes generated `data.json` and temporary save files. |
| `tests/test_pawpal.py` | Tests restored profiles, care history, IDs, invalid data and failed saves. |
| `diagrams/uml_final.mmd` | Includes the owner's JSON save/load methods alongside the scheduling API. |
| `README.md` | Documents persistence, verification and limitations. |

## User guide

### Add pets and care routines

1. Enter your name under **Owner**.
2. Under **Add a Pet**, enter a pet name, choose **dog**, **cat** or **other**, and click **Add pet**. Repeat for each pet.
3. Under **Schedule a Task**, choose a pet and enter a title, care category, start date, time, duration and priority.
4. Set **Repeats** to **Once**, **Daily**, **Weekly** or **Monthly**. For repeating care, **Every N** controls the interval: for example, Weekly with Every N = 2 means every two weeks. Leave **End date (optional)** empty for an ongoing routine.
5. Click **Add task**. **Pets and Tasks** lists the pets and their routine settings.

A new task defaults to 30 minutes, Medium priority and the Other category. Supported categories are Other, Exercise, Play, Training, Grooming and Meal. Categories are labels; they do not change which tasks are included.

### Build and filter a daily plan

1. Open **Build Schedule**, select **Day**, then click **Generate schedule**.
2. Review **Completed care** and **Planned care** totals above **Today's plan**. Despite its heading, this table shows the selected day, which may differ from today.
3. Use **Show pet** and **Show status** to narrow the visible rows.

The table shows **Time**, **Pet**, **Task**, **Priority**, **Overlap** and **Done**. Rows appear in High → Medium → Low order, with earlier times first within each priority. Time ranges include the full duration; tasks ending on another day show a day offset. All scheduled care is included before display filters. Filters change visible rows only: minute totals and overlap reviews still cover all pets.

After the first **Generate schedule** click, the plan rebuilds on later interactions, including changing **Day**. Any missing occurrences generated for that day are saved automatically.

### Complete or reopen care

Check the task's **Done** checkbox. Completed care remains visible when **Show status** is All or Completed. Uncheck Done to reopen it.

Completing a repeating task creates or reuses its next occurrence based on the completion date, at the routine's usual time. For example, completing a daily task today creates tomorrow's occurrence. Future repeating tasks have disabled Done checkboxes until their scheduled day; one-time tasks can be completed early. Reopening a task keeps its successor, and completing it again creates no duplicate.

### Review overlapping tasks

Warnings above the plan name the pets and tasks and show the overlapping interval. Red **Overlap** badges identify affected rows. Choose either action:

- **Reschedule a task:** the app opens the prefilled **Schedule a Task** form. Select the occurrence to move, change **Time** or **Start date**, then click **Reschedule task**. Other fields remain read-only. **Cancel** returns to the plan without saving.
- **Keep both:** acknowledge intentional overlap, such as walking two dogs together. This clears that pair's warning and badges without moving or completing either task. Another unresolved overlap can still keep a task's badge visible.

Overlap reviews include pending care hidden by filters and care continuing from the previous day. Acknowledgment applies to the current task occurrences, times and durations; changed or new overlaps need review again. The app shows **No overlaps need review for this day** when all overlaps have been handled.

### Manage overdue care

Open **Overdue Tasks** to see incomplete care dated before today. Mark individual tasks done or choose **Delete all … overdue tasks**, then **Yes, delete them** to remove all pending overdue occurrences.

Completed history remains saved in `data.json`. Deleting an overdue occurrence allows an active repeating routine to continue with a fresh occurrence today or later. One-time tasks stay deleted.

## Scheduling rules

| Behavior | Rule |
|---|---|
| First occurrence | Adding a routine creates at most one pending occurrence on or after today and its start date, within its optional end date. Normal schedule generation does not backfill past days. |
| Calendar generation | **Generate schedule** fills matching occurrences for the selected day, anchored to each routine's start date and repeat interval, even if earlier care remains incomplete. Repeated generation preserves completed and rescheduled occurrences without duplicates. |
| Day membership | Plan rows and minute totals belong to the day an occurrence starts. An overnight task contributes its full duration to that day; overlap warnings can also appear on the following day while it is still running. |
| Completion-based recurrence | Completing repeating care creates or reuses a successor from the completion date: +N days, +7 × N days or +N months. It uses the routine's scheduled time, even if the completed occurrence was overdue or moved. Start and end dates still apply. |
| Monthly dates | Dates clamp to the last valid day of shorter months. Calendar generation stays anchored to the original start date, so a January 31 routine can fall on February 28 and March 31. |
| Plan order | Tasks display High → Medium → Low first, then by scheduled date and time, title and task ID. Completed care retains its priority and stays included. |
| Rescheduling | Moving an occurrence preserves its ID and original slot. It does not change the routine's usual time or repeat pattern. |
| Overlaps and totals | Pending tasks conflict when their time ranges overlap; tasks that only touch at an endpoint do not. Both can remain in the plan. Each task contributes its full duration to the totals, including acknowledged overlaps. |

### Priority-based scheduling (Challenge 3)

`CareTask.priority` supports `Priority.LOW`, `Priority.MEDIUM` and `Priority.HIGH`, with Medium as the default. A routine's priority is copied to its generated tasks and preserved in `data.json`.

`Scheduler.sort_by_priority()` orders tasks by priority first, then scheduled date and time. `get_tasks()`, day queries, pet/status filters and daily plans use this order. A High task at 20:00 appears before a Medium task at 08:00; two High tasks appear in time order. Sorting changes the order of the results while preserving task times and completion status.

The CLI example below prints a **Today's Schedule (priority first, then time)** section with explicit priority labels, followed by the daily plan in the same order. It demonstrates High Medication at 09:00 and High Playtime at 20:00 before Medium Breakfast at 08:00, with Low Brush fur last.

`sort_by_time()` remains available for chronological views. Conflict detection and next-free-slot scans explicitly use it, and overdue/upcoming lists stay chronological.

### Optional time limits in the backend

The Streamlit app clears owner time limits and includes all scheduled care. The backend's `PetOwner.set_preferences()` method can set a same-day availability window and/or a daily care-minute allowance.

With limits set, `Scheduler.build_daily_plan(day)` considers pending tasks by priority, then time, title and ID. Each task must fit completely within the availability window and remaining allowance. Completed care stays included and consumes the allowance. Excluded tasks remain saved, and `DailyPlan.reasons` explains every inclusion or exclusion.

Both availability times must be supplied, with the end later on the same day. The daily allowance must be a nonnegative whole number of minutes; invalid preference changes leave existing values unchanged. Selection uses a priority-first greedy algorithm, so it does not guarantee the most tasks or the best use of every minute.

## Professional UI and output formatting (Challenge 4)

PawPal+ uses **Streamlit**, custom CSS and Python string formatting to make care schedules easier to scan.

| Formatting feature | Functions or libraries used |
|---|---|
| Color-coded priority and overlap badges | `badge_html()` creates labeled badges: purple for High, gold for Medium, gray for Low and red for Overlap. Custom CSS added through `st.html()` supports light and dark themes. |
| Structured task rows and tables | `show_plan_tasks()` uses `st.columns()` and `st.container()` to align Time, Pet, Task, Priority, Overlap and Done. `st.table()` displays pet and routine summaries. |
| Readable time ranges | `format_time_range()` uses `datetime.strftime()` to produce compact AM/PM ranges and adds a day offset for care that ends on a later day. |
| Color-coded care totals | `st.metric()` and custom CSS display completed minutes in green and planned minutes in purple. |
| Clear feedback and icons | `st.success()`, `st.warning()`, `st.error()` and `st.info()` distinguish confirmations, warnings, errors and guidance. The app uses a 🐾 title/page icon and a ⚠️ icon for overlap warnings. |
| Aligned CLI output | `print_tasks()` in `main.py` uses Python f-strings with fixed-width fields and separators to align pet names, task titles and optional priority labels, alongside times and Completed/Pending status. |

The interface helpers are defined in `app.py`. Streamlit is listed in `requirements.txt`; the CLI formatting uses Python's built-in `print()` and f-strings.

## Implementation summary

The backend uses five main domain/scheduling classes plus the `DailyPlan` result dataclass. The [final UML diagram](diagrams/uml_final.mmd) documents all six dataclasses, the `Frequency` and `Priority` enums, and their relationships.

| Class | Responsibility |
|---|---|
| `PetOwner` | Owns pets, saves/loads the full care history as JSON, gathers tasks through `get_all_tasks()`, stores optional time limits and supports overdue cleanup. |
| `Pet` | Holds a pet profile and its care routines. |
| `CareRoutine` | Defines recurrence, category, duration and priority; generates occurrences and handles recurring completion. |
| `CareTask` | Represents one dated occurrence, tracks completion and preserves its original slot when moved. |
| `Scheduler` | Sorts schedules by priority and then time, filters across pets, builds daily plans, detects conflicts, suggests free slots and delegates completion to routines. |
| `DailyPlan` | Holds included/excluded task references, explanations by task ID and completed/planned/remaining minute totals. |

A `PetOwner` owns many pets; each `Pet` holds routines; each `CareRoutine` generates tasks. `Scheduler` collects those tasks through the owner. `build_daily_plan()` selects existing tasks without modifying them; `generate_schedule()` first creates missing occurrences for the requested day, then builds its plan.

The interface in `app.py` uses `Scheduler.filter_tasks()` to identify visible task IDs after planning, preserving plan order and totals. Streamlit session state holds the working owner and overlap acknowledgments; the owner is loaded from and saved to `data.json`. `CareTask.set_completion_status()` only changes status; use `Scheduler.mark_task_complete()` when completion should also generate the next occurrence.

### Project structure

| Path | Purpose |
|---|---|
| [app.py](app.py) | Streamlit forms, daily plan, overlap controls and overdue view. |
| [pawpal_system.py](pawpal_system.py) | Domain models, validation and scheduling logic; uses the standard library. |
| [main.py](main.py) | Runnable CLI demonstration with sample pets and tasks. |
| [tests/test_pawpal.py](tests/test_pawpal.py) | Automated backend tests. |
| `data.json` | Generated local care data; ignored by Git. |
| [requirements.txt](requirements.txt) | Streamlit and pytest dependencies. |
| [diagrams/uml_final.mmd](diagrams/uml_final.mmd) | Final Mermaid class diagram. Earlier diagrams remain in `diagrams/`. |
| [reflection.md](reflection.md) | Project design reflection and tradeoffs. |
| [ai_interactions.md](ai_interactions.md) | Notes on AI collaboration during development. |

The backend also supports profile edits, routine edits and routine removal. Routine edits preserve completed history, overdue tasks and rescheduled occurrences while replacing future pending tasks. Removing a routine deletes pending tasks and retains completed history. The current interface exposes creation, completion, overlap rescheduling and overdue cleanup; editing profiles and routines and removing routines require calling the backend methods directly.

## Demo Walkthrough

### Demo video

[Watch the PawPal+ demo video](Pawpal%2B.mov)

### Main UI features

- **Owner and Add a Pet:** enter your name and add multiple pets by name and species.
- **Schedule a Task:** create care routines with a pet, title, category, dates, time, duration, priority and repeat interval.
- **Pets and Tasks:** review each pet and its routine settings.
- **Build Schedule:** generate care for a selected day, filter by pet or status, review completed/planned minute totals and mark tasks done or reopen them.
- **Overlap controls:** inspect conflict warnings, choose **Reschedule a task** to move one occurrence, or choose **Keep both** to acknowledge intentional overlap.
- **Overdue Tasks:** complete missed care or delete all pending overdue occurrences while preserving completed history.

### Example workflow

1. Start the app with `python -m streamlit run app.py` and enter your name under **Owner**.
2. Add **Luna** as a cat and **Mochi** as a dog using **Add a Pet**.
3. Schedule **Brush fur** for Luna today at **6 PM**, repeating **Once**, for **30 minutes**, with **Low** priority. Add **Breakfast** for Luna today at **8 AM**, also Once for 30 minutes, with **Medium** priority. Add **Evening walk** for Mochi today at **6 PM**, repeating **Daily** with **Every N = 1**, for 30 minutes, with **High** priority.
4. Open **Build Schedule**, leave **Day** set to today and click **Generate schedule**. High-priority Evening walk appears first, then Medium Breakfast, then Low Brush fur. Review the full time ranges and care-minute totals.
5. Change **Show pet** to Luna, then try **Show status**. Visible rows change while the totals and overlap review still cover both pets. Restore All pets and All to see the full plan.
6. Review the warning for Brush fur and Evening walk. Choose **Reschedule a task**, select Evening walk, set **Time** to **6:30 PM** and save. The two tasks now meet at an endpoint without overlapping. For care you can perform together, **Keep both** acknowledges the overlap instead.
7. Mark Evening walk **Done**, then select tomorrow as **Day**. Its next daily occurrence appears at the routine's usual **6 PM**, because moving today's occurrence does not change the routine. The future task's Done checkbox is disabled until its scheduled day.

To demonstrate overdue care immediately, follow [Testing mode: sample overdue tasks](#testing-mode-sample-overdue-tasks), then use **Overdue Tasks** to complete or delete the examples.

### Scheduler behaviors demonstrated

- **Priority-based scheduling:** tasks from all pets are ordered High → Medium → Low first, then by scheduled date and time. The CLI also shows an explicit chronological sort for comparison.
- **Filtering after planning:** pet/status filters preserve the plan's selection and order, and totals still describe all pets.
- **Conflict warnings:** incomplete tasks are checked for overlapping durations. Rescheduling can clear a conflict; Keep both records acceptance in the UI while the backend continues to detect the actual overlap.
- **Daily recurrence and duplicate protection:** completing today's daily task creates or reuses tomorrow's occurrence at the routine's usual time. Completing the same task again does not add another occurrence.
- **Explained daily planning:** completed and pending care minutes are totaled separately. The CLI displays the backend's reasons for including each task.
- **Overdue cleanup:** incomplete care from earlier days is listed separately, and deleting it preserves completed history and lets active repeating routines continue.

### Sample CLI output

Run the demo from the project root with the virtual environment activated:

```bash
python main.py
```

The CLI creates its own sample data and demonstrates these behaviors, including free-slot suggestions and priority-first scheduling. Its initial time-sort example uses tasks with the default Medium priority; the later priority-schedule example uses all three levels. In the UI, the owner chooses the new date and time manually. Dates below are from an October 17, 2026 run; actual dates follow the machine's local date.

```text
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

Today's Schedule (priority first, then time)
------------------------------------------------------------
High   | 09:00 | Luna     | Medication           | Pending
High   | 20:00 | Mochi    | Playtime             | Pending
Medium | 08:00 | Luna     | Breakfast            | Completed
Medium | 10:00 | Mochi    | Long walk            | Pending
Medium | 11:00 | Mochi    | Short walk           | Pending
Low    | 18:00 | Luna     | Brush fur            | Pending

Daily care plan
Completed: 15 min | Planned: 105 min

Today's plan (priority first, then time)
------------------------------------------------------------
09:00 | Luna     | Medication
  High priority; scheduled care.
20:00 | Mochi    | Playtime
  High priority; scheduled care.
08:00 | Luna     | Breakfast
  Already completed.
10:00 | Mochi    | Long walk
  Medium priority; scheduled care.
11:00 | Mochi    | Short walk
  Medium priority; scheduled care.
18:00 | Luna     | Brush fur
  Low priority; scheduled care.

Not included in this plan
------------------------------------------------------------
(none)
```

## Testing PawPal+

With the virtual environment activated, run from the project root:

```bash
python -m pytest -q tests/test_pawpal.py
```

Verified locally on October 17, 2026 with the environment listed in [Prerequisites](#prerequisites):

```text
...................................                                      [100%]
35 passed in 0.22s
```

The 35 backend cases in `tests/test_pawpal.py` cover completion status, adding routines, chronological and priority sorting, pet/routine/task links, daily/weekly/monthly generation, daily recurring completion, pet/status filtering, plan totals and optional-limit explanations, overlap detection, rescheduling identity, overdue cleanup and JSON persistence. Priority checks include later High tasks appearing before earlier Low tasks, chronological order within a priority, included/excluded plan order and correct conflict/free-slot scans with mixed priorities. Persistence checks include profile/history round trips, loading without task generation, unique IDs after starting a separate process or reloading the backend, invalid data and preservation of previous data when saving fails or a live session contains duplicate IDs.

**Confidence level: ★★★★☆ (4/5).** Core backend workflows pass. Interface verification is manual; automated interface coverage and broader recurrence edge cases, including month-end behavior and repeated completion, remain future work.

### Manual interface checks

1. Add two pets and several routines, including two overlapping tasks. Generate a schedule and check the order, time ranges and minute totals.
2. Change pet/status filters and confirm totals still cover all pets.
3. Complete today's daily task; view tomorrow to verify its successor. Reopen and complete the original again to check duplicate protection. Confirm future recurring tasks have disabled Done checkboxes.
4. Move one overlapping task through **Reschedule a task**. For another overlap, choose **Keep both** and confirm the warning clears without moving either task.
5. Use testing mode below to add overdue examples, then try completing individual tasks and deleting the remaining overdue tasks.
6. Refresh the browser and restart the server. Check that pets, routines, completion status and rescheduled times are restored. Display filters and overlap acknowledgments reset in a new session.

### Testing mode: sample overdue tasks

Stop the app, then restart with `PAWPAL_TESTING=1` to make overdue examples available without waiting a day.

**macOS / Linux**

```bash
PAWPAL_TESTING=1 python -m streamlit run app.py
```

**Windows PowerShell**

```powershell
$env:PAWPAL_TESTING = "1"
python -m streamlit run app.py
```

Add a pet, open **Overdue Tasks**, expand **Testing only: sample overdue tasks**, choose a pet and click **Add sample overdue tasks**. This inserts two one-time examples dated one and two days ago.

These sample tasks are persisted too. Complete or delete them after testing. For normal use, stop the app and relaunch without the variable. In PowerShell, first run `Remove-Item Env:PAWPAL_TESTING`. Saved pets and care records remain available after restarting.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Missing `streamlit` or `pytest` module | Activate `.venv` and rerun `python -m pip install --upgrade -r requirements.txt`. Use `python -m streamlit` so the app runs with the same interpreter. |
| Streamlit reports an unknown argument or missing API | Upgrade dependencies in the active environment. See the verified versions in [Prerequisites](#prerequisites); the declared Streamlit minimum predates some interface APIs. |
| The default port is occupied | Run `python -m streamlit run app.py --server.port 8502` and use the URL printed in the terminal. |
| No tasks appear | Add a pet and routine, click **Generate schedule**, and check the selected day, filters, start/end dates and repeat interval. Past one-time routines do not generate new tasks. |
| A future task cannot be marked done | Repeating care can only be completed on its scheduled day or later. |
| A warning refers to a hidden task | Overlap reviews cover all pending care occupying the selected day, including tasks hidden by filters or starting the previous day. |
| Saved care cannot be loaded | Check the error and the `data.json` beside `app.py`. Restore a valid backup or repair the file. To intentionally start fresh, stop the app and move the file aside. |
| Changes could not be saved | Check that the app directory is writable and there is enough disk space. Previous saved data is retained if the replacement fails. |

## Current limitations

- Storage is one local file for one owner. Simultaneous sessions do not synchronize changes; the last successful save wins. It is not a multi-user database.
- Overlap acknowledgments and display settings remain session-only, so intentional overlaps need review again in a new session.
- Data survives restarts while the file remains on disk. Deployments with temporary storage need a persistent disk or another storage service.
- Dates and times use the machine running the app; there is no timezone selection or conversion.
- Conflict resolution requires owner review; the app does not automatically move care. `Scheduler.next_free_slot()` provides free-slot suggestions through the backend and CLI demo.
- The interface does not yet expose the backend's profile/routine editing, routine removal or optional time limits.
- The automated suite covers the backend; interface behavior needs manual verification.
