# Bill text quality audit

Run from `apps/api` with `DATABASE_URL` pointing to the intended database:

```sh
python scripts/audit_text_quality.py --fields summary_short_el summary_long_el --include-legacy DIAVGEIA --include-legacy PARLIAMENT
```

The default is a dry run. Output includes source, field, reason, count, sample
IDs, `would_clear`, and `report_only`. It never prints the bill text.
The last two columns count permission for each reason, so a legacy field with
both `non_greek` and `error_page` appears as report-only for `non_greek`
and would-clear for `error_page`. A field is eligible if at least one reason
permits clearing, and is backed up and cleared once. The summary counts eligible
fields rather than summing reasons. `would_clear` reflects scan-time eligibility;
a concurrent edit or review can still prevent the guarded update.

Fields whose current content matches their generation provenance use every
quality reason. Fields without provenance are eligible only for sources named
by `--include-legacy`, and default to these reasons:

- `refusal_or_meta`
- `reader_metadata`
- `mojibake`
- `error_page`

`non_greek`, `mixed_script` and `foreign_script` are report-only for legacy fields
by default. Official documents can contain foreign names, titles and homoglyph
quirks such as Greek capitals inside brand names or Cyrillic look-alikes.
`--legacy-reasons` replaces the default list.
An explicit override such as `--legacy-reasons non_greek mixed_script` permits
those two reasons for the named legacy sources. It does not limit reasons for
provenance-owned fields. Review the dry run with the same options before apply.

Approval is tied to an exact plan. Run the dry run with `--plan-csv /path/to/new-plan.csv`:
the plan lists every field the run would clear as `id,field,reasons,sha256` (no text,
mode 0600, new file only). The approver signs off on that file.

To apply, add `--apply --backup-csv /path/to/new-private-backup.csv
--expect-from /path/to/approved-plan.csv --max-rows N`. Apply clears only fields whose
id, field and current value digest are in the approved plan; new hits and changed values
are skipped and counted. N must be a nonnegative integer, including for Python
callers. If more than N fields match, the run aborts before writing the
backup or any update. The backup
must be a new file; it is written with mode 0600 and flushed to disk before any
updates. Reviewed fields, edited fields whose provenance no longer matches, and
sensitive fields remain protected. Applying invalidates the representation cache
after each batch that changes fields.

## Language signals

Greek fields require a Greek share of at least 0.6 over letters, excluding URLs
and complete quoted Latin titles. The existing short-pill acronym exception
remains. Conservative English grammar patterns (for example, `introduces new
requirements` or `Please provide the document so I can summarize it`) also report
`non_greek`, even with Greek padding. Complete quotations are exempt from these
clause checks; names, titles, brands and acronym runs alone do not fail them.

Refusals require a self-referential lead-in at the start of a line, after Markdown,
ordered-list or Unicode bullet formatting is removed. Complete quoted speech and
definitions using «ως μοντέλο» do not establish a refusal. Horizontal whitespace
is collapsed before matching to keep long spaces/tabs from causing backtracking.
HTML error headings are checked independently of adjacent titles and before text
extraction can discard them. Flattened `Error Access Denied Reference #…` remains
an error-page signal; error terms embedded or quoted in legislative prose do not.

`mixed_script` counts words containing both Greek letters and Latin letters
outside the case-sensitive homoglyph allowance `ABCEHIKMNOPTXYZaceiopuvxy`.
For example, `Aπόφαση` is accepted, while `κίνδυnu` contains a non-homoglyph `n`.
Two suspect words fail at any length; one fails in prose of at most 200 words.
This catches corruption in short summaries while tolerating one isolated typo
in longer official documents. Tests cover the 200/201-word boundary and two
suspect words in 1,000 words. This is a deterministic heuristic, not a measured
precision claim for the production corpus.

`foreign_script` checks explicitly enumerated Unicode script-name prefixes for
Cyrillic, CJK (including Japanese and Korean), Indic scripts, Arabic, Hebrew,
and Thai, plus the existing Vietnamese-specific Latin letters. Modifier letters
(category `Lm`), symbols, and ordinary accented Latin names do not trigger it.
Foreign letters are checked even inside quotes. Greek numeral signs U+02B9,
U+0374, and U+0375 are accepted.
