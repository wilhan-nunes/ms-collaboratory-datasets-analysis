# MSCollaboratory: MassIVE USIs, GNPS2 links, deposition timeline

Finds every MassIVE dataset matching a keyword (default `mscollaboratory`), lists
its mzML files, emits GNPS2-ready USIs and classical-networking launch links, and
plots depositions over time.

## Install

    pip install -r requirements.txt

## Run

    python massive_usis.py            # datasets -> USIs -> links (+ metadata)
    python plot_depositions.py        # bar plot from datasets.csv

Useful flags: `--keyword`, `--outdir`, `--refresh` (bypass the file cache),
`--max-url-chars`; `--freq quarter` on the plot.

## Refresh on GitHub Actions

`.github/workflows/update-analysis.yml` runs the whole pipeline on demand: go to the
repo's **Actions** tab, pick **Update analysis**, and hit **Run workflow**. The form
takes `keyword`, `freq` (year/quarter), and `refresh`. From the CLI:

    gh workflow run update-analysis.yml -f keyword=mscollaboratory -f freq=year

It regenerates everything in `output/`, commits the result back to the branch if
anything changed, and attaches the same files as a downloadable run artifact.
Everything it queries is public, so no secrets or repository configuration are
needed. A monthly `schedule` trigger is included but commented out.

Between runs the workflow carries `file_cache.json` in the Actions cache, so it only
FTP-lists accessions it hasn't seen — the first run is slow, later ones are not.
Tick `refresh` to discard that cache and re-list every dataset from scratch.

## Outputs (`output/`)

| File | Contents |
|---|---|
| `datasets.csv` | one row per dataset: accession, deposition date, mzML count, title, submitter |
| `usis.txt` | every USI, one per line |
| `usis_by_dataset.json` | `{accession: [usi, ...]}` |
| `gnps2_links.txt` | launch URLs, grouped and commented by dataset |
| `depositions_over_time.png` + `_table.csv` | the bar plot and its underlying counts |
| `file_cache.json` | raw ppx listings; reused so reruns skip the slow FTP walk. Gitignored — regenerated on first run |

## USI and link format

USIs follow `mzspec:<accession>:<basename>`. `ppx` returns repo-relative paths
(`ccms_peak/Negative raw data/KP027_Negative.mzML`) but a GNPS2 USI addresses the
file by basename, so directories are stripped and any duplicate basenames within a
dataset are collapsed.

Links are `…/workflowinput?workflowname=classical_networking_workflow#{"usi": "…"}`
with the USIs joined by literal `\n`, percent-encoded. `build_link()` reproduces the
reference URL byte-for-byte.

Datasets whose link would exceed `--max-url-chars` (default 8000) are split into
numbered parts — each part is a valid standalone job. Large datasets are the norm
here, so 66 datasets currently produce ~156 links.

## Deposition dates — no extra API needed

`QueryDatasets` already returns the deposition date on each row (`createdMillis`,
plus human-readable `created` / `create_time`), so the timeline comes free from the
search that was already happening. `createdMillis` is parsed as UTC into
`deposition_date`.

Two things the plot handles deliberately: years with zero depositions are drawn as
zero-height bars rather than dropped (dropping them compresses the time axis and
fakes a smoother trend), and the in-progress current year is hatched and labelled
`(partial)` so its short bar doesn't read as a decline.

## Files

- `massive_usis.py` — the pipeline
- `plot_depositions.py` — the timeline plot
- `retrieve_massive_files_ORIGINAL.py`, `massive_mzml_files_ORIGINAL.json` — the
  original script and its output, kept for reference; the JSON seeded `file_cache.json`
- `test_massive_api.py` — scratch probe of the QueryDatasets endpoint
