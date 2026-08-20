# Interview Preparation — FinSight

20 questions an interviewer could ask, with what each tests, how to answer, and the
mistake to avoid. Answer in your own words — understanding beats memorising.

---

### 1. Why did you use synthetic data?
- **Tests:** honesty and data awareness.
- **Answer:** Real customer/transaction data is private and regulated, so I generated
  synthetic data with a fixed seed. Crucially, I *documented the relationships I
  injected* (`behavioral_spec.md`), so my analysis is an honest re-discovery of known
  signals, not a claim of magic insight.
- **Avoid:** sounding apologetic. Framed well, it shows maturity.

### 2. Doesn't synthetic data mean you just "found what you put in"?
- **Tests:** whether you understand the circularity risk.
- **Answer:** Yes — that's exactly why I separated the ground truth from the analysis.
  The generation labels never enter the analytics data or the database. So the value
  isn't "I discovered travel customers like travel"; it's that standard techniques
  (SQL, RFM) *recover* documented tendencies, and I can show where they don't.
- **Avoid:** pretending the patterns are real-world discoveries.

### 3. Why SQLite instead of PostgreSQL/MySQL?
- **Tests:** tool-choice judgement.
- **Answer:** The goal was SQL *analytics*, not database administration. SQLite is
  zero-install, reproducible, and the queries (window functions, CTEs) port directly
  to Postgres. For a single-analyst reproducible project it removes setup friction
  with no analytical downside.
- **Avoid:** "because it was easy" without the reproducibility/portability reasoning.

### 4. Why Power BI and not Tableau?
- **Tests:** honesty about tool familiarity.
- **Answer:** I'm learning Power BI and it integrates cleanly with a CSV/SQL workflow
  on Windows. The concepts (data model, measures, visuals) transfer to Tableau; the
  choice was about what I could go deep on, not a claim that one is superior.
- **Avoid:** bluffing Tableau experience you don't have.

### 5. How did you validate your data?
- **Tests:** data-quality thinking.
- **Answer:** A dedicated `data_quality.py` step inspects the raw data for missing
  values, duplicates, orphan foreign keys, invalid categories, negative amounts,
  extreme values and bad dates, and writes a report. I also kept a log of the defects
  I injected and checked detection against it as an optional validation.
- **Avoid:** "I checked for nulls." Be specific about the range of checks.

### 6. Why is a null `campaign_id` not a data-quality problem?
- **Tests:** whether you understand your schema's meaning.
- **Answer:** A null `campaign_id` legitimately means a non-campaign transaction, so
  flagging it as "missing" would be wrong. I explicitly excluded it — data quality is
  about *meaning*, not blindly counting nulls.
- **Avoid:** treating every null as an error.

### 7. How did you calculate campaign ROI?
- **Tests:** metric rigour.
- **Answer:** ROI = (margin revenue − discount cost) / discount cost, where margin
  revenue = margin_rate × campaign revenue. It measures the offer's unit economics.
  All divisions guard against a zero denominator.
- **Avoid:** vague "revenue minus cost". State the exact formula and the guard.

### 8. You found high-redemption campaigns with negative ROI — explain.
- **Tests:** business reasoning (this is your best story).
- **Answer:** Redemption measures popularity, not profit. If a campaign's discount is
  deeper than the margin it earns, it can be popular *and* lose money. My ROI
  definition surfaces exactly that tension — 11 of 30 campaigns were margin-negative.
- **Avoid:** conflating "popular" with "successful".

### 9. How did you segment customers, and why rule-based?
- **Tests:** segmentation understanding + judgement.
- **Answer:** RFM computed from transaction behaviour — Recency, Frequency, Monetary,
  each scored 1–4 by quartile, then documented rules map to High Value / Regular /
  Low Engagement / At Risk. Rule-based because a business user must understand *why* a
  customer is "At Risk"; a clustering black box is harder to act on and explain.
- **Avoid:** implying rules are "less advanced" — explainability is a deliberate choice.

### 10. Why not K-Means?
- **Tests:** not over-engineering.
- **Answer:** K-Means would work, but on data with documented rules it would largely
  re-find those rules, and its clusters need interpretation before a business can use
  them. I listed it as future work and chose the transparent method for v1.
- **Avoid:** adding ML just to sound advanced.

### 11. How does your anomaly detection work?
- **Tests:** statistics + pragmatism.
- **Answer:** Two simple methods: IQR on transaction amounts (in log space, because
  amounts are right-skewed) to flag implausibly large values, and month-over-month %
  change on campaign revenue/redemption to flag sudden drops. It flags for review,
  never deletes.
- **Avoid:** claiming it detects fraud.

### 12. Why IQR in log space?
- **Tests:** whether you understand your data's distribution.
- **Answer:** Transaction amounts are log-normal, so a plain IQR fence flags the whole
  natural upper tail. Taking IQR on log10(amount) makes the distribution roughly
  symmetric, so only genuinely extreme values are flagged — it cleanly isolated the
  25 extreme values I had injected.
- **Avoid:** applying IQR to skewed data without acknowledging the skew.

### 13. Why flag outliers instead of deleting them?
- **Tests:** judgement.
- **Answer:** A large transaction might be a data error or a genuine big purchase.
  That's a review decision, not something a cleaning script should silently discard.
  Deleting real data to make charts look neat is a real risk.
- **Avoid:** "I removed outliers" with no nuance.

### 14. How did you stop the LLM from hallucinating numbers?
- **Tests:** responsible AI use (a strong differentiator).
- **Answer:** Python/SQL computes every metric into a verified `metrics.json`. The LLM
  receives only that and a strict prompt: use only supplied numbers, never invent or
  recompute, say so if information is missing. The model narrates; it never analyses.
- **Avoid:** implying the LLM does the analysis.

### 15. What happens if the LLM still gives a wrong insight?
- **Tests:** critical thinking about AI limits.
- **Answer:** Because it only has verified numbers and is told not to compute, the
  blast radius is small — a wording issue, not a wrong figure. The summary is clearly
  labelled AI-generated, the numbers remain the source of truth, and a human reviews
  it. If the API is unavailable, a deterministic template runs instead.
- **Avoid:** claiming the LLM is fully reliable.

### 16. How is the project reproducible?
- **Tests:** engineering discipline.
- **Answer:** One `params.yaml` with a fixed seed drives generation; every step writes
  a file the next reads. `python src/run_pipeline.py` rebuilds everything identically.
  Regenerable artifacts are gitignored; source, docs and ground truth are committed.
- **Avoid:** hardcoded values scattered through scripts.

### 17. How would you scale this to millions of transactions?
- **Tests:** systems thinking.
- **Answer:** Move storage to a columnar warehouse (BigQuery/Postgres), push
  aggregations into SQL instead of Pandas, process in batches or with a framework like
  Spark if needed, and pre-aggregate the Power BI model. The analytics logic stays the
  same; the execution layer changes.
- **Avoid:** claiming the current SQLite/Pandas setup already scales.

### 18. How would you improve the recommendation engine?
- **Tests:** knowing your method's limits.
- **Answer:** Today it's rule-based on recent category, frequency and engagement — very
  explainable but not personalised. I'd add collaborative filtering or a simple model
  to capture cross-category patterns, and A/B test recommendations against redemption.
- **Avoid:** overselling it as an ML recommender.

### 19. How would you measure whether a campaign truly *worked*?
- **Tests:** analytical depth.
- **Answer:** Redemption/ROI are useful but don't prove causation. Ideally I'd measure
  *incremental* lift — compare a targeted group against a holdout control — so I know
  the campaign drove behaviour rather than capturing spend that would have happened.
- **Avoid:** treating raw redemption as proof of impact.

### 20. What are the project's limitations?
- **Tests:** self-awareness.
- **Answer:** Synthetic data isn't real behaviour; segmentation and the recommender are
  rule-based; anomaly detection flags but doesn't diagnose; the LLM only summarises;
  Power BI is a reporting layer, not the source of truth. These are intentional and
  documented.
- **Avoid:** claiming there are no limitations.

---

**General tips:** open with the *business question*, then the method, then the caveat.
Have the numbers ready (38.08M revenue, 1,481 active customers, 30 campaigns, 56.5%
redemption, 11/30 negative-ROI). Be the person who can say what their project *can't*
do — that's what separates a strong candidate.
