# VIDYA-X AI — Intelligent Study Planner & Spaced Repetition Evaluation (Step 12)

> **Document Version**: 1.0.0  
> **Last Updated**: October 2026  

---

## 1. Overview & Architecture

Step 12 introduces **Personalized Study Planning**, **Transparent Topic Prioritization**, **Spaced Repetition Flashcard Scheduling**, and **Empirical Exam Readiness Estimation** to VIDYA-X AI.

The planner answers the core student question:
> *"How should I spend my available study time today to maximize learning and be ready for my exam?"*

---

## 2. Topic Prioritization Algorithm & Formula

The prioritization engine evaluates every topic in a course using a 6-signal weighted scoring function:

$$\text{priority\_score} = 0.30 \cdot M_{\text{need}} + 0.20 \cdot E_{\text{recent}} + 0.15 \cdot C_{\text{misconception}} + 0.15 \cdot P_{\text{need}} + 0.10 \cdot R_{\text{due}} + 0.10 \cdot X_{\text{exam}}$$

### Signal Definitions:

1. **Mastery Need ($M_{\text{need}}$)** (Weight: 30%):
   - Derived from BKT topic mastery probability $P(L)$.
   - For mastered or developing topics: $M_{\text{need}} = 1.0 - P(L)$.
   - For weak topics ($P(L) < 0.50$): $M_{\text{need}} = \min(1.0, 1.5 \cdot (1.0 - P(L)))$.
   - Cold start (no history): Default $P(L) = 0.20 \implies M_{\text{need}} = 0.80$.

2. **Recent Error Signal ($E_{\text{recent}}$)** (Weight: 20%):
   - Calculated as the error rate ($\text{incorrect} / \text{total}$) across quiz attempts submitted in the past 7 days for the topic.

3. **Active Misconception Signal ($C_{\text{misconception}}$)** (Weight: 15%):
   - $1.0$ if an active `supported` or `under_review` misconception exists for the topic.
   - $0.75$ if a `suspected` misconception exists.
   - $0.50$ if the misconception is `improving`.
   - $0.0$ if no active misconception exists.

4. **Foundational Prerequisite Need ($P_{\text{need}}$)** (Weight: 15%):
   - Evaluates whether foundational prerequisite concepts for this topic have low mastery ($P(L) < 0.50$).
   - $P_{\text{need}} = \max(0.0, 1.0 - P(L)_{\text{prereq}})$.

5. **Flashcard Review Due Signal ($R_{\text{due}}$)** (Weight: 10%):
   - $R_{\text{due}} = \min(1.0, \text{due\_cards} / 5.0)$ where flashcards are due for active recall review today.

6. **Exam Proximity Signal ($X_{\text{exam}}$)** (Weight: 10%):
   - Evaluates remaining calendar days to `exam_date`.
   - $\le 7 \text{ days} \implies 1.0$, $\le 14 \text{ days} \implies 0.80$, $\le 30 \text{ days} \implies 0.50$, else $0.20$.

---

## 3. Spaced Repetition Policy (Flashcards Engine)

Flashcard scheduling relies on an active recall rating policy:

| Student Rating | Next Interval Calculation | Target Review Time |
| :---: | :--- | :--- |
| **Again** | Interval reset to $0.0$ days | $+10$ minutes |
| **Hard** | $\max(1.0, \text{prev\_interval} \times 1.2)$ | $+1.0$ days minimum |
| **Good** | Initial: $3.0$ days; Subsequent: $\max(3.0, \text{prev\_interval} \times 2.0)$ | $+3.0$ days minimum |
| **Easy** | Initial: $7.0$ days; Subsequent: $\max(7.0, \text{prev\_interval} \times 2.5)$ | $+7.0$ days minimum |

---

## 4. Exam Readiness Categories & Evaluation Rules

The readiness engine categorizes student readiness based strictly on empirical evidence without overstating precision:

| Category | Category Label | Evaluation Criteria |
| :---: | :--- | :--- |
| `insufficient_data` | **Insufficient Data** | Total attempts $< 3$ OR topic coverage $< 20\%$. |
| `needs_substantial_review` | **Needs Substantial Review** | Average topic mastery $< 0.45$ OR active supported misconceptions $\ge 3$. |
| `building_readiness` | **Building Readiness** | Average topic mastery between $0.45$ and $0.75$. |
| `reasonably_prepared` | **Reasonably Prepared** | Average topic mastery $\ge 0.75$ AND topic coverage $\ge 70\%$. |

---

## 5. Verification & Test Metrics

- **Unit Test Suite**: `backend/test_study_plan.py` (12/12 passing).
- **Full System Regressions**: 100% pass rate across Step 7, 8, 9, 10, 11, 12 test suites (77 total tests passing).
- **Time Budget Feasibility**: 100% of generated study plan days adhere strictly to the student's daily minutes budget.
- **Exam Date Boundary**: 0 tasks scheduled beyond `exam_date`.
- **Data Isolation**: 100% cross-student & cross-course boundary isolation enforced.
