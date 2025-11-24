# HooterTour

HooterTour is a full-stack travel marketplace built on Flask. It renders a marketing site with Jinja templates, exposes a JSON API for tours, bookings, reviews, testimonials, and users, and wires those experiences to MongoDB, Stripe, JWT-authenticated sessions, and scheduled background jobs. The app bootstraps demo data, syncs images into MongoDB GridFS-like collections, and ships with admin tooling for recalculating aggregate ratings.

---

## Highlights

- **Python + Flask stack**: Flask, Flask-Bootstrap, MongoEngine ORM, APScheduler for cron-like jobs, and Stripe for payments.
- **MongoDB-first design**: Models live in `models/`, backed by a single `Database` singleton (`db.py`) that initializes collections, maintains cached users, and exposes helpers for binary image storage.
- **Hybrid UI**: Server-rendered templates in `templates/` (Bootstrap theme, hero, destinations, dashboards) plus REST APIs mounted under `/api/v1`.
- **Auth & security**: BCrypt-hashed passwords, JWT cookies, role-based access decorators, password reset tokens via email, and Hashids-based public profile slugs.
- **Operational tooling**: Data importer, static/tour image upload scripts, Stripe webhook endpoint, background cleanup of unpaid bookings, and a Click command for recomputing tour ratings.

---

## Libraries & Tooling

Key packages and assets used throughout the stack (full pins live in `requirements.txt`):

- **Web & templating**: `Flask`, `Flask-Bootstrap`, `Flask-WTF`, `WTForms`, `Jinja2`, `Werkzeug`.
- **Database & data modeling**: `pymongo`, `mongoengine`, `SQLAlchemy`, `python-dateutil`, `bson`.
- **Auth & security**: `bcrypt`, `python-jose`, `hashids`, `itsdangerous`, `cryptography`.
- **Scheduling & CLI**: `APScheduler`, `click`.
- **Payments & integrations**: `stripe`, `requests`.
- **Configuration & runtime**: `python-dotenv`, `dotenv`, `gunicorn`, `typing_extensions`, `anyio`.
- **Media processing**: `Pillow` for automatic compression/downscaling.
- **API helpers**: `fastapi`, `starlette`, `pydantic`.

Bundled front-end libraries (under `static/lib/`) include Bootstrap, Owl Carousel, Tempus Dominus, Animate.css, WOW.js, Waypoints, and jQuery easing plugins.

---

## Architecture Overview

```
HooterTour/
├── main.py                 # Flask app bootstrap, schedulers, blueprints, startup data/image loaders
├── db.py                   # MongoDB connection singleton + helper methods for collections and binary images
├── controllers/            # Business logic for auth, tours, bookings, reviews, testimonials, views, etc.
├── routes/                 # Flask Blueprints that bind HTTP routes to controllers (API + page routes)
├── models/                 # MongoEngine documents: User, Tour, Booking, Review, Testimonial
├── templates/              # Jinja templates for marketing pages, dashboard, emails
├── static/                 # CSS/JS/vendor assets referenced by templates
├── public/                 # Uploaded/user-provided assets that can be synced into MongoDB collections
├── Data/                   # JSON seeds plus `DataImporter` for Mongo bootstrapping
├── scripts/                # Image ingestion helpers for Mongo collections
├── Commands/               # Flask CLI command(s), e.g., `update-ratings`
├── Utils/                  # Cross-cutting utilities (API query builder, custom errors, email helper)
└── requirements.txt        # Locked dependencies
```

### Request flow (API)
1. **Blueprint entry** in `routes/*.py`
2. **Auth decorators** (`protect`, `restrict_to`, `is_logged_in`)
3. **Controller** executes business logic and MongoEngine queries
4. **Serialize response** via `to_json()` or template render

### Request flow (web pages)
1. `routes/viewRoutes.py` wraps controllers with alert + auth decorators
2. `controllers/viewController.py` loads tours/users/testimonials
3. Jinja templates under `templates/` render Bootstrap UI

---

## Key Features

- **Tour catalog & discovery**: `/api/v1/tours` exposes filtering, geospatial queries (`tours-within`, `distances`), stats, monthly plans, and slug lookups for the marketing pages.
- **Booking lifecycle**: `controllers/bookingController.py` handles CRUD, mock checkout sessions, Stripe webhooks, and a background cleanup job (APScheduler) that deletes unpaid bookings older than 24 hours.
- **Stripe integration**: The `webhook-checkout` endpoint validates events via `STRIPE_WEBHOOK_SECRET` and marks bookings as paid. The UI currently uses a mock redirect flow that can be swapped with live Checkout sessions.
- **Authentication & authorization**: JWT cookies, password resets via signed tokens and email (SMTP configurable), `protect` and `restrict_to` decorators for route-level access control, and profile-specific dashboards using Hashids slugs.
- **Reviews & testimonials**: Users can post reviews (role-gated), testimonials feed the home page carousel, and `Commands/update_tour_ratings.py` recomputes aggregate ratings from review documents.
- **Media management**: User avatars and marketing assets are stored on disk and mirrored into MongoDB collections (`user_imgs`, `imgs`, optional `tour_imgs`), served back via `/images/...` routes with graceful fallbacks. Upload scripts now auto-compress oversized images (target controlled via `MAX_IMAGE_SIZE_MB`, default 15.5 MB) before persisting them.
- **Templated marketing site**: Landing pages (`index.html`, `destination.html`, `about.html`, etc.) use `static/css`, `static/js`, and vendor libraries to showcase tours, guides, and testimonials.

---

## Prerequisites

- Python **3.11+** (virtual environments recommended)
- MongoDB database (local instance or hosted Atlas cluster)
- Stripe account (for test keys + webhook signing secret)
- SMTP credentials (optional, for welcome/reset emails)

---

## API Surface (Summary)

| Resource      | Path prefix          | Notes |
|---------------|----------------------|-------|
| Users         | `/api/v1/users`      | Signup/login/logout, password reset, profile CRUD, admin-only list/create/delete, avatar upload |
| Tours         | `/api/v1/tours`      | Public listing, slug lookup, stats, geospatial queries; admin/guide CRUD |
| Reviews       | `/api/v1/reviews`    | Authenticated review CRUD (user/admin scopes) |
| Bookings      | `/api/v1/bookings`   | Booking CRUD, checkout session builder, Stripe webhook |
| Testimonials  | `/api/v1/testimonials` | CRUD endpoints feeding marketing pages |
| Views         | `/` + `/destination`, `/about`, `/dashboard/<slug>`, etc. | Jinja-rendered pages gated by `is_logged_in`/`protect` decorators |
| Images        | `/images/...`        | Streams binary data stored in MongoDB collections with fallback placeholder |

Each controller lives under `controllers/` and returns either JSON responses (API) or `render_template(...)` outputs (views). Common behaviors (filtering, pagination) are provided by `Utils/apiFeature.py`.

---

## Email & Notifications

- `Utils/email.Email` renders templates under `templates/email/` (welcome + password reset) via Jinja.
- SMTP transport is dynamic: in development it uses the host/port in env vars with STARTTLS; in production the code assumes SendGrid but can be adapted.
- Failures during signup/reset are logged but do not stop the request—README users should check logs when email delivery fails.

---

## Background Jobs & Maintenance

- `cleanup_unpaid_bookings()` runs every 24 hours via APScheduler in `main.py`.
- `scripts/upload_images.py` uploads marketing assets to the `imgs` collection only when empty; re-run manually if you add new files. When a file is larger than `MAX_IMAGE_SIZE_MB`, the script re-encodes/resizes it (quality and downscale behavior can be tuned via the env vars consumed in `scripts/upload_images.py`).
- `scripts/upload_tour_images.py` mirrors the same compression pipeline and expects `db.save_image_to_tour_imgs`; double-check `db.py` before enabling (methods are commented out in some revisions).
- CLI `update-ratings` recalculates tour aggregates—use after bulk review imports.

---

## Front-End Notes

- Templates combine Bootstrap 4, custom SCSS/CSS (`static/css/style.css`), Owl Carousel, Tempus Dominus, WOW.js, and custom JS (`static/js/main.js`).
- `templates/index.html` is the marketing landing page; `footer.html`, `header.html`, and other partials can be reused across pages.
- Assets under `public/` are intended for runtime uploads, while `static/` stores versioned theme assets bundled with the repo.

---

## Troubleshooting

- **Mongo connection failures**: Verify `MONGODB_URI`, network access rules, and DNS resolution. `db.py` logs detailed errors and aborts startup if it cannot `ping`.
- **Hashids profile slugs**: User saves run twice internally to generate a slug; do not manually supply `profile_slug` in API payloads.
- **Image uploads exceeding 16 MB**: Scripts now try to compress large assets automatically. If compression fails because the minimum quality/dimension safeguards kick in, lower `MAX_IMAGE_SIZE_MB`, relax the guardrails (see env vars in the upload scripts), or resize the file manually before rerunning the uploader.
- **Stripe webhook signature errors**: Ensure your public URL matches the endpoint configured in Stripe and that `STRIPE_WEBHOOK_SECRET` is current.
- **Email sending**: Missing SMTP creds or blocked ports will throw exceptions. Provide valid `EMAIL_*` env vars or disable email sending in development.

---



