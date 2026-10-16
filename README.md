# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🧩 Implementation Summary

The backend lives in `pawpal_system.py` as five small classes, and `main.py` is a CLI demo that uses them.

| Class | What it does |
|---|---|
| `PetOwner` | Owns the pets and collects every task through `get_all_tasks()`. |
| `Pet` | Holds a pet's profile and its care routines. |
| `CareRoutine` | A recurring activity (for example "Feed Luna every day at 8 AM") that generates tasks. |
| `CareTask` | One dated occurrence of a routine, which can be completed or rescheduled. |
| `Scheduler` | Organizes tasks across all pets: today's list, overdue, upcoming, filtering and conflicts. |

**How they work together**

1. A `PetOwner` has many `Pet`s, a `Pet` has many `CareRoutine`s, and a `CareRoutine` generates many `CareTask`s.
2. Adding a routine with `Pet.add_routine()` links it to the pet and generates its tasks for the next 90 days. A routine repeats once, daily, weekly or monthly, every N units, between a start date and an optional end date. Each routine also has a duration in minutes and a priority (low, medium or high), which its tasks inherit.
3. The `Scheduler` gets all tasks from `PetOwner.get_all_tasks()`, which walks pets, then routines, then tasks. It sorts and filters them, so the today view, the overdue view and conflict detection (tasks whose times overlap) all start from that one list.

**Behaviors worth knowing**

- Tasks are only generated from today forward, so a deleted overdue task never comes back.
- A task the user rescheduled is never overwritten when its routine is regenerated.
- Removing a routine deletes its pending tasks but keeps completed ones as history.
- Invalid edits (an unknown field, an interval below 1) raise an error instead of silently changing data.

Run the tests with `python -m pytest`.

## 🖥️ Sample Output

Running `python main.py` prints today's schedule for the owner, sorted by time:

```
Today's Schedule
Owner: Karina
Date: 2026-10-16
------------------------------------------------------------
08:00 | Luna     | Breakfast            | Pending
09:30 | Mochi    | Morning walk         | Pending
18:00 | Luna     | Brush fur            | Pending
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | | e.g., by priority, duration |
| Filtering | | e.g., skip tasks if time runs out |
| Conflict handling | | e.g., overlapping time slots |
| Recurring tasks | | e.g., daily vs. weekly |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
