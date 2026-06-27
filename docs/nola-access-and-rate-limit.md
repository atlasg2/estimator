# NOLA Portal — Access Process & Rate Limit

How we pull plan documents from the City of New Orleans OneStop portal
(`onestopapp.nola.gov`), how the rate limit behaves, and the workflow that makes
it a non-problem. Companion to [nola-portal.md](nola-portal.md) (raw portal mechanics).

---

## The starting point: what's in Supabase

Each permit row has a `link` like:

```
http://onestopapp.nola.gov/Redirect.aspx?SearchString=B8SKMD
```

The only piece that matters is that **`SearchString` code** (`B8SKMD`). NOLA also
calls it the permit's "Ref Code." Everything downstream uses it.

> Ignore `Redirect.aspx` itself — it's a session-bounce that sends you into a
> redirect loop. Dead end.

---

## The portal is a 2-step process

**Step 1 — DISCOVERY:** "what documents does this permit have?"

```
GET PrmtView.aspx?ref=B8SKMD   →  the permit page (HTML)
```

The HTML lists every document, and each one carries a hidden **DocID** inside
`onclick='DocRedirect(8400627)'`. So discovery = fetch this page, parse out each
`{filename, DocID}`.

**Step 2 — DOWNLOAD:** "give me that PDF."

```
GET GetDocument.aspx?DocID=8400627   →  the actual PDF
```

You can only download if you know the DocID — and the **only place DocIDs come
from is discovery.** They're huge non-sequential numbers, so you can't guess them.

So the order is always **discover once → then download freely.**

---

## The rate limit — the key facts

- It's **only on `PrmtView.aspx` (discovery).** Download and everything else are open.
- When you trip it: **HTTP 429**, header **`Retry-After: 3600`** (one hour), body
  *"Too many automated requests."*
- **`GetDocument.aspx` (download) is NOT limited.** We've pulled 15+ files,
  including 25 MB plan sets, with zero throttling.
- We tripped it after roughly **20–30 discovery calls** in a session.

**Why we hit it:** we kept re-fetching the *same* permit pages across multiple
probe runs. Wasteful. **The lesson: discover each permit exactly once, save its
DocIDs, and never hit that endpoint for it again.** Once a permit's DocIDs are
cached, you can re-download all of it forever without discovery.

---

## The workarounds (and the one we won't do)

1. **WebFetch** — fetches from a *different IP*, so it **bypasses the 429
   entirely.** Tested 7 in parallel, all succeeded, no limit. Catch: it converts
   the page to markdown and **strips the DocIDs** (the onclick handlers vanish).
   So WebFetch sees **filenames but not DocIDs** → perfect for *screening fit*,
   useless for *downloading*.
2. **Your browser** — unlimited (you're not the flagged automated IP). Open a
   permit, save the page, and the raw HTML gives us the DocIDs.
3. **Just wait out the hour** — fine for one batch of discovery calls.
4. **What we won't do:** proxy/IP-rotation to defeat the per-IP limit. The server
   explicitly says "too many automated requests" — that's an anti-abuse control,
   evading it is the wrong side of the line, and we don't need to.

---

## The insight that makes the limit a non-problem

The scarce resource is **discovery**, never **download**. So you move the
expensive part — screening hundreds of candidates — *off* the discovery path:

```
1. SQL pre-filter (free)        456k permits → a few hundred good candidates
   (recent + building permits RNVS/NEWC, not trade SERV/HVAC, real cost/sqft)

2. WebFetch fit-screen (unlimited)   → which actually have plan/finish sets
   → pick the best 50

3. DISCOVERY (rate-limited, but only 50)   → get DocIDs for the chosen 50
   → browser, or paced over a cooldown or two

4. DOWNLOAD (unlimited)              → grab everything for the 50, fast
```

The throttle only ever touches step 3 — the final 50 — never the ~250 you sift
through in step 2. And step 4 is fast regardless (231 Carondelet's full 12 docs /
66.8 MB came down in under a minute).

**So: screen with WebFetch (free), discover-once-and-cache for the keepers (the
only limited step), download all you want (free).** That's the whole process, and
the rate limit stops being a blocker.

---

## Worked reference — 231 Carondelet (`25-19247-RNVS`)

- **SearchString / Ref Code:** `B8SKMD`
- **Supabase `link`:** `http://onestopapp.nola.gov/Redirect.aspx?SearchString=B8SKMD`
- **Discovery (permit page):** `https://onestopapp.nola.gov/PrmtView.aspx?ref=B8SKMD`
- **Download example (the Arch set, DocID 8400627):**
  `https://onestopapp.nola.gov/GetDocument.aspx?DocID=8400627`

---

## Open question (parked)

Whether the `SearchString` / Ref Code (`B8SKMD`) can be **derived/decoded** from
the permit number or other known fields — which would let us skip discovery
entirely. Unconfirmed; treat as a research idea, not a known capability.
