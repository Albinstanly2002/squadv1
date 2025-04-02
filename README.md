# Squad Gaming Center

A web application for managing gaming center bookings and setups.

## Features

- User registration and authentication
- Booking management (create, view, reschedule, cancel)
- Admin panel for managing setups and pricing
- Real-time availability checking
- Responsive design

## Tech Stack

- Frontend: HTML, CSS, JavaScript
- Backend: Python, Flask
- Database: Firebase Firestore
- Authentication: JWT

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/yourusername/squad-gaming-center.git
cd squad-gaming-center
```

2. Set up the backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
```
Edit `.env` with your configuration:
- Set up Firebase project and download credentials
- Generate a secure JWT secret
- Set admin credentials

4. Initialize the database:
```bash
python init_admin.py
```

5. Run the development server:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Security Considerations

- Never commit `.env` or `firebase-credentials.json` to version control
- Use strong passwords and JWT secrets
- Keep dependencies updated
- Follow security best practices for production deployment

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
