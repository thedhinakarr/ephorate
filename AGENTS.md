# AGENTS.md

Standing instructions for any coding agent working in this repository. The full build plan is in `PROJECT_PLAN.md`; read it before starting a milestone.

## What this project is

Ephorate is a service that predicts, for each pull request, the probability that merging it will cause a production incident. The prediction is calibrated on the customer's own history of changes and incidents. A team sets a risk threshold; changes below it can merge after automated checks, and changes above it are routed to the right human reviewer. Every merge is then tracked against later incidents so the model keeps improving.

Use **Ephorate** as the product name and `ephorate` for project identifiers. The intended domain to purchase is `ephorate.dev`; purchase and ownership have not been verified.

The product exists because AI coding agents have made writing code much faster while human code review has not sped up, so review has become the bottleneck. Existing AI reviewers label changes "low risk" from reading the diff. This product's difference is that its risk number is a measured probability, checked against real outcomes. Keep that in mind when making design choices: anything that makes the score less auditable or less tied to outcomes works against the point of the product.

## Rules that always apply

- **Read-only toward customer systems by default.** The service reads from GitHub, PagerDuty and Datadog. The only things it writes are a check run and comments on a pull request. It never merges, approves, pushes or deletes unless a feature flag for that customer is explicitly on, and that flag defaults to off.
- **The LLM supplies features, never the decision.** LLM output may be used as input columns to the risk model. The merge decision comes from the calibrated model plus the policy file, so that every decision can be explained and reproduced.
- **No customer code or incident text in logs, test fixtures or error messages.** Log identifiers and counts. Tests use the public-repository fixtures described in the plan.
- **Time-based splits only.** Any model evaluation trains on earlier data and tests on later data. A random split leaks future information and makes results meaningless.
- **Secrets come from the environment.** Never commit keys, tokens, private keys or `.env` files. If a secret is needed and missing, stop and ask.
- **Check current documentation for library and API versions** before pinning them. Do not rely on remembered version numbers.

## How to work

- Work one milestone at a time, in the order given in `PROJECT_PLAN.md`. Do not start a milestone until the previous one meets its acceptance criteria.
- Each milestone ends with: tests passing, `README.md` updated with how to run what was built, and a short entry in `docs/DECISIONS.md` for any choice the plan left open.
- Small, reviewable pull requests. One concern per pull request.
- If the plan and reality disagree (an API no longer works as described, a library is unmaintained), stop, write down what you found, and propose an alternative. Do not silently substitute.
- Items marked **HUMAN** in the plan need a person: creating accounts, registering the GitHub App, providing credentials, approving spend, and any production deploy. Prepare everything up to that point, then ask.

## Commands

Fill these in during Milestone 0 and keep them current.

- Install: `make install`
- Lint and type-check: `make lint`
- Tests: `make test`
- Run locally: `make dev`
- Run the backtest: `make backtest REPO=<path-or-url>`

## Code conventions

- Python for backend and modelling, with type hints and a strict type checker. TypeScript for the dashboard.
- Formatting and linting are enforced in CI; do not hand-format.
- Database changes go through migrations, never ad hoc SQL.
- Every external API call goes through a client module in `packages/connectors/` so it can be mocked.
