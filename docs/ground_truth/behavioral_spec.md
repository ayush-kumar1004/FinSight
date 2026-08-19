# Behavioural Ground Truth

**Why this document exists.** All FinSight data is synthetic. Rather than pretend
that every pattern the analysis "finds" is a real discovery, I wrote down the
relationships I *deliberately* built into the data generator. The analysis
(SQL, RFM, campaign analytics) then becomes an honest re-discovery exercise: I
can check whether standard techniques recover the tendencies I injected — and
where they don't.

These hidden labels live only here. They are **never** written into the analytics
CSVs or the SQLite database:
- `generation_labels_customers.csv` — each customer's `generation_persona` (engagement) and `preferred_category`
- `generation_labels_campaigns.csv` — each campaign's `latent_quality`

Everything is reproducible from `config/params.yaml` with a single fixed
`seed: 42`.

---

## B1 — Income band influences transaction amount

**What I injected.** Transaction amounts are drawn from a log-normal whose mean
rises with the customer's income band (`income_amount` in params.yaml).

**Why.** Higher-income customers plausibly spend more per transaction. It gives
segmentation and revenue analysis something real to reflect.

**What we expect to observe.** Average transaction value increases monotonically
from Low to High income. Observed in the generated data:

| income_band | avg txn amount (₹) |
|---|---|
| Low | ~710 |
| Lower-Mid | ~1,060 |
| Mid | ~1,570 |
| Upper-Mid | ~2,300 |
| High | ~3,750 |

It is a **tendency, not a rule** — the spread (sigma = 0.55) means individual
high-income customers can still have small transactions.

---

## B2 — Category preference influences activity & campaign engagement

**What I injected.** Each customer has a hidden `preferred_category`. When
sampling the category of each transaction, the preferred category gets an extra
probability weight (`category_preference_boost: 3.0`).

**Why.** Real customers lean toward certain spending categories; campaigns in a
customer's favoured category should see more relevant engagement.

**What we expect to observe.** Category revenue mix differs across the customer
base, and customers transact in their preferred category more often than a
uniform 1/9 split would predict. The preference label itself is hidden, so the
analysis can only see the *behaviour* it produces.

---

## B3 — Campaign latent quality influences redemption

**What I injected.** Every campaign has a hidden `latent_quality` of Strong,
Average or Weak, with base redemption propensities of ~12% / 6% / 2.5%
(`campaign_quality` in params.yaml). Quality feeds both the funnel redemption
step and the share of matching transactions attributed to the campaign.

**Why.** Some campaigns are simply better than others. This is the core business
signal the campaign analytics and anomaly detection are meant to surface.

**What we expect to observe.** Redemption rate (redeemed ÷ engaged) is clearly
ordered by quality. Observed:

| latent_quality | mean redemption rate |
|---|---|
| Weak | ~0.20 |
| Average | ~0.49 |
| Strong | ~0.87 |

The weakest campaigns are the ones the "underperforming campaigns" query and the
month-over-month anomaly check should flag. (Rates are conditional on engagement,
so they run higher than a redeemed-per-impression rate would.)

---

## B4 — Customer engagement level influences the campaign funnel

**What I injected.** Each customer has a hidden `generation_persona` of Engaged,
Normal or Dormant with different click / engage / redeem multipliers
(`engagement_persona` in params.yaml). The interaction funnel
(impression → click → engaged → redeemed) is generated from these.

**Why.** Engagement is not uniform — a minority of customers drive most of the
interaction. This is what RFM segmentation and the "Low Engagement / At Risk"
groups should partly reflect.

**What we expect to observe.** Click and redemption volumes are concentrated in
the Engaged persona; a Dormant tail interacts rarely. RFM must recover the
*behavioural* consequence without ever seeing the persona label.

---

## B5 — Seasonality in selected categories

**What I injected.** Multiplicative monthly demand weights (`seasonality` in
params.yaml): Travel peaks in vacation months (May–Jun, Dec–Jan); Shopping and
Electronics peak around a festival month (October).

**Why.** Time trends make the monthly analysis and the month-over-month anomaly
check meaningful instead of flat noise.

**What we expect to observe.** Monthly transaction counts for Travel show clear
humps in May/Jun and Dec/Jan; Shopping/Electronics rise in October. Example
(Travel monthly transaction counts): May ~210, Jun ~196 vs a ~130 baseline.

---

## Honest caveats

- These relationships are **soft tendencies**, deliberately noisy. The data is not
  perfectly predictable, which is the point.
- A hidden `generation_persona` exists only to *drive* generation. The analytics
  segmentation is computed independently from transaction behaviour (RFM) — it is
  not this label. Comparing the two is an optional validation, not the method.
- Because the data is synthetic, no result here should be read as a claim about
  real customer behaviour.
