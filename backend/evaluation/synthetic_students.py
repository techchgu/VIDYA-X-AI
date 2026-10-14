"""
VIDYA-X AI — Synthetic Learner Profiles (Step 13)

Defines 8 reproducible synthetic student profiles (A through H) for evaluating
learner model behavior, adaptive question selection, misconception remediation, and study planning.
"""

SYNTHETIC_PROFILES = {
    "profile_a_new_learner": {
        "name": "Profile A: New Learner",
        "student_id": "synth_student_a",
        "course_id": "synthetic_physics",
        "description": "No quiz history, no mastery estimates, cold start.",
        "expected_behavior": "Provides diagnostic starter assessment without assuming weak/strong topics.",
    },
    "profile_b_weak_foundation": {
        "name": "Profile B: Weak Foundation",
        "student_id": "synth_student_b",
        "course_id": "synthetic_physics",
        "description": "Low mastery in prerequisite concept, developing in target topic.",
        "expected_behavior": "Prioritizes foundational prerequisite review before advanced practice.",
    },
    "profile_c_conceptual_error": {
        "name": "Profile C: Repeated Conceptual Error",
        "student_id": "synth_student_c",
        "course_id": "synthetic_physics",
        "description": "Supported misconception recorded across distinct attempts.",
        "expected_behavior": "Recommends targeted remediation session with source citations.",
    },
    "profile_d_improving_learner": {
        "name": "Profile D: Improving Learner",
        "student_id": "synth_student_d",
        "course_id": "synthetic_physics",
        "description": "Recent correct answers after previous mistakes.",
        "expected_behavior": "Reduces remedial repetition and advances target difficulty.",
    },
    "profile_e_mastered_learner": {
        "name": "Profile E: Mastered Learner",
        "student_id": "synth_student_e",
        "course_id": "synthetic_physics",
        "description": "High mastery (>0.85) across all course topics.",
        "expected_behavior": "Favors active recall review and transfer practice over basic drills.",
    },
    "profile_f_sparse_evidence": {
        "name": "Profile F: Sparse Evidence",
        "student_id": "synth_student_f",
        "course_id": "synthetic_physics",
        "description": "Only 1-2 attempts total.",
        "expected_behavior": "Acknowledges uncertainty and gathers more diagnostic evidence.",
    },
    "profile_g_near_exam": {
        "name": "Profile G: Exam Near",
        "student_id": "synth_student_g",
        "course_id": "synthetic_physics",
        "description": "Exam date in 4 days, tight daily time budget.",
        "expected_behavior": "Schedules focused high-yield review within time budget and exam date.",
    },
    "profile_h_course_isolation": {
        "name": "Profile H: Conflicting Course Data",
        "student_id": "synth_student_h",
        "course_id": "synthetic_physics",
        "description": "Student enrolled in multiple courses with similar names.",
        "expected_behavior": "Strictly isolates recommendations and citations to target course.",
    },
}
