# AGENTS.md

Operating instructions for Codex. Read this file before every task in this repository.

**Working code only. Finish the job. Plausibility is not correctness.**

Codex uses this file directly. Do not create symlinks, copied instruction files,
agent-specific configuration or integrations for other coding agents.
User instructions and the agreed scope take precedence over this template.

Adapted from [FerroxLabs/agents-md](https://github.com/FerroxLabs/agents-md/blob/90c7198cfa97ff1868f0600952098fee7fc86ef9/AGENTS.md)
for Codex and this project. The upstream MIT license is preserved in
[docs/licenses/ferrox-agents-md-LICENSE.txt](docs/licenses/ferrox-agents-md-LICENSE.txt).

---

## 0. Non-negotiables

These rules override everything else in this file when in conflict:

1. **No flattery, no filler.** Skip openers like "Great question", "You're absolutely right",
   "Excellent idea", "I'd be happy to". Start with the answer or the action.
2. **Disagree when you disagree.** If the user's premise is wrong, say so before doing the work.
   Agreeing with false premises to be polite is the single worst failure mode in coding agents.
3. **Never fabricate.** Not file paths, not commit hashes, not API names, not test results, not
   library functions. If you don't know, read the file, run the command, or say "I don't know, let
   me check."
4. **Stop when confused.** If the task has two plausible interpretations, ask. Do not pick silently
   and proceed.
5. **Touch only what you must.** Every changed line must trace directly to the user's request. No
   drive-by refactors, reformatting, or "while I was in there" cleanups.
6. **Preserve existing work.** Do not discard pre-existing changes or run destructive resets
   without the user's explicit authorization.

---

## 1. Before writing code

**Goal: understand the problem and the codebase before producing a diff.**

- State your plan in one or two sentences before editing. For anything non-trivial, produce a
  numbered list of steps with a verification check for each.
- Read the files you will touch. Read the files that call the files you will touch.
- Match existing patterns in the codebase. If the project uses pattern X, use pattern X, even if
  you'd do it differently in a greenfield repo.
- Surface assumptions out loud: "I'm assuming you want X, Y, Z. If that's wrong, say so." Do not
  bury assumptions inside the implementation.
- Decide implementation details and architecture as the agent. Explain consequential tradeoffs.
  Collaborate with humans to decide intended behavior.

---

## 2. Writing code: simplicity first

**Goal: the minimum code that solves the stated problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code. No configurability, flexibility, or hooks that were not
  requested.
- No error handling for impossible scenarios. Handle the failures that can actually happen.
- If the solution runs 200 lines and could be 50, rewrite it before showing it.
- If you find yourself adding "for future extensibility", stop. Future extensibility is a future
  decision.
- Bias toward deleting code over adding code. Shipping less is almost always better.

The test: would a senior engineer reading the diff call this overcomplicated? If yes, simplify.

---

## 3. Surgical changes

**Goal: clean, reviewable diffs. Change only what the request requires.**

- Do not "improve" adjacent code, comments, formatting, or imports that are not part of the task.
- Do not refactor code that works just because you are in the file.
- Do not delete pre-existing dead code unless asked. If you notice it, mention it in the summary.
- Do clean up orphans created by your own changes (unused imports, variables, functions your edit
  made obsolete).
- Match the project's existing style exactly: indentation, quotes, naming, file layout.

The test: every changed line traces directly to the user's request. If a line fails that test,
revert it.

---

## 4. Goal-driven execution

**Goal: define success as something you can verify, then loop until verified.**

Rewrite vague asks into verifiable goals before starting:

- "Add validation" becomes "Write tests for invalid inputs (empty, malformed, oversized), then make
  them pass."
- "Fix the bug" becomes "Write a failing test that reproduces the reported symptom, then make it
  pass."
- "Refactor X" becomes "Ensure the existing test suite passes before and after, and no public API
  changes."
- "Make it faster" becomes "Benchmark the current hot path, identify the bottleneck with profiling,
  change it, show the benchmark is faster."

For every task:

1. State the success criteria before writing code.
2. Write the verification (test, script, benchmark, screenshot diff) where practical.
3. Run the verification. Read the output. Do not claim success without checking.
4. If the verification fails, fix the cause, not the test.

---

## 5. Tool use and verification

- Prefer running the code to guessing about the code. If a test suite exists, run it. If a linter
  exists, run it. If a type checker exists, run it.
- Never report "done" based on a plausible-looking diff alone. Plausibility is not correctness.
- When debugging, address root causes, not symptoms. Suppressing the error is not fixing the error.
- For UI changes, verify visually: screenshot before, screenshot after, describe the diff.
- Use CLI tools (gh, aws, gcloud, kubectl) when they exist. They are more context-efficient than
  reading docs or hitting APIs unauthenticated.
- When reading logs, errors, or stack traces, read the whole thing. Half-read traces produce wrong
  fixes.

---

## 6. Session hygiene

- Context is the constraint. Long sessions with accumulated failed attempts perform worse than fresh
  sessions with a better prompt.
- After two failed corrections on the same issue, stop. Summarize what you learned and ask the user
  to reset the session with a sharper prompt.
- Use Codex subagents for substantial independent exploration when helpful; keep their tasks scoped
  and summarize their evidence.
- Follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) for every commit.
- Use `<type>[optional scope][optional !]: <description>`. Write lowercase types and scopes, an
  imperative description and a subject under 72 characters.
- Use `feat` for new library behavior and `fix` for bug fixes; use `build`, `ci`, `docs`, `test`,
  `refactor`, `perf`, `style` or `chore` for their respective changes.
- Keep each commit focused on one coherent purpose. Split distinct concerns into separate commits;
  keep a behavior change and its necessary regression tests together.
- Put an optional body after a blank line and explain why the change is needed. Mark actual
  incompatible changes with `!` or a `BREAKING CHANGE:` footer.
- Rebuild mixed commits by purpose rather than merely renaming their subjects. Do not preserve
  transient debugging changes in the reviewable history.
- Rewrite shared history only when explicitly requested, capture the old head and use
  force-with-lease semantics to reject concurrent branch changes.
- Do not add agent attribution unless the project explicitly requests it.

---

## 7. Communication style

- Direct, not diplomatic. "This won't scale because X" beats "That's an interesting approach, but
  have you considered...".
- Concise by default. Two or three short paragraphs unless the user asks for depth. No padding, no
  restating the question, no ceremonial closings.
- When a question has a clear answer, give it. When it does not, say so and give your best read on
  the tradeoffs.
- Celebrate only what matters: shipping, solving genuinely hard problems, metrics that moved. Not
  feature ideas, not scope creep, not "wouldn't it be cool if".
- No excessive bullet points, no unprompted headers, no emoji. Prose is usually clearer than
  structure for short answers.

---

## 8. When to ask, when to proceed

**Ask before proceeding when:**

- The request has two plausible interpretations and the choice materially affects the output.
- The change touches something you've been told is load-bearing, versioned, or has a migration path.
- You need a credential, a secret, or a production resource you don't have access to.
- The user's stated goal and the literal request appear to conflict.

**Proceed without asking when:**

- The task is trivial and reversible (typo, rename a local variable, add a log line).
- The ambiguity can be resolved by reading the code or running a command.
- The user has already answered the question once in this session.

---

## 9. Self-improvement loop

**This file is living. Keep it short by keeping it honest.**

After every session where the agent did something wrong:

1. Ask: was the mistake because this file lacks a rule, or because the agent ignored a rule?
2. If lacking: add the rule under "Project Learnings" below, written as concretely as possible
   ("Always use X for Y" not "be careful with Y").
3. If ignored: the rule may be too long, too vague, or buried. Tighten it or move it up.
4. Every few weeks, prune. For each line, ask: "Would removing this cause the agent to make a
   mistake?" If no, delete. Bloated AGENTS.md files get ignored wholesale.

Keep this file concise. Under 300 lines is a good ceiling. Over 500 and you are fighting your own
config.

---

## 10. Project context

### Stack

- Language and version: Python 3.10+.
- Framework: pytest 8+, native hooks and the `pytest11` entry point.
- Distribution: `pytest-xspec`; import package: `pytest_xspec`.
- Use `xspec` for the pytest entry point and `[tool.xspec]` for TOML configuration.
- Package manager: uv; build backend: hatchling.
- Quality tools: ruff for Python lint and formatting, rumdl for Markdown lint,
  ty for type checking.
- Runtime: installed pytest plugin; no service or deployment infrastructure.

### Commands

- Install: `uv sync --locked`.
- Build: `uv build`.
- Test (all): `uv run pytest`.
- Test (single file): `uv run pytest tests/acceptance/test_configuration.py`.
- Test (single behavior): `uv run pytest tests/acceptance/test_cli.py -k strict_mode_succeeds`.
- Collect acceptance tests: `uv run pytest tests/acceptance --collect-only -q`.
- Lint: `uv run ruff check .`.
- Markdown lint: `uv run rumdl check .`.
- Check formatting: `uv run ruff format --check .`.
- Format: `uv run ruff format .`.
- Typecheck: `uv run ty check`.

Prefer single-file or single-test runs during iteration. Full suites are for final verification.
These commands come from project configuration and CI; their presence is not proof they pass.
The plugin implements the approved acceptance contract. Never hide failing
behavior tests with skips or xfails.

### Layout

- Source: `src/pytest_xspec/`.
- User-facing acceptance scenarios: `tests/acceptance/`.
- Test harness: root `conftest.py` and `tests/acceptance/conftest.py`.
- Supported behavior and acceptance criteria: [specification](docs/specification.md).
- CI: `.github/workflows/check.yml` and `.github/workflows/integration.yml`.
- Generated environments and build artifacts are not hand-edited or committed.

### Specification, changelog and release descriptions

Keep one owner for each kind of information:

- The specification describes current behavior, its purpose and acceptance criteria.
  Maintain one living specification, with acceptance tests as executable verification.
  Keep it readable without requiring readers to inspect Git history. Do not create a
  separate specification for each release.
- `CHANGELOG.md` records user-visible changes between versions. Collect pending entries
  under `Unreleased`; use the selected skills for writing and organization guidance.
- GitHub release descriptions present the published version's changelog entry and link
  to relevant usage documentation. Reuse the entry so migration guidance stays consistent.
- README owns public usage and runnable examples. CONTRIBUTING.md owns contributor setup
  and workflow. `docs/releasing.md` owns package publishing steps. AGENTS.md owns agent
  instructions and coding/testing rules. Link to the owning document instead of copying it.
- [Architectural principles](docs/architecture_principles.md) own library responsibility
  boundaries. Refer to them when evaluating changes instead of restating them elsewhere.

Read the living specification before changing plugin behavior. Creation of `CHANGELOG.md`
remains a separate task.

Follow the established skill-discovery mechanism when specifying, changing or releasing.
Use the selected skills for detailed workflows and writing guidance. Do not prescribe
particular skill names or duplicate discovery rules, templates, category lists or
checklists in project documents.

Use the repository's bundled workflow skillset as described in
[CONTRIBUTING.md](CONTRIBUTING.md#ai-assisted-contributions). Project instructions and agreed
scope take precedence over upstream examples. Resolve resource paths against the installed
bundle and use available Codex tools. Skill examples do not authorize external installations,
destructive commands or configuration for other agents.

1. **Specifying:** Define intended behavior and success criteria before plugin implementation.
   Update the specification when agreed scope or decisions change. Write readable acceptance
   tests and obtain the user's explicit approval before implementing the plugin behavior.
2. **Changing:** After approval, use red-green-refactor. Keep the specification, tests and
   affected public usage documentation aligned. Add changelog entries alongside user-visible
   changes, including migration guidance where needed.
3. **Releasing:** Apply the checks relevant to this pytest library and follow
   [docs/releasing.md](docs/releasing.md) for publishing. Finalize the changelog entry with
   the version and release date, then reuse it in the release description. Keep the package
   version, tag and changelog consistent, following the existing version source and
   publishing workflow.

### Project conventions and agreed workflow

- Follow [CONTRIBUTING.md](CONTRIBUTING.md#proposing-changes) when proposing and evaluating changes.
- Keep user-facing acceptance tests readable by a junior developer. Cover internal implementation
  details and exhaustive validation combinations in agent-owned unit tests.
- Assert public outcomes through real pytest runs; avoid coupling acceptance tests to internals.
- Acceptance tests run the installed plugin in real pytest subprocesses using isolated user
  projects. Reuse the setup in [acceptance fixtures](tests/acceptance/conftest.py).
  Use real supported configuration files, including pytest settings such as marker registration.
- Keep unit tests independent of the filesystem where possible, testing validation directly.
  Cover file parsing and loading in acceptance tests.
- Python style follows ruff: Python 3.10 target, 100-character lines and sorted imports.
- Apply the same annotation and type rules to library code, tests, fixtures, scenarios and examples.
  Annotate function parameters and return values, and supply generic type arguments.
  Annotations on `*args` and `**kwargs` are optional and may use `Any`.
  Otherwise prefer concrete types or `object` with runtime narrowing over `Any`.
- Use casts only after runtime validation or at serialization boundaries with a known schema.
  A cast does not validate the value. Keep lint exceptions in [pyproject.toml](pyproject.toml).
  Limit S101 exceptions to test code, including examples, and FBT001 exceptions to `tests/`.
- Runtime dependencies must remain limited to pytest for v0.1.
- Keep `__init__.py` files completely empty: no docstrings, comments or code.
  The package-root `__init__.py` may only export public user-facing functions.
- Do not merge, release or deploy as a side effect of preparing a reviewable change.
- Apply TDD, CI, review and documentation workflows to the agreed task.
- Codex only: no setup, symlinks or instruction files for other agents.
- Do not restart the agreed workflow or request approval already given in the session.

---

## 11. Project Learnings

**Accumulated corrections. This section is for the agent to maintain, not just the human.**

When the user corrects your approach, append a one-line rule here before ending the session. Write
it concretely ("Always use X for Y"), never abstractly ("be careful with Y"). If an existing line
already covers the correction, tighten it instead of adding a new one. Remove lines when the
underlying issue goes away (model upgrades, refactors, process changes).

- Whenever you use or mention a skill, include a clickable Markdown link to its
  exact `SKILL.md` file, using an absolute local path so the user can open it in
  their editor.
- Read `.codex/config.toml` before selecting skills and honor `enabled = false`;
  use enabled project workflows instead of disabled home-level workflows.
- Keep discussion-only turns read-only until the user requests edits.
- Create commits only when the user explicitly requests a commit. Approval to implement changes
  does not authorize committing them.
- Keep pull request descriptions short, covering the change and essential validation.
- Fix required code-health findings before resolving their threads; a rationale alone does not
  clear a failed quality gate. Leave disputed findings open for the maintainer's decision.
- Update verified acceptance checkboxes before closing issues, and record agreed scope changes
  explicitly instead of marking superseded criteria as implemented.
- Keep `tasks/plan.md` and `tasks/todo.md` local and out of commits.
- Keep README guidance focused on what users learn from runnable public examples.
  Present its motivation as one connected argument through engineering principles,
  without naming specific development methods.
  For terminology edits, preserve its structure, examples and public configuration keys.
  Run example commands from the repository root, without `cd` or `--project`.
  Document the shared command once, and explain only the options that differ.
  Use `uv run --locked` to sync automatically without a separate setup command.
  Link generated example reports after the commands that create them.
  Keep the specification and acceptance scenarios internal. Document package
  initializer and editor-navigation conventions in developer instructions.
- Link CONTRIBUTING.md from README. Do not require contributors to read AGENTS.md.
  Link to tool and CI configuration instead of repeating their settings and checks.
- Use commas and full stops in README prose, never semicolons or dashes.
  Use colons between example names and captions. Keep table outcomes short.
  Preserve required punctuation in commands, names, code and Markdown syntax.
- Explain report terminology in plain language and illustrate combined test
  outcomes with a concrete example. Split README usage and runnable example
  commands into short sections with descriptive headings for each task or topic.
- Use domain-neutral requirement IDs and test names in specification examples,
  acceptance tests and their scenario files.
- Structure tests as Arrange, Act, Assert blocks separated by blank lines;
  keep execution out of assertions and omit AAA comments.
- Use parallel names for related validation tests, distinguishing file structure from
  requirement inventory contents rather than mixing file-format and domain terms.
- A rejected acceptance input must produce a domain diagnostic; an unrecognized
  CLI option is not evidence that marker or inventory validation works.
- Check aggregation in both test collection orders to catch first-result shortcuts.
- Observe scenario execution through stdout, and pair every no-execution check with a positive
  execution check so missing instrumentation cannot make the test pass.
- Keep acceptance expectations local and example behavior in named, lintable Python
  scenario files; do not import scenarios from other test modules or generate
  test bodies through substitutions and fallbacks. Exclude scenario files from
  the outer pytest collection, and copy them into isolated user projects.
  Keep requirement predicates boolean and assert in tests; pass expected test
  identities and outcomes as tuples, hiding JSON field names inside the helper.
  Reporting-format tests retain literal JSON expectations.
  Inline requirement and summary lookups in assertions instead of introducing
  aliases for report sections.
- Store acceptance TOML test data in lintable `.toml` files, with deliberately malformed
  syntax in `.toml.invalid` files, and copy them into isolated user projects.
- Keep acceptance tests within the agreed scope; do not add tests for deferred features
  or tests that freeze their current absence.
- Use `pyproject.toml` for pytest settings in new demos unless they specifically demonstrate
  `pytest.ini` configuration.
- Refer to scenarios through package imports, not string paths; use their package
  search paths when copying. Within scenarios, add empty `__init__.py` files only
  in referenced leaf folders to give editor navigation a concrete target.
- Assert complete test identities and outcomes, not only counts or sets that
  can hide duplicated, omitted or unrelated report records.
- Keep the product name `pytest-xspec` consistent across packaging, configuration,
  reports and documentation; use `pytest_xspec` for Python imports.
- Trigger CI on pull requests and pushes to `master`; avoid duplicate feature-branch push runs.
- Report collected tests that never execute as SKIPPED, including collect-only
  and early-stop runs; keep their associated requirements unverified.
- Keep `tests`, `tests/unit` and `tests/acceptance` as packages with empty
  `__init__.py` files so unit and acceptance modules can share basenames.
- Separate completed control-flow blocks from following statements with a blank line.
- After a repository rename, check prior integration setup and retry failed external
  uploads before requesting manual account changes.
- For stale badges, verify both the source image and GitHub's proxied image
  before claiming the issue is fixed.

---

## 12. Provenance

The operating rules are adapted from FerroxLabs' AGENTS.md at commit
`90c7198cfa97ff1868f0600952098fee7fc86ef9`. The Codex adaptation removes
other-agent setup, replaces tool-specific wording and fills project context
from the repository and the user's instructions. Source license: MIT.
