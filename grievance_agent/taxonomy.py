"""Grievance categories, urgency levels and routes.

Categories follow the grievance areas named in the UGC (Redressal of Grievances of
Students) Regulations, 2023, grouped for intake. Adjust the list to your institution.
"""
from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "admission": "Admission, documents and certificates",
    "fees_refund": "Fees, refunds and excess charges",
    "scholarship": "Scholarships and financial aid",
    "exams_results": "Examinations and results",
    "evaluation": "Evaluation and marks",
    "academic_quality": "Teaching and academic quality",
    "infrastructure": "Infrastructure, hostel and facilities",
    "discrimination": "Discrimination (caste, gender, disability, religion, region)",
    "harassment": "Harassment or victimisation, including sexual harassment",
    "ragging": "Ragging",
    "safety": "Personal safety, threats or violence",
    "wellbeing": "Student wellbeing (non-clinical)",
    "other": "Other",
}

# Categories that must always be handled by a person (by policy / statute), even when calm.
MANDATORY_HUMAN_CATEGORIES = {"discrimination", "harassment", "ragging", "safety"}

URGENCY_LEVELS = ("routine", "sensitive", "high")
URGENCY_RANK = {level: i for i, level in enumerate(URGENCY_LEVELS)}

# Routes, in priority order.
URGENT_ALERT = "URGENT_ALERT"                    # a person is alerted now (self-harm, violence)
HUMAN_REVIEW_AMBIGUOUS = "HUMAN_REVIEW_AMBIGUOUS"  # unclear or unverifiable: a person reads it first
SGRC_PRIORITY = "SGRC_PRIORITY"                  # sensitive or statutory category, priority queue
SGRC_STANDARD = "SGRC_STANDARD"                  # normal committee process

ROUTES = (URGENT_ALERT, HUMAN_REVIEW_AMBIGUOUS, SGRC_PRIORITY, SGRC_STANDARD)
ROUTE_PRIORITY = {r: i for i, r in enumerate(ROUTES)}
ESCALATION_ROUTES = {URGENT_ALERT, HUMAN_REVIEW_AMBIGUOUS}

ROUTE_LABELS = {
    URGENT_ALERT: "Urgent human alert",
    HUMAN_REVIEW_AMBIGUOUS: "Human review (unclear account)",
    SGRC_PRIORITY: "SGRC priority queue",
    SGRC_STANDARD: "SGRC standard queue",
}

ROUTE_STUDENT_MESSAGE = {
    URGENT_ALERT: "A member of staff has been alerted and will contact you as soon as possible.",
    HUMAN_REVIEW_AMBIGUOUS: "A member of the Grievance Cell will read your account and may contact you to understand it better.",
    SGRC_PRIORITY: "Your grievance has been placed in the committee's priority queue. A member of staff will contact you.",
    SGRC_STANDARD: "Your grievance has been sent to the Students' Grievance Redressal Committee for the standard process.",
}
