// User Management Module (Admin Only)
const Users = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        const btnOpenCreate = document.getElementById("btn-open-create-user-modal");
        if (btnOpenCreate) {
            btnOpenCreate.addEventListener("click", () => this.openCreateModal());
        }

        const userForm = document.getElementById("user-form");
        if (userForm) {
            userForm.addEventListener("submit", (e) => this.handleSaveUser(e));
        }

        const resetForm = document.getElementById("form-reset-password");
        if (resetForm) {
            resetForm.addEventListener("submit", (e) => this.handleResetPasswordSubmit(e));
        }

        const btnGenPwd = document.getElementById("btn-generate-password");
        if (btnGenPwd) {
            btnGenPwd.addEventListener("click", () => this.generateSecurePassword());
        }

        const btnTogglePwd = document.getElementById("btn-toggle-pwd-visibility");
        if (btnTogglePwd) {
            btnTogglePwd.addEventListener("click", () => this.togglePasswordVisibility());
        }

        // Close modal buttons inside modal-reset-password
        document.querySelectorAll("#modal-reset-password .btn-close-modal").forEach(btn => {
            btn.addEventListener("click", () => {
                document.getElementById("modal-reset-password").classList.add("hidden");
            });
        });
    },

    async load() {
        if (!App.currentUser || App.currentUser.role !== "admin") return;

        try {
            const res = await App.fetchAPI("/users");
            if (res.ok) {
                const users = await res.json();
                this.renderUsers(users);
            }
        } catch (e) {
            console.error("Failed to fetch users", e);
        }
    },

    renderUsers(users) {
        const tbody = document.getElementById("users-tbody");
        if (!tbody) return;

        if (!users || users.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No users found.</td></tr>`;
            return;
        }

        tbody.innerHTML = users.map(u => `
            <tr>
                <td>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="user-avatar" style="width: 32px; height: 32px; font-size: 0.85rem;">${u.username[0].toUpperCase()}</div>
                        <div>
                            <strong>${this.escapeHtml(u.username)}</strong>
                            <div class="text-muted" style="font-size: 0.75rem;">ID: #${u.id}</div>
                        </div>
                    </div>
                </td>
                <td>${this.escapeHtml(u.email)}</td>
                <td>
                    <span class="badge ${u.role === 'admin' ? 'badge-info' : 'badge-neutral'}">${u.role.toUpperCase()}</span>
                </td>
                <td>
                    <span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">
                        ${u.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                </td>
                <td>
                    <span class="badge ${u.totp_enabled ? 'badge-success' : 'badge-neutral'}" title="${u.totp_enabled ? 'Google 2FA is Active' : 'Google 2FA is Disabled'}">
                        <i class="fa-solid ${u.totp_enabled ? 'fa-shield-halved' : 'fa-shield'}"></i> ${u.totp_enabled ? 'ACTIVE' : 'DISABLED'}
                    </span>
                </td>
                <td>
                    <span class="text-muted">${u.created_at ? new Date(u.created_at).toLocaleDateString() : '--'}</span>
                </td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-icon btn-sm" onclick="Users.openEditModal(${JSON.stringify(u).replace(/"/g, '&quot;')})" title="Edit User Details">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        
                        <button class="btn btn-icon btn-sm" onclick="Users.openResetPasswordModal(${u.id}, '${this.escapeQuotes(u.username)}')" title="Reset Password" style="color: var(--accent-amber);">
                            <i class="fa-solid fa-key"></i>
                        </button>

                        ${u.totp_enabled ? `
                            <button class="btn btn-icon btn-sm" onclick="Users.toggle2FA(${u.id}, '${this.escapeQuotes(u.username)}', false)" title="Disable Google 2FA" style="color: var(--accent-rose);">
                                <i class="fa-solid fa-shield-slash"></i>
                            </button>
                        ` : `
                            <button class="btn btn-icon btn-sm" onclick="Users.toggle2FA(${u.id}, '${this.escapeQuotes(u.username)}', true)" title="Activate Google 2FA" style="color: var(--accent-cyan);">
                                <i class="fa-solid fa-shield-heart"></i>
                            </button>
                        `}

                        ${u.id !== App.currentUser.id ? `
                            <button class="btn btn-icon btn-sm btn-danger-hover" onclick="Users.deleteUser(${u.id}, '${this.escapeQuotes(u.username)}')" title="Delete User">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `).join("");
    },

    openCreateModal() {
        document.getElementById("edit-user-id").value = "";
        document.getElementById("user-modal-title").textContent = "Create New User";
        document.getElementById("user-form").reset();
        document.getElementById("user-username").disabled = false;
        document.getElementById("user-password").required = true;
        document.getElementById("user-password-group").classList.remove("hidden");
        document.getElementById("user-active-group").classList.add("hidden");
        document.getElementById("modal-user").classList.remove("hidden");
    },

    openEditModal(user) {
        document.getElementById("edit-user-id").value = user.id;
        document.getElementById("user-modal-title").textContent = `Edit User: ${user.username}`;
        document.getElementById("user-username").value = user.username;
        document.getElementById("user-username").disabled = true;
        document.getElementById("user-email").value = user.email;
        document.getElementById("user-role").value = user.role;
        document.getElementById("user-is-active").checked = user.is_active;

        document.getElementById("user-password").value = "";
        document.getElementById("user-password").required = false;
        document.getElementById("user-password").placeholder = "Leave blank to keep unchanged";
        document.getElementById("user-active-group").classList.remove("hidden");

        document.getElementById("modal-user").classList.remove("hidden");
    },

    openResetPasswordModal(userId, username) {
        document.getElementById("reset-pwd-user-id").value = userId;
        document.getElementById("reset-pwd-username-display").textContent = username;
        document.getElementById("reset-pwd-new-password").value = "";
        document.getElementById("reset-pwd-confirm-password").value = "";
        document.getElementById("reset-pwd-new-password").type = "password";
        document.getElementById("modal-reset-password").classList.remove("hidden");
    },

    generateSecurePassword() {
        const length = 12;
        const upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        const lower = "abcdefghijklmnopqrstuvwxyz";
        const digits = "0123456789";
        const special = "@#%*";
        const allChars = upper + lower + digits + special;

        let pwd = upper[Math.floor(Math.random() * upper.length)] +
                  lower[Math.floor(Math.random() * lower.length)] +
                  digits[Math.floor(Math.random() * digits.length)] +
                  special[Math.floor(Math.random() * special.length)];

        for (let i = pwd.length; i < length; i++) {
            pwd += allChars[Math.floor(Math.random() * allChars.length)];
        }

        pwd = pwd.split('').sort(() => 0.5 - Math.random()).join('');

        const newPwdInput = document.getElementById("reset-pwd-new-password");
        const confirmPwdInput = document.getElementById("reset-pwd-confirm-password");
        newPwdInput.value = pwd;
        confirmPwdInput.value = pwd;
        newPwdInput.type = "text";
        App.showToast("Generated secure random password", "info");
    },

    togglePasswordVisibility() {
        const newPwdInput = document.getElementById("reset-pwd-new-password");
        const icon = document.querySelector("#btn-toggle-pwd-visibility i");
        if (newPwdInput.type === "password") {
            newPwdInput.type = "text";
            if (icon) icon.className = "fa-solid fa-eye-slash";
        } else {
            newPwdInput.type = "password";
            if (icon) icon.className = "fa-solid fa-eye";
        }
    },

    async handleResetPasswordSubmit(e) {
        e.preventDefault();
        const userId = document.getElementById("reset-pwd-user-id").value;
        const newPwd = document.getElementById("reset-pwd-new-password").value;
        const confirmPwd = document.getElementById("reset-pwd-confirm-password").value;

        if (newPwd !== confirmPwd) {
            App.showToast("Passwords do not match. Please re-check.", "warning");
            return;
        }

        try {
            const res = await App.fetchAPI(`/users/${userId}/reset-password`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ new_password: newPwd })
            });

            if (res.ok) {
                App.showToast("User password successfully reset!", "success");
                document.getElementById("modal-reset-password").classList.add("hidden");
            } else {
                const data = await res.json();
                App.showToast(data.detail || "Failed to reset password", "error");
            }
        } catch (err) {
            App.showToast("Request error resetting password", "error");
        }
    },

    async toggle2FA(userId, username, enable) {
        const actionLabel = enable ? "ACTIVATE" : "DISABLE";
        if (!confirm(`Are you sure you want to ${actionLabel} Google 2FA for user '${username}'?`)) return;

        try {
            const res = await App.fetchAPI(`/users/${userId}/toggle-2fa`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enabled: enable })
            });

            if (res.ok) {
                App.showToast(`Google 2FA is now ${enable ? 'ACTIVE' : 'DISABLED'} for ${username}`, "success");
                this.load();
            } else {
                const data = await res.json();
                App.showToast(data.detail || `Failed to ${actionLabel.toLowerCase()} 2FA`, "error");
            }
        } catch (e) {
            App.showToast("Network error updating 2FA status", "error");
        }
    },

    async handleSaveUser(e) {
        e.preventDefault();
        const userId = document.getElementById("edit-user-id").value;
        const isEdit = !!userId;

        if (!isEdit) {
            // Create user
            const payload = {
                username: document.getElementById("user-username").value.trim(),
                email: document.getElementById("user-email").value.trim(),
                password: document.getElementById("user-password").value,
                role: document.getElementById("user-role").value
            };

            try {
                const res = await App.fetchAPI("/users", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.ok) {
                    App.showToast(`User '${data.username}' created successfully`, "success");
                    document.getElementById("modal-user").classList.add("hidden");
                    this.load();
                } else {
                    App.showToast(data.detail || "Failed to create user", "error");
                }
            } catch (err) {
                App.showToast("Request error creating user", "error");
            }
        } else {
            // Update user
            const payload = {
                email: document.getElementById("user-email").value.trim(),
                role: document.getElementById("user-role").value,
                is_active: document.getElementById("user-is-active").checked
            };
            const pwd = document.getElementById("user-password").value;
            if (pwd) payload.password = pwd;

            try {
                const res = await App.fetchAPI(`/users/${userId}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    App.showToast("User updated successfully", "success");
                    document.getElementById("modal-user").classList.add("hidden");
                    this.load();
                } else {
                    const data = await res.json();
                    App.showToast(data.detail || "Failed to update user", "error");
                }
            } catch (err) {
                App.showToast("Request error updating user", "error");
            }
        }
    },

    async deleteUser(userId, username) {
        if (!confirm(`Are you sure you want to permanently delete user '${username}'?`)) return;
        try {
            const res = await App.fetchAPI(`/users/${userId}`, { method: "DELETE" });
            if (res.ok) {
                App.showToast(`User '${username}' deleted`, "info");
                this.load();
            }
        } catch (e) {
            App.showToast("Failed to delete user", "error");
        }
    },

    escapeHtml(str) {
        if (!str) return "";
        return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    },

    escapeQuotes(str) {
        if (!str) return "";
        return String(str).replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, "&quot;");
    }
};

window.Users = Users;
document.addEventListener("DOMContentLoaded", () => Users.init());
