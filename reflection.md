# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

My UML design includes five main classes: PetOwner, Pet, CareRoutine, CareTask, and Scheduler. The design below is the current version saved in diagrams/uml_draft.mmd, and the changes I made since my first draft are described in section 1b.
A pet owner can manage multiple pets, each with recurring care routines such as feeding or walking. These routines generate tasks with a scheduled date, time, and completion status.
The design supports three core features: managing pet profiles, organizing regular care, and viewing and completing today’s tasks.

Responsibilities I assigned to each class:
- PetOwner: the user of the app. It keeps the list of pets, adds and removes them, and gathers tasks across all pets to show today's tasks sorted by time. Overdue incomplete tasks are listed separately and can be cleared.
- Pet: holds one pet's profile (species, breed, birthday, photo, needs, care instructions) and keeps its own care routines, so the profile can be updated and routines attached or removed.
- CareRoutine: a recurring care activity for one pet, such as feeding or walking. It stores how often, at what time, for how long and how important the care is, and generates the dated tasks for a date range.
- CareTask: a single dated instance of a routine. It copies the routine's duration and priority, tracks whether it was completed, and can be rescheduled.
- Scheduler: organizes tasks across all pets. It gets every task through PetOwner.get_all_tasks(), then builds today's, overdue and upcoming lists, filters by pet or status, orders tasks that start at the same time by priority, and finds tasks whose times overlap.

I split routines from tasks so that a recurring activity is defined once and its daily occurrences can be completed or rescheduled on their own.

What information it needs to hold (attributes):
What actions it can perform (methods):

PetOwner
- Attributes: owner_id, name, email, pets
- Methods: add_pet(), remove_pet(), get_all_tasks(), get_pet_for_task(), view_todays_tasks(), view_overdue_tasks(), clear_overdue_tasks()

Pet
- Attributes: pet_id, name, species, breed, birthday, photo, pet_needs, care_instructions, routines
- Methods: update_profile(fields), get_care_routines(), add_routine(), remove_routine()

CareRoutine (one routine per pet)
- Attributes: routine_id, pet_id, title, frequency (ONCE, DAILY, WEEKLY or MONTHLY), interval, scheduled_time, start_date, end_date, duration_minutes, priority (LOW, MEDIUM or HIGH), is_active, tasks
- Methods: update_routine(fields), generate_tasks(range_start, range_end), get_tasks()
- Examples: “Feed Luna every day at 8 AM.” and “Trim Luna’s nails every 2 weeks at 6 PM.”

CareTask
- Attributes: task_id, routine_id, title, scheduled_date_time, original_date_time, duration_minutes, priority, completion_status, is_rescheduled (calculated from the two date-times), end_date_time (calculated: scheduled time plus duration)
- Methods: set_completion_status(completion_status), reschedule(new_date_time)
- Example: “Feed Luna today at 8 AM — completed.”

Scheduler
- Attributes: owner
- Methods: get_tasks(), tasks_on(), todays_tasks(), overdue_tasks(), upcoming_tasks(), filter_tasks(), find_conflicts()

Relationships: a PetOwner owns many Pets, a Pet has many CareRoutines, and a CareRoutine generates many CareTasks (composition, 1 to many). Each child stores only its direct parent's ID (pet_id on CareRoutine, routine_id on CareTask), so a task's pet is found through its routine (get_pet_for_task()). IDs are assigned automatically. A Scheduler holds one PetOwner and gets every task through PetOwner.get_all_tasks(), and the owner's view methods delegate to the Scheduler.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes, my design changed in two main ways:
- **Frequency became an enum plus an interval** (ONCE, DAILY, WEEKLY, MONTHLY and "every N"). I first stored frequency as a free string, but that could not express routines like "trim nails every 2 weeks" or "monthly grooming", so generate_tasks() could not create the right dates reliably. I also added an optional end_date and generate tasks 90 days ahead.
- **I added a Scheduler class** that was not in my first UML. I needed one place to organize tasks across all pets: sorted lists for today and overdue tasks, filtering by pet, and conflict detection. It gets every task through PetOwner.get_all_tasks(), so PetOwner and Pet stay simple.


---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?

I used Claude Code in VS Code for the whole project. First for design brainstorming: turning my class list into a Mermaid UML diagram and reviewing it for gaps. Then for implementation: filling in the four classes, adding a Scheduler class, writing docstrings, and drafting two tests. I also used it to write up the README and this reflection from what we decided.

- What kinds of prompts or questions were most helpful?

Specific review questions worked best, such as "ensure the relationships make sense and that I haven't included unnecessary complexity" and "any gray areas regarding my 3 core functionalities?". Asking "why are you suggesting this?" or "what do you recommend and why?" before approving a change also helped, because I understood each decision before it went into the code.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.

The AI first made view_todays_tasks() include overdue incomplete tasks, sorted by time. I did not accept that: I wanted today's list to show only today's tasks, with overdue tasks in a separate tab where I can complete or delete them. The design changed to view_todays_tasks(), view_overdue_tasks() and clear_overdue_tasks().

Other suggestions I accepted or changed:
- Accepted: composition between owner, pets, routines and tasks; add_routine() and remove_routine() on Pet, after I asked what they were for; a frequency enum plus an interval; original_date_time to protect rescheduled tasks; automatic IDs; get_pet_for_task(); a Scheduler class that gets its tasks through PetOwner.get_all_tasks(); and removing Pet.owner_id and get_all_routines() when I asked it to check for unnecessary complexity.
- Rejected: is_due_today() on CareTask (I asked why it was needed when a daily walk is due every day), and removing pet_needs (I kept both pet_needs and care_instructions).
- Changed: get_care_routines() returns inactive routines too, the task window is 90 days instead of 30, and set_completion() became set_completion_status() so it does not clash with the attribute name.

I also kept my own method names even though the assignment's tests mention mark_complete() and adding a task to a Pet, and tested the same behavior through set_completion_status() and add_routine().

- How did you evaluate or verify what the AI suggested?

I checked the AI's work in four ways:
- I asked the AI to lay out every agreed change in the chat before it edited any file, and I approved them first.
- I compared the class lists in this file against the UML diagram line by line.
- I ran scenario checks against the implementation: a routine every 2 weeks, a monthly routine starting on Jan 31 (it lands on Feb 28), end_date, no duplicate tasks when generating twice, no tasks created in the past, a rescheduled task not overwritten, completed history kept when a routine is removed, and the Scheduler using get_all_tasks(). One check failed at first, but the test's date window was wrong, not the code.
- I ran my two pytest tests with python -m pytest (2 passed) and the main.py demo, and saved its output in the README.

Not covered yet: the Streamlit UI, and saving data between sessions (a possible future improvement). Conflict detection only compares start times and durations, and does not suggest a fix.

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
