import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file
load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            print("WARNING: Supabase URL or Key is missing. Check your .env file.")
            self.client = None
        else:
            self.client: Client = create_client(self.url, self.key)

    def get_user_by_id_number(self, id_number):
        """Fetch a user and their role by their ID number (Matric No or Staff ID)"""
        if not self.client: return None
        
        response = self.client.table("portal_users").select("*").eq("user_id_number", id_number).execute()
        return response.data[0] if response.data else None

    def get_student_profile(self, user_id):
        """Fetch the full profile for a student"""
        if not self.client: return None
        
        response = self.client.table("student_profiles").select("*").eq("id", user_id).execute()
        return response.data[0] if response.data else None

    def get_clearance_status(self, student_id):
        """Fetch the clearance status for all units for a given student"""
        if not self.client: return []
        
        response = self.client.table("clearance_records").select("*").eq("student_id", student_id).execute()
        return response.data

    def get_all_pending_clearances(self, unit_key):
        """Fetch all students and their clearance status for a specific unit"""
        if not self.client: return []
        
        # We want to see all students and their status for this specific unit
        # In a real app, this would be a join between portal_users (students) and clearance_records
        response = self.client.table("student_profiles").select("*, portal_users(id, user_id_number)").execute()
        students = response.data
        
        status_response = self.client.table("clearance_records").select("*").eq("unit_key", unit_key).execute()
        statuses = {s['student_id']: s for s in status_response.data}
        
        # Merge status into student profile
        for student in students:
            student['clearance_status'] = statuses.get(student['portal_users']['id'], {"status": "pending"})
            
        return students

    def update_clearance_status(self, student_id, unit_key, status, reason=None):
        """Update the clearance status for a specific unit"""
        if not self.client: return False
        
        # Check if record exists
        existing = self.client.table("clearance_records").select("*").eq("student_id", student_id).eq("unit_key", unit_key).execute()
        
        data = {
            "student_id": student_id,
            "unit_key": unit_key,
            "status": status,
            "rejection_reason": reason,
            "updated_at": "now()"
        }
        
        if existing.data:
            response = self.client.table("clearance_records").update(data).eq("student_id", student_id).eq("unit_key", unit_key).execute()
        else:
            response = self.client.table("clearance_records").insert(data).execute()
            
        return len(response.data) > 0

    def get_student_complaints(self, student_id):
        """Fetch all complaints for a specific student"""
        if not self.client: return []
        
        response = self.client.table("student_complaints").select("*").eq("student_id", student_id).order("created_at", desc=True).execute()
        return response.data

    def get_complaints(self, unit_key=None):
        """Fetch complaints, optionally filtered by unit_key"""
        if not self.client: return []
        
        query = self.client.table("student_complaints").select("*, portal_users(user_id_number), student_profiles(full_name)")
        if unit_key:
            query = query.eq("target_unit", unit_key)
            
        response = query.eq("status", "open").execute()
        return response.data

    def resolve_complaint(self, complaint_id, note):
        """Mark a complaint as resolved with a note"""
        if not self.client: return False
        
        response = self.client.table("student_complaints").update({
            "status": "resolved",
            "resolution_note": note
        }).eq("id", complaint_id).execute()
        
        return len(response.data) > 0

    def create_complaint(self, student_id, subject, message, target_unit):
        """Create a new complaint ticket"""
        if not self.client: return False
        
        response = self.client.table("student_complaints").insert({
            "student_id": student_id,
            "subject": subject,
            "message": message,
            "target_unit": target_unit
        }).execute()
        
        return len(response.data) > 0

    # --- Phase 6: Thesis Alignment Additions ---

    def log_activity(self, user_id, action_type, details=None):
        """Record an activity in the audit logs"""
        if not self.client: return False
        try:
            self.client.table("audit_logs").insert({
                "user_id": user_id,
                "action_type": action_type,
                "details": details or {}
            }).execute()
            return True
        except Exception as e:
            print(f"Failed to log activity: {e}")
            return False

    def get_audit_logs(self, limit=50):
        """Fetch recent system activity logs"""
        if not self.client: return []
        response = self.client.table("audit_logs").select("*, portal_users(user_id_number, role)").order("created_at", desc=True).limit(limit).execute()
        return response.data

    def create_announcement(self, title, content, author_id):
        """Create a new system announcement"""
        if not self.client: return False
        response = self.client.table("announcements").insert({
            "title": title,
            "content": content,
            "created_by": author_id
        }).execute()
        return len(response.data) > 0

    def get_active_announcements(self):
        """Fetch all active announcements"""
        if not self.client: return []
        response = self.client.table("announcements").select("*, portal_users(user_id_number)").eq("is_active", True).order("created_at", desc=True).execute()
        return response.data

    def save_student_document(self, student_id, document_name, file_path):
        """Save a new student document record"""
        if not self.client: return False
        response = self.client.table("student_documents").insert({
            "student_id": student_id,
            "document_name": document_name,
            "file_path": file_path
        }).execute()
        return len(response.data) > 0

    def get_student_documents(self, student_id):
        """Fetch documents uploaded by a student"""
        if not self.client: return []
        response = self.client.table("student_documents").select("*").eq("student_id", student_id).order("uploaded_at", desc=True).execute()
        return response.data

    # --- Metrics & Dashboard Stats ---

    def get_admin_stats(self):
        """Fetch high-level statistics for the admin dashboard"""
        if not self.client: return {"total_students": 0, "pending_clearances": 0, "cleared_today": 0, "open_complaints": 0, "weekly_cleared": 0, "monthly_cleared": 0}
        
        from datetime import datetime, timedelta
        
        # Total students
        try:
            total_res = self.client.table("portal_users").select("id", count="exact").eq("role", "student").execute()
            total_students = total_res.count or 0
        except:
            total_students = 0
        
        # Pending and time-based clearances
        try:
            clr_res = self.client.table("clearance_records").select("status, updated_at").execute()
            records = clr_res.data
        except:
            records = []
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        pending = 0; cleared_today = 0; weekly = 0; monthly = 0
        for r in records:
            if r["status"] == "pending": pending += 1
            if r["status"] == "cleared":
                try:
                    dt_str = r['updated_at'].split('+')[0].split('.')[0]
                    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                    if dt >= today_start: cleared_today += 1
                    if dt >= week_ago: weekly += 1
                    if dt >= month_ago: monthly += 1
                except:
                    pass
        
        # Open complaints
        try:
            comp_res = self.client.table("student_complaints").select("id", count="exact").eq("status", "open").execute()
            open_complaints = comp_res.count or 0
        except:
            open_complaints = 0
                
        return {
            "total_students": total_students,
            "pending_clearances": pending,
            "cleared_today": cleared_today,
            "open_complaints": open_complaints,
            "weekly_cleared": weekly,
            "monthly_cleared": monthly
        }

    def get_staff_stats(self, unit_key):
        """Fetch statistics for a specific staff unit"""
        if not self.client: return {"pending": 0, "cleared": 0, "total_requests": 0}
        
        response = self.client.table("clearance_records").select("status").eq("unit_key", unit_key).execute()
        records = response.data
        
        pending = sum(1 for r in records if r["status"] == "pending")
        cleared = sum(1 for r in records if r["status"] == "cleared")
        
        return {"pending": pending, "cleared": cleared, "total_requests": len(records)}

    def get_all_student_records(self):
        """Fetch all students with their total clearance progress"""
        if not self.client: return []
        
        profiles_res = self.client.table("student_profiles").select("*").execute()
        clearance_res = self.client.table("clearance_records").select("student_id, status").execute()
        
        clearances = {}
        for r in clearance_res.data:
            sid = r["student_id"]
            if sid not in clearances: clearances[sid] = []
            clearances[sid].append(r["status"])
            
        students = []
        for p in profiles_res.data:
            sid = p["id"]
            user_clearances = clearances.get(sid, [])
            cleared_count = sum(1 for s in user_clearances if s == "cleared")
            
            if cleared_count == 8: status = "Completed"
            elif len(user_clearances) > 0: status = "In Progress"
            else: status = "Pending"
            
            p["cleared_count"] = cleared_count
            p["clearance_status_text"] = status
            students.append(p)
            
        return students

db = DatabaseManager()
