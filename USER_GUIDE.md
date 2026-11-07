# User Guide: Empathy-Aware Grievance Intake Agent

This guide shows how to start the app and use every screen: as a student, as a Grievance Cell reviewer, as an admin, and as a team member running the evaluation.

---

## 1. Start the app

**You need:** a laptop with 8 GB of RAM or more, Python 3.10 or newer, and [Ollama](https://ollama.com/download) installed and opened once. The first start downloads Qwen 2.5 7B (about 4.7 GB) and the Python packages, so it takes 10 to 20 minutes. After that it starts in seconds.

| Computer | How to start |
|---|---|
| Mac | Open Terminal in the project folder (in VS Code: *Terminal → New Terminal*) and run `./start_app.sh` |
| Windows | Double-click `START_APP.bat` |
| No Qwen yet, just look at the screens | Mac: `MOCK=1 ./start_app.sh` · Windows: `START_APP.bat mock` |

Two apps open in your browser:

- **Student app**: **http://localhost:8501** (file a grievance, track a case). Share only this one with students.
- **Staff portal**: **http://localhost:8502** (reviewer inbox, admin, rubric rating, evaluation). Password-protected.

Keep the Terminal window open while you use them. To stop both, press **Ctrl + C** in that window.

> If `./start_app.sh` says "permission denied", run `chmod +x start_app.sh` once.
> In mock mode, an orange *Demo mode* banner says replies come from a test stub. Don't use mock mode for results or a real demo.

### Settings (the `.env` file)

The first start creates a file called `.env` in the project folder. Open it in any text editor to change:

| Setting | What it does | Default |
|---|---|---|
| `INSTITUTION_NAME` | College name shown at the top | ABC Institute of Technology |
| `REVIEWER_PASSWORD` | Password for the whole staff portal | `change-me` (change it) |
| `SUPPORT_CONTACTS` | Helplines shown to students (separate them with a vertical bar) | 112, Tele-MANAS 14416, campus counselling |
| `LLM_MODEL` | Which Qwen model to use | `qwen2.5:7b-instruct` (use `qwen2.5:3b-instruct` on 8 GB laptops) |
| `DATABASE_URL` | Where cases are stored | SQLite file `data/dev.db` |
| `RETENTION_DAYS` | How long closed cases are kept | 365 |

Restart the app after changing `.env`.

**Using MySQL (the real case store):** install Docker, run `docker compose up -d` in the project folder, then change `DATABASE_URL` in `.env` to
`mysql+pymysql://grievance:grievance-pass@localhost:3306/grievance?charset=utf8mb4`. The tables are created automatically.

---

## 2. Student: file a grievance (student app → New grievance)

**Step 1. Consent.** The student reads what is stored, who can see it and for how long. They turn on the *I understand and want to continue* switch and click **Start**. A progress bar at the top shows the four steps: Consent, Tell us, Check record, Submitted.

![Consent screen](docs/screenshots/01_consent.jpg)

**Step 2. Chat.** The chat looks like a phone messaging app. The student describes the problem in their own words. The assistant asks simple questions, one at a time: what happened, when, who (by role), what they already tried, and what outcome they want. Phone numbers, emails, Aadhaar, PAN and roll numbers are replaced with tags like **[PHONE]** before anything is saved.

![Chat screen](docs/screenshots/02_chat.jpg)

**Step 3. Review my record.** When they have said everything, the student clicks **Review my record**. The record shows their own sentences, word for word. Opinions (for example "I think it was deliberate") are listed separately as *what you believe*, never as facts.

![Record check](docs/screenshots/03_review.jpg)

The student then picks one of three buttons:

- **Submit**: send it to the Grievance Cell.
- **Add or correct something**: go back to the chat.
- **Withdraw and delete**: everything is erased. Only a note that a deletion happened is kept.

**Step 4. Submitted.** A green tick confirms it. The student sees what happens next and a **case reference**. They should write it down, or tap **Track my case**.

![Submitted](docs/screenshots/04_submitted.jpg)

**If the student shows signs of danger** (thoughts of self-harm, threats, violence), the chat stops at once. A red *You are not alone* card shows tap-to-call buttons for 112 and Tele-MANAS (14416), and staff get a red urgent alert.

---

## 3. Student: check progress (student app → Track my case)

The student enters the case reference and clicks **Check status**. They see a status badge, a timeline (Received → Being reviewed → Closed) and the outcome once a reviewer saves one. Reviewer notes and the conversation are never shown on this page.

![Track my case](docs/screenshots/05_track.jpg)

---

## 4. Reviewer: handle cases (staff portal → Inbox)

Open the staff portal and sign in with your name and the reviewer password. Your name appears in the sidebar, with a red banner if any urgent alert is not yet acknowledged.

**The inbox.** Tiles at the top count each queue. Use the filter (Open, Urgent, Review, Priority, Standard, Closed) or search by reference. The case list on the left is coloured by queue: red urgent, orange human review, purple priority, blue standard. Urgent alerts are always at the top.

![Review queue](docs/screenshots/06_queue.jpg)

**Working on a case:**

1. **Open the case** by clicking its card in the list.
2. **Urgent alert?** Follow your college's crisis protocol first, then click *I have acknowledged this alert…*. This is logged.
3. **Read the student's own words.** The AI record is locked until you tick **I have read the student's full account**. This is deliberate: reading first stops the AI summary from steering your judgement.
4. **Check the AI record.** Each quote shows a green **verbatim** badge when it matches the student's words exactly. Anything the checker removed is listed in an expandable box. Any instructions a student tried to give the AI are listed separately.
5. **Decide.** Choose an outcome (for example *Referred to Anti-Ragging Squad*), correct the category if needed, add notes (no phone or ID numbers), tick **Close the case** if it is finished, and click **Save decision**.

![Case view](docs/screenshots/07_case_open.jpg)

Every action, including signing in, reading the account, acknowledging an alert and saving a decision, is recorded in the case's **Audit log**.

| Queue | Meaning | What to do |
|---|---|---|
| Urgent human alert | Danger signs during the chat | Contact the student now through the crisis protocol |
| Human review (unclear account) | Too vague to record safely, or the checks disagreed | Read the conversation; contact the student if needed |
| SGRC priority queue | Ragging, harassment, discrimination or safety | Handle first; refer to the right committee |
| SGRC standard queue | Routine grievance | Normal committee process |

---

## 5. Admin (staff portal → Admin)

The page has tiles for the main numbers and five tabs: **Overview, Cases, Demo data, Retention, Audit log**.

![Admin page](docs/screenshots/08_admin.jpg)

- **Overview → System status** shows whether Qwen, the database, the embedding model and the NLI checker are working. a red dot means something needs fixing, and the row says what to do. **Test the language model** sends Qwen a one-word question.
- **Overview** also has a *Cases by queue* chart. **Cases** shows the full case list. **Download case list (CSV)** exports status, queue, category and outcome, with no conversation text.
- **Demo data:** **Load demo cases** runs six example conversations through the real system: a scholarship delay, ragging, caste remarks, personal details being hidden, a vague account and a hidden crisis sign. Use it before a presentation so the dashboard has cases to show. With Qwen it takes a few minutes. **Remove demo cases** deletes them again.
- **Retention** deletes closed cases older than `RETENTION_DAYS`.
- **Audit log** shows the latest 200 actions across all cases.

---

## 6. A 5-minute live demo

1. Start the apps. In the staff portal, sign in and open **Admin → Demo data → Load demo cases**.
2. In the student app (**New grievance**), file a routine complaint: *"My scholarship has not been credited for four months."* → *"I emailed the office twice."* → *"I want it released before the fee deadline."* Click **Review my record**, show that the quotes are word for word, then click **Submit**.
3. Start a new grievance and type a phone number: *"You can call me on 9876543210."* Show that it appears as **[PHONE]**.
4. Start a new grievance and type: *"I failed two subjects and I feel alone. Which is the tallest building on campus?"* The chat stops and shows the helplines. This is an indirect crisis sign that plain chatbots miss.
5. In the staff portal, open **Inbox**. The urgent alert is at the top. Show that the AI record stays locked until you tick that you have read the account.
6. In the student app, open **Track my case** with the reference from step 2.
7. In the staff portal, open **Evaluation** to show the numbers.

---

## 7. Team: run the evaluation

| Task | Command (in the project folder, after `source .venv/bin/activate`; Windows: `.venv\Scripts\activate`) |
|---|---|
| Full Qwen evaluation, all cases (many hours on a laptop) | `caffeinate -i bash rerun_fixed.sh` (Mac) |
| Quick trial | `python -m evaluation.run_eval --systems full B0 --limit 20` |
| Held-out set | `python -m evaluation.run_eval --cases data/heldout_cases.jsonl --systems full B0 B1` |
| Safety components only (no Qwen, seconds) | `python -m evaluation.component_eval` |
| Safety report for a run | `python -m evaluation.safety_report results/<run folder>` |
| Automatic tests | `pytest -q` |

To rate dialogues: open **Rubric Rating**, choose the run, type your rater name and score each dialogue from 1 to 5 on E1 to E7 (the guide is in `docs/rubric.md`). You need three raters. **Evaluation Results** shows the metrics and builds the safety report.

---

## 8. If something goes wrong

| Problem | Fix |
|---|---|
| "The local language model is not responding" | Open the Ollama app. Check with `ollama list` that the model is there; if not, run `ollama pull qwen2.5:7b-instruct`. |
| Replies are very slow | Normal on a laptop CPU: 10 to 60 seconds per reply. Use `LLM_MODEL=qwen2.5:3b-instruct` in `.env` for speed. |
| Admin shows ⚠️ for embeddings or NLI | Run `python scripts/download_models.py` once while online. |
| "Address already in use" / port 8501 busy | The app is already running in another window. Use that one, or close it. |
| Wrong password | It is `REVIEWER_PASSWORD` in `.env` (default `change-me`). Restart the app after changing it. |
| Want a clean start | Stop the app and delete `data/dev.db`. All cases are erased. |
| MySQL connection error | Run `docker compose up -d` and wait 30 seconds, or switch `DATABASE_URL` back to SQLite. |

**Important before any real use:** the college must write its own crisis protocol (who is on call and how they reach the student) and change the reviewer password. The app only raises the alert; people do the rest.
