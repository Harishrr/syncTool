// Core Application State & Auth Management
const App = {
    token: localStorage.getItem("synctool_token") || null,
    currentUser: null,
    activeView: "dashboard",
    ws: null,
    temp2faToken: null,

    init() {
        this.bindEvents();
        this.checkAuth();
        this.handleHashChange();
        window.addEventListener("hashchange", () => this.handleHashChange());
    },

    bindEvents() {
        // Nav items
        document.querySelectorAll(".nav-item").forEach(item => {
            item.addEventListener("click", (e) => {
                const view = item.getAttribute("data-view");
                if (view) {
                    this.switchView(view);
                }
            });
        });

        // Sign Out
        document.getElementById("btn-signout").addEventListener("click", () => {
            this.logout();
        });

        // Login form
        const loginForm = document.getElementById("login-form");
        if (loginForm) {
            loginForm.addEventListener("submit", (e) => this.handleLogin(e));
        }

        // TOTP verification form
        const totpForm = document.getElementById("totp-form");
        if (totpForm) {
            totpForm.addEventListener("submit", (e) => this.handleTotpVerify(e));
        }

        document.getElementById("btn-totp-cancel").addEventListener("click", () => {
            document.getElementById("totp-form").classList.add("hidden");
            document.getElementById("login-form").classList.remove("hidden");
            this.temp2faToken = null;
        });

        // Modal close buttons
        document.querySelectorAll(".btn-close-modal").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const modal = e.target.closest(".modal-backdrop");
                if (modal) modal.classList.add("hidden");
            });
        });

        // Setup 2FA modal trigger
        document.getElementById("btn-setup-2fa-modal").addEventListener("click", () => {
            this.openSetup2FAModal();
        });

        // Setup 2FA confirmation
        const formConfirm2FA = document.getElementById("form-confirm-2fa");
        if (formConfirm2FA) {
            formConfirm2FA.addEventListener("submit", (e) => this.handleConfirm2FA(e));
        }

        // Disable 2FA
        const btnDisable2FA = document.getElementById("btn-disable-2fa");
        if (btnDisable2FA) {
            btnDisable2FA.addEventListener("click", () => this.handleDisable2FA());
        }

        // DB test form
        const dbTestForm = document.getElementById("db-test-form");
        if (dbTestForm) {
            dbTestForm.addEventListener("submit", (e) => this.handleTestDB(e));
        }

        // DB apply button
        const btnApplyDB = document.getElementById("btn-apply-db-conn");
        if (btnApplyDB) {
            btnApplyDB.addEventListener("click", (e) => this.handleApplyDB(e));
        }
    },

    async checkAuth() {
        if (!this.token) {
            this.showAuthOverlay();
            return;
        }

        try {
            const res = await this.fetchAPI("/auth/me");
            if (res.ok) {
                this.currentUser = await res.json();
                this.hideAuthOverlay();
                this.updateUserUI();
                this.connectWebSocket();
                this.refreshActiveView();
                this.checkDatabaseStatus();
            } else {
                this.logout();
            }
        } catch (e) {
            console.error("Auth check failed", e);
            this.logout();
        }
    },

    showAuthOverlay() {
        document.getElementById("auth-overlay").classList.remove("hidden");
        document.getElementById("login-form").classList.remove("hidden");
        document.getElementById("totp-form").classList.add("hidden");
    },

    hideAuthOverlay() {
        document.getElementById("auth-overlay").classList.add("hidden");
    },

    async handleLogin(e) {
        e.preventDefault();
        const identifier = document.getElementById("login-identifier").value.trim();
        const password = document.getElementById("login-password").value;

        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username_or_email: identifier, password: password })
            });

            const data = await res.json();
            if (!res.ok) {
                this.showToast(data.detail || "Authentication failed", "error");
                return;
            }

            if (data.requires_2fa) {
                this.temp2faToken = data.temp_token;
                document.getElementById("login-form").classList.add("hidden");
                document.getElementById("totp-form").classList.remove("hidden");
                document.getElementById("totp-code").focus();
                this.showToast("Please enter your Google Authenticator code", "info");
            } else if (data.auth_data) {
                this.token = data.auth_data.access_token;
                this.currentUser = data.auth_data.user;
                localStorage.setItem("synctool_token", this.token);
                this.hideAuthOverlay();
                this.updateUserUI();
                this.connectWebSocket();
                this.refreshActiveView();
                this.checkDatabaseStatus();
                this.showToast(`Welcome back, ${this.currentUser.username}!`, "success");
            }
        } catch (err) {
            this.showToast("Network error communicating with server", "error");
        }
    },

    async handleTotpVerify(e) {
        e.preventDefault();
        const code = document.getElementById("totp-code").value.trim();
        if (!code || !this.temp2faToken) return;

        try {
            const res = await fetch("/api/auth/verify-2fa", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ temp_token: this.temp2faToken, code: code })
            });

            const data = await res.json();
            if (!res.ok) {
                this.showToast(data.detail || "Verification failed", "error");
                return;
            }

            this.token = data.access_token;
            this.currentUser = data.user;
            localStorage.setItem("synctool_token", this.token);
            this.hideAuthOverlay();
            this.updateUserUI();
            this.connectWebSocket();
            this.refreshActiveView();
            this.checkDatabaseStatus();
            this.showToast(`2FA Verified. Welcome, ${this.currentUser.username}!`, "success");
        } catch (err) {
            this.showToast("Verification request failed", "error");
        }
    },

    logout() {
        this.token = null;
        this.currentUser = null;
        localStorage.removeItem("synctool_token");
        if (this.ws) {
            try { this.ws.close(); } catch(e){}
        }
        this.showAuthOverlay();
        this.showToast("Signed out successfully.", "info");
    },

    updateUserUI() {
        if (!this.currentUser) return;
        document.getElementById("current-username").textContent = this.currentUser.username;
        document.getElementById("current-user-avatar").textContent = this.currentUser.username[0].toUpperCase();
        document.getElementById("current-user-role").textContent = this.currentUser.role.toUpperCase();

        const roleBadge = document.getElementById("current-user-role");
        if (this.currentUser.role === "admin") {
            roleBadge.style.color = "var(--accent-emerald)";
            document.querySelectorAll(".admin-only").forEach(el => el.classList.remove("hidden"));
        } else {
            roleBadge.style.color = "var(--accent-cyan)";
            document.querySelectorAll(".admin-only").forEach(el => el.classList.add("hidden"));
        }

        const twoFaEl = document.getElementById("current-user-2fa");
        if (this.currentUser.totp_enabled) {
            twoFaEl.classList.add("active");
            twoFaEl.title = "Google Authenticator: Protected";
        } else {
            twoFaEl.classList.remove("active");
            twoFaEl.title = "Google Authenticator: Inactive (Click to setup)";
        }
    },

    async openSetup2FAModal() {
        try {
            const res = await this.fetchAPI("/auth/setup-2fa", { method: "POST" });
            if (!res.ok) {
                this.showToast("Could not initiate 2FA setup", "error");
                return;
            }
            const data = await res.json();
            document.getElementById("qr-code-img").src = data.qr_code_base64;
            document.getElementById("totp-secret-text").textContent = data.secret;
            document.getElementById("form-confirm-2fa").dataset.secret = data.secret;

            const btnDisable = document.getElementById("btn-disable-2fa");
            if (this.currentUser && this.currentUser.totp_enabled) {
                btnDisable.classList.remove("hidden");
            } else {
                btnDisable.classList.add("hidden");
            }

            document.getElementById("modal-2fa-setup").classList.remove("hidden");
        } catch (e) {
            this.showToast("Error opening 2FA setup", "error");
        }
    },

    async handleConfirm2FA(e) {
        e.preventDefault();
        const secret = document.getElementById("form-confirm-2fa").dataset.secret;
        const code = document.getElementById("confirm-2fa-code").value.trim();

        try {
            const res = await this.fetchAPI("/auth/confirm-2fa", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ secret: secret, code: code })
            });
            const data = await res.json();
            if (res.ok) {
                this.showToast("Google Authenticator 2FA enabled!", "success");
                document.getElementById("modal-2fa-setup").classList.add("hidden");
                this.checkAuth();
            } else {
                this.showToast(data.detail || "Invalid code", "error");
            }
        } catch (err) {
            this.showToast("Failed to verify 2FA", "error");
        }
    },

    async handleDisable2FA() {
        if (!confirm("Are you sure you want to disable Google Authenticator 2FA?")) return;
        try {
            const res = await this.fetchAPI("/auth/disable-2fa", { method: "POST" });
            if (res.ok) {
                this.showToast("2FA disabled.", "info");
                document.getElementById("modal-2fa-setup").classList.add("hidden");
                this.checkAuth();
            }
        } catch (e) {
            this.showToast("Failed to disable 2FA", "error");
        }
    },

    async checkDatabaseStatus() {
        if (this.currentUser && this.currentUser.role === "admin") {
            try {
                const res = await this.fetchAPI("/system/db-info");
                if (res.ok) {
                    const data = await res.json();
                    const activeType = data.active_type.toUpperCase();
                    document.getElementById("db-active-type").textContent = `DB: ${activeType}`;
                    document.getElementById("settings-db-active").textContent = activeType;
                    document.getElementById("settings-db-host").textContent = data.postgres_host;
                    document.getElementById("settings-db-port").textContent = data.postgres_port;
                    document.getElementById("settings-db-name").textContent = data.postgres_db;
                    document.getElementById("settings-db-user").textContent = data.postgres_user;
                }
            } catch (e) {}
        }
    },

    async handleTestDB(e) {
        e.preventDefault();
        const payload = {
            host: document.getElementById("test-db-host").value.trim(),
            port: parseInt(document.getElementById("test-db-port").value.trim() || 5432),
            dbname: document.getElementById("test-db-name").value.trim(),
            user: document.getElementById("test-db-user").value.trim(),
            password: document.getElementById("test-db-password").value
        };

        const resultEl = document.getElementById("db-test-result");
        resultEl.textContent = "Testing connection...";
        resultEl.style.color = "var(--accent-cyan)";

        try {
            const res = await this.fetchAPI("/system/test-postgres", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                resultEl.textContent = "✓ Connected to PostgreSQL successfully!";
                resultEl.style.color = "var(--accent-emerald)";
                this.showToast("PostgreSQL connection confirmed!", "success");
            } else {
                resultEl.textContent = `✗ Failed: ${data.message}`;
                resultEl.style.color = "var(--accent-rose)";
            }
        } catch (err) {
            resultEl.textContent = "Error testing database connection";
            resultEl.style.color = "var(--accent-rose)";
        }
    },

    async handleApplyDB(e) {
        if (e) e.preventDefault();
        const payload = {
            host: document.getElementById("test-db-host").value.trim(),
            port: parseInt(document.getElementById("test-db-port").value.trim() || 5432),
            dbname: document.getElementById("test-db-name").value.trim(),
            user: document.getElementById("test-db-user").value.trim(),
            password: document.getElementById("test-db-password").value
        };

        const resultEl = document.getElementById("db-test-result");
        resultEl.textContent = "Connecting and switching database...";
        resultEl.style.color = "var(--accent-cyan)";

        try {
            const res = await this.fetchAPI("/system/apply-postgres", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                resultEl.textContent = "✓ Active DB switched to PostgreSQL!";
                resultEl.style.color = "var(--accent-emerald)";
                this.showToast("Active database switched to PostgreSQL!", "success");
                await this.checkDatabaseStatus();
            } else {
                resultEl.textContent = `✗ Failed: ${data.message}`;
                resultEl.style.color = "var(--accent-rose)";
            }
        } catch (err) {
            resultEl.textContent = "Error applying database connection";
            resultEl.style.color = "var(--accent-rose)";
        }
    },

    handleHashChange() {
        const hash = window.location.hash.replace("#", "") || "dashboard";
        this.switchView(hash);
    },

    switchView(viewName) {
        if (!this.currentUser && viewName !== "dashboard") return;

        // Non-admins cannot view user management or logs
        if (this.currentUser && this.currentUser.role !== "admin" && (viewName === "users" || viewName === "logs")) {
            this.showToast("Access restricted to administrators.", "warning");
            viewName = "dashboard";
        }

        this.activeView = viewName;
        window.location.hash = viewName;

        // Nav active class
        document.querySelectorAll(".nav-item").forEach(item => {
            if (item.getAttribute("data-view") === viewName) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        // View display
        document.querySelectorAll(".content-view").forEach(view => {
            view.classList.remove("active");
        });
        const targetView = document.getElementById(`view-${viewName}`);
        if (targetView) targetView.classList.add("active");

        // Page title
        const titleMap = {
            dashboard: "Dashboard Overview",
            jobs: "Data Transfer Jobs",
            users: "User Management & RBAC",
            logs: "System Activity & Audit Logs",
            reports: "Transfer Reports & Analytics",
            settings: "Database & System Configuration"
        };
        document.getElementById("page-title").textContent = titleMap[viewName] || "Sync Tool";

        this.refreshActiveView();
    },

    refreshActiveView() {
        if (this.activeView === "dashboard" && window.Dashboard) Dashboard.load();
        if (this.activeView === "jobs" && window.Jobs) Jobs.load();
        if (this.activeView === "users" && window.Users) Users.load();
        if (this.activeView === "logs" && window.Logs) Logs.load();
        if (this.activeView === "reports" && window.Reports) Reports.load();
    },

    connectWebSocket() {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/jobs`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                document.getElementById("ws-status-text").textContent = "Live Sync Connected";
                const dot = document.querySelector(".header-status-pill .status-dot");
                if (dot) {
                    dot.classList.remove("offline");
                    dot.classList.add("online");
                }
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (e) {}
            };

            this.ws.onclose = () => {
                document.getElementById("ws-status-text").textContent = "Connecting...";
                const dot = document.querySelector(".header-status-pill .status-dot");
                if (dot) {
                    dot.classList.remove("online");
                    dot.classList.add("offline");
                }
                // Reconnect after 3 seconds
                setTimeout(() => {
                    if (this.token) this.connectWebSocket();
                }, 3000);
            };
        } catch (e) {
            console.error("WS error", e);
        }
    },

    handleWebSocketMessage(msg) {
        if (msg.type === "job_progress" || msg.type === "job_status") {
            if (window.Jobs) Jobs.updateJobLive(msg);
            if (window.Dashboard) Dashboard.updateJobLive(msg);
        }
    },

    async fetchAPI(url, options = {}) {
        const fullUrl = url.startsWith("/api") ? url : `/api${url}`;
        options.headers = options.headers || {};
        if (this.token) {
            options.headers["Authorization"] = `Bearer ${this.token}`;
        }
        const res = await fetch(fullUrl, options);
        if (res.status === 401) {
            this.logout();
        }
        return res;
    },

    showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        const iconMap = {
            success: "fa-circle-check",
            error: "fa-triangle-exclamation",
            warning: "fa-circle-exclamation",
            info: "fa-circle-info"
        };
        const icon = iconMap[type] || "fa-circle-info";

        toast.innerHTML = `<i class="fa-solid ${icon}"></i><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
};

window.App = App;
document.addEventListener("DOMContentLoaded", () => App.init());
