# app.py
# This is the main file for our Python backend using the Flask framework.

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import json
import requests # Used for making HTTP requests to the Gemini API

# --- APP SETUP ---
app = Flask(__name__, static_folder=None)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- DATABASE CONFIGURATION ---
DATABASE_FILE = 'smartq.db'

def get_db_connection():
    """ Creates a connection to the SQLite database. """
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

def create_tables():
    """ Creates the necessary database tables with a 'status' column. """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if 'patients' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patients';")
    if cursor.fetchone() is None:
        print("Creating 'patients' table...")
        cursor.execute('''
            CREATE TABLE patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                issue TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                status TEXT DEFAULT 'Waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    # Check if 'restaurants' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='restaurants';")
    if cursor.fetchone() is None:
        print("Creating 'restaurants' table...")
        cursor.execute('''
            CREATE TABLE restaurants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                party_size INTEGER NOT NULL,
                reservation_time TEXT NOT NULL,
                status TEXT DEFAULT 'Waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    # Check if 'banks' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='banks';")
    if cursor.fetchone() is None:
        print("Creating 'banks' table...")
        cursor.execute('''
            CREATE TABLE banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                service TEXT NOT NULL,
                status TEXT DEFAULT 'Waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    conn.commit()
    conn.close()
    print("Database tables checked/created successfully.")

# --- API ROUTES (ENDPOINTS) ---

@app.route('/')
def index():
    """ A simple route to check if the server is running. """
    return "Welcome to the SMART Q Python Backend!"

# --- GENERIC ROUTES FOR ALL TYPES ---

@app.route('/api/<string:record_type>', methods=['GET'])
def get_records(record_type):
    """ API endpoint to get all records of a specific type. """
    if record_type not in ['patients', 'restaurants', 'banks']:
        return jsonify({'error': 'Invalid record type'}), 404
    
    conn = get_db_connection()
    records = conn.execute(f'SELECT * FROM {record_type} ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in records])

@app.route('/api/<string:record_type>/<int:record_id>', methods=['DELETE'])
def delete_record(record_type, record_id):
    """ API endpoint to delete a specific record. """
    if record_type not in ['patients', 'restaurants', 'banks']:
        return jsonify({'error': 'Invalid record type'}), 404
        
    conn = get_db_connection()
    conn.execute(f'DELETE FROM {record_type} WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Record deleted successfully'})

@app.route('/api/<string:record_type>/<int:record_id>', methods=['PUT'])
def update_record(record_type, record_id):
    """ API endpoint to update a specific record. """
    if record_type not in ['patients', 'restaurants', 'banks']:
        return jsonify({'error': 'Invalid record type'}), 404
    
    data = request.get_json()
    conn = get_db_connection()
    
    if record_type == 'patients':
        conn.execute('UPDATE patients SET name = ?, issue = ?, appointment_date = ? WHERE id = ?',
                     (data['name'], data['issue'], data['appointmentDate'], record_id))
    elif record_type == 'restaurants':
        conn.execute('UPDATE restaurants SET name = ?, party_size = ?, reservation_time = ? WHERE id = ?',
                     (data['name'], data['partySize'], data['reservationTime'], record_id))
    elif record_type == 'banks':
        conn.execute('UPDATE banks SET name = ?, service = ? WHERE id = ?',
                     (data['name'], data['service'], record_id))

    conn.commit()
    conn.close()
    return jsonify({'message': 'Record updated successfully'})


@app.route('/api/<string:record_type>/<int:record_id>/status', methods=['PATCH'])
def update_status(record_type, record_id):
    """ API endpoint to update the status of a specific record. """
    if record_type not in ['patients', 'restaurants', 'banks']:
        return jsonify({'error': 'Invalid record type'}), 404
    
    data = request.get_json()
    new_status = data.get('status')
    if not new_status:
        return jsonify({'error': 'Status is required'}), 400
        
    conn = get_db_connection()
    conn.execute(f'UPDATE {record_type} SET status = ? WHERE id = ?', (new_status, record_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Status updated successfully'})

# --- SPECIFIC POST ROUTES ---

@app.route('/api/patients', methods=['POST'])
def add_patient():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('INSERT INTO patients (name, issue, appointment_date) VALUES (?, ?, ?)',
                 (data['name'], data['issue'], data['appointmentDate']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Patient added successfully'}), 201

@app.route('/api/restaurants', methods=['POST'])
def add_restaurant():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('INSERT INTO restaurants (name, party_size, reservation_time) VALUES (?, ?, ?)',
                 (data['name'], data['partySize'], data['reservationTime']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Reservation added successfully'}), 201

@app.route('/api/banks', methods=['POST'])
def add_bank_customer():
    data = request.get_json()
    conn = get_db_connection()
    conn.execute('INSERT INTO banks (name, service) VALUES (?, ?)',
                 (data['name'], data['service']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Bank customer added successfully'}), 201
    
# --- GEMINI AI ROUTE ---
@app.route('/api/generate-ai-suggestion', methods=['POST'])
def generate_ai_suggestion():
    """
    API endpoint to get an AI-powered suggestion from the Gemini API.
    """
    data = request.get_json()
    prompt_type = data.get('type')
    input_text = data.get('text')
    context_text = data.get('context') # For name, etc.

    if not prompt_type or not input_text:
        return jsonify({'error': 'Type and text are required'}), 400

    # Construct the prompt based on the type
    prompt = ""
    if prompt_type == 'triage':
        prompt = f"Generate brief triage notes for a patient presenting with the following issue: \"{input_text}\". Focus on key questions to ask and potential immediate assessments. Format as a short, professional list."
    elif prompt_type == 'themes':
        prompt = f"Suggest 3 creative and fun restaurant themes for a party of {input_text}. Provide a short, catchy name and a one-sentence description for each theme."
    elif prompt_type == 'email':
        prompt = f"Draft a brief, professional, and friendly follow-up email to a bank customer named {context_text or 'Valued Customer'} regarding their request for the following service: \"{input_text}\". Sign off as \"Your Bank Team\"."
    else:
        return jsonify({'error': 'Invalid suggestion type'}), 400

    # Call the Gemini API
    try:
        api_key = "" # Leave empty
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        
        response = requests.post(api_url, json=payload)
        response.raise_for_status() # Raise an exception for bad status codes
        
        result = response.json()
        
        if result.get('candidates'):
            suggestion = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'suggestion': suggestion})
        else:
            return jsonify({'error': 'No content received from AI API.'}), 500
            
    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        return jsonify({'error': f'Could not connect to AI service: {e}'}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({'error': 'An unexpected error occurred while generating suggestion.'}), 500


# --- RUN THE APPLICATION ---
if __name__ == '__main__':
    create_tables()
    app.run(debug=True, port=5000)
