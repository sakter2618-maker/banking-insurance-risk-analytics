# Interview Guide — Banking & Insurance Risk Analytics

এই ফাইলটা শুধু আপনার প্রস্তুতির জন্য। প্রতিটা প্রশ্নের নিচে **বাংলায় ব্যাখ্যা** আর **ইংরেজিতে যা বলবেন** দেওয়া আছে।

---

## ১. ৩০ সেকেন্ডের Project Pitch

**English (মুখস্থ করে নিন):**
> "I built an end-to-end risk analytics project for banking and insurance. I used 50,000 real bank transactions and 41,000 real bank customers, and because those files had no loan outcomes or insurance claims, I generated a synthetic loan book and claims table linked to the real customers, using documented industry risk rules. I answered four business questions with Python, SQL and Excel: which customers default most, which transactions look abnormal, which segment is riskiest, and which claim patterns suggest fraud. I built a probability-of-default model, a K-Means segmentation, an Isolation Forest for anomalies, and a composite risk score — and presented everything in an interactive Streamlit app and a written risk report."

---

## ২. Data নিয়ে প্রশ্ন

**Q: Why did you use synthetic data? Isn't that a weakness?**

বাংলা: আসল UCI file-এ `default = yes` মাত্র ৩টা, আর কোনো insurance claim নেই। তাই ঐ দুটো analysis করা সম্ভব ছিল না। আমি নিয়ম লিখে (documented) data বানিয়েছি এবং সেটা সব জায়গায় স্পষ্ট লিখে দিয়েছি — এটাই সততা।

English:
> "The real customer file had only 3 defaults out of 41,000 and no claims, so I couldn't analyse those honestly. Instead of dropping them, I simulated them with transparent rules based on known risk drivers — credit score, DTI, employment — and labelled them clearly as synthetic everywhere. The point is to show the method; in a real job I'd plug in the bank's actual loan data and the same pipeline would run."

**Q: What data quality issues did you find?**

> "Three: the transaction dates came in two different formats, which I unified; 87% of transactions had no time, so I didn't do time-of-day analysis; and in the augmented transaction file, customer age and occupation changed within the same account, so I didn't trust them for account-level conclusions. In the customer file, 21% had an *unknown* credit status, which I reported as a data-quality risk itself. I also removed 12 duplicate customer rows."

---

## ৩. Analysis নিয়ে প্রশ্ন

**Q: How did you build the default model? Why logistic regression?**

বাংলা: Logistic regression ব্যাংকে standard, কারণ প্রতিটা feature-এর প্রভাব ব্যাখ্যা করা যায় (regulator-রা explainability চায়)।

> "I trained a logistic regression on 75% of loans and tested on 25%. The AUC was 0.71 — meaning it ranks a random defaulter above a random non-defaulter 71% of the time. I chose logistic regression because banks need explainable models for regulators; I can show exactly how much credit score or DTI moves the risk."

**AUC মানে কী?** ০.৫ = coin toss (কোনো কাজের না), ১.০ = perfect। ০.৭–০.৮ credit risk-এ ভালো ধরা হয়।

**Q: How did you segment customers?**

> "K-Means with four clusters on standardised credit score, DTI, income, loan amount and late payments. I named each cluster from its profile — Steady Prime, Stretched Mid-Market, Affluent Prime and Stressed Borrowers. Stressed Borrowers default at 61% versus 4% for Steady Prime."

**Standardise কেন?** Income হাজারে, DTI ১০–৪০-এ — scale না মিলালে income একাই cluster ঠিক করে ফেলত।

**Q: How did you detect abnormal transactions without a fraud label?**

> "Two layers. First, seven business rules — for example 3+ login attempts, an amount more than 3 standard deviations above that account's normal, or draining over 80% of the balance. Second, an Isolation Forest, an unsupervised model that isolates unusual points. A transaction is suspicious if it hits two rules or the model flags it — 2,071, or 4.1%. Rules are explainable, the model catches combinations rules miss."

**Q: How did you create the risk tiers?**

> "A 0–100 score: 60% the model's default probability, 25% delinquency history, 15% DTI. Then four tiers. I validated it by checking the actual default rate per tier: 3%, 10%, 19%, 61% — each tier is clearly riskier than the one below."

**Q: What is "lift"?**

বাংলা: Flag থাকলে fraud rate ÷ গড় fraud rate। Lift ৩.৪ মানে ঐ flag থাকলে fraud হওয়ার সম্ভাবনা গড়ের ৩.৪ গুণ।

---

## ৪. SQL নিয়ে প্রশ্ন

**Q: Show me a complex query.** → `sql/02_business_queries.sql` এর **Q7** দেখান।

বাংলা: প্রথমে CTE দিয়ে প্রতিটা account-এর গড় আর standard deviation বের করেছি, তারপর join করে z-score > 3 এমন transaction বের করেছি।

> "I used a CTE to compute each account's average and standard deviation, joined it back to transactions, and kept those more than 3 standard deviations above the account's own norm. That catches a $1,300 transaction from someone who normally spends $200, which a fixed threshold would miss."

অন্য ভালো উদাহরণ: **Q12** (CASE দিয়ে red-flag score), **Q14** (দুটো CTE, loan + claims cross-product risk)।

---

## ৫. Business নিয়ে প্রশ্ন

**Q: What would you recommend to the bank?**

> "Five things: verify income for unemployed and student applicants; contact Critical-tier borrowers after the first missed payment, because that's where risk jumps 8×; add one-time-password authentication after 3 failed logins; send claims with 3+ red flags to the investigation unit and fast-track clean claims; and fix the unknown credit status for a fifth of customers."

**Q: What would you do with more time?**

> "Use real loan data, try a gradient-boosting model and compare it against logistic regression, add time-of-day features if timestamps were complete, and set up the dashboard to refresh automatically from the database."

---

## ৬. মনে রাখার মতো সংখ্যা

| বিষয় | সংখ্যা |
|---|---|
| Transactions | 50,000 (495 accounts) |
| Customers | 41,176 |
| Loans / default rate | 15,000 / 12.3% |
| PD model AUC | 0.71 |
| Suspicious transactions | 2,071 (4.1%) |
| Critical tier | 972 borrowers, 61% default, $15.2M |
| Claims / fraud rate | 9,000 / 6.4% |
| Claims for review | 570 (3+ red flags) |

---

## ৭. Dashboard নিয়ে প্রশ্ন

**Q: Why Streamlit?**

বাংলা: Streamlit দিয়ে Python-এই পুরো interactive app বানানো যায়, আর free-তে live link পাওয়া যায়। Filter বদলালে সব chart আর সংখ্যা নতুন করে হিসাব হয়।

> "Streamlit let me build the whole interactive app in Python, reusing the same pandas logic as my analysis. Users can filter by loan grade, purpose, channel or policy type, and download watch-lists — for example Critical-tier borrowers or the fraud alert queue — as CSV for the operations team."
