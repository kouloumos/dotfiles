# Blog Post Template

Generate a blog post announcing the release. This is read by the general public — citizens, journalists, municipal officials, civic tech enthusiasts — not just developers.

## Tone

Approachable, clear, focused on impact. Explain what changed in terms of what people can now do, not how it was built. Avoid jargon. Write for someone who uses the platform but doesn't write code.

## Structure

```markdown
# [Title — descriptive, not just the version number]

<!-- Opening paragraph: 2-3 sentences framing what this release is about. What's the theme or biggest change? Why does it matter? -->

## [Section per major feature/change — use descriptive headings]

<!-- For each notable change:
  - What can users now do that they couldn't before?
  - Why does this matter? (transparency, accessibility, civic engagement)
  - Optional: screenshot or visual description if it's a UI change
-->

<!-- Repeat for 2-4 major items. Don't cover everything — just the highlights. -->

## Looking Ahead

<!-- 1-2 sentences about what's coming next. Optional but gives readers a reason to stay engaged. -->

---

*[Project Name] is open source. Follow our progress on [GitHub](repo-url) or join the conversation on [Discord](discord-url).*
```

## Rules

- **Title should be descriptive**, not just "Version 2026.4.1" — e.g., "Meeting Search Gets Smarter" or "Now Supporting 12 More Municipalities"
- **No technical jargon** — translate developer language to user language. "Faster search" not "Elasticsearch query optimization"
- **Focus on 2-4 highlights** — this is a blog post, not a changelog
- **Include the human impact** — why does this feature matter for civic transparency?
- **Keep it under 500 words** — respect the reader's time
- **Skip purely internal changes** — refactors, dependency updates, CI changes don't belong here
- **If the release is minor** (mostly fixes/polish), the post can be shorter — 200 words is fine. Or suggest to the user that this release may not warrant a blog post.
