import requests

moodle_url = "http://localhost:8000/login/token.php"
rest_url = "http://localhost:8000/webservice/rest/server.php"

# Test login
try:
    res = requests.post(
        moodle_url,
        data={"username": "profesor1", "password": "profesor1", "service": "moodle_mobile_app"}
    )
    data = res.json()
    print("Login:", data)
    
    if "token" in data:
        token = data["token"]
        # Get site info
        res2 = requests.post(
            rest_url,
            data={"wstoken": token, "wsfunction": "core_webservice_get_site_info", "moodlewsrestformat": "json"}
        )
        info = res2.json()
        print("Site info:", info)
        
        userid = info.get("userid")
        if userid:
            # Get courses
            res3 = requests.post(
                rest_url,
                data={"wstoken": token, "wsfunction": "core_enrol_get_users_courses", "userid": userid, "moodlewsrestformat": "json"}
            )
            print("Courses:", res3.json())
except Exception as e:
    print("Error:", e)
