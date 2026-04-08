---
name: create-issue
description: Create a well-structured GitHub issue from a conversation or description
argument-hint: <optional: brief description of the issue>
---

# Create GitHub Issue

Help create well-structured GitHub issues from conversations, bug reports, or feature ideas.

## Determine the Repository

Use the current git repo by default:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

If `$ARGUMENTS` includes a repo reference (e.g., `schemalabz/opencouncil-tasks`), use that instead.

## Search for Related Issues

Before drafting, ALWAYS search GitHub for related existing issues and PRs:

```bash
gh search issues "<relevant keywords>" --repo <REPO> --limit 5
gh search prs "<relevant keywords>" --repo <REPO> --limit 5
```

If related issues exist, present them:
- "I found these related issues: #42 <title>, #67 <title>. Is your request different, or should we add to an existing one?"

Only proceed with creating a new issue if the user confirms it is distinct.

## Fetching Labels

Always fetch the current labels from GitHub before assigning them:

```bash
gh label list --repo <REPO> --limit 50
```

Use the actual labels returned. Do not hardcode or assume label names.

## Issue Types

Every issue gets one type label:
- **bug** — something is broken or not working as expected
- **feature** — new functionality that does not exist yet
- **task** — maintenance, refactoring, documentation, or other work items

## Writing Style

- **Describe the problem, not the solution.** Focus on WHAT needs to happen, not HOW.
- **Leave implementation open.** Never prescribe architecture, patterns, libraries, or specific code changes.
- **Keep it concise.** Clear enough for any contributor to pick up, without removing their agency.
- **Let the contributor decide.** If there are multiple approaches, do not pick one.

Bad: "Implement this using a Redis cache with a 5-minute TTL on the /api/search endpoint"
Good: "Search results for repeated queries could benefit from caching to reduce response times"

## Handling Vague Descriptions

If the description is brief or vague, ask 2-3 focused follow-up questions to understand:
- What the user is trying to achieve (the goal, not the solution)
- What currently happens vs what they expect
- Any context about where in the platform this applies

Keep it conversational, not bureaucratic.

## Bug Reports

When someone reports a bug:
- Ask what they expected to happen vs what actually happened
- Ask for steps to reproduce if they can recall them
- Help them articulate the problem without putting words in their mouth

## Workflow

### Step 1: Understand the Request
Based on what the user said (or `$ARGUMENTS`):
- Determine the issue type (bug, feature, task)
- Search GitHub for related issues
- If anything is unclear, ask ONE round of focused questions (2-3 max)

### Step 2: Generate Preview
Show the user a formatted preview:

```
ISSUE PREVIEW

Title: <concise, action-oriented title>

Body:
### Concept
<1-3 paragraphs: what this is about and why it matters>

### User Story
As a <role>, I want <goal>, so that <benefit>.

### Context
<any relevant context — existing behavior, related features, constraints>

Labels: <label1>, <label2>
```

Ask: "Reply **yes** to create, **edit** to change something, or **cancel** to abort."

### Step 3: Create the Issue
After user confirms:

```bash
gh issue create --repo <REPO> --title "<TITLE>" --body "<BODY>" --label "<label1>" --label "<label2>"
```

Report the issue URL back to the user.

## Guidelines
- NEVER create an issue without showing a preview and getting explicit approval
- Keep titles concise and action-oriented (imperative mood)
- The Concept section explains value, not implementation
- User Stories reflect real user needs
