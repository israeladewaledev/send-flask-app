import urllib.request
import urllib.parse
import json

def test_session(role, id_number):
    print(f"\n--- Testing complete flow for {role} ({id_number}) ---")
    
    # Login
    url = "http://127.0.0.1:5001/api/login"
    data = json.dumps({"role": role, "id_number": id_number, "password": "password123"}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    cookie = None
    try:
        with urllib.request.urlopen(req) as response:
            cookie = response.getheader('Set-Cookie')
            print(f"Login success: {json.loads(response.read().decode())}")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    routes = [
        "/admin/home", 
        "/admin/records", 
        "/admin/view_profile/NUCS20210452", 
        "/staff/home?unit=library", 
        "/staff/clearance?unit=library", 
        "/staff/inventory?unit=library", 
        "/staff/finance?unit=accounts", 
        "/staff/residents?unit=hostel", 
        "/staff/amenities?unit=services",
        "/student/home",
        "/student/clearance",
        "/student/complaints",
        "/student/profile"
    ]

    for route in routes:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:5001{route}")
            if cookie: req.add_header('Cookie', cookie)
            with urllib.request.urlopen(req) as response:
                print(f"{route}: {response.status}")
        except urllib.error.HTTPError as e:
            print(f"{route}: {e.code}  <--- ERROR")
        except Exception as e:
            print(f"{route}: {e}")

test_session("student", "NU/CS/2021/452")
test_session("staff_library", "STAFF-LIB-01")
