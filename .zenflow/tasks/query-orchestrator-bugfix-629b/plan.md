# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 0065e17a-ea5a-444e-ab7f-53058e5c562c -->

Assess the task's difficulty, as underestimating it leads to poor outcomes.
- easy: Straightforward implementation, trivial bug fix or feature
- medium: Moderate complexity, some edge cases or caveats to consider
- hard: Complex logic, many caveats, architectural considerations, or high-risk changes

Create a technical specification for the task that is appropriate for the complexity level:
- Review the existing codebase architecture and identify reusable components.
- Define the implementation approach based on established patterns in the project.
- Identify all source code files that will be created or modified.
- Define any necessary data model, API, or interface changes.
- Describe verification steps using the project's test and lint commands.

Save the output to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach
- Source code structure changes
- Data model / API / interface changes
- Verification approach

If the task is complex enough, create a detailed implementation plan based on `{@artifacts_path}/spec.md`:
- Break down the work into concrete tasks (incrementable, testable milestones)
- Each task should reference relevant contracts and include verification steps
- Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function).

Save to `{@artifacts_path}/plan.md`. If the feature is trivial and doesn't warrant this breakdown, keep the Implementation step below as is.

Yes. state.py is exactly where the contract mismatch is coming from.

What the file says (and why you’re still getting NoneType ... update)
	•	In BaseState, you currently define:

error_info: Dict[str, Any]  # {type, message, context, suggestion}

That implies “always a dict”.
	•	But multiple agent outputs (and your own runtime logs) clearly allow None:

error_info: Optional[Dict[str, Any]]

And your log shows:

"error_info": null

So the state contract is inconsistent: the graph allows None, but parts of the orchestrator treat it as a dict and call .update(...) → crash.

What to change in state.py (minimum fix)

Make BaseState.error_info optional to match reality:

error_info: Optional[Dict[str, Any]]

What to change in the orchestrator (still required)

Even after fixing typing, you must normalize before update everywhere you do state["error_info"].update(...):

error_info = state.get("error_info")
if not isinstance(error_info, dict):
    error_info = {}
error_info.update({...})
state["error_info"] = error_info

Best practice (so this never returns)

Create a single helper (e.g., set_error(state, type, message, **meta)) and use it everywhere. That prevents future regressions and removes duplicated normalization logic.

If you want, paste the relevant orchestrator sections (or point me at the file), and I’ll tell you the exact minimal diff to implement set_error(...) and replace the current .update(...) call sites.

---

### [x] Step: Implementation
<!-- chat-id: 20562910-f1f6-4d90-a4e2-649319ad1d77 -->

Implement the task according to the technical specification and general engineering best practices.

1. Break the task into steps where possible.
2. Implement the required changes in the codebase.
3. Add and run relevant tests and linters.
4. Perform basic manual verification if applicable.
5. After completion, write a report to `{@artifacts_path}/report.md` describing:
   - What was implemented
   - How the solution was tested
   - The biggest issues or challenges encountered
