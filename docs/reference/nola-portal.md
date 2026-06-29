# NOLA OneStop Plan Retrieval

Status: active
Owner: engineering
Last verified: 2026-06-19

How we get the actual plan PDFs (architectural drawings, finish schedules) for a City of New Orleans
permit — fully automated, no login, no clicking. This is the bridge from the `NolaPermit` table
(the lead index, see [architecture.md](../architecture.md), *External lead source - NolaPermit*) to
real plan files we can feed into the takeoff system.

**TL;DR — the whole thing is three GETs, no auth:**

```
stored link  ──►  Redirect.aspx?SearchString=XXXXXX        (XXXXXX is the permit's "Ref Code")
GET           ──►  PrmtView.aspx?ref=XXXXXX                 (HTML already lists every document)
GET           ──►  GetDocument.aspx?DocID=NNNNNNN           (returns the raw PDF)
```

---

## The data we start from

Each row in `NolaPermit` has a `link` column that looks like:

```
http://onestopapp.nola.gov/Redirect.aspx?SearchString=B8SKMD
```

That `SearchString` value (`B8SKMD`) is the only key we need. Everything below is derived from it.

---

## How the portal actually works (and the dead ends)

In a browser the flow *looks* like: click the link → a search page → click **View** → permit page →
click the **Documents** tab → click each file's download icon. That's four interactions and a
session. Underneath, almost none of it is real. Here's what each layer actually does.

### 1. `Redirect.aspx?SearchString=XXX` is a session-stashing bounce — ignore it

Hitting it returns `302 → /Search.aspx` and sets two cookies (`ASP.NET_SessionId`, `bg_ok=1`). It
stashes the search token in server-side session and bounces you to a results page. If you follow it
naively with `curl -L` you get a redirect loop (`?SearchString=XXX&SearchString=XXX&…`). **Dead end —
don't use this path.**

### 2. The "Ref Code" on the results page == the SearchString

`Search.aspx` (rendered from session) shows the matching permit with the text:

```
Permit #25-19247-RNVS · Ref Code: B8SKMD
```

That **Ref Code is identical to the SearchString** in the original link. That's the key insight: we
don't need the search step at all — we already have the ref.

(The **View** button on that page calls `SummaryRedirect('Permit', 1065242)` using an internal
numeric permit id. That's a *different* id we never need — skip it.)

### 3. `PrmtView.aspx?ref=XXX` is the permit page — and it needs no cookies

Go straight there:

```
GET https://onestopapp.nola.gov/PrmtView.aspx?ref=B8SKMD     → 200, ~59 KB of HTML
```

Verified it returns the full page **with no cookies, no session, no referer.** It's an ASP.NET
WebForms page (`__VIEWSTATE`, `__doPostBack`, etc.) but we never post anything — we only read.

### 4. The document list is already inline in that HTML

The **Documents** tab is *not* an AJAX call — its contents (`<div id="documents">`) are baked into the
same HTML, hidden behind a Bootstrap tab. Each document is an `<li>`:

```html
<li> 231 Carondelet CD Drawings Arch Plans (RCC).pdf (7/31/2025)
     <a href="#" onclick='DocRedirect(8400627)'><i class="fas fa-file-download"></i></a> </li>
```

So a regex over the page gives us, for every document: **filename, date, and the numeric `DocID`**
(the argument to `DocRedirect(...)`).

### 5. `DocRedirect(n)` → the one download URL

`DocRedirect` isn't defined inline; it lives in the `/bundles/onestop` JS bundle. Fetched and
de-minified it is literally:

```js
function DocRedirect(n){
  var t = document.getElementById("vDir").value;          // virtual dir, "/" here
  window.open(location.protocol+"//"+location.host + (t==="/" ? "" : t)
              + "/GetDocument.aspx?DocID=" + n, "_blank");
}
```

i.e. the download is just:

```
GET https://onestopapp.nola.gov/GetDocument.aspx?DocID=8400627   → the PDF (no auth)
```

Confirmed: returns `Content-Type: application/pdf`, body starts with `%PDF-`, multi-page, up to tens
of MB (the 231 Carondelet arch set is **24.6 MB**).

---

## The full recipe (per permit)

1. Parse `SearchString` out of `NolaPermit.link` → call it `ref`.
2. `GET PrmtView.aspx?ref=<ref>`.
3. Regex the HTML for every `<li> … DocRedirect(<DocID>)` → list of `{ name, docId, date }`.
4. Classify each (plans vs paperwork — see below).
5. For each kept doc: `GET GetDocument.aspx?DocID=<docId>` → save the PDF.

No cookies, no `__VIEWSTATE`, no POST, no rate-limit seen. Just GETs.

### Verified curl (copy-paste runnable)

```bash
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# 1. permit page → list documents
curl -s -A "$UA" "https://onestopapp.nola.gov/PrmtView.aspx?ref=B8SKMD" -o pv.html
grep -oE "DocRedirect\([0-9]+\)" pv.html        # → DocRedirect(8400627), ...

# 2. download a document by id
curl -s -A "$UA" "https://onestopapp.nola.gov/GetDocument.aspx?DocID=8400627" -o plans.pdf
head -c5 plans.pdf                               # → %PDF-
```

---

## Which documents to keep

A permit's doc list mixes the **plan set** with **paperwork**. Real example — 231 Carondelet
(`B8SKMD`), a restaurant build-out, 12 documents:

| Keep | DocID | File |
|---|---|---|
| ✅ plans | `8400627` | 231 Carondelet CD Drawings **Arch Plans** (RCC).pdf — 24.6 MB, finishes/floor plans live here |
| ✅ plans | `8400631` | 231 Carondelet CD Drawings **MEP Plans** (RCC).pdf |
| 🟡 plan, not flooring | `8400629` | Plumbing Riser Diagram |
| ⚪ skip | `9275210` | Building Permit.pdf |
| ⚪ skip | `9260476` | Receipt.pdf |
| ⚪ skip | `8599788` | LDH Armada Approval.pdf |
| ⚪ skip | `9184842` | Construction Contract (executed).pdf |
| ⚪ skip | `8662973` | Recorded Act of Sale.PDF |
| ⚪ skip | `8662974` | Articles of Organization.pdf |
| ⚪ skip | `8400634` | LDH Approval.pdf |
| ⚪ skip | `8400638` | Restaurant Classification and Uses Form.pdf |
| ⚪ skip | `8400632` | State Fire Marshal Approval.pdf |

**Keep heuristic** (filename, case-insensitive):

- **KEEP** if it matches: `drawing | plan | arch | mep | floor | structural | elev | detail | schedule | \bcd\b | A-?\d` (e.g. `A-101`)
- **DROP** if it matches: `receipt | building permit | contract | act of sale | articles | approval | license | authoriz | classification | fire marshal | insurance | invoice | affidavit`

Always record **all** documents in a manifest (even skipped ones) so nothing is silently lost — you
can pull a skipped DocID by hand any time.

> Bonus: the **"Restaurant Classification and Uses Form"** tells you the occupancy type without even
> opening the plans — a cheap signal for triaging leads.

---

## Gotchas / notes

- **`ref` == `SearchString`.** Don't build the search/session flow; go straight to `PrmtView`.
- **No `Content-Length` on `HEAD`.** A `curl -sI` against `GetDocument.aspx` returns `0`/no length;
  you only learn a file's size by actually GETting it. Filter by filename, not by a pre-checked size.
- **`Content-Type` is the odd string `application/application/pdf`** (their bug) — don't match it
  exactly; check for `pdf` substring or the `%PDF-` magic bytes instead.
- **Some files are big** (10–25 MB plan sets). Download sequentially and be polite; consider a
  per-file size cap if pulling many leads at once.
- **Filenames can collide / contain `/` and spaces.** Sanitize to a safe filesystem name and
  de-dupe; key documents by `DocID` (globally unique), not by filename.
- **`.PDF` vs `.pdf`** — extension case varies; match case-insensitively.
- **Politeness / legality.** This is public open-records data (the dataset is CC0 and the portal is
  public, no auth). Still: throttle, set a real User-Agent, and don't hammer — one permit is ~1 page
  fetch + N file GETs.
- **Robustness.** A permit may have **zero** documents, or only paperwork. Handle the empty case;
  don't assume every lead yields a plan set.

---

## Where this plugs in

- Source of leads: `NolaPermit` rows with `leadStatus = "saved"` (triaged on `/permits`).
- Planned scraper: `scripts/nola-docs.ts` (`npm run nola:docs`) → for each saved lead, pull plan PDFs
  into `data/nola/<permitNum>/` + a `manifest.json` listing every document found and which were kept.
  Idempotent (skips a permit whose folder already has a manifest).
- End state (later): upload the kept PDFs to Supabase storage and create a `Document` + per-page
  `PlanSheet` per lead, so scraped plans flow into the existing finish-extraction pipeline exactly
  like an uploaded bid (mirrors the upload path in `app/actions.ts`).
