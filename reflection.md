# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

My UML design includes five main classes: PetOwner, Pet, CareRoutine, CareTask, and Scheduler, plus a DailyPlan result dataclass. The design below is the current working version saved in diagrams/uml_draft.mmd, and the changes I made since my first draft are described in section 1b.
A pet owner can manage multiple pets, each with recurring care routines such as feeding or walking. These routines generate tasks with a scheduled date, time, and completion status.
The design supports three core features: managing pet profiles, organizing regular care, and viewing and completing today’s tasks. Routines create their first pending occurrence when added. Generating a schedule fills matching occurrences for the selected day, and completing a task creates or reuses its next occurrence.

Responsibilities I assigned to each class:
- PetOwner: the user of the app. It keeps the list of pets, adds and removes them, and gathers tasks across all pets. Optional time limits remain supported for direct Python callers; the Streamlit app clears them to include all scheduled care. Overdue incomplete tasks are listed separately and can be cleared.
- Pet: holds one pet's profile (species, breed, birthday, photo, needs, care instructions) and keeps its own care routines, so the profile can be updated and routines attached or removed.
- CareRoutine: a recurring care activity for one pet, such as feeding or walking. It stores how often, at what time, for how long and how important the care is, plus its care category. It seeds one pending occurrence by default and can fill matching occurrences in a bounded date range for calendar scheduling. Completion creates or reuses the next occurrence from the completion date. Future repeating tasks cannot be completed before their scheduled day.
- CareTask: a single dated instance of a routine. It copies the routine's duration and priority, tracks whether it was completed, and can be rescheduled.
- Scheduler: organizes tasks across all pets. It gets every task through PetOwner.get_all_tasks(), then builds today's, overdue and upcoming lists, filters by pet or status, orders tasks that start at the same time by priority, and finds tasks whose times overlap. Its build_daily_plan() method includes all of the day's existing care by default. Direct Python callers can still apply time limits, which select pending tasks by priority. It returns tasks in time order with a reason for each inclusion or exclusion. Completed care stays visible and counts toward any care-time allowance. It returns shared warning text for the CLI and UI through conflict_warning(). It can also suggest the next free time slot for Python callers and the CLI. The app instead lets the owner choose a new date and time or keep both tasks, storing acceptance of that exact overlap in session state. When a recurring task is marked complete, it asks the routine to create the next occurrence from today's date.
- DailyPlan: holds included and excluded tasks, explanations keyed by task ID, and completed, planned and remaining minutes. Creating a plan does not change the tasks.

I split routines from tasks so that a recurring activity is defined once and its daily occurrences can be completed or rescheduled on their own.

What information it needs to hold (attributes):
What actions it can perform (methods):

PetOwner
- Attributes: owner_id, name, email, pets, available_start, available_end, daily_care_minutes
- Methods: set_preferences(), add_pet(), remove_pet(), get_all_tasks(), get_pet_for_task(), get_routine_for_task(), view_todays_tasks(), view_overdue_tasks(), clear_overdue_tasks()

Pet
- Attributes: pet_id, name, species, breed, birthday, photo, pet_needs, care_instructions, routines
- Methods: update_profile(fields), get_care_routines(), add_routine(), remove_routine()

CareRoutine (each routine belongs to one pet)
- Attributes: routine_id, pet_id, title, frequency (ONCE, DAILY, WEEKLY or MONTHLY), interval, scheduled_time, start_date, end_date, duration_minutes, priority (LOW, MEDIUM or HIGH), is_active, tasks, category
- Methods: update_routine(fields), generate_tasks(range_start, range_end, first_only=True), add_task(scheduled_date_time), complete_task(task), get_tasks()
- Examples: “Feed Luna every day at 8 AM.” and “Trim Luna’s nails every 2 weeks at 6 PM.”

CareTask
- Attributes: task_id, routine_id, title, scheduled_date_time, original_date_time, duration_minutes, priority, completion_status, is_rescheduled (calculated from the two date-times), end_date_time (calculated: scheduled time plus duration)
- Methods: set_completion_status(completion_status), reschedule(new_date_time)
- Example: “Feed Luna today at 8 AM — completed.”

Scheduler
- Attributes: owner
- Methods: sort_by_time(), get_tasks(), tasks_on(), todays_tasks(), generate_schedule(day), build_daily_plan(day), overdue_tasks(), upcoming_tasks(), filter_tasks(), find_conflicts(), conflict_warning(group), next_free_slot(), mark_task_complete()

DailyPlan
- Attributes: included, excluded, reasons, completed_minutes, planned_minutes, remaining_minutes
- Methods: none; this dataclass holds the planner's result.

Relationships: a PetOwner owns many Pets, a Pet has many CareRoutines, and a CareRoutine generates many CareTasks (composition, 1 to many). Each child stores only its direct parent's ID (pet_id on CareRoutine, routine_id on CareTask), so a task's pet is found through its routine (get_pet_for_task()). IDs are assigned automatically. A Scheduler holds one PetOwner and gets every task through PetOwner.get_all_tasks(), and the owner's view methods delegate to the Scheduler. The Scheduler builds a DailyPlan that refers to existing CareTasks and explains the selection.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes, my design changed during implementation. I added a **Scheduler class** that was not in my original UML. I needed one place to organize tasks across all pets, sort today's and overdue tasks, filter by pet, and detect scheduling conflicts. It retrieves tasks through `PetOwner.get_all_tasks()`, keeping the `PetOwner` and `Pet` classes simpler.


---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

My scheduler detects overlapping tasks but leaves the owner to decide whether to reschedule or keep both. This requires manual review, but it is reasonable because some overlaps are intentional, such as walking two dogs together.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?

I initially used AI for design brainstorming: turning my class list into a Mermaid UML diagram and reviewing it for gaps. Then for implementation: filling in the four classes, adding a Scheduler class, writing docstrings, and drafting two tests. I also used it to write up the README and this reflection from what we decided. Later, AI helped implement the agreed change to completion-based recurrence. We then planned owner preferences and task explanations before editing the code, and I chose to count completed care toward the whole day's care-time allowance.

- What kinds of prompts or questions were most helpful?

Specific review questions worked best, such as "ensure the relationships make sense and that I haven't included unnecessary complexity" and "any gray areas regarding my 3 core functionalities?". Asking "why are you suggesting this?" or "what do you recommend and why?" before approving a change also helped, because I understood each decision before it went into the code.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.

The AI first made view_todays_tasks() include overdue incomplete tasks, sorted by time. I did not accept that: I wanted today's list to show only today's tasks, with overdue tasks in a separate tab where I can complete or delete them. The design changed to view_todays_tasks(), view_overdue_tasks() and clear_overdue_tasks().

Other suggestions I accepted or changed:
- Accepted: composition between owner, pets, routines and tasks; add_routine() and remove_routine() on Pet, after I asked what they were for; a frequency enum plus an interval; original_date_time to protect rescheduled tasks; automatic IDs; get_pet_for_task(); a Scheduler class that gets its tasks through PetOwner.get_all_tasks(); and removing Pet.owner_id and get_all_routines() when I asked it to check for unnecessary complexity.
- Rejected: is_due_today() on CareTask (I asked why it was needed when a daily walk is due every day), and removing pet_needs (I kept both pet_needs and care_instructions).
- Changed: get_care_routines() returns inactive routines too, recurrence seeds one pending occurrence instead of a 90-day forecast and can fill a selected calendar day on request, and set_completion() became set_completion_status() so it does not clash with the attribute name.

I tested task completion and task addition through set_completion_status() and add_routine().

- How did you evaluate or verify what the AI suggested?

I asked the AI to lay out every agreed change in the chat before it edited any file, and I approved the changes first. I compared the class lists in this file against the UML diagram line by line. I also ran my two pytest tests with python -m pytest (2 passed) and the main.py demo, and saved the demo's output in the README.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
