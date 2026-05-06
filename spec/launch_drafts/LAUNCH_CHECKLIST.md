# Bourdon launch checklist

**Status:** Living checklist. Tick items as you go. Don't post until every
item in the "Pre-launch" section is green.

---

## Pre-launch (in order)

- [x] **Landing page deployed to Cloudflare Workers**
      Verified live at `https://bourdon-cloud-landing.ryandavispro1.workers.dev`
      (commit `9821eba`, 2026-04-27)
- [x] **Cloudflare custom domain bound** to the `bourdon-cloud-landing`
      worker (after deleting the orphan `continuo-web` worker + its imported
      IONOS A/AAAA records, see commit `0d77742` for the journey)
- [x] **IONOS DNS pointed at Cloudflare** — nameservers changed to
      `bob.ns.cloudflare.com` + `diva.ns.cloudflare.com`. Propagation
      complete; bourdon.ai now resolves to Cloudflare anycast
      (`172.67.164.58`, `104.21.10.194`, IPv6).
- [x] **`curl https://bourdon.ai` returns HTTP 200 with the landing
      HTML** — verified via 1.1.1.1 resolver: 9.2KB, ~370ms cold
- [ ] **GitHub repo `getbourdon/bourdon` About sidebar populated**:
      - Description: "Cross-agent memory federation with a recognition-
        first runtime model. Pre-alpha. MIT."
      - Website field: `https://bourdon.ai`
      - Topics: `ai-memory`, `agent-memory`, `mcp`, `recognition-first`,
        `llm-tools`, `local-first`, `python`, `cross-agent-federation`
- [ ] **README's "Status" section updated** — first line reads
      "Pre-Alpha v0.0.7 — [bourdon.ai](https://bourdon.ai)"
      (currently the link is buried below the changelog)
- [ ] **Twitter draft reviewed in Ry's voice** —
      `spec/launch_drafts/twitter_thread.md` reads like Ry, not like
      Claude. Edit anything formulaic.
- [ ] **HN Show draft reviewed in Ry's voice** —
      `spec/launch_drafts/hn_show.md` same check
- [ ] **All 7 tweets fit in 280 chars** — manually count after edits

## Day-of launch

- [ ] **Time of day**: aim for Tuesday-Thursday, 9-11am Pacific. Best HN
      front-page traction window for technical posts.
- [ ] **Twitter thread posts FIRST** — 7 tweets, post them in sequence
      with ~30s between tweets so they all chain
- [ ] **Wait 30 minutes** — let the thread breathe
- [ ] **HN Show posts** at the URL `https://bourdon.ai`
- [ ] **Pin the Twitter thread** to your profile
- [ ] **Cross-link**: reply to your own first tweet with the HN URL once
      it's submitted

## First-hour engagement

- [ ] **Monitor HN comments** — reply to first 3-5 substantive comments
      within the first hour. Early engagement boosts ranking.
- [ ] **Skip drive-by criticism** — reply to "have you considered X?"
      comments, not to "this looks like Y but worse" ones
- [ ] **Watch for prior-art flags** specifically — if someone in the
      field surfaces a paper/project framing recognition-first runtime
      timing the way Bourdon does, engage seriously. That's the highest-
      value feedback the launch can produce.
- [ ] **Don't argue about the wedge** — let RELATED_WORK.md do the
      arguing. Link to it.

## First 24h

- [ ] **Twitter mentions**: reply to substantive technical questions, not
      to engagement-bait. Skip emojis-only replies.
- [ ] **HN comments**: keep replying for at least 4 hours. Use the
      first wave to identify which questions to answer in a follow-up
      blog post or FAQ doc.
- [ ] **Track**: GitHub stars, repo clones, traffic to bourdon.ai
      (Cloudflare dashboard has analytics for free).

## Day 2-3 (if HN traction held)

- [ ] **Cross-post to r/MachineLearning** — only if HN reached front page
      OR generated 30+ substantive comments. Repost format: link to HN
      thread + 2-paragraph framing of the discussion.
- [ ] **Anthropic Discord post** — share in #showcase or equivalent
      channel. Tag relevant maintainers if appropriate.
- [ ] **OpenAI dev forum post** — same idea, the Codex adapter angle
      gives this a natural home.

## Week 1 follow-ups

- [ ] **FAQ document** — `docs/FAQ.md` covering the top 5-10 questions
      that came in. Reuse the answers given on HN/Twitter.
- [ ] **Blog post or follow-up note** — a 1500-word writeup of the launch
      reception, what surfaced, what surprised. Hosted on bourdon.ai.
- [ ] **Adapter PRs** — if anyone offered to build a Cursor or Cline
      adapter, follow up with them within a week. Adapters are the
      highest-leverage way to grow the federation footprint.

## Don't post unless

- [ ] **The recognition-first runtime is wired into a real agent's
      response loop** — wait. The current state ("recognition runtime
      exists as a Python module; integration is the open empirical
      test") is honest about pre-alpha status. Posting before that is
      fine. Posting and *claiming* the integration is done would not be.
- [ ] **bourdon.ai is reachable** — do not post linking to a 404
- [ ] **The repo CI is red** — keep CI green before launch; broken CI
      on the front page of the repo is a credibility hit

## Failure modes to expect

- **HN doesn't bite.** ~70% of Show HN posts don't reach front page.
  That's fine — the landing page + GitHub URL stay durable. The launch
  is a publish-the-thesis move first, traffic-spike second.
- **A Mem0/Zep/Letta maintainer pushes back on the framing.** Engage
  respectfully via RELATED_WORK.md. The doc was written specifically
  to acknowledge their work, not compete with it.
- **Someone surfaces actual prior art on recognition-first runtime
  timing.** This is the genuine bad outcome. If it happens, update
  POSITIONING.md with the citation, document the loss in
  FINDINGS_JOURNAL.md, and revise the wedge framing. Better to be
  publicly corrected than to claim something untrue.

---

*Generated 2026-04-27 alongside the Bourdon launch drafts. Living
document — update as launches teach us things.*
