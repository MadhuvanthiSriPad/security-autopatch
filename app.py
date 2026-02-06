"""
Vulnerable Flask application for CodeQL testing.
Contains intentional security vulnerabilities that CodeQL will detect.
"""

from flask import Flask, request, render_template_string
import sqlite3
import os
import subprocess
import pickle
import base64

app = Flask(__name__)

# VULNERABILITY 1: Hardcoded secret
DATABASE_PASSWORD = "super_secret_password_123"
API_KEY = "sk-1234567890abcdef"


def get_db_connection():
    conn = sqlite3.connect('users.db')
    return conn


# VULNERABILITY 2: SQL Injection
@app.route('/user')
def get_user():
    user_id = request.args.get('id')
    conn = get_db_connection()
    cursor = conn.cursor()
    # Directly interpolating user input into SQL query
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    return str(result)


# VULNERABILITY 3: Cross-Site Scripting (XSS)
@app.route('/greet')
def greet():
    name = request.args.get('name', 'Guest')
    # Directly rendering user input without escaping
    return render_template_string(f"<h1>Hello, {name}!</h1>")


# VULNERABILITY 4: Command Injection
@app.route('/ping')
def ping():
    host = request.args.get('host')
    # Directly passing user input to shell command
    result = subprocess.check_output(f"ping -c 1 {host}", shell=True)
    return result


# VULNERABILITY 5: Path Traversal
@app.route('/read')
def read_file():
    filename = request.args.get('file')
    # No validation of file path
    filepath = os.path.join('/var/data/', filename)
    with open(filepath, 'r') as f:
        return f.read()


# VULNERABILITY 6: Insecure Deserialization
@app.route('/load')
def load_data():
    data = request.args.get('data')
    # Deserializing untrusted data
    decoded = base64.b64decode(data)
    obj = pickle.loads(decoded)
    return str(obj)


# VULNERABILITY 7: Weak Cryptography
import hashlib

@app.route('/hash')
def hash_password():
    password = request.args.get('password')
    # Using weak MD5 hash
    hashed = hashlib.md5(password.encode()).hexdigest()
    return hashed


if __name__ == '__main__':
    app.run(debug=True)
