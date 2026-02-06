import base64
import json
import os
import sqlite3
import tempfile
import unittest

from app import app


class TestSQLInjectionFix(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.db_path = "users.db"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("INSERT OR IGNORE INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT OR IGNORE INTO users (id, name) VALUES (2, 'Bob')")
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_normal_query(self):
        response = self.client.get("/user?id=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Alice", response.data.decode())

    def test_sql_injection_attempt(self):
        response = self.client.get("/user?id=1 OR 1=1")
        data = response.data.decode()
        self.assertNotIn("Bob", data)


class TestPathTraversalFix(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_path_traversal_blocked(self):
        response = self.client.get("/read?file=../../etc/passwd")
        self.assertIn(response.status_code, [400, 404, 500])


class TestDeserializationFix(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_valid_json_data(self):
        payload = base64.b64encode(json.dumps({"key": "value"}).encode()).decode()
        response = self.client.get(f"/load?data={payload}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("key", response.data.decode())

    def test_invalid_data_rejected(self):
        import pickle
        malicious = base64.b64encode(pickle.dumps({"test": "data"})).decode()
        response = self.client.get(f"/load?data={malicious}")
        self.assertNotEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
