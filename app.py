from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import pymysql
import os
import json
import base64
from werkzeug.security import generate_password_hash, check_password_hash
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response
)
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, AuthenticatorSelectionCriteria, UserVerificationRequirement

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_it_inventory_key_2026")

RP_ID = "it-inventory-system-ns6u.onrender.com"  # Your Render host domain
RP_NAME = "IT Inventory System"

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get("TIDB_HOST", "localhost"),
        user=os.environ.get("TIDB_USER", "root"),
        password=os.environ.get("TIDB_PASSWORD", ""),
        database=os.environ.get("TIDB_NAME", "test"),
        port=int(os.environ.get("TIDB_PORT", 4000)),
        ssl={'ssl': {}}
    )

# --- ROUTE PROTECTIONS ---
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('index.html', user=session.get('user'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# --- PASSWORD AUTHENTICATION ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name', '')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password required"}), 400

    pwd_hash = generate_password_hash(password)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO users (username, password_hash, full_name) VALUES (%s, %s, %s)",
                           (username, pwd_hash, full_name))
        conn.commit()
        return jsonify({"status": "success", "message": "Account created! You can now log in."})
    except Exception as e:
        return jsonify({"status": "error", "message": "Username already taken or database error"}), 400
    finally:
        conn.close()

@app.route('/api/login/password', methods=['POST'])
def login_password():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user'] = {"id": user['id'], "username": user['username'], "full_name": user['full_name']}
            return jsonify({"status": "success", "message": "Login successful!"})
        return jsonify({"status": "error", "message": "Invalid username or password"}), 401
    finally:
        conn.close()

# --- BIOMETRIC / FINGERPRINT WEBAUTHN ENDPOINTS ---
@app.route('/api/webauthn/register-options', methods=['POST'])
def webauthn_register_options():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = session['user']
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=str(user['id']).encode('utf-8'),
        user_name=user['username'],
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        )
    )
    session['register_challenge'] = options.challenge
    return options.json()

@app.route('/api/inventory', methods=['GET', 'POST'])
def handle_inventory():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data = request.json
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO it_inventory (
                    it_business_name, system_unit, issued_company_owned, employee_name,
                    date_visited, it_code, model_brand, ram, storage_capacity,
                    serial_hdd_all, description_specs, date_issued, unit_age,
                    depreciation_date, findings, fa_number, mac_address,
                    action_taken, remarks, tech_support
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    it_business_name=%s, system_unit=%s, issued_company_owned=%s, employee_name=%s,
                    date_visited=%s, model_brand=%s, ram=%s, storage_capacity=%s,
                    serial_hdd_all=%s, description_specs=%s, date_issued=%s, unit_age=%s,
                    depreciation_date=%s, findings=%s, fa_number=%s, mac_address=%s,
                    action_taken=%s, remarks=%s, tech_support=%s
                """
                def p_date(d): return d if d else None
                vals = (
                    data.get('it_business_name'), data.get('system_unit'), data.get('issued_company_owned'), data.get('employee_name'),
                    p_date(data.get('date_visited')), data.get('it_code'), data.get('model_brand'), data.get('ram'), data.get('storage_capacity'),
                    data.get('serial_hdd_all'), data.get('description_specs'), p_date(data.get('date_issued')), data.get('unit_age'),
                    p_date(data.get('depreciation_date')), data.get('findings'), data.get('fa_number'), data.get('mac_address'),
                    data.get('action_taken'), data.get('remarks'), data.get('tech_support'),
                    data.get('it_business_name'), data.get('system_unit'), data.get('issued_company_owned'), data.get('employee_name'),
                    p_date(data.get('date_visited')), data.get('model_brand'), data.get('ram'), data.get('storage_capacity'),
                    data.get('serial_hdd_all'), data.get('description_specs'), p_date(data.get('date_issued')), data.get('unit_age'),
                    p_date(data.get('depreciation_date')), data.get('findings'), data.get('fa_number'), data.get('mac_address'),
                    data.get('action_taken'), data.get('remarks'), data.get('tech_support')
                )
                cursor.execute(sql, vals)
            conn.commit()
            return jsonify({"status": "success", "message": "Saved successfully!"})
        else:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM it_inventory ORDER BY updated_at DESC")
                recs = cursor.fetchall()
                for r in recs:
                    for df in ['date_visited', 'date_issued', 'depreciation_date']:
                        if r[df]: r[df] = str(r[df])
            return jsonify(recs)
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
