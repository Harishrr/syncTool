import os
import sys
import unittest
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure app is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app.database as database
from app.main import app
from app.models import User, Job, JobRun, SystemLog
from app.auth.security import hash_password, verify_password
from app.auth.totp import generate_totp_secret, get_provisioning_uri, generate_qr_code_base64, verify_totp_code
import pyotp
from app.engines.robocopy import RobocopyEngine
from app.services import job_service, user_service

class TestSyncTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.Base.metadata.create_all(bind=database.engine)
        db = database.SessionLocal()
        db.query(JobRun).delete()
        db.query(Job).delete()
        db.query(SystemLog).delete()
        db.query(User).filter(User.username != "admin").delete()
        db.commit()
        user_service.seed_initial_admin(db)
        db.close()

        cls.client = TestClient(app)

        # Setup test folders for Robocopy
        cls.test_dir = Path("./test_sandbox").resolve()
        cls.test_src = cls.test_dir / "source"
        cls.test_dst = cls.test_dir / "destination"
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
        cls.test_src.mkdir(parents=True, exist_ok=True)
        
        # Create dummy test files
        for i in range(5):
            (cls.test_src / f"file_{i}.txt").write_text(f"Sample data payload {i} for testing sync tool.")

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_database_and_admin_seed(self):
        db = database.SessionLocal()
        admin = db.query(User).filter(User.username == "admin").first()
        self.assertIsNotNone(admin, "Admin user should exist in database")
        self.assertEqual(admin.role, "admin")
        self.assertTrue(verify_password("Admin@12345", admin.hashed_password))
        db.close()

    def test_02_google_authenticator_totp(self):
        secret = generate_totp_secret()
        self.assertTrue(len(secret) >= 16)
        uri = get_provisioning_uri("testuser", secret)
        self.assertTrue(uri.startswith("otpauth://totp/SyncTool:testuser"))
        qr_b64 = generate_qr_code_base64(uri)
        self.assertTrue(qr_b64.startswith("data:image/png;base64,"))
        
        # Generate valid code using pyotp and test verification
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        self.assertTrue(verify_totp_code(secret, current_code))
        self.assertFalse(verify_totp_code(secret, "000000"))

    def test_03_robocopy_engine_execution(self):
        progress_updates = []
        def on_prog(p, f, s, bc, tb):
            progress_updates.append((p, f, s))

        if self.test_dst.exists():
            shutil.rmtree(self.test_dst, ignore_errors=True)

        engine = RobocopyEngine(
            job_id=999,
            source=str(self.test_src),
            destination=str(self.test_dst),
            progress_callback=on_prog
        )
        result = engine.run()
        self.assertEqual(result["status"], "success")
        self.assertLessEqual(result["exit_code"], 7)
        # Verify files actually copied to destination
        copied_files = list(self.test_dst.glob("*.txt"))
        self.assertEqual(len(copied_files), 5)

    def test_04_csv_import_service(self):
        csv_text = (
            "name,transfer_type,source_path,dest_path,host,port,remote_username,remote_password\n"
            f"CSV Test Job,robocopy,{self.test_src},{self.test_dst},,,,\n"
            "CSV SFTP Job,sftp,C:\\test_src,/remote/path,192.168.1.1,22,root,pass\n"
        )
        db = database.SessionLocal()
        res = job_service.import_jobs_from_csv(db, csv_text)
        self.assertEqual(res["imported_count"], 2)
        self.assertEqual(len(res["errors"]), 0)
        
        # Verify in DB
        imported_job = db.query(Job).filter(Job.name == "CSV Test Job").first()
        self.assertIsNotNone(imported_job)
        self.assertEqual(imported_job.transfer_type, "robocopy")
        db.close()

    def test_05_api_login_and_me(self):
        # Test valid login
        res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["requires_2fa"])
        token = data["auth_data"]["access_token"]
        self.assertIsNotNone(token)

        # Test /api/auth/me with Bearer token
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["username"], "admin")
        self.assertEqual(me_data["role"], "admin")

    def test_06_api_user_crud_and_rbac(self):
        # Login as admin
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        token = login_res.json()["auth_data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create new user
        new_user_res = self.client.post("/api/users", headers=headers, json={
            "username": "operator1",
            "email": "operator1@synctool.local",
            "password": "Operator@123",
            "role": "user"
        })
        self.assertEqual(new_user_res.status_code, 201)
        created_user = new_user_res.json()
        user_id = created_user["id"]
        self.assertEqual(created_user["role"], "user")

        # Test list users
        list_res = self.client.get("/api/users", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(len(list_res.json()), 2)

        # Test login as non-admin user
        op_login = self.client.post("/api/auth/login", json={
            "username_or_email": "operator1",
            "password": "Operator@123"
        })
        self.assertEqual(op_login.status_code, 200)
        op_token = op_login.json()["auth_data"]["access_token"]
        op_headers = {"Authorization": f"Bearer {op_token}"}

        # Non-admin trying to access /api/users should get 403 Forbidden!
        forbidden_res = self.client.get("/api/users", headers=op_headers)
        self.assertEqual(forbidden_res.status_code, 403)

    def test_07_api_job_lifecycle(self):
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['auth_data']['access_token']}"}

        # Create a job via API
        job_payload = {
            "name": "Integration Test Robocopy",
            "transfer_type": "robocopy",
            "source_path": str(self.test_src),
            "dest_path": str(self.test_dst)
        }
        res = self.client.post("/api/jobs", headers=headers, json=job_payload)
        self.assertEqual(res.status_code, 200)
        job = res.json()
        job_id = job["id"]

        # Start job
        start_res = self.client.post(f"/api/jobs/{job_id}/start", headers=headers)
        self.assertEqual(start_res.status_code, 200)

        # Fetch job details
        detail_res = self.client.get(f"/api/jobs/{job_id}", headers=headers)
        self.assertEqual(detail_res.status_code, 200)

    def test_08_api_reports_and_logs(self):
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['auth_data']['access_token']}"}

        # Reports summary
        rep_res = self.client.get("/api/reports/summary", headers=headers)
        self.assertEqual(rep_res.status_code, 200)
        self.assertIn("total_jobs", rep_res.json())

        # Logs view (Admin only)
        logs_res = self.client.get("/api/logs", headers=headers)
        self.assertEqual(logs_res.status_code, 200)
        self.assertIn("logs", logs_res.json())
        self.assertGreaterEqual(logs_res.json()["total"], 1)

    def test_09_test_postgres_connection_with_special_chars(self):
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['auth_data']['access_token']}"}

        # Test connection with password containing '@'
        db_res = self.client.post("/api/system/test-postgres", headers=headers, json={
            "host": "localhost",
            "port": 5432,
            "dbname": "synctool_db",
            "user": "postgres",
            "password": "Admin@54321"
        })
        self.assertEqual(db_res.status_code, 200)
        data = db_res.json()
        self.assertTrue(data["success"])
        self.assertIn("successful", data["message"].lower())

    def test_10_fs_browser_endpoints(self):
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['auth_data']['access_token']}"}

        # Browse local directory
        # Browse local directory
        res = self.client.get(f"/api/fs/local?path={str(self.test_src)}&show_files=true", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("items", data)
        self.assertGreaterEqual(len(data["items"]), 5)

        # Create new folder via browse endpoint
        test_folder = self.test_src / "test_created_folder_10"
        if test_folder.exists():
            shutil.rmtree(test_folder, ignore_errors=True)

        mkdir_res = self.client.post("/api/fs/mkdir", headers=headers, json={
            "parent_path": str(self.test_src),
            "folder_name": "test_created_folder_10"
        })
        self.assertEqual(mkdir_res.status_code, 200)
        self.assertTrue(test_folder.exists())

    def test_11_job_overwrite_mode_options(self):
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['auth_data']['access_token']}"}

        # Create job with 'newer' overwrite mode
        res_newer = self.client.post("/api/jobs", headers=headers, json={
            "name": "Job Newer Mode",
            "transfer_type": "robocopy",
            "source_path": str(self.test_src),
            "dest_path": str(self.test_dst),
            "overwrite_mode": "newer"
        })
        self.assertEqual(res_newer.status_code, 200)
        self.assertEqual(res_newer.json()["overwrite_mode"], "newer")

        # Create job with 'always' overwrite mode
        res_always = self.client.post("/api/jobs", headers=headers, json={
            "name": "Job Always Mode",
            "transfer_type": "robocopy",
            "source_path": str(self.test_src),
            "dest_path": str(self.test_dst),
            "overwrite_mode": "always"
        })
        self.assertEqual(res_always.status_code, 200)
        self.assertEqual(res_always.json()["overwrite_mode"], "always")

    def test_12_admin_reset_user_password(self):
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['auth_data']['access_token']}"}

        # Ensure user doesn't exist yet
        db = database.SessionLocal()
        db.query(User).filter(User.username == "pwdtestuser").delete()
        db.commit()
        db.close()

        # Create a user to test password reset
        user_res = self.client.post("/api/users", headers=headers, json={
            "username": "pwdtestuser",
            "email": "pwdtestuser@synctool.local",
            "password": "InitialPassword@123",
            "role": "user"
        })
        self.assertEqual(user_res.status_code, 201)
        user_id = user_res.json()["id"]

        # Reset user password as admin
        reset_res = self.client.post(f"/api/users/{user_id}/reset-password", headers=headers, json={
            "new_password": "NewSecretPassword@456"
        })
        self.assertEqual(reset_res.status_code, 200)

        # Verify old password fails
        bad_login = self.client.post("/api/auth/login", json={
            "username_or_email": "pwdtestuser",
            "password": "InitialPassword@123"
        })
        self.assertEqual(bad_login.status_code, 401)

        # Verify new password succeeds
        good_login = self.client.post("/api/auth/login", json={
            "username_or_email": "pwdtestuser",
            "password": "NewSecretPassword@456"
        })
        self.assertEqual(good_login.status_code, 200)

    def test_13_admin_toggle_user_2fa(self):
        login_res = self.client.post("/api/auth/login", json={
            "username_or_email": "admin",
            "password": "Admin@12345"
        })
        headers = {"Authorization": f"Bearer {login_res.json()['auth_data']['access_token']}"}

        # Ensure user doesn't exist yet
        db = database.SessionLocal()
        db.query(User).filter(User.username == "twofauser").delete()
        db.commit()
        db.close()

        # Create a user to test 2FA toggle
        user_res = self.client.post("/api/users", headers=headers, json={
            "username": "twofauser",
            "email": "twofauser@synctool.local",
            "password": "TwofaPassword@123",
            "role": "user"
        })
        self.assertEqual(user_res.status_code, 201)
        user_id = user_res.json()["id"]
        self.assertFalse(user_res.json()["totp_enabled"])

        # Admin activates Google 2FA for this user
        enable_res = self.client.post(f"/api/users/{user_id}/toggle-2fa", headers=headers, json={
            "enabled": True
        })
        self.assertEqual(enable_res.status_code, 200)
        self.assertTrue(enable_res.json()["totp_enabled"])

        # Login now prompts for 2FA
        login_2fa = self.client.post("/api/auth/login", json={
            "username_or_email": "twofauser",
            "password": "TwofaPassword@123"
        })
        self.assertEqual(login_2fa.status_code, 200)
        self.assertTrue(login_2fa.json()["requires_2fa"])

        # Admin disables Google 2FA for this user
        disable_res = self.client.post(f"/api/users/{user_id}/toggle-2fa", headers=headers, json={
            "enabled": False
        })
        self.assertEqual(disable_res.status_code, 200)
        self.assertFalse(disable_res.json()["totp_enabled"])

        # Login directly succeeds without 2FA
        direct_login = self.client.post("/api/auth/login", json={
            "username_or_email": "twofauser",
            "password": "TwofaPassword@123"
        })
        self.assertEqual(direct_login.status_code, 200)
        self.assertFalse(direct_login.json()["requires_2fa"])

if __name__ == "__main__":
    unittest.main()
