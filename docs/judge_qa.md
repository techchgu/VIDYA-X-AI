# VIDYA-X AI — Hackathon Judge Questions & Answers (Q&A Preparation)

**Project:** VIDYA-X AI — Your Course-Aware, Adaptive & Multimodal AI Tutor  
**Track:** Multimodal AI Hackathon 2026 — Track D: Personalized Tutoring & Adaptive Learning  
**Target:** 38 Concise, Technically Defensible Answers (2–5 Sentences Each)

---

## Part 1: Product & Differentiation

### 1. What problem does VIDYA-X AI solve?
Generic AI chatbots give plausible answers, but they frequently contradict a professor's specific syllabus, use unassigned formulas, or hallucinate concepts. Furthermore, asking questions is only a fraction of learning—students also need adaptive retrieval practice, diagnosis of their errors, and structured study plans. VIDYA-X AI solves this by connecting multimodal course ingestion with source-cited tutoring, psychometric learner modeling, targeted misconception remediation, and spaced repetition.

### 2. Why is this more than a chatbot with file upload?
A chatbot wrapper simply appends uploaded text to an LLM context window and forgets the conversation when closed. VIDYA-X AI builds a structured course knowledge graph, tracks empirical topic mastery via Bayesian Knowledge Tracing across every quiz attempt, isolates systematic misconception patterns, and computes an active daily study schedule. It is an end-to-end cognitive mastery system, not an isolated chat box.

### 3. Who is the primary user?
Our primary users are university and secondary students taking rigorous, quantitative or structured academic courses (e.g., Physics, Engineering, Biology, Chemistry) who must master specific course syllabi under time constraints. It also serves self-paced online learners who lack individual teaching assistant access and need continuous diagnostic feedback on their problem-solving attempts.

### 4. What is the main differentiator?
Our main differentiator is the closed-loop connection between source-grounded tutoring and cognitive modeling: every quiz mistake updates a persistent Bayesian learner model, which immediately feeds into targeted misconception contrast cards and spaced repetition flashcard schedules. The tutor knows what the student has mastered, what they misunderstand, and what they need to review today.

### 5. What is the most valuable user journey?
A student uploads their lecture slides and textbook chapter, asks the AI Tutor for clarification on a confusing concept, and immediately takes an adaptive quiz that targets their exact knowledge frontier. When they make an error, the system diagnoses whether it was an arithmetic slip or a conceptual misconception, presents a step-by-step contrastive remediation, and adds an active-recall flashcard to their daily review schedule.

---

## Part 2: RAG, Retrieval & Grounding

### 6. How does the system answer using the student's own course material?
Uploaded materials are parsed page-by-page or slide-by-slide, chunked into semantically coherent units with intact location metadata, and embedded into a vector space. When a query is asked, we perform an isolated vector similarity search filtered by `course_id`, inject the top relevant excerpts into our grounded prompt template, and mandate that every claim cite the exact supporting passage.

### 7. How are PDF pages, slide numbers, and video timestamps preserved?
Our document extractors retain 1-indexed document coordinates throughout ingestion: PyMuPDF tracks page indices, `python-pptx` tracks slide shape indices, and FFmpeg paired with `faster-whisper` annotates speech chunks with millisecond-accurate `[HH:MM:SS]` intervals. These coordinates are stored in the database metadata columns and forwarded directly into the frontend citation badge components.

### 8. How do you prevent hallucinated citations?
The citation resolution pipeline validates every cited identifier against the actual retrieved chunk metadata before returning the response to the client. If an LLM attempts to fabricate a citation index or reference a non-existent document, the post-processing filter strips the phantom reference and verifies that every clickable citation links to an authentic stored excerpt.

### 9. What happens when the answer is absent from the material?
The system utilizes a calibrated similarity and lexical overlap gate: if the maximum retrieval similarity or term overlap between the query and the course material falls below our safety threshold, the system triggers safe abstention. Instead of guessing, the AI Tutor informs the student: *"I could not find sufficient information in your course materials to answer this question accurately."*

### 10. How do you evaluate retrieval and answer grounding?
We built an automated evaluation suite (`backend/evaluation/`) containing versioned JSONL benchmark cases that deterministically test Recall@K, Precision@K, Hit Rate, and Mean Reciprocal Rank (MRR). We also run automated abstention tests using out-of-domain queries to guarantee that the system rejects unsupported prompts.

### 11. Why use pgvector?
We chose PostgreSQL with `pgvector` because it allows unified transactional storage of relational entities (students, courses, quiz attempts, BKT states) alongside high-dimensional vector embeddings within a single ACID-compliant database. This eliminates the operational complexity, network latency, and consistency hazards of managing a separate standalone vector database alongside our relational data.

### 12. What are the limitations of retrieval-augmented generation?
Standard RAG relies on semantic proximity, which can miss cross-chapter synthesis where an answer requires integrating facts scattered across 10 different lectures. Additionally, if the course notes contain typos or conflicting definitions, RAG will faithfully reflect those errors unless an authoritative instructor knowledge graph is established.

---

## Part 3: Multimodal Understanding & Visuals

### 13. How does the system process PDFs and slide decks?
PDFs are parsed with PyMuPDF (`fitz`), which extracts text streams along with 1-based page indices and embedded raster images. PowerPoint presentations (`.pptx`) are traversed using `python-pptx`, capturing slide titles, bullet points, table contents, and instructor speaker notes, which often contain critical exam hints omitted from the main slides.

### 14. How does it handle video?
For lecture videos (`.mp4`), FFmpeg extracts the audio track into a temporary buffer, which is transcribed by `faster-whisper` to produce timestamped text segments. In Step 14, we also implemented keyframe extraction at 30-second intervals using FFmpeg, enabling the system to index slide changes and blackboard diagrams alongside the audio transcript.

### 15. How are diagrams, charts, and equations interpreted?
Extracted visual figures are routed to our vision pipeline: when configured with Gemini 1.5 Flash, the model generates structured JSON descriptions extracting visible text labels, coordinate axes, directional relationships, and LaTeX equations. These structured descriptions are embedded and stored as `visual_description` chunks in our knowledge base, enabling visual figures to be cited in tutor answers.

### 16. How do you handle unreadable or ambiguous visual content?
The vision analysis prompt explicitly instructs the model to populate an `uncertain_regions` field rather than guessing unreadable annotations. If an image has poor resolution or occluded text, the structured description records this uncertainty, and our local fallback generates a conservative generic descriptor based on the surrounding slide text.

### 17. How do you avoid claiming support for modalities that are not fully implemented?
We maintain strict honesty in our architecture documentation: video transcription and PDF/slide text extraction are fully implemented and verified with automated tests. Keyframe visual extraction and description indexing are implemented with both cloud vision and local deterministic fallbacks; for demo environments lacking a live Gemini API key, we clearly state that local heuristic descriptors are used.

---

## Part 4: Adaptive Learning & Cognitive Modeling

### 18. How does the system estimate a student's mastery?
We estimate mastery using Bayesian Knowledge Tracing (BKT), a widely validated psychometric model that calculates the latent probability $P(L_t)$ that a student knows a specific skill given their chronological sequence of correct and incorrect attempts. Each attempt updates the prior mastery using probability formulas incorporating slip and guess probabilities.

### 19. What is Bayesian Knowledge Tracing, and why use it?
BKT is a probabilistic hidden Markov model designed specifically for education. We use it instead of crude percentage scores because it accounts for lucky guesses ($P(G)=0.25$ on 4-option MCQs) and careless slips ($P(S)=0.10$ on known concepts), providing an mathematically principled, explainable metric that updates in real time without calling an expensive LLM.

### 20. How does the system choose the next question?
Our adaptive question selector (`services/adaptive_scoring_service.py`) evaluates candidate questions using a composite score based on: (1) mastery gap targeting the student's zone of proximal development, (2) difficulty matching, (3) prerequisite readiness, (4) recent error recency, and (5) novelty penalization to prevent repetitive questions.

### 21. How are prerequisites considered?
Our knowledge service tracks concept dependency relationships (e.g., *'Vector Components'* is a prerequisite for *'Inclined Plane Force Resolution'*). If a student has low mastery ($P(L) < 0.40$) on a prerequisite concept, the question selection engine dampens the weight of advanced downstream questions until the foundational concept is reinforced.

### 22. How do you detect possible misconceptions?
Misconception detection operates on two levels: first, fast deterministic heuristics inspect numerical answers for recognizable error signatures like sign errors (missing negative), scale errors ($\times 10$ or $\div 10$), and inverse relationships. Second, if an error is ambiguous, our diagnostic prompt analyzes the incorrect choice against course definitions, categorizing the issue as *Suspected* on the first occurrence and *Supported* after two repeat occurrences.

### 23. How do you avoid overreacting to one incorrect answer?
We implement a two-stage state machine: a single incorrect attempt flags a misconception only as *Suspected* and triggers a mild BKT slip update without disruptive interventions. A misconception is elevated to *Supported* only when the student exhibits at least two consistent error signals across related questions, preventing false alarms caused by careless typos.

### 24. How do flashcards and spaced repetition fit into the learning workflow?
When a student completes a quiz or remediation session, weak concepts and definitions are automatically distilled into active recall flashcards. Flashcards are reviewed in a 3D flip card interface and scheduled using a modified Leitner/SM-2 spaced repetition algorithm, ensuring difficult items appear daily while mastered concepts escalate to 3, 7, and 14-day intervals.

---

## Part 5: Evaluation & Quality Assurance

### 25. What metrics have actually been measured?
On our automated test suite, we have measured **68 passing tests out of 68 (100%)**, **0.0 Course Isolation Violations**, and a **1.0 (100%) Unsupported Question Abstention Rate**. On our initial deterministic 10-case evaluation run, Recall@3 was measured at 0.20 using lightweight local n-gram vectors, demonstrating the need for dense embedding models in production.

### 26. How large is the evaluation dataset?
Our benchmark repository (`backend/evaluation/datasets/`) currently includes versioned JSONL suites covering 10 retrieval queries, 5 RAG grounding cases, 8 synthetic student archetypes (Profiles A–H), and 6 study planner scheduling constraints. This provides a repeatable regression suite for developer iterations.

### 27. How do you test personalization without a large real-student dataset?
We use 8 deterministic synthetic learner profiles representing standard student personas (e.g., Novice, Intermediate, Exam-in-3-Days, Low Time Budget, Persistent Sign Error). By feeding standardized attempt sequences into our BKT engine, we verify that question selection and study planning respond correctly to known mastery vectors.

### 28. How do you distinguish software correctness from learning effectiveness?
Software correctness measures whether our code executes without crashing, updates database tables, and returns HTTP 200 responses. Educational effectiveness measures whether real students achieve higher test scores or retain information longer using our tool; as honest engineers, we explicitly state that measuring true learning gains requires longitudinal clinical studies with human students, which is planned for future work.

### 29. What are the most important current limitations?
Our main limitations are: (1) video processing runs synchronously and can be slow on long lecture recordings, (2) complex diagram parsing requires external cloud vision API keys, and (3) our evaluation suite currently uses a compact synthetic test set rather than thousands of real student submissions.

---

## Part 6: Engineering, Security & Scaling

### 30. Why use FastAPI?
FastAPI provides native asynchronous I/O with high concurrency throughput, automatic OpenAPI documentation at `/docs`, and strict Pydantic data validation. It is lightweight, pythonic, and integrates seamlessly with scientific Python libraries like PyMuPDF and NumPy.

### 31. Why PostgreSQL and pgvector?
PostgreSQL is the industry-standard open-source relational database, and the `pgvector` extension allows us to store vector embeddings directly alongside courses, quizzes, and learner profiles in a single ACID-compliant database. This eliminates the synchronization failures and dual-database maintenance required when using standalone vector databases like Pinecone or Qdrant.

### 32. How do you handle large video uploads and long-running jobs?
We enforce a 50MB request ceiling at the API gateway layer to prevent denial-of-service memory exhaustion. For production scaling, video transcription and large document chunking are designed to be dispatched to a background worker pool using Redis and Celery, returning immediate job tokens to the client.

### 33. How do you protect API keys and learner data?
API keys (such as `GEMINI_API_KEY`) are stored strictly in server-side environment variables and are never transmitted to the frontend client. Diagnostic endpoints like `/health/ai` report model availability status without revealing secret strings, and student database tables are strictly partitioned.

### 34. How do you isolate courses and students?
Course isolation is enforced at the database query level: all vector similarity searches, knowledge graph traversals, and flashcard queries execute with mandatory `WHERE course_id = :course_id` clauses. Our automated evaluation suite includes a specific release gate verifying that cross-course leakage is exactly 0.0.

### 35. What would you change to support many concurrent students?
To scale to thousands of simultaneous learners, we would: (1) place FastAPI behind multiple Gunicorn worker processes behind an Nginx load balancer, (2) move heavy PDF and video extraction to asynchronous Celery workers backed by Redis, (3) cache frequent vector queries in Redis, and (4) use an HNSW index in pgvector for sub-millisecond approximate nearest neighbor searches.

### 36. What happens when the AI provider is unavailable?
VIDYA-X AI features graceful offline degradation: if cloud LLM providers are unavailable, the system falls back to extractive RAG summarization, pure mathematical BKT calculations, and deterministic flashcard reviews. The core learner modeling, quiz taking, and spaced repetition features continue functioning without external API dependencies.

### 37. How would you reduce AI inference costs?
We reduce inference costs through three architectural decisions: (1) BKT learner modeling and spaced repetition run as pure local math with zero LLM calls, (2) quiz questions are deduplicated via SHA-256 hashes and cached in the database for reuse, and (3) we use compact, fast models like Gemini 1.5 Flash for vision and summarization tasks.

### 38. What would you build next with more time?
With additional development time, our top priorities are: (1) integrating directly with Canvas and Blackboard via standard LTI 1.3 protocols, (2) building collaborative peer-study sessions where students can practice together, and (3) conducting a multi-week randomized controlled study to empirically measure retention gains compared to static study guides.
