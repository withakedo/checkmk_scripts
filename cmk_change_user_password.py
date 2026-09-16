#!/usr/bin/env python3
"""Checkmk: Reset Password.

Input:  Username
Action:  Unlocks the user (if locked) and sets a random
          20-character password. No forced password change upon login.
Output:  Username + new password.
"""
import sys
import secrets
import string
import requests

# --- Config -------------------------------------------------------------
HOST   = "CMK_URL"
SITE   = "SITE_NAME"
USER   = "API_USER"
SECRET = "SECRET"

PW_LENGTH        = 20
ACTIVATE_CHANGES = True
# ------------------------------------------------------------------------


BASE = f"{HOST}/{SITE}/check_mk/api/v1"
 
sess = requests.Session()
sess.headers.update({
    "Authorization": f"Bearer {USER} {SECRET}",
    "Accept": "application/json",
})
 
 
def gen_password(n=PW_LENGTH):
    alphabet = string.ascii_letters + string.digits + "!@#$%*"
    return "".join(secrets.choice(alphabet) for _ in range(n))
 
 
def get_user(uid):
    r = sess.get(f"{BASE}/objects/user_config/{uid}")
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    return r.json().get("extensions", {}), r.headers.get("ETag")
 
 
def reset_password(uid, etag, password):
    body = {
        "auth_option": {
            "auth_type": "password",
            "password": password,
            "enforce_password_change": False,
        },
        "disable_login": False, # Unlock User
    }
    r = sess.put(
        f"{BASE}/objects/user_config/{uid}",
        headers={"If-Match": etag, "Content-Type": "application/json"},
        json=body,
    )
    r.raise_for_status()
 
 
def main():
    uid = sys.argv[1] if len(sys.argv) > 1 else input("Username: ").strip()
    if not uid:
        print("No Username given")
        sys.exit(1)
 
    ext, etag = get_user(uid)
    if ext is None:
        print(f"User '{uid}' does not exsist.")
        sys.exit(1)
 
    password = gen_password()
    reset_password(uid, etag, password)
 
    print()
    print(f"Username: {uid}")
    print(f"Password: {password}")
 
 
if __name__ == "__main__":
    main()
