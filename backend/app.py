from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, auth
from datetime import datetime, timedelta
import json
import os
import hashlib
import jwt
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='../', static_url_path='')
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5000", "http://127.0.0.1:5000", "https://*.onrender.com"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Retrieve environment variables
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")
JWT_SECRET = os.getenv("JWT_SECRET")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Ensure all required environment variables are set
if not all([FIREBASE_CREDENTIALS, JWT_SECRET, ADMIN_USERNAME, ADMIN_PASSWORD]):
    raise ValueError("Missing required environment variables! Check your Render settings.")

print("✅ Environment variables loaded successfully!")

# Initialize Firebase
try:
    cred_dict = json.loads(FIREBASE_CREDENTIALS)  # Convert JSON string to dictionary
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase initialized successfully!")
except json.JSONDecodeError as e:
    raise ValueError("❌ Invalid JSON format in FIREBASE_CREDENTIALS") from e
except Exception as e:
    raise RuntimeError(f"❌ Firebase initialization failed: {str(e)}") from e


# Admin Authentication Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Bearer token required'}), 401
        
        try:
            token = auth_header.split('Bearer ')[1].strip()
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=['HS256'],
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'require': ['admin', 'exp']
                }
            )
            
            if not payload.get('admin'):
                return jsonify({'error': 'Admin access required'}), 403
                
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return decorated_function

# User Authentication Decorator
def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Bearer token required'}), 401
        
        try:
            token = auth_header.split('Bearer ')[1]
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            if not payload.get('user_id'):
                return jsonify({'error': 'User authentication required'}), 403
            request.user = payload
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated_function

# Admin Login Route
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # Verify credentials against environment variables
        if (username == ADMIN_USERNAME and 
            hashlib.sha256(password.encode()).hexdigest() == hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()):
            
            token = jwt.encode({
                'admin': True,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, JWT_SECRET, algorithm='HS256')
            
            return jsonify({'token': token}), 200
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Initialize Admin Credentials (run once to set up admin)
@app.route('/api/admin/init', methods=['POST'])
def init_admin():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Hash password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Store in Firestore
        admin_ref = db.collection('admin').document('credentials')
        admin_ref.set({
            'username': username,
            'password': hashed_password,
            'created_at': datetime.now().isoformat()
        })
        
        return jsonify({'message': 'Admin credentials initialized'}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Root route to serve the frontend
@app.route('/')
def serve_frontend():
    return send_from_directory('../', 'index.html')

# Route to serve static files
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('../', path)

# Helper functions
def get_available_time_slots(date):
    """Get available time slots for a given date"""
    # Operating hours: 10:00 AM to 11:00 PM
    all_slots = [f"{hour:02d}:00" for hour in range(10, 24)]  # 10 AM to 11 PM
    
    # Get bookings for the date
    bookings_ref = db.collection('bookings')
    bookings = bookings_ref.where('date', '==', date).get()
    
    # Get setup availability
    setup_ref = db.collection('setup_availability').document('current')
    setup_data = setup_ref.get()
    available_setups = setup_data.to_dict() if setup_data.exists else {
        'ps5_setup_1': True,
        'ps5_setup_2': True,
        'racing_simulator': True,
        'pool_table': True
    }
    
    # Count bookings per time slot and setup
    slot_bookings = {slot: {'total': 0, 'setups': {}} for slot in all_slots}
    for booking in bookings:
        booking_data = booking.to_dict()
        if booking_data.get('status') not in ['cancelled']:
            slot = booking_data.get('time')
            setup = booking_data.get('setup')
            if slot in slot_bookings:
                slot_bookings[slot]['total'] += 1
                if setup not in slot_bookings[slot]['setups']:
                    slot_bookings[slot]['setups'][setup] = 0
                slot_bookings[slot]['setups'][setup] += 1
    
    # Check available slots based on setup availability
    available_slots = []
    total_setups = sum(1 for setup, available in available_setups.items() if available)
    
    for slot in all_slots:
        # A slot is available if:
        # 1. Total bookings are less than total available setups
        # 2. At least one setup type has availability
        if slot_bookings[slot]['total'] < total_setups:
            # Check specific setup availability
            for setup, count in slot_bookings[slot]['setups'].items():
                if setup.startswith('ps5') and count >= 2:  # Both PS5 setups are booked
                    continue
                if setup in ['racing_simulator', 'pool_table'] and count >= 1:  # Single setup is booked
                    continue
            available_slots.append(slot)
    
    return available_slots

def calculate_price(setup_type, duration, players):
    """Calculate price based on setup type, duration and number of players"""
    # Get current pricing from Firestore
    pricing_ref = db.collection('pricing').document('current')
    pricing_data = pricing_ref.get()
    base_prices = pricing_data.to_dict() if pricing_data.exists else {
        'squad': 400,
        'individual': 120,
        'ps5_specific': 400,
        'racing': 150,
        'pool': 400
    }
    
    if setup_type == 'individual':
        return base_prices[setup_type] * players * duration
    else:
        return base_prices[setup_type] * duration

# Routes
@app.route('/api/bookings', methods=['POST'])
@user_required
def create_booking():
    try:
        data = request.json
        required_fields = ['setup', 'players', 'date', 'time', 'duration']
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get user details from token
        user_ref = db.collection('users').document(request.user['user_id'])
        user_data = user_ref.get().to_dict()
        
        # Check if time slot is available
        available_slots = get_available_time_slots(data['date'])
        if data['time'] not in available_slots:
            return jsonify({'error': 'Selected time slot is not available'}), 400
        
        # Calculate price
        price = calculate_price(data['setup'], int(data['duration']), int(data['players']))
        
        # Create booking document
        booking_data = {
            'user_id': request.user['user_id'],
            'name': user_data['name'],
            'email': user_data['email'],
            'phone': user_data['phone'],
            'setup': data['setup'],
            'players': int(data['players']),
            'date': data['date'],
            'time': data['time'],
            'duration': int(data['duration']),
            'price': price,
            'status': 'confirmed',
            'created_at': datetime.now().isoformat()
        }
        
        # Add to Firestore
        booking_ref = db.collection('bookings').document()
        booking_ref.set(booking_data)
        
        # Add booking ID to the response data
        booking_data['id'] = booking_ref.id
        
        return jsonify({
            'message': 'Booking created successfully',
            'booking_id': booking_ref.id,
            'booking': booking_data
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings/<booking_id>', methods=['PUT'])
@admin_required
def update_booking(booking_id):
    try:
        data = request.json
        booking_ref = db.collection('bookings').document(booking_id)
        booking = booking_ref.get()
        
        if not booking.exists:
            return jsonify({'error': 'Booking not found'}), 404
        
        booking_data = booking.to_dict()
        
        # Handle cancellation
        if 'status' in data and data['status'] == 'cancelled':
            booking_ref.update({'status': 'cancelled'})
            updated_booking = booking_ref.get().to_dict()
            updated_booking['id'] = booking_id
            return jsonify(updated_booking), 200
        
        # Handle rescheduling
        if 'date' in data and 'time' in data:
            # Validate time format (HH:00)
            try:
                hour = int(data['time'].split(':')[0])
                if hour < 10 or hour > 23:
                    return jsonify({'error': 'Invalid time slot. Hours must be between 10 AM and 11 PM'}), 400
            except:
                return jsonify({'error': 'Invalid time format'}), 400
            
            # Check if new time slot is available
            available_slots = get_available_time_slots(data['date'])
            if data['time'] not in available_slots:
                return jsonify({'error': 'Selected time slot is not available'}), 400
            
            # Update booking with new date and time
            update_data = {
                'date': data['date'],
                'time': data['time'],
                'status': 'rescheduled',
                'updated_at': datetime.now().isoformat()
            }
            
            booking_ref.update(update_data)
            
            updated_booking = booking_ref.get().to_dict()
            updated_booking['id'] = booking_id
            return jsonify(updated_booking), 200
        
        return jsonify({'error': 'Invalid update request'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings/<booking_id>', methods=['DELETE'])
@admin_required
def delete_booking(booking_id):
    try:
        booking_ref = db.collection('bookings').document(booking_id)
        booking = booking_ref.get()
        
        if not booking.exists:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Delete the booking
        booking_ref.delete()
        return jsonify({'message': 'Booking deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings', methods=['GET'])
@admin_required
def get_bookings():
    try:
        date = request.args.get('date')
        bookings_ref = db.collection('bookings')
        
        # Apply date filter if provided
        if date:
            bookings_ref = bookings_ref.where('date', '==', date)
        
        bookings = bookings_ref.get()
        
        bookings_list = []
        for booking in bookings:
            booking_data = booking.to_dict()
            booking_data['id'] = booking.id
            bookings_list.append(booking_data)
        
        return jsonify(bookings_list), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bookings/check', methods=['GET'])
def check_booking():
    try:
        booking_id = request.args.get('id')
        email = request.args.get('email')
        
        if not booking_id or not email:
            return jsonify({'error': 'Booking ID and email are required'}), 400
        
        booking_ref = db.collection('bookings').document(booking_id)
        booking = booking_ref.get()
        
        if not booking.exists:
            return jsonify({'error': 'Booking not found'}), 404
        
        booking_data = booking.to_dict()
        if booking_data['email'] != email:
            return jsonify({'error': 'Invalid credentials'}), 403
        
        booking_data['id'] = booking_id
        return jsonify(booking_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/availability', methods=['GET'])
@user_required
def get_availability():
    try:
        date = request.args.get('date')
        if not date:
            return jsonify({'error': 'Date parameter is required'}), 400
        
        # Get available time slots
        available_slots = get_available_time_slots(date)
        
        # Get setup availability
        setup_ref = db.collection('setup_availability').document('current')
        setup_data = setup_ref.get()
        setup_availability = setup_data.to_dict() if setup_data.exists else {
            'ps5_setup_1': True,
            'ps5_setup_2': True,
            'racing_simulator': True,
            'pool_table': True
        }
        
        return jsonify({
            'date': date,
            'available_slots': available_slots,
            'setup_availability': setup_availability
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pricing', methods=['GET'])
def get_pricing():
    try:
        pricing_ref = db.collection('pricing').document('current')
        pricing = pricing_ref.get()
        
        if not pricing.exists:
            # Set default pricing if not exists
            default_pricing = {
                'squad': 400,
                'individual': 120,
                'ps5_specific': 400,
                'racing': 150,
                'pool': 400
            }
            pricing_ref.set(default_pricing)
            return jsonify(default_pricing), 200
        
        return jsonify(pricing.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pricing', methods=['PUT'])
@admin_required
def update_pricing():
    try:
        data = request.json
        pricing_ref = db.collection('pricing').document('current')
        pricing_ref.update(data)
        
        # Get the updated pricing
        updated_pricing = pricing_ref.get().to_dict()
        return jsonify(updated_pricing), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/setup-availability', methods=['GET'])
def get_setup_availability():
    try:
        setup_ref = db.collection('setup_availability').document('current')
        setup = setup_ref.get()
        
        if not setup.exists:
            # Set default availability if not exists
            default_availability = {
                'ps5_setup_1': True,
                'ps5_setup_2': True,
                'racing_simulator': True,
                'pool_table': True
            }
            setup_ref.set(default_availability)
            return jsonify(default_availability), 200
        
        return jsonify(setup.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/setup-availability', methods=['PUT'])
@admin_required
def update_setup_availability():
    try:
        data = request.json
        setup_ref = db.collection('setup_availability').document('current')
        setup_ref.update(data)
        
        # Get the updated availability
        updated_availability = setup_ref.get().to_dict()
        return jsonify(updated_availability), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# User Registration Route
@app.route('/api/user/register', methods=['POST'])
def user_register():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        phone = data.get('phone')
        
        if not all([email, password, name, phone]):
            return jsonify({'error': 'All fields are required'}), 400
        
        # Check if user already exists
        user_ref = db.collection('users').where('email', '==', email).get()
        if len(list(user_ref)) > 0:
            return jsonify({'error': 'User already exists'}), 400
        
        # Hash password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Create user document
        user_data = {
            'email': email,
            'password': hashed_password,
            'name': name,
            'phone': phone,
            'created_at': datetime.now().isoformat()
        }
        
        user_ref = db.collection('users').document()
        user_ref.set(user_data)
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user_ref.id,
            'email': email,
            'name': name,
            'exp': datetime.utcnow() + timedelta(days=30)
        }, JWT_SECRET, algorithm='HS256')
        
        return jsonify({
            'token': token,
            'user': {
                'id': user_ref.id,
                'email': email,
                'name': name
            }
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# User Login Route
@app.route('/api/user/login', methods=['POST'])
def user_login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Get user from Firestore
        users_ref = db.collection('users').where('email', '==', email).get()
        user_list = list(users_ref)
        
        if not user_list:
            return jsonify({'error': 'User not found'}), 404
        
        user_doc = user_list[0]
        user_data = user_doc.to_dict()
        
        # Verify password
        if hashlib.sha256(password.encode()).hexdigest() != user_data['password']:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user_doc.id,
            'email': email,
            'name': user_data['name'],
            'exp': datetime.utcnow() + timedelta(days=30)
        }, JWT_SECRET, algorithm='HS256')
        
        return jsonify({
            'token': token,
            'user': {
                'id': user_doc.id,
                'email': email,
                'name': user_data['name']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/bookings', methods=['GET'])
@user_required
def get_user_bookings():
    try:
        user_id = request.user['user_id']
        bookings_ref = db.collection('bookings').where('user_id', '==', user_id)
        bookings = bookings_ref.get()
        
        bookings_list = []
        for booking in bookings:
            booking_data = booking.to_dict()
            booking_data['id'] = booking.id
            bookings_list.append(booking_data)
        
        return jsonify(bookings_list), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/bookings/<booking_id>', methods=['PUT'])
@user_required
def update_user_booking(booking_id):
    try:
        data = request.json
        booking_ref = db.collection('bookings').document(booking_id)
        booking = booking_ref.get()
        
        if not booking.exists:
            return jsonify({'error': 'Booking not found'}), 404
        
        booking_data = booking.to_dict()
        
        # Verify the booking belongs to the user
        if booking_data['user_id'] != request.user['user_id']:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Handle cancellation
        if 'status' in data and data['status'] == 'cancelled':
            booking_ref.update({'status': 'cancelled'})
            updated_booking = booking_ref.get().to_dict()
            updated_booking['id'] = booking_id
            return jsonify(updated_booking), 200
        
        # Handle rescheduling
        if 'date' in data and 'time' in data:
            # Validate time format (HH:00)
            try:
                hour = int(data['time'].split(':')[0])
                if hour < 10 or hour > 23:
                    return jsonify({'error': 'Invalid time slot. Hours must be between 10 AM and 11 PM'}), 400
            except:
                return jsonify({'error': 'Invalid time format'}), 400
            
            # Check if new time slot is available
            available_slots = get_available_time_slots(data['date'])
            if data['time'] not in available_slots:
                return jsonify({'error': 'Selected time slot is not available'}), 400
            
            # Update booking with new date and time
            update_data = {
                'date': data['date'],
                'time': data['time'],
                'status': 'rescheduled',
                'updated_at': datetime.now().isoformat()
            }
            
            booking_ref.update(update_data)
            
            updated_booking = booking_ref.get().to_dict()
            updated_booking['id'] = booking_id
            return jsonify(updated_booking), 200
        
        return jsonify({'error': 'Invalid update request'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/bookings/<booking_id>', methods=['DELETE'])
@user_required
def delete_user_booking(booking_id):
    try:
        booking_ref = db.collection('bookings').document(booking_id)
        booking = booking_ref.get()
        
        if not booking.exists:
            return jsonify({'error': 'Booking not found'}), 404
        
        booking_data = booking.to_dict()
        
        # Verify the booking belongs to the user
        if booking_data['user_id'] != request.user['user_id']:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Delete the booking
        booking_ref.delete()
        return jsonify({'message': 'Booking deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 