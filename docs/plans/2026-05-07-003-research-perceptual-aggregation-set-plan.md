---
title: "research: Build the perceptual aggregation evidence set"
type: research
status: active
date: 2026-05-07
origin: docs/specs/social-navigation-metrics.md
related:
  - docs/plans/2026-05-07-002-feat-social-navigation-feature-computation-plan.md
---

# research: Build the perceptual aggregation evidence set

## Summary

Build a versioned research dataset and modeling workflow that maps the 12
objective social-navigation submetrics in
`docs/specs/social-navigation-metrics.md` to four user-facing perceptual axes:
Perceived Dexterity, Perceived Safety, Perceived Social Awareness, and
Impression.

This is partly manual scientific work and partly automatable research
infrastructure. The manual work is deciding whether evidence is valid,
interpreting heterogeneous HRI studies, and defending the final dependency
graph. The automation should handle repeatable literature discovery, paper
metadata extraction, scale mapping, provenance checks, feature normalization,
model fitting, and artifact generation.

The output should be a "perceptual aggregation set": a versioned evidence
matrix plus a trained or prior-weight aggregation artifact that the metric
implementation can load when computing dashboard scores.

## Problem Frame

The current metric spec defines objective features and an equal-weight macro
baseline. That is a good v0 implementation fallback, but it is not strong
enough as a research claim. The stronger claim is that the four dashboard axes
are perceptual constructs grounded in human ratings, not just convenient
averages of three nearby formulas.

The hard part is that public HRI literature usually gives one of three things:

- validated survey scales, such as Godspeed, RoSAS, NARS, GAToRS, or Almere;
- study-level findings about robot behavior and perception;
- raw or reusable datasets, which may not contain our exact 12 objective
  features.

So the plan should not assume one perfect dataset exists. It should create a
repeatable pipeline for collecting many partial sources, representing their
evidence strength honestly, and training only when the rows are actually
compatible.

## Scope

In scope:

- A source registry for papers, datasets, scales, and extracted study metadata.
- A dependency matrix from submetrics to the four axes.
- Evidence grading for every feature-axis relationship.
- A normalized target-axis mapping from public HRI survey constructs.
- A data model for rows that contain objective features, subjective labels, or
  literature-derived priors.
- Baseline, expert-prior, and trained aggregation artifacts.
- Validation protocol using the team's withheld associate/friend sample.

Out of scope:

- Running a new human-subject study as part of this plan.
- Changing the 12 objective feature formulas in
  `docs/specs/social-navigation-metrics.md`.
- Treating weak literature priors as equivalent to direct behavioral datasets.
- Hiding uncertainty from the dashboard or paper.

## Research Answer: Manual vs Automated

This should not be a fully manual spreadsheet job, but it also should not be an
unsupervised scraping exercise. The scientific asset is the reviewed evidence
set.

Manual work:

- Decide which HRI scales correspond to each of the four axes.
- Judge whether a study measures general robot perception, embodied HRI,
  navigation behavior, proxemics, social awareness, or only appearance.
- Code the strength of every claimed feature-axis link.
- Resolve construct disagreements, such as whether "competence" maps more to
  dexterity, impression, or both.
- Approve each versioned aggregation artifact before it can be used as more
  than a draft prior.

Automatable work:

- Search and deduplicate candidate literature and datasets.
- Extract citation metadata, DOI, year, sample size, robot/task type, available
  variables, scale items, and reported constructs.
- Maintain a machine-readable source registry.
- Convert extracted tables into a canonical row format.
- Compute our 12 features from any available trajectory/behavior traces.
- Fit constrained aggregation models and compare them to equal-weight and
  expert-prior baselines.
- Emit a signed/versioned aggregation artifact with provenance and uncertainty.

## Evidence Model

Each evidence item should answer: "How strongly does this source support a
relationship between objective submetric X and perceptual axis Y?"

Recommended evidence levels:

- `direct_dataset`: source includes behavior traces or condition-level
  variables that can be mapped to one or more objective submetrics, plus human
  ratings that map to an axis.
- `condition_level`: source manipulates behavior conditions, such as distance,
  speed, approach style, or smoothness, and reports subjective ratings, but raw
  traces are unavailable.
- `scale_construct`: source validates perceptual constructs but has no robot
  behavior features.
- `literature_prior`: source argues for a relationship, but without reusable
  quantitative labels.
- `expert_prior`: team-authored hypothesis pending external evidence.

Every feature-axis link should also carry:

- `expected_sign`: positive, negative, or non-monotonic.
- `applicable_context`: empty room, static bystanders, moving bystanders,
  morphology-specific, task-specific, or general HRI.
- `confidence`: high, medium, low.
- `uncertainty_reason`: what would change the weight estimate.
- `provenance`: source ids, notes, extraction reviewer, extraction date.

## Axis Construct Mapping

Use public HRI scales as construct anchors, not as direct one-to-one labels.

Initial mapping hypothesis:

- Perceived Dexterity: task success, completion time, path efficiency, and
  stability should map most closely to perceived competence, intelligence,
  capability, reliability, and usefulness.
- Perceived Safety: distance, proxemic intrusion, speed near humans, and
  controlledness should map to perceived safety, discomfort, anxiety, unease,
  and trust.
- Perceived Social Awareness: gesture response, acknowledgement clarity,
  human-aware approach, and proxemic respect should map to warmth, sociability,
  responsiveness, interaction comfort, and appropriateness.
- Impression: motion smoothness, stability, morphology-task fit, and overall
  behavioral polish should map to likeability, animacy, warmth, discomfort
  reduction, and general attitude.

Important: submetrics may influence multiple axes. For example, proxemic
intrusion is safety-first but also affects social awareness; stability affects
safety and impression; task success affects dexterity and competence-like
impression. The dependency matrix should make these cross-axis links visible.

## Candidate Source Families

Start with these source families because they are widely used in HRI perception
work:

- Godspeed Questionnaire Series: anthropomorphism, animacy, likeability,
  perceived intelligence, and perceived safety.
- RoSAS and RoSAS-SF: warmth, competence, and discomfort.
- NARS and related attitude scales: negative attitudes toward robots and
  interaction anxiety.
- Almere Model: acceptance of assistive social agents, including usefulness,
  ease of use, enjoyment, sociability, trust, anxiety, and intention to use.
- GAToRS and adjacent general-attitude scales: survey-level general robot
  perception.
- Proxemics and social-navigation studies: personal space, approach behavior,
  speed, collision avoidance, and human comfort.
- Movement smoothness/SPARC literature: objective smoothness grounding, used as
  a prior for impression rather than a direct HRI perception claim unless paired
  with human ratings.

Seed references:

- HRI Scale Database, Godspeed Questionnaire Series:
  https://hriscaledatabase.psychology.gmu.edu/
- HRI Scale Database, RoSAS:
  https://hriscaledatabase.psychology.gmu.edu/social%20attributes/2024/06/12/RoSAS.html
- RoSAS development paper:
  https://doi.org/10.1145/2909824.3020208
- Almere Model paper:
  https://link.springer.com/article/10.1007/s12369-010-0068-5
- General Attitudes Towards Robots Scale:
  https://link.springer.com/article/10.1007/s12369-022-00880-3
- SPARC smoothness analysis:
  https://jneuroengrehab.biomedcentral.com/articles/10.1186/s12984-015-0090-9
- SPARC gait application:
  https://jneuroengrehab.biomedcentral.com/articles/10.1186/s12984-018-0398-3

## Proposed Artifacts

Create these files when implementation begins:

- `docs/research/perceptual-aggregation/README.md`
- `docs/research/perceptual-aggregation/source-registry.yaml`
- `docs/research/perceptual-aggregation/evidence-matrix.csv`
- `docs/research/perceptual-aggregation/axis-construct-map.yaml`
- `docs/research/perceptual-aggregation/extraction-guidelines.md`
- `docs/research/perceptual-aggregation/model-card-v0.1.md`
- `data/perceptual_aggregation/README.md`
- `data/perceptual_aggregation/processed/aggregation_set_v0_1.csv`
- `data/perceptual_aggregation/artifacts/equal_weights_v0_1.json`
- `data/perceptual_aggregation/artifacts/expert_prior_v0_1.json`
- `data/perceptual_aggregation/artifacts/trained_weights_v0_1.json`

The `data/` paths are proposed. If the repo wants generated datasets outside
git, keep the schema and model cards in git and store larger raw data by
documented external reference.

## Implementation Units

### U1. Define the Evidence Schema

Goal: create the canonical shape for sources, extracted variables, feature-axis
links, and aggregation artifacts.

Files:

- Create: `docs/research/perceptual-aggregation/README.md`
- Create: `docs/research/perceptual-aggregation/extraction-guidelines.md`
- Create: `docs/research/perceptual-aggregation/axis-construct-map.yaml`
- Create: `docs/research/perceptual-aggregation/source-registry.yaml`

Decisions:

- Keep source metadata separate from interpreted evidence. A paper can be in
  the registry before it supports any weight.
- Store construct mappings explicitly so later reviewers can challenge them
  without reverse-engineering code.
- Require reviewer initials/date for manual extraction rows.

Validation:

- Schema examples include one scale-only source, one condition-level source,
  and one direct-dataset source.
- Axis ids match `docs/specs/social-navigation-metrics.md`.
- Feature ids match the 12 submetrics from the feature-computation plan.

### U2. Build the Literature and Dataset Discovery Workflow

Goal: make literature collection repeatable enough that the evidence set can
evolve without becoming folklore.

Files:

- Create: `docs/research/perceptual-aggregation/search-protocol.md`
- Create: `docs/research/perceptual-aggregation/source-registry.yaml`
- Optional script later: `scripts/research/find_perceptual_sources.py`

Approach:

- Define search queries for each source family and each feature group.
- Track inclusion/exclusion reasons.
- Prefer primary papers, dataset repositories, OSF/project pages, ACM/IEEE
  metadata, Springer open access pages, and official scale databases.
- Mark papers that only validate a scale as construct anchors, not training
  data.

Validation:

- Every included source has a DOI or stable URL when available.
- Every excluded source has a short reason.
- Registry can be sorted by source family, evidence level, and axis relevance.

### U3. Create the Manual Extraction Protocol

Goal: make human review consistent across colleagues.

Files:

- Update: `docs/research/perceptual-aggregation/extraction-guidelines.md`
- Create: `docs/research/perceptual-aggregation/evidence-matrix.csv`

Approach:

- Define extraction fields for sample size, participant population, robot,
  embodiment, task, behavioral manipulation, objective variables, survey scale,
  subjective constructs, reported effect sizes, and availability of raw data.
- Require a source to state whether it supports direct fitting,
  condition-level priors, construct mapping only, or no usable evidence.
- Include a double-review lane for high-impact weights.

Validation:

- Two reviewers independently extract the same pilot set of 5 sources.
- Disagreements are logged as evidence notes rather than silently averaged away.
- The first evidence matrix version can regenerate the same dependency graph.

### U4. Assemble the First Aggregation Set

Goal: produce `aggregation_set_v0_1` with enough rows to compare baselines.

Files:

- Create: `data/perceptual_aggregation/README.md`
- Create: `data/perceptual_aggregation/processed/aggregation_set_v0_1.csv`
- Create: `docs/research/perceptual-aggregation/model-card-v0.1.md`

Approach:

- Include only rows with approved extraction status.
- Separate direct numeric rows from prior rows.
- Normalize target constructs into the four axis ids with documented mapping.
- Store feature availability masks, because many studies will only support a
  subset of the 12 features.

Validation:

- Dataset version records source count by evidence level.
- No row can enter the training split without provenance and construct mapping.
- Missing features are explicit, not filled with neutral values by default.

### U5. Fit Baseline, Prior, and Trained Aggregators

Goal: create comparable artifacts for dashboard scoring and research analysis.

Files:

- Create: `data/perceptual_aggregation/artifacts/equal_weights_v0_1.json`
- Create: `data/perceptual_aggregation/artifacts/expert_prior_v0_1.json`
- Create: `data/perceptual_aggregation/artifacts/trained_weights_v0_1.json`
- Optional script later: `scripts/research/train_perceptual_aggregator.py`

Approach:

- Baseline: equal weights within the three spec-defined submetrics per axis.
- Expert prior: manually reviewed dependency matrix with cross-axis links.
- Trained model: constrained linear or regularized model with non-negative
  weights where monotonicity is known, sparsity for weak links, and uncertainty
  estimates.
- Compare all models against held-out public rows where available.

Validation:

- Model artifacts declare feature order, axis order, training data version,
  maturity label, fallback behavior, and unsupported links.
- Trained weights cannot be loaded if feature ids differ from the runtime metric
  output.
- Expert-prior and trained artifacts both beat or explain failures against the
  equal-weight baseline before being promoted.

### U6. Validate Against the Withheld Local Sample

Goal: reserve associates/friends ratings for validation, not fitting.

Files:

- Create: `docs/research/perceptual-aggregation/local-validation-protocol.md`
- Update: `docs/research/perceptual-aggregation/model-card-v0.1.md`

Approach:

- Define short post-run survey items that map to the four axes.
- Use benchmark videos or interactive runs with recorded objective features.
- Compare equal weights, expert prior, and trained weights on rank correlation,
  calibration error, and qualitative failure cases.
- Preserve validation results as model-card updates.

Validation:

- Local validation rows are marked `validation_only`.
- The model card reports sample size, scenario coverage, known bias, and whether
  the model is promoted from `draft_prior` to `validated`.
- Dashboard metadata can show aggregation model version and validation status.

## Model Maturity Labels

Use these labels in model artifacts and dashboard report metadata:

- `equal_weight_baseline`: transparent implementation fallback.
- `draft_prior`: dependency matrix exists, but no empirical fit.
- `dataset_fit`: trained or estimated from public evidence rows.
- `locally_validated`: checked against withheld local ratings.
- `benchmark_validated`: validated against a larger benchmark-specific human
  study.

The first scientifically honest target is `dataset_fit` plus a separate local
validation report. `benchmark_validated` is later work.

## Sequencing

1. Define schema, construct map, and extraction guidelines.
2. Run a pilot source extraction with 10 to 15 sources across Godspeed, RoSAS,
   Almere, NARS/GAToRS, proxemics, and SPARC/smoothness.
3. Review the dependency matrix manually with the team.
4. Build the first aggregation set and baseline artifacts.
5. Fit constrained trained weights only if direct or condition-level evidence is
   sufficient.
6. Validate against the withheld local sample.
7. Promote the artifact maturity label or keep equal/expert prior as the
   dashboard fallback.

## Risks

- Public data may not contain enough direct rows to train 12-feature weights.
  Mitigation: allow condition-level priors and explicitly report maturity.
- General robot attitude surveys may over-emphasize appearance and understate
  navigation behavior. Mitigation: tag embodiment/task context and avoid using
  appearance-only rows as direct training data.
- Cross-axis dependencies can make the model look arbitrary. Mitigation:
  publish the dependency matrix, signs, evidence levels, and uncertainty.
- Small local validation sample can overfit team preferences. Mitigation: use it
  for validation only and report sample limitations.

## Success Criteria

- A reviewer can trace every non-equal weight to source evidence or an explicit
  expert prior.
- The artifact says exactly what it is: baseline, draft prior, dataset fit, or
  validated model.
- The dashboard can present four scores with model version and uncertainty.
- The paper can defend the aggregation method without pretending the evidence is
  cleaner than it is.
