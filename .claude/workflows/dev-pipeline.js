export const meta = {
  name: 'dev-pipeline',
  description: 'Design agent proposes one improvement, a develop agent implements it on a new branch, a test agent independently verifies it. Never pushes or deploys — that is always a separate, human-approved step.',
  whenToUse: 'Invoke manually ("run the dev pipeline") whenever you want an autonomous design→build→test cycle for this app. Read the returned summary and decide separately whether to merge/deploy.',
  phases: [
    { title: 'Design', detail: 'Agent inspects the app and proposes one well-scoped improvement' },
    { title: 'Develop', detail: 'Agent implements the design on a new branch in an isolated worktree' },
    { title: 'Test', detail: 'A second, independent agent re-runs tests and reviews the diff against the plan' },
  ],
}

const DESIGN_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string', description: 'Short imperative title, e.g. "Add trail-difficulty filter to search"' },
    rationale: { type: 'string', description: 'Why this is worth doing next, in 1-3 sentences' },
    plan: { type: 'string', description: 'Concrete implementation plan a developer could follow directly' },
    files_likely_touched: { type: 'array', items: { type: 'string' } },
    risk_level: { type: 'string', enum: ['low', 'medium', 'high'] },
  },
  required: ['title', 'rationale', 'plan', 'files_likely_touched', 'risk_level'],
  additionalProperties: false,
}

const DEV_SCHEMA = {
  type: 'object',
  properties: {
    branch: { type: 'string' },
    summary: { type: 'string', description: 'What was actually implemented, in plain language' },
    files_changed: { type: 'array', items: { type: 'string' } },
    self_tests_passed: { type: 'boolean' },
    self_test_notes: { type: 'string' },
  },
  required: ['branch', 'summary', 'files_changed', 'self_tests_passed', 'self_test_notes'],
  additionalProperties: false,
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    tests_passed: { type: 'boolean' },
    matches_plan: { type: 'boolean' },
    ready_to_review: { type: 'boolean', description: 'true only if tests pass, scope matches the plan, and no significant issues were found' },
    findings: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['tests_passed', 'matches_plan', 'ready_to_review', 'findings', 'summary'],
  additionalProperties: false,
}

const APP_CONTEXT = `This is Trailhead, a national-parks trip-planning PWA. FastAPI backend in app/backend (see app/backend/main.py for routes), React+TypeScript PWA in app/frontend. Read app/README.md's capability table to see what already exists, and skim the last ~20 commits (git log --oneline -20) so you don't re-propose or re-touch something just finished.`

phase('Design')
log('Design agent is scoping the next improvement...')
const design = await agent(
  `You are the design agent for this app. ${APP_CONTEXT}

Propose exactly ONE well-scoped next improvement — a feature, fix, or piece of polish that is genuinely useful and not already built. Prefer small, coherent, shippable scope over ambitious rewrites. Avoid anything that would need a paid API key or credential you can't test yourself. Do NOT touch deploy/infra config (Dockerfile, render.yaml) unless the improvement is specifically about deployment. Do not write any code — only investigate and propose.`,
  { schema: DESIGN_SCHEMA, phase: 'Design', label: 'design' }
)
log(`Design: "${design.title}" (risk: ${design.risk_level})`)

phase('Develop')
const branch = 'agent/' + design.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 44)
log(`Develop agent implementing on branch ${branch}...`)
const dev = await agent(
  `You are the develop agent for this app. ${APP_CONTEXT}

Implement this design on a NEW branch named "${branch}", created from the current HEAD:

Title: ${design.title}
Rationale: ${design.rationale}
Plan: ${design.plan}
Files likely touched: ${design.files_likely_touched.join(', ') || '(not specified — use your judgment)'}

Rules:
- Implement only what the plan calls for. No unrelated refactors, no scope creep.
- Follow this repo's existing code style and conventions (see CLAUDE.md / existing files for the pattern).
- Run the relevant checks yourself before finishing: backend tests live in app/backend (pytest, with TRAILHEAD_DISABLE_POLLER=1), frontend build is "npm run build" in app/frontend. Fix failures before you finish.
- Commit your work locally on branch "${branch}" with a clear message.
- Do NOT push, do NOT merge into any other branch, do NOT open a pull request. A human reviews and deploys separately, later.
- Report exactly what you changed and whether your own checks passed.`,
  { schema: DEV_SCHEMA, phase: 'Develop', label: 'develop', isolation: 'worktree' }
)
log(`Develop: ${dev.files_changed.length} file(s) changed, self-tests ${dev.self_tests_passed ? 'passed' : 'FAILED'}`)

phase('Test')
log('Independent test/verify agent reviewing the change...')
const verify = await agent(
  `You are an independent test and verification agent for this app. ${APP_CONTEXT}

A develop agent claims to have implemented the following on branch "${dev.branch || branch}" (it already exists in this repo with a commit on it — check out that existing branch, do not create a new one):

Title: ${design.title}
Plan: ${design.plan}
Develop agent's own summary: ${dev.summary}
Develop agent's self-reported test result: ${dev.self_tests_passed ? 'passed' : 'FAILED'} — ${dev.self_test_notes}

Do not trust the self-report. Independently:
1. Check out branch "${dev.branch || branch}" in a fresh worktree.
2. Re-run the real checks: backend "pytest" in app/backend (with TRAILHEAD_DISABLE_POLLER=1) and "npm run build" in app/frontend if frontend files changed.
3. Review "git diff" against the base branch for correctness, scope creep beyond the plan, and any obvious bugs.
4. Do NOT fix anything yourself and do NOT push/merge — you are a reviewer, not a developer.

Report honestly, including any problems found, even minor ones.`,
  { schema: VERIFY_SCHEMA, phase: 'Test', label: 'verify', isolation: 'worktree' }
)
log(`Verify: ready_to_review=${verify.ready_to_review}`)

return {
  design,
  branch: dev.branch || branch,
  develop: dev,
  verify,
  recommendation: verify.ready_to_review
    ? 'Tests pass and the change matches the plan. Ready for human review before merge/deploy.'
    : 'Do not deploy as-is — see verify.findings for what needs fixing.',
}
