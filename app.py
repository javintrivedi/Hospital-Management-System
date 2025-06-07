from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import sqlite3
import logging

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Database connection parameters
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "javin1326",
    "database": "hospital_management"
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# SQLite Database connection for user authentication
# def get_sqlite_connection():
#     conn = sqlite3.connect('database.db')
#     conn.row_factory = sqlite3.Row
#     return conn

# Register error handlers
@app.errorhandler(404)
def page_not_found(e):
    app.logger.error(f"404 error: {e}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"500 error: {e}")
    return render_template('500.html'), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
            cursor.close()
            db.close()
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password.', 'danger')
        except Exception as e:
            app.logger.error(f"Error during login: {e}")
            flash('An error occurred during login. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute('INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)',
                           (username, email, password_hash))
            db.commit()
            cursor.close()
            db.close()
            flash('Signup successful! Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username or email already exists.', 'danger')
        except Exception as e:
            app.logger.error(f"Error during signup: {e}")
            flash('An error occurred during signup. Please try again.', 'danger')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def home():
    user_info = None
    if 'user_id' in session:
        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
            user_info = cursor.fetchone()
            cursor.close()
            db.close()
        except Exception as e:
            app.logger.error(f"Error fetching user info: {e}")
            user_info = None
    return render_template('merged_home.html', user_info=user_info)

@app.route('/appointments')
def appointments():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        query = "SELECT * FROM doctor"
        cursor.execute(query)
        doctors = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template('index.html', doctors=doctors)
    except Exception as e:
        app.logger.error(f"Error loading doctors: {e}")
        return f"Error loading doctors: {e}", 500

def fetch_all_from_table(table_name):
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        query = f"SELECT * FROM {table_name}"
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        db.close()
        return results
    except Exception as e:
        app.logger.error(f"Error fetching {table_name}: {e}")
        return None

@app.route('/api/doctors')
def get_doctors():
    doctors = fetch_all_from_table('doctor')
    if doctors is None:
        return jsonify({"error": "Error fetching doctors"}), 500
    return jsonify(doctors), 200

@app.route('/api/patients')
def get_patients():
    patients = fetch_all_from_table('patient')
    if patients is None:
        return jsonify({"error": "Error fetching patients"}), 500
    return jsonify(patients), 200

@app.route('/api/rooms')
def get_rooms():
    rooms = fetch_all_from_table('room')
    if rooms is None:
        return jsonify({"error": "Error fetching rooms"}), 500
    return jsonify(rooms), 200

@app.route('/api/pharmacy')
def get_pharmacy():
    pharmacies = fetch_all_from_table('pharmacy')
    if pharmacies is None:
        return jsonify({"error": "Error fetching pharmacy"}), 500
    return jsonify(pharmacies), 200

@app.route('/api/bills')
def get_bills():
    bills = fetch_all_from_table('bills')
    if bills is None:
        return jsonify({"error": "Error fetching bills"}), 500
    return jsonify(bills), 200

from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from pytz import timezone as ZoneInfo  # fallback to pytz

@app.route('/api/appointments')
def get_appointments():
    appointments = fetch_all_from_table('appointments')
    if appointments is None:
        return jsonify({"error": "Error fetching appointments"}), 500

    # Convert datetime from UTC/GMT to IST
    ist_zone = ZoneInfo('Asia/Kolkata')
    for appointment in appointments:
        if 'datetime' in appointment and appointment['datetime']:
            # Parse datetime string if needed
            dt = appointment['datetime']
            if isinstance(dt, str):
                try:
                    dt_obj = datetime.fromisoformat(dt)
                except ValueError:
                    dt_obj = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
            else:
                dt_obj = dt
            # Assume dt_obj is in UTC, convert to IST
            dt_obj_utc = dt_obj.replace(tzinfo=ZoneInfo('UTC'))
            dt_obj_ist = dt_obj_utc.astimezone(ist_zone)
            appointment['datetime'] = dt_obj_ist.strftime('%Y-%m-%d %H:%M:%S')

    return jsonify(appointments), 200

def validate_required_fields(data, required_fields):
    return all(field in data and str(data[field]).strip() for field in required_fields)

@app.route('/api/patients/add', methods=['POST'])
def add_patient():
    try:
        data = request.get_json()
        if not validate_required_fields(data, ['name', 'gender', 'dob', 'mobile']):
            return jsonify({"error": "All fields are required"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        query = "INSERT INTO patient (name, gender, dob, mobile_no) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (data['name'], data['gender'], data['dob'], data['mobile']))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"message": "Patient added successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error adding patient: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/rooms/add', methods=['POST'])
def add_room():
    try:
        data = request.get_json()
        if not validate_required_fields(data, ['room_no', 'room_type', 'status', 'price', 'facilities']):
            return jsonify({"error": "All fields are required"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        query = """
        INSERT INTO room (room_no, room_type, status, price, facilities)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (data['room_no'], data['room_type'], data['status'], data['price'], data['facilities']))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"message": "Room added successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error adding room: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/bills/add', methods=['POST'])
def add_bill():
    try:
        data = request.get_json()
        if not validate_required_fields(data, ['patient_id', 'amount', 'name']):
            return jsonify({"error": "All fields are required"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        query = "INSERT INTO bills (patient_id, amount, name) VALUES (%s, %s, %s)"
        cursor.execute(query, (data['patient_id'], data['amount'], data['name']))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"message": "Bill added successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error adding bill: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/appointments/add', methods=['POST'])
def add_appointment():
    try:
        data = request.get_json()
        if not validate_required_fields(data, ['patient_id', 'doctor_id', 'datetime']):
            return jsonify({"error": "All fields are required"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        query = "INSERT INTO appointments (patient_id, doctor_id, datetime) VALUES (%s, %s, %s)"
        cursor.execute(query, (data['patient_id'], data['doctor_id'], data['datetime']))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"message": "Appointment added successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error adding appointment: {e}")
        return jsonify({"error": str(e)}), 500

import mysql.connector

# Add new table creation query for doctor_patient_room_assignment
def create_assignment_table():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctor_patient_room_assignment (
            assignment_id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            doctor_id INT NOT NULL,
            room_no INT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
            FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id),
            FOREIGN KEY (room_no) REFERENCES room(room_no)
        )
        """)
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        app.logger.error(f"Error creating assignment table: {e}")

# Add new table creation query for users table in MySQL
def create_users_table():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        app.logger.error(f"Error creating users table: {e}")

# Call the table creation functions on startup
create_assignment_table()
create_users_table()

@app.route('/api/assignments')
def get_assignments():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        query = """
        SELECT a.assignment_id, p.name AS patient_name, d.name AS doctor_name, r.room_no
        FROM doctor_patient_room_assignment a
        JOIN patient p ON a.patient_id = p.patient_id
        JOIN doctor d ON a.doctor_id = d.doctor_id
        JOIN room r ON a.room_no = r.room_no
        """
        cursor.execute(query)
        assignments = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(assignments), 200
    except Exception as e:
        app.logger.error(f"Error fetching assignments: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/assignments/add', methods=['POST'])
def add_assignment():
    try:
        data = request.get_json()
        if not all(k in data for k in ('patient_id', 'doctor_id', 'room_no')):
            return jsonify({"error": "All fields are required"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        query = """
        INSERT INTO doctor_patient_room_assignment (patient_id, doctor_id, room_no)
        VALUES (%s, %s, %s)
        """
        cursor.execute(query, (data['patient_id'], data['doctor_id'], data['room_no']))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"message": "Assignment added successfully"}), 200
    except Exception as e:
        app.logger.error(f"Error adding assignment: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)
