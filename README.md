# Ancient Event

Mobile-friendly ticket generator and entrance verification website.

## Features
- First account becomes the admin; admin can create staff accounts.
- Generate unique ticket IDs and QR codes.
- Verify by camera scan or by typing/searching a ticket ID.
- Valid unused tickets are immediately marked used in the database.
- Used and invalid tickets are rejected.
- Guest list and ticket status dashboard.
- PostgreSQL on Render for shared, real-time data across devices.

## Deploy from an Android phone
1. Download and extract this ZIP.
2. Create a GitHub repository named `ancient-event`.
3. Upload the **contents** of this ZIP (not the ZIP itself): `app.py`, `requirements.txt`, `render.yaml`, `README.md`, and the `templates` and `static` folders.
4. On Render, choose **New + → Blueprint** and connect the GitHub repository. Render reads `render.yaml` and creates the web service and PostgreSQL database.
5. Wait for the service to become **Live**, then open the `.onrender.com` URL.
6. Choose **Create admin account**. The first account becomes admin. Keep its password safe.
7. Sign in, create tickets, and add staff accounts from the dashboard.

## Important
- The first admin registration is open only until the first account exists. After that, new staff accounts must be created by an admin.
- PostgreSQL is required for reliable shared ticket status across staff devices. Do not remove the `DATABASE_URL` setting.
- QR scanning needs camera permission and normally requires HTTPS; Render provides HTTPS.
- A free Render web service may sleep when idle. The first request can take a little time.
- This starter app is not a substitute for a professional security audit. Use a strong admin password and keep the Render database private.
