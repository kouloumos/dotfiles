---
name: save-context
description: Save working documents to .context/ with proper frontmatter
argument-hint: <optional-slug>
---

# Save Context

Save important session outputs, drafts, or working documents to `.context/`.

## Setup (if needed)

If `.context/` doesn't exist in the current project, create it along with a README:

```bash
mkdir -p .context
```

Then create `.context/README.md`:

```markdown
# .context

Working documents, session notes, and draft issues.

## Convention

- Files named `YYYY-MM-DD-slug.md`
- Each file has YAML frontmatter with a `context` field
- The `context` summarizes how we got here — enough to resume later

```yaml
---
context: "Brief but dense summary of the situation, trigger, and purpose of this document."
---
```

Just drop markdown here. No other structure required.
```

## File Format

```
.context/YYYY-MM-DD-slug.md
```

Use today's date and a descriptive slug. If `$ARGUMENTS` contains a slug, use that. Otherwise, derive one from the content.

## Frontmatter

Every file must have a `context` field in YAML frontmatter:

```yaml
---
context: |
  [Your context here]
---
```

## What Makes Good Context

The `context` field should give a future reader (human or AI) enough to understand:

- What was happening when this was written — the situation, the trigger, the problem being solved
- How we got here — the journey, the reasoning, what influenced the thinking
- What this document is and what it's for
- How it connects to other work, issues, or documents
- What state things are in — what's done, what's pending, what needs action before using this

Write it as narrative, not tags. Someone reading just the context field should be able to decide if they need to read the rest, and have enough background to understand it if they do.

## Workflow

1. Check if `.context/` exists; if not, create it and the README
2. Determine the slug (from `$ARGUMENTS` or derive from content)
3. Write the file with today's date: `.context/YYYY-MM-DD-slug.md`
4. Include proper YAML frontmatter with a meaningful `context` field
5. Add the content below the frontmatter
