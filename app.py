from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from db_manager import db
import os
from dotenv import load_dotenv

from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "nile_university_secret_2026")
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB max

# --- Constants ---
UNIT_NAMES = {
    'library': 'Library Services',
    'accounts': 'Account Unit',
    'hostel': 'Hostel Unit',
    'services': 'Student Services',
    'division': 'Academic Division',
    'store': 'Central Store',
    'department': 'Academic Department',
    'honoris': 'Honoris 21C Skills Program'
}

# --- Authentication Logic ---
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    id_number = data.get('id_number')
    role = data.get('role')
    
    user = db.get_user_by_id_number(id_number)
    if user:
        if user['role'] != role and not (role.startswith('staff') and user['role'] == 'staff'):
            return jsonify({"success": False, "message": "Role mismatch."}), 401
            
        session['user_id'] = user['id']
        session['user_id_number'] = user['user_id_number']
        session['role'] = user['role']
        if user['unit_key']: session['staff_unit'] = user['unit_key']
        
        db.log_activity(user['id'], "login", {"role": user['role']})
        
        return jsonify({"success": True, "role": user['role'], "unit": user['unit_key']})
    return jsonify({"success": False, "message": "Invalid credentials."}), 404

@app.route('/api/student/initiate_clearance', methods=['POST'])
def api_initiate_clearance():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"success": False}), 401
    
    success = True
    for unit in UNIT_NAMES.keys():
        if not db.update_clearance_status(user_id, unit, 'pending'):
            success = False
            
    if success:
        db.log_activity(user_id, "initiated_clearance")
        
    return jsonify({"success": success})

# --- Student Routes ---
@app.route('/student/home')
def student_home():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('index'))
    
    profile = db.get_student_profile(user_id)
    status_list = db.get_clearance_status(user_id)
    cleared_count = len([s for s in status_list if s['status'] == 'cleared'])
    progress = int((cleared_count / 8) * 100) if status_list else 0
    
    announcements = db.get_active_announcements()
    
    return render_template('student/home.html', profile=profile, progress=progress, announcements=announcements)

@app.route('/student/clearance')
def student_clearance():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('index'))
    
    records = db.get_clearance_status(user_id)
    # Convert to dict for easier template lookups: { 'library': 'cleared', ... }
    status_map = {r['unit_key']: r for r in records}
    
    return render_template('student/clearance.html', status_map=status_map, unit_names=UNIT_NAMES)

@app.route('/student/complaints')
def student_complaints():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('index'))
    
    # We need a new db method for this
    complaints = db.get_student_complaints(user_id)
    return render_template('student/complaints.html', complaints=complaints, unit_names=UNIT_NAMES)

@app.route('/student/profile')
def student_profile():
    user_id = session.get('user_id')
    if not user_id: return redirect(url_for('index'))
    profile = db.get_student_profile(user_id)
    documents = db.get_student_documents(user_id)
    return render_template('student/profile.html', profile=profile, documents=documents)

@app.route('/api/student/upload_document', methods=['POST'])
def api_upload_document():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    if 'document' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400
        
    file = request.files['document']
    doc_name = request.form.get('document_name', 'Uploaded Document')
    
    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"}), 400
        
    if file:
        filename = secure_filename(f"{user_id}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        db.save_student_document(user_id, doc_name, f"/static/uploads/{filename}")
        db.log_activity(user_id, "uploaded_document", {"document_name": doc_name})
        
        return jsonify({"success": True})

# --- Staff Routes ---
def get_staff_context():
    unit_key = request.args.get('unit', session.get('staff_unit'))
    if not unit_key: return None, None
    unit_info = {"name": unit_key.replace('_', ' ').title(), "id": f"S-{unit_key.upper()[:3]}"}
    return unit_key, unit_info

@app.route('/api/staff/update_clearance', methods=['POST'])
def api_update_clearance():
    data = request.json
    student_id = data.get('student_id')
    unit_key = data.get('unit_key')
    status = data.get('status')
    reason = data.get('reason')
    
    if db.update_clearance_status(student_id, unit_key, status, reason):
        db.log_activity(session.get('user_id'), "updated_clearance", {"student_id": student_id, "unit": unit_key, "status": status})
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Database update failed."}), 500

@app.route('/api/student/complaint', methods=['POST'])
def api_create_complaint():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.json
    success = db.create_complaint(
        user_id, 
        data.get('subject'), 
        data.get('message'), 
        data.get('target_unit')
    )
    if success:
        db.log_activity(user_id, "submitted_complaint", {"target_unit": data.get('target_unit')})
    return jsonify({"success": success})

@app.route('/api/staff/resolve_complaint', methods=['POST'])
def api_resolve_complaint():
    data = request.json
    success = db.resolve_complaint(data.get('complaint_id'), data.get('note'))
    if success:
        db.log_activity(session.get('user_id'), "resolved_complaint", {"complaint_id": data.get('complaint_id')})
    return jsonify({"success": success})

@app.route('/staff/home')
def staff_home():
    unit_key, unit_info = get_staff_context()
    if not unit_key: return redirect(url_for('index'))
    stats = db.get_staff_stats(unit_key)
    return render_template('staff/home.html', unit_key=unit_key, unit=unit_info, stats=stats)

@app.route('/staff/clearance')
def staff_clearance():
    unit_key, unit_info = get_staff_context()
    if not unit_key: return redirect(url_for('index'))
    students = db.get_all_pending_clearances(unit_key)
    return render_template('staff/clearance.html', unit_key=unit_key, unit=unit_info, students=students)

@app.route('/staff/academic')
def staff_academic():
    unit_key, unit_info = get_staff_context()
    if not unit_key: return redirect(url_for('index'))
    return render_template('staff/academic.html', unit_key=unit_key, unit=unit_info)

@app.route('/staff/complaints')
def staff_complaints():
    unit_key, unit_info = get_staff_context()
    if not unit_key: return redirect(url_for('index'))
    complaints = db.get_complaints(unit_key)
    return render_template('staff/complaints.html', unit_key=unit_key, unit=unit_info, complaints=complaints)

# --- Supplementary Pages ---
@app.route('/staff/inventory')
def staff_inventory():
    unit_key, unit_info = get_staff_context()
    return render_template('staff/inventory.html', unit_key=unit_key, unit=unit_info)

@app.route('/staff/finance')
def staff_finance():
    unit_key, unit_info = get_staff_context()
    return render_template('staff/finance.html', unit_key=unit_key, unit=unit_info)

@app.route('/staff/residents')
def staff_residents():
    unit_key, unit_info = get_staff_context()
    return render_template('staff/residents.html', unit_key=unit_key, unit=unit_info)

@app.route('/staff/amenities')
def staff_amenities():
    unit_key, unit_info = get_staff_context()
    return render_template('staff/amenities.html', unit_key=unit_key, unit=unit_info)

@app.route('/staff/skills')
def staff_skills():
    unit_key, unit_info = get_staff_context()
    return render_template('staff/skills.html', unit_key=unit_key, unit=unit_info)

# --- Admin Routes ---
@app.route('/admin/home')
def admin_home():
    announcements = db.get_active_announcements()
    logs = db.get_audit_logs(limit=20)
    stats = db.get_admin_stats()
    return render_template('admin/home.html', announcements=announcements, logs=logs, stats=stats)

@app.route('/api/admin/announcement', methods=['POST'])
def api_create_announcement():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"success": False}), 401
    data = request.json
    success = db.create_announcement(data.get('title'), data.get('content'), user_id)
    if success: db.log_activity(user_id, "created_announcement", {"title": data.get('title')})
    return jsonify({"success": success})

@app.route('/admin/records')
def admin_records():
    students = db.get_all_student_records()
    return render_template('admin/records.html', students=students)

@app.route('/admin/view_profile/<id_literal>')
def admin_view_profile(id_literal):
    # Look up matching user: matric IDs may have slashes stripped from the URL
    # Try direct match first, then look through all students
    user = db.get_user_by_id_number(id_literal)
    if not user:
        # Try to find by stripped matric (slashes removed)
        all_students = db.get_all_student_records()
        for s in all_students:
            if s.get('matric_no', '').replace('/', '') == id_literal:
                user = db.get_user_by_id_number(s['matric_no'])
                break

    profile = None
    documents = []
    clearance_summary = {"cleared": 0, "total": 8}

    if user:
        profile = db.get_student_profile(user['id'])
        documents = db.get_student_documents(user['id'])
        records = db.get_clearance_status(user['id'])
        clearance_summary["cleared"] = sum(1 for r in records if r['status'] == 'cleared')

    return render_template('admin/view_profile.html',
        student_id=id_literal,
        profile=profile,
        documents=documents,
        clearance_summary=clearance_summary)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
