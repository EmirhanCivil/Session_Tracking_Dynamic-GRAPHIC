Web-Based Session and Product Management App (Flask)
This is a web-based application built with Flask to monitor user sessions and manage product entries. The app supports two user roles: user and admin, each with tailored access and features.

🔧 Technologies Used
Python

Flask

SQLite (or Oracle DB)

Bootstrap 4.5.2

Matplotlib

👥 User Roles
User: Can view and add their own products only.

Admin: Can view and manage all users’ products and session data with additional analytics access.

🔐 Features
User registration and login system

Role-based access control (user/admin)

Session tracking (login time, user ID, etc.)

Product addition and deletion (admin-only for deletion)

Session and login activity analytics:

Users who logged in more than 3 times in the last hour

Session activity over the past 24 hours

Data Guard performance monitoring screen that highlights delays exceeding 6 seconds

📈 Data Visualization
Bar and line charts to display user activity

Charts are generated using Matplotlib and rendered as base64 images within the UI

Accessible via the admin dashboard

🖼️ UI Design
Responsive and user-friendly layout built with Bootstrap

Separate dashboard views for admin and user roles

Clean login/registration pages with helpful messages and alerts
