# Squad Gaming Center Backend

This is the backend server for the Squad Gaming Center website, built with Flask and Firebase.

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Firebase:
   - Create a new Firebase project at https://console.firebase.google.com/
   - Generate a new private key for your service account
   - Download the service account key file and rename it to `firebase-credentials.json`
   - Place the file in the backend directory

3. Initialize the database:
   - Run the Flask application
   - The application will automatically create the necessary collections and documents

## API Endpoints

### Bookings
- `POST /api/bookings` - Create a new booking
- `GET /api/bookings` - Get all bookings or filter by date

### Availability
- `GET /api/availability` - Get available time slots for a specific date

### Pricing
- `GET /api/pricing` - Get current pricing
- `PUT /api/pricing` - Update pricing (admin only)

### Setup Availability
- `GET /api/setup-availability` - Get current setup availability
- `PUT /api/setup-availability` - Update setup availability (admin only)

## Running the Server

```bash
python app.py
```

The server will start on http://localhost:5000

## Security

- Admin endpoints require Firebase authentication
- Make sure to set up proper CORS policies in production 