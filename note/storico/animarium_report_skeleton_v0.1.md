# Animarium: an open, reproducible pipeline for synthetic populations of Italian cities — from ISTAT sources to open data

**Technical report v1.0 — skeleton v0.1, 17 August 2026**
Mirko Degli Esposti · Department of Physics and Astronomy (DIFA), University of Bologna

> **How to read this skeleton.** Each section carries three annotations:
> `SOURCE:` the project note(s) the text is drawn from (Italian, internal);
> `STATUS:` `rerun` = re-executed for this report on the public commit
> (Parma 034027, Castenaso 037011, Bologna 037006), `reported` = taken from
> notes with date and commit, `todo` = not yet written anywhere;
> `TABLE:` tables to fill, with the script that produces them.
> Section numbers are provisional. Working length target: 40–60 pages incl. appendices.

---

## Front matter

- **Abstract** (≤ 250 words): four rings, eleven municipalities, 1.91 M individuals / 888 K households, sources certified in a registry, three publication regimes, viewer at animarium.pages.dev, reproducibility on three municipalities. `STATUS: todo`
- **Version binding table** — the report is meaningless without it:

| artefact | identifier | how to verify |
|---|---|---|
| this report | v1.0, arXiv:XXXX | — |
| GSP pipeline | commit `…`, tag `report-v1.0` | `git rev-parse` |
| Animarium viewer | commit `…`, tag `…` | idem |
| public bundle | SHA-256 per municipality (Parquet, manifest) | `sha256sum` |
| source fingerprints | `fonti/impronte/` at the same commit | `python -m gsp.fonti --verifica` |
| companion papers | arXiv:2603.27312 (GibbsPCD), arXiv:2607.00910 (SIVE) | — |

- **How to cite** the report, the dataset, and a *view* (URL-state, §V.2).
- **Licences**: code (choose: MIT / Apache-2.0), data bundle (CC-BY-4.0, inherited from all sources), attribution file `fonti/ATTRIBUZIONI.md`. `SOURCE: piano_trattamento_v2 §2, fonti_e_pacchetto_v8 §10–11`
- **Scope statement**: what this report is (release document + reproducibility record) and is not (a methods paper on MaxEnt; a validation paper on LLM populations).

---

## Part I — Architecture: the four rings

### I.0 One figure
Pipeline from `fetch_comune.py` to `assign_nucleo.py`, rings coloured, assumptions numbered where they enter, publication regimes as the last box. `SOURCE: GSP_popolazioni_full_riferimento_v22 §5` `STATUS: todo (figure)`

### I.1 Design principles (short, before the rings)
- Every attribute has a declared *place* (ring); moving it is a measurement (TVD), not a judgement. `SOURCE: fonti_e_pacchetto_v8 §12`
- Every metric that scales with cell count is normalised against its null hypothesis. `SOURCE: same; riferimento §11.1`
- Two code paths that must produce identical output are a permanent regression test. `SOURCE: memory / riferimento §4`
- Retractions are annotated, never overwritten (→ Part III.6).

### I.2 Ring 1 — the joint model (MaxEnt, exact and GibbsPCD)
- Ten constrained attributes; constraint sets K6C / K9C (K7C Parma, K10C Brescia as historical case); 16 blocks; absent vs zero cells; 26 impossible pairs at α = 0.
- Exact solution where |X| allows; PCD elsewhere; MRE ≈ 4·10⁻⁴ independent of |X| over one order of magnitude.
- **Only a summary**: the method is in arXiv:2603.27312; here we document the *configuration* per municipality and the numbers reproduced.
`SOURCE: riferimento §2.1, §5, §14; maxent_pcd_paper_4_arxiv; nota_combinazioni_impossibili_v2` `STATUS: rerun (3), reported (8)`
`TABLE: I.2a per municipality — |X|, level (K6C/K9C), n_zone, solver, MRE(α>0), entropy — from fit_K9C.json`

### I.3 Ring 2 — donated attributes (AVQ hot-deck) and citizenship
- Regional pools (LOM 8,111 / EMR 4,629), years stacked, `ISTRMi = 99` dropped, conditioning cell `sesso × macroetà × istruzione4` with hierarchical collapse.
- Whole-vector donation preserves inter-target correlations by construction; assumption (6).
- Effective sample size: Kish `n_eff` **per variable universe**, not on the whole population (why the latter is meaningless). Castenaso as contrast case.
- Country of citizenship: municipal census × local geographic source; tiers 0–D; provenance not tracked (declared limit).
- Codebook resolutions: `FIDUCIA` (interpersonal, inverted polarity), `AMBIENTE`, `FORZE_ARMATE` missing from the battery (declared).
`SOURCE: riferimento §2.2, §6, §13; design_animarium_v13 §13.3–13.6` `STATUS: rerun n_eff (3), reported (8)`
`TABLE: I.3a n_eff by variable universe, 11 municipalities; I.3b coverage of the country tier per municipality`

### I.4 Ring 3 — sub-municipal placement
- Section assignment under assumption (8); exact (largest-remainder) allocation vs multinomial (MAE 0.74–1.58 vs ≈ 9.6); single-year age under (9); address uniform within section under (10), from ANNCSU.
- Where compositional signal lives: 80–98 % lost below the quartiere; partition alignment matters more than granularity.
`SOURCE: riferimento §3, §5, §7; nota_segnale_compositivo_v3; nota_background_sezione_v1` `STATUS: reported; MAE rerun (3)`

### I.5 Ring 4 — households (nuclei)
- Why household membership cannot live in the joint model; role derived downstream conditioned on `zona × età × cittadinanza × sesso`.
- Two-part design: household size constrained at section level (PF3–PF8), internal composition from a repertoire (`repertorio_nuclei_v1.json`); `gsp.nucleo` API.
- Validation on Parma municipal microdata; two pre-registered predictions, both falsified (→ III.6).
- The 18–25 % "coniugati incoerenti" as a structural property, not a bug; married children living with parents.
`SOURCE: nota_nucleo_familiare_v3; nota_repertorio_avq_v3 (to be added to project); memory` `STATUS: rerun (3), reported (8)`
`TABLE: I.5a per municipality — nuclei, mean size, share by size vs PF3–PF8, coniugati incoerenti split`

### I.6 Derived layers (no new information, declared as such)
- `gsp.lavoro` (sector × position from cens2011), detailed education title (CLAIST + cens2011 tree), names and surnames from registered onomastic repertoires; biography rendering.
- Explicit warning: apparent diversity grows while real diversity does not (same AVQ signature ⇒ same agent).
`SOURCE: piano_trattamento_v2 §3.1; fonti_e_pacchetto_v8 §6, §9; nota_biografia_v2; design_animarium_v13 §14` `STATUS: reported`

### I.7 Publication regimes and the disclosure argument
- Three products, three regimes: `pubblico` (no name, no street/civic, coordinate randomised within section), `persona` (prompt material, samples), `narrativo` (full, generated on demand, dozens).
- One function is the single point of enforcement: `gsp.individui.esporta_pubblico()` / `campione()`; deterministic seed from municipality code.
- Argument in three levels: simulation from aggregates ≠ anonymisation; the AVQ vector is the only real thing in a record and is protected at source; the address carries no information.
`SOURCE: piano_trattamento_v2 §1, §3–4; fonti_e_pacchetto_v8 §10; design_animarium_v13 §15` `STATUS: rerun (regime applied to the release bundle)`

---

## Part II — Sources and their certification

### II.1 The registry as a method
`fonti/registro.yaml`: universe, licence, access date, fingerprint, `usabile_per` / `non_usabile_per`; three storage levels (git / local / remote); `file` vs `multi_istanza`; `parametri_da` and `derivato_da`; the immutable raw and the versioned normaliser. Outcomes of `--verifica` and why a state that always fails is a state nobody looks at.
`SOURCE: fonti_e_pacchetto_v8 §1–5, §11–12` `STATUS: reported; commands rerun on public clone`

### II.2 Source families and their legal condition
ISTAT SDMX tables (rate limit and its consequences), Basi Territoriali, ANNCSU as EU high-value dataset (Reg. 2023/138, Garante opinion 12/12/2024), AVQ public-use microdata (protection built into the data), six municipal open-data portals, cens2011 education and labour, CLAIST, onomastic repertoires (CC0 / CC-BY-SA), Parma municipal microdata (**used for validation only, not redistributed**).
`SOURCE: piano_trattamento_v2 §2; fonti_e_pacchetto_v8 §6–9` `STATUS: reported`
`TABLE: II.2a registry dump — id, family, licence, storage level, ring(s) fed, columns produced (script: python -m gsp.fonti --elenco)`

### II.3 The seventeen normalisers and what they caught
One row each: form, characteristic diagnostic, at least one anomaly found by running the code (total codes not uniform in cens2011; Parma codebook refuted by the data; Modena CKAN hash with two timestamps; Ncomp anomalies = collective households).
`SOURCE: fonti_e_pacchetto_v8 §4; nota_nucleo_familiare_v3 §2` `STATUS: reported`

### II.4 Source → ring → column
The traceability table the viewer's Method page will read from. `STATUS: todo (script to generate from registry + schema)`

### II.5 What is deliberately not registered / not used
Consultation-only sources; K10C; San Vito dei Normanni without zonal articulation; EM1–EM6 deferred; PF3–PF8 present on disk and used only in ring 4.
`SOURCE: riferimento §8; memory` `STATUS: reported`

---

## Part III — Reproducibility and quality report

### III.1 Environment and determinism
WSL2 Ubuntu 24.04, conda `ml` Python 3.11, `pip install -e .`, package layout `src/gsp/`; every random seed derived from the municipality code; artefacts must not embed their generation date (hash stability). Full command list → Appendix C.
`SOURCE: riferimento §4; fonti_e_pacchetto_v8 §12; design_animarium_v13 §7.1` `STATUS: rerun`

### III.2 The byte-for-byte method
Baseline before, `diff -r` after: package migration, `gsp.common` consolidation, Animarium `sys.path` removal. Two code paths as regression test (Czech Republic / South Africa classification bug found this way).
`STATUS: reported, with dates`

### III.3 Ring-by-ring quality tables (eleven municipalities, three re-run)
Every table has a `status` column. Metrics: MRE by block with sampling floor and z-scores (`verifica_vincoli.py`), MAE per section, `n_eff` by universe, reference coverage by level, household size vs PF3–PF8, coniugati incoerenti decomposition.
`SOURCE: riferimento §11, §13, §14; design_animarium_v13 §3.4, §13; nota_nucleo_familiare_v3` `STATUS: rerun (3) / reported (8)`

### III.4 Assumptions and resolution limits, in one place
(4′), (6), (8), (9), (10), (11 — now lifted by ring 4, state precisely what remains); education at 4 age classes not 8; `media` overestimated in 9–14; cohort effect lost 65–74/75+; migratory background at zone resolution; quinquennial seam.
`SOURCE: riferimento §7` `STATUS: reported`

### III.5 Open points carried into v1.0
Citizenship in the AVQ conditioning cell (patch prepared, not applied — with the trust-by-citizenship numbers); `idx_don` written upstream; `FORZE_ARMATE`; EM1–EM6; Ring 4-bis; Parma quartiere aggregation test; Ravenna Gibbs intermediate case.
`SOURCE: riferimento §8; memory (agosto coda)` `STATUS: reported`

### III.6 Register of retractions and falsified predictions
Explicit list, dated: the −418 gap as configuration coincidence; `quartiere` = `zona`; whole-population `n_eff` broken but variable-universe `n_eff` immune; the two ring-4 predictions; the codebook-11 "coabitazione" reading contradicted by PF9; MRE aggregate hiding 1 % cell errors; raking MRE = 0 as tautology.
`SOURCE: design_animarium_v13 §0.1, §12–13; nota_nucleo_familiare_v3 §2.2, §2.4, §6.3, §7` `STATUS: reported`

---

## Part IV — The Animarium release

### IV.1 What the viewer is
Static page + DuckDB-WASM, no scaffold; GSP produces, Animarium consumes; dependency declared in `pyproject.toml`. Panels: marginals with three markers (bar / tick / diamond), map without geometries, individual card with "SYNTHETIC — DOES NOT EXIST", trust battery with the two bands (n vs n_eff), regional atlas.
`SOURCE: design_animarium_v13 §0, §4, §7` `STATUS: reported`

### IV.2 The public bundle
Parquet schema (three column blocks, rows by `zona, sezione`), manifest, references from `cs_K9C.json`, national means as registered derived source; sizes; what `--pubblico` removes and why nothing is lost; the URL as citation of a view.
`SOURCE: design_animarium_v13 §3, §5, §15; fonti_e_pacchetto_v8 §10` `STATUS: rerun`
`TABLE: IV.2a schema per column — block, type, ring, regime in which it appears`

### IV.3 Deployment and versioning
Cloudflare Pages, deploy from folder, why not GitHub Pages; the release tag ↔ bundle hash binding; how to rebuild the bundle in one command.
`SOURCE: design_animarium_v13 §8, §15; README` `STATUS: rerun`

---

## Part V — The narrative layer and its use

### V.1 From record to persona
Rendering rules for `persona` and `narrativo`; what a persona-prompt contains; deterministic derivations declared as such; sampling by signature vs by individual as an open design choice.
`SOURCE: nota_biografia_v2; design_animarium_v13 §4.4, §14; piano_trattamento_v2 §3` `STATUS: reported`

### V.2 LLM-driven simulation as evidence of use (not as validation)
- SIVE: controllability of a synthetic population (Montelago, 120 personas, three trust strata) — pointer to arXiv:2607.00910, one paragraph.
- Brescia conditions on GSP populations: story transmission Spearman +0.90 across DeepSeek / GPT-4o-mini / Haiku 4.5; demographic priors on categorical items only in DeepSeek. Reported as a property of the *models*, with the caveat that validation of LLM populations is outside this report.
- SimComm/Caffaro: application context only, one paragraph, no results.
`SOURCE: registro_esperimento_sive_gsp_v5; sive_paper_v6; simcomm_agentsociety_notes; report_simcomm` `STATUS: reported`
`TABLE: V.2a the cross-model result (Spearman, per model, per condition)`

### V.3 Intended and unintended uses
What the population supports (compositional comparison, pre-testing communication, teaching); what it does not (any geography of trust below the municipality; any claim about a real address). The interpretation-risk argument.
`SOURCE: design_animarium_v13 §15; piano_trattamento_v2` `STATUS: reported`

---

## Appendices

- **A. Column schema by ring** (all regimes; type; source; assumption). `SOURCE: riferimento §1–2`
- **B. Registry dump** (`python -m gsp.fonti --elenco`, formatted).
- **C. Command list** to rebuild everything from a public clone (fetch → fit → assign → enrich → nucleo → bundle → deploy), with expected runtimes on the reference machine.
- **D. Per-municipality fact sheets** (11 × half page): population, zones, level, solver, key metrics, status.
- **E. Changelog** GSP and Animarium relevant to v1.0.
- **F. Attribution file** (`fonti/ATTRIBUZIONI.md`, verbatim).

---

## Work plan (not part of the report)

1. Public GitHub: hygiene (secrets, absolute paths, non-redistributable data, English README, licence).
2. Close the release blocker: `to_parquet.py` → `gsp.individui.esporta_pubblico()`, seed from municipality code.
3. Rerun rings 1–4 on 034027, 037011, 037006 from the public commit; record bundle hashes.
4. Fill `rerun` tables; import `reported` numbers with date + commit.
5. Write Parts I–V; figures I.0 and IV.1.
6. Internal read-through against the retraction register (nothing silently overwritten).
7. arXiv (cs.CY primary, stat.AP / cs.SI cross-list, to be decided) together with the public regime going live.
