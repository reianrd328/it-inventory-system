from flask import Flask, request, jsonify, render_template
import pymysql
import os

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get("TIDB_HOST", "localhost"),
        user=os.environ.get("TIDB_USER", "root"),
        password=os.environ.get("TIDB_PASSWORD", ""),
        database=os.environ.get("TIDB_NAME", "test"),
        port=int(os.environ.get("TIDB_PORT", 4000)),
        ssl={'ssl': {}} # Required for TiDB Serverless SSL connections
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/inventory', methods=['POST'])
def save_inventory():
    data = request.json
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
            INSERT INTO it_inventory (
                it_business_name, system_unit, issued_company_owned, employee_name,
                date_visited, it_code, model_brand, ram, storage_capacity,
                serial_hdd_all, description_specs, date_issued, unit_age,
                depreciation_date, findings, fa_number, mac_address,
                action_taken, remarks, tech_support
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON DUPLICATE KEY UPDATE
                it_business_name=%s, system_unit=%s, issued_company_owned=%s, employee_name=%s,
                date_visited=%s, model_brand=%s, ram=%s, storage_capacity=%s,
                serial_hdd_all=%s, description_specs=%s, date_issued=%s, unit_age=%s,
                depreciation_date=%s, findings=%s, fa_number=%s, mac_address=%s,
                action_taken=%s, remarks=%s, tech_support=%s
            """
            
            # Helper function to handle empty date inputs
            def parse_date(d): 
                return d if d else None

            values = (
                data.get('it_business_name'), data.get('system_unit'), data.get('issued_company_owned'), data.get('employee_name'),
                parse_date(data.get('date_visited')), data.get('it_code'), data.get('model_brand'), data.get('ram'), data.get('storage_capacity'),
                data.get('serial_hdd_all'), data.get('description_specs'), parse_date(data.get('date_issued')), data.get('unit_age'),
                parse_date(data.get('depreciation_date')), data.get('findings'), data.get('fa_number'), data.get('mac_address'),
                data.get('action_taken'), data.get('remarks'), data.get('tech_support'),
                # Values for ON DUPLICATE KEY UPDATE:
                data.get('it_business_name'), data.get('system_unit'), data.get('issued_company_owned'), data.get('employee_name'),
                parse_date(data.get('date_visited')), data.get('model_brand'), data.get('ram'), data.get('storage_capacity'),
                data.get('serial_hdd_all'), data.get('description_specs'), parse_date(data.get('date_issued')), data.get('unit_age'),
                parse_date(data.get('depreciation_date')), data.get('findings'), data.get('fa_number'), data.get('mac_address'),
                data.get('action_taken'), data.get('remarks'), data.get('tech_support')
            )
            cursor.execute(sql, values)
        connection.commit()
        return jsonify({"status": "success", "message": "Record saved successfully!"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        connection.close()

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM it_inventory ORDER BY updated_at DESC")
            records = cursor.fetchall()
            # Convert date objects to string format for clean JSON serialization
            for r in records:
                for date_field in ['date_visited', 'date_issued', 'depreciation_date']:
                    if r[date_field]:
                        r[date_field] = str(r[date_field])
        return jsonify(records)
    finally:
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)
