# COMPASS buddy program

Pairs every new joiner with a buddy whose working style is close to theirs, using one
five-question assessment that both sides take. The Program admin assigns every buddy, and the joiner
then follows a 4-week induction and reviews their buddy at the end.

* **Backend:** Python, Django, Django REST Framework (`backend/`)
* **Frontend:** React, TypeScript, Vite, Tailwind (`frontend/`)
* **Database:** SQLite while developing

## Run it

**One server, one address.** Django serves both the API and the web app, so this is all you run:

```bash
cd backend
venv\Scripts\activate
python manage.py runserver
```

Open **http://localhost:8000** and sign in. Everything (the admin screens, the joiner and buddy portal,
the API and the Django admin) is on that one address.

The web app is served from `frontend/dist`. Build it again whenever you change the frontend code:

```bash
cd frontend
npm run build      # once
npm run watch      # or leave this running in a second terminal: it rebuilds on every save
```

Refresh the page after a rebuild. If `frontend/dist` is missing, Django shows a message telling you to
run `npm run build`.

**The look.** Light and simple: white side menu and cards, one calm blue for buttons and the selected item, on a light grey page. All colours and the font are set
once, in `frontend/src/index.css` (the brand blue, its light tint, the
heading colour and the success green); buttons, inputs and cards are in `frontend/src/styles.ts`.
Change them there and every screen follows.

**Editing the frontend with instant refresh (optional).** `npm run dev` starts Vite on
http://localhost:5173, which updates the page the moment you save a file and sends API calls to Django
on port 8000. Use it only while you are changing the screens.

### First-time setup (already done on this machine)

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo           # demo data (development only, see below)
cd ../frontend
npm install
```

### Demo data (development only)

`python manage.py seed_demo` **wipes** every joiner, buddy and their history and starts a clean demo
of **100 buddies and 10 joiners** (`--buddies 50 --joiners 20` for other numbers):

* 100 buddies across 6 departments and 5 cities, with finished profiles so the match can suggest them,
  but no joiners assigned yet: you assign them.
* 10 joiners. The 2 generated ones join in 5 to 45 days and one of them has answered and waits for a
  buddy; the rest have not answered yet.
* 16 of them are the named demo people (buddies E001-E008, joiners C001-C008, none answered yet).
* A sample 4-week induction programme.

It prints the 16 named people's usernames and passwords, and the one password every generated person
shares. Run it again any time to start over.

**Demo sign-in.** Under the login form there is a list of every joiner and buddy: click one to open
their portal without a password. It follows `DEBUG` (`DEMO_SIGN_IN = DEBUG` in
`config/settings.py`), so in production it disappears and the server answers 404. Never set it to
`True` on a real deployment.

## Who signs in

There is **one login page for everyone**, `/login`.

| Who | Username | Password | Goes to |
|---|---|---|---|
| Superuser (the developer) | their username | their password | the admin screens |
| Program admin (runs COMPASS) | their username | their password | the admin screens |
| Joiner | candidate ID, e.g. `C005` | the 8-character password from their email | their portal |
| Buddy | employee ID, e.g. `E005` | the 8-character password from their email | their portal |

* The superuser and Program admins can do the same things in COMPASS. Only the superuser can add
  Program admins: in the Django admin (`/admin`), under **Users**, add a user and tick **Staff status**.
* When the Program admin adds a joiner or a buddy (the form or a CSV upload), COMPASS emails them
  their username and password. Each person gets one password, made once and kept, so every later
  email (Day 1, a reminder) repeats the same one. **Send login details** (on the joiner's
  page, or under More actions on a buddy's page) emails the same username and password again.
* Sign-in is limited to 10 attempts a minute from one address, so passwords cannot be guessed.

## How a joiner moves through COMPASS

1. The Program admin adds a joiner (a form, a CSV upload, or later the HRMS feed) and adds buddies to
   the pool. Both get their login details by email.
2. A buddy completes their profile in their portal. Every joiner gets the same **five emails** from
   Team United before joining (`backend/notifications/prejoining.py`), then a sixth after it:

   | # | Email | When |
   |---|---|---|
   | 1 | Welcome to United Group | When added |
   | 2 | Your COMPASS login details: username, password, and the 5 questions and hobbies to answer | When added |
   | 3 | Get to know United Group: our story, values, handbook | 14 days before joining |
   | 4 | Everything you need for Day 1: address, time, what to bring and wear, manager and buddy | 3 days before joining |
   | 5 | See you tomorrow | 1 day before joining |
   | 6 | How was your COMPASS buddy? (the review) | After the 4-week induction |

   A joiner added later than an email's day gets it the next day, so everyone gets all five. The
   questions are due 7 days before joining (Settings), or within 2 days for a joiner added 10 days or
   less before joining; no answers by then means manual pairing. There are no automatic reminders:
   **Send reminder** on the joiner's page sends one.

   The story video, handbook, social links, phone, dress code and each location's office are on the
   **Settings** page; each joiner's manager and reporting time are on their page (**Day 1 and
   pre-joining emails**). A blank one is left out of the email. In their portal the joiner also picks
   what they enjoy outside work and taps **Yes, I'll be there** from 3 days before joining.
3. When a joiner submits, the match runs: eligibility filter, scoring, flags, then the tiers
   (same department and location, same department elsewhere, other departments, weaker matches).
4. The Program admin reviews the ranked suggestions and **assigns** one. A reason is required if the
   choice is not the top suggestion, is a Weaker match, or carries a Red flag.
5. The pairing is **active at once**: nobody has to accept. The buddy is emailed that they have been
   assigned; the joiner sees their buddy in their portal and in emails 4 and 5. For **2 days** after
   assigning, **Change buddy** on the joiner's page picks someone else (both buddies are told).
6. The pairing runs **30 days** from the joining date: the **4-week induction**. The joiner sees the
   induction timetable in their portal and ticks each item when it is done. Their buddy sees the same
   timetable, read only, in their own portal.
7. After the 4 weeks the joiner **reviews their buddy**: three questions (1 to 5) and a comment, in
   their portal. Only the Program admins see the answers, in the **Buddy reviews** report.
8. After Day 30 the pairing closes.

## Where things are

| Screen | Address |
|---|---|
| Sign in | `/login` |
| Admin screens | `/hr`: home, joiners, buddies, induction programme, reports, settings, audit log |
| Joiner and buddy portal | `/portal` |
| The five questions (opened from the portal) | `/assess/joiner/<token>`, `/assess/buddy/<token>` |
| Raw data (superuser) | http://127.0.0.1:8000/admin |

* **Buddies** shows the pool in **groups** (department and location). Clicking a buddy, there or on
  any buddy name in **Reports** or on a joiner's page, opens the same panel: the joiners they look
  after now, how many they have had in total, and their past joiners.
* **Induction** is where the Program admin writes the 4-week programme: a table of week, day,
  activity and who it is with. Every joiner follows the same programme.
* **Settings** holds the lists of **departments and locations**. Joiners and buddies are given one of
  each from a drop-down, and the CSV imports refuse anything else ("sales" is stored as "Sales"), so
  the match never misses a buddy because of a typo. One that people still have cannot be removed.
* **Reports**: four numbers at a glance (total buddies, total joiners, total assigned a buddy,
  average buddy review; each opens the matching list), then two plain tables:
  **Buddies** and **Buddy reviews**. Buddies with no profile yet are highlighted; each table has a
  search box and Excel/CSV downloads. Joiners are on the Joiners page.

In development the emails print in the terminal that runs `runserver`, and every email sent is listed
in the Django admin under **Notifications**.

## The daily job

```bash
python manage.py run_daily
```

Sends the joiners' emails 3 to 5 on their days, routes late joiners to manual pairing, asks joiners
to review their buddy after the 4 weeks and closes finished pairings. It is safe to run repeatedly.
Schedule it once a day (Windows Task Scheduler or cron). Use `--today 2026-12-01` to pretend it is
another day.

## Tests

```bash
cd backend
python manage.py test
cd ../frontend
npm run build                   # type-checks and builds
npm run lint
```

The matching rules are a plain Python module with no Django in it
(`backend/compass_app/engine.py`), tested against the worked examples in the design spec.

## Before going live

* Create the superuser on the live server (`python manage.py createsuperuser`) and set a real
  `SECRET_KEY`, `DEBUG = False` and `ALLOWED_HOSTS`. Do not run `seed_demo`: it wipes data.
* Point `MAILERS` in `config/settings.py` at a real mail server and set `FRONTEND_URL`.
* Switch to PostgreSQL and serve the built frontend (`npm run build`).
* Connect the HRMS feed. The CSV imports are the stand-in for it.
* Agree the buddy review questions with L&D (`backend/feedback/questions.py`), the real induction
  programme (the Induction page), and the manual-routing day (Settings).
* Put the joiner's manager into the match: skip-level managers need the HRMS manager chain, so
  only the direct manager is excluded today.
