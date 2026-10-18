# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agent Workflow (SF7)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

### Challenge 1: Advanced Algorithmic Capability

**What task did you give the agent?**

I used an AI coding assistant to implement and review PawPal+'s scheduling logic. The advanced capability documented here is **finding the next available time slot**, which goes beyond sorting and filtering tasks. Its goal is to suggest the earliest start time with enough uninterrupted minutes for a task, considering pending care across all pets.

The original implementation prompt was not preserved in this log. In the follow-up review, I asked Codex to check the project against the challenge requirements and complete this workflow documentation for the capability already implemented.

**What did the agent do?**

The completed implementation and documentation involve these files:

- `pawpal_system.py`: implements `Scheduler.next_free_slot(duration, after, exclude_task_id=None)`. It sorts existing tasks by time, skips completed tasks and the occurrence being moved, and scans busy intervals until it finds a gap long enough for the requested duration. It rejects nonpositive durations and returns a suggestion without changing any task.
- `main.py`: demonstrates the algorithm during conflict resolution. Two 30-minute tasks overlap at 18:00; the scheduler suggests 18:30 for one task. The demo then explicitly reschedules that occurrence and confirms that the conflict is resolved.
- `README.md`: describes free-slot suggestions and includes the CLI example. The feature is available through the backend and CLI; the Streamlit interface lets the owner choose a new date and time manually.
- `ai_interactions.md`: records this Challenge 1 workflow and its verification.

During the follow-up review, Codex inspected the implementation, ran `python -m pytest -q` using the project's virtual environment (**14 passed**), and ran `python main.py` successfully. The CLI verified the free-slot example; the existing test suite does not directly test `next_free_slot()`.

**What did you have to verify or fix manually?**

As recorded in `reflection.md`, I chose to keep conflict resolution under the owner's control because some overlaps are intentional, such as walking two dogs together. The suggestion method therefore does not automatically move care; rescheduling is a separate action.

No manual code correction specific to `next_free_slot()` is recorded. Verification in this follow-up was performed by Codex through code inspection, the passing backend tests, and the CLI demonstration. Broader free-slot edge cases and manual interface checks are not claimed here.

---

## Prompt Comparison (SF11)

> Compare two different prompts (or two different models) on the same task.

| | Option A: Codex | Option B: Claude |
|-|----------|----------|
| **Model / tool used** | OpenAI Codex, in the Codex desktop app. | Claude Sonnet 5.5, in Claude Code (Claude desktop app, Code tab). |
| **Prompt / task** | "Suggest a solution for automatically rescheduling conflicting pet-care tasks in PawPal for the upcoming week. Consider task priority and duration, use free time slots, and preserve recurring routines. Explain the algorithm without implementing it." | The identical prompt. Claude first read `pawpal_system.py`, then answered without changing any code. |
| **Response summary** | Proposed a priority-aware scheduler for a seven-day window: generate routine occurrences, detect overlaps using full durations, reserve fixed commitments, and place flexible conflicting tasks in High → Medium → Low order. Choose valid free slots close to the original time, preserve each routine's repeat pattern, and report conflicts that cannot be resolved. | Proposed priority-ordered greedy placement into a per-day free-slot map: generate the week's occurrences, split tasks into fixed and movable, rank movable tasks (priority, then flexibility, then longest duration), and let each claim its original slot or the nearest fitting gap. Moved tasks stay within their own recurrence period, and tasks that cannot be placed are reported as unresolved. Changes are returned as a proposal and applied only after confirmation. |
| **What was useful** | Connected the proposal to PawPal's existing conflict detection, free-slot suggestions, and occurrence-level rescheduling. Explained how to fit the entire task duration, respect intentional "Keep both" overlaps, and preserve task identity when moving one occurrence. Also identified that completion-date-based successor generation could shift recurring dates after a cross-day move. | Pointed out a real gap in `next_free_slot()`: it ignores the owner's availability window and `daily_care_minutes`, so it can suggest late-night or over-limit slots. Explained why most tasks never move (a task that wins its original slot is untouched) and why re-running produces no moves. Gave a comparison table of the existing code against what automatic rescheduling needs. Offered default flexibility limits by care category, so no new data fields are needed at first. Listed edge cases and five concrete tests. |
| **What was flawed or limited** | The greedy approach does not guarantee the best overall weekly arrangement. Fixed commitments, task-specific time windows, and permission to move care across days would require additional preferences that PawPal does not currently provide. The response described the design without demonstrating or validating it on an actual weekly schedule. | Also greedy, so it has the same optimality limit. The per-category drift limits (for example ±30–45 minutes for meals) are my own examples, not values from PawPal's data or requirements. It treated every overlap as a conflict to resolve and only mentioned intentional overlaps (such as walking two dogs together) as an optional future `can_overlap` flag, without checking how the app handles "Keep both". It saw that `complete_task()` rejects completing repeating tasks dated after today, but missed that successor dates are computed from the completion date, which Codex caught. The "idempotent" and "priority-safe" claims, and the suggested tests, were reasoned from the code and not run. |
| **Final decision** | Keep the automatic weekly scheduler as a future design proposal. Retain the current free-slot suggestions and owner-controlled rescheduling, which allow intentional overlaps. No automatic rescheduling was implemented from this prompt. | Keep as a future design input alongside Codex's proposal. No code was implemented from this prompt. If an automatic scheduler is built, take from Claude the bounded free-slot search (respecting availability and the daily cap), the priority-ordered placement, and the proposal-then-confirm flow. Take from Codex the "Keep both" handling and the recurring-date safeguards. |

**Which approach did you use in your final implementation and why?**

For the current implementation, I kept free-slot suggestions separate from rescheduling so the owner can decide whether to move an occurrence or keep an intentional overlap. Neither proposal was implemented. The two responses agree on the core design: priority-ordered greedy placement, full-duration checks, moving individual occurrences without changing the routine, and reporting what cannot be placed. They differ mainly in emphasis. Codex stayed closer to PawPal's owner-controlled behavior and caught the recurring-date drift. Claude found the `next_free_slot()` limitation and added a more detailed placement procedure and test list. A combined design would need the additional scheduling preferences noted above and validation on a real weekly schedule before adoption.
