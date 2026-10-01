# Sync Tool - Enterprise Data Synchronization & Migration

**Sync Tool** is a high-performance, enterprise-grade file synchronization and data replication application written in Python. It is designed with a **dual-target architecture**: running as a native Windows Desktop application immediately, and seamlessly deployable as a multi-user Web-Hosted application with zero code rewrite.

---

## 🌟 Key Features

### 1. Dual Deployment Architecture
- **Desktop Application**: Launches with `run_desktop.bat` or `python desktop_launcher.py`, creating a native Windows window (via Microsoft Edge WebView2 / PyWebView) with full desktop performance.
- **Web-Hosted Application**: Launches with `run_web.bat` or `uvicorn app.main:app --host 0.0.0.0 --port 8000`, supporting multi-user browser access across your network or cloud.

### 2. Enterprise Database Engine
- **PostgreSQL**: Primary enterprise database support (`synctool_db`).
- **Smart Automatic Fallback**: If PostgreSQL credentials are not yet configured on first launch, Sync Tool automatically falls back to local SQLite (`synctool_local.db`) so the application is instantly usable out-of-the-box.
- **Database Settings Panel**: Easily test and configure PostgreSQL credentials directly in the app.

### 3. Authentication & RBAC (Role-Based Access Control)
- **Role Separation**: `admin` and `user` (operator) roles.
- **Google Authenticator (2FA / TOTP)**: Standard TOTP support using `pyotp` and QR code scanning.
- **Admin User Management**: Administrators can create users, assign roles, deactivate accounts, and reset 2FA.
- **Default Administrator Credentials**:
  - **Username**: `admin`
  - **Email**: `admin@synctool.local`
  - **Password**: `Admin@12345`

### 4. Transfer Protocol Engines
- **Windows Robocopy**: High-performance multi-threaded native Windows file copy with real-time progress parsing, byte counter, speed calculator, and process suspension/resumption (`psutil` suspend/resume).
- **SFTP (SSH)**: Remote server transfers over SFTP using Paramiko with chunk callbacks, pause, and stop support.
- **UDP Streamer**: High-speed UDP packet transfer protocol for fast data migration between servers.
- **Bulk Execution**: Single-click "Start All", "Pause All", and "Stop All" operations.
- **CSV Batch Import**: Import bulk sync jobs using CSV files with drag-and-drop support.

### 5. Telemetry, Logs & Reporting
- **Dual-Tier Activity Logging**: Timestamped rotating file logs (`logs/sync_tool.log`) + indexed database logs.
- **Admin Log Explorer**: Filter system events by log level (`INFO`, `WARNING`, `ERROR`), category, date range, and keyword.
- **Interactive Reports**: Aggregated transfer metrics, historical execution runs, and **1-Click Export to CSV**.

---

## 🚀 Quick Start

### 1. Installation
All required dependencies are specified in `requirements.txt`:
```powershell
pip install -r requirements.txt
```

### 2. Running as a Desktop App
Double-click `run_desktop.bat` or execute:
```powershell
python desktop_launcher.py
```

### 3. Running as a Web Server
Double-click `run_web.bat` or execute:
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Then navigate to `http://localhost:8000` in any web browser.

---

## 📋 CSV Batch Import Format

To import multiple jobs simultaneously, prepare a CSV file with the following columns (a sample is included in `sample_jobs.csv`):

```csv
name,transfer_type,source_path,dest_path,host,port,remote_username,remote_password
Local Robocopy Backup,robocopy,C:\SourceFolder,D:\BackupFolder,,,,
SFTP Offsite Sync,sftp,C:\DataToUpload,/remote/backup,192.168.1.50,22,backup_user,SecretPass123
High-Speed UDP Pipe,udp,C:\LargeStream,/remote/incoming,192.168.1.60,9999,,
```

---

## 🔒 Google Authenticator (2FA) Setup

1. Sign in with your account credentials.
2. Click the **Shield Icon** in the bottom-left sidebar.
3. Scan the generated QR code using the **Google Authenticator** app on your mobile device.
4. Enter the 6-digit verification code to activate 2FA.
5. On your next login, the application will automatically prompt for your 6-digit TOTP code.
# syncTool
