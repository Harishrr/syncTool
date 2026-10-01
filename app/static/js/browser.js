// File & Directory Explorer Component for Robocopy, SFTP, and UDP
const Browser = {
    targetInputId: null,
    protocol: "robocopy",
    isDestination: false,
    mode: "local", // "local" or "sftp"
    currentPath: "",
    parentPath: null,
    selectedPath: "",
    selectedIsDir: true,
    showFiles: true,
    filterText: "",
    sftpCreds: { host: "", port: 22, username: "", password: "" },
    items: [],
    drives: [],
    shortcuts: [],
    isLoading: false,

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // Close modal
        const modal = document.getElementById("modal-file-browser");
        if (!modal) return;

        modal.querySelectorAll(".btn-close-modal").forEach(btn => {
            btn.addEventListener("click", () => this.close());
        });

        // Tabs: Local vs Remote SFTP
        const tabs = modal.querySelectorAll(".browser-tab");
        tabs.forEach(tab => {
            tab.addEventListener("click", () => {
                tabs.forEach(t => t.classList.remove("active"));
                tab.classList.add("active");
                const mode = tab.getAttribute("data-mode");
                this.switchMode(mode);
            });
        });

        // Navigation actions
        document.getElementById("btn-browser-up")?.addEventListener("click", () => this.goUp());
        document.getElementById("btn-browser-refresh")?.addEventListener("click", () => this.refresh());
        document.getElementById("btn-browser-home")?.addEventListener("click", () => this.goHome());

        // Address bar
        const addressInput = document.getElementById("browser-address-input");
        const btnGo = document.getElementById("btn-browser-go");
        if (addressInput && btnGo) {
            btnGo.addEventListener("click", () => {
                const p = addressInput.value.trim();
                if (p) this.navigateTo(p);
            });
            addressInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    btnGo.click();
                }
            });
        }

        // Search / Filter
        const filterInput = document.getElementById("browser-filter-input");
        if (filterInput) {
            filterInput.addEventListener("input", (e) => {
                this.filterText = e.target.value.toLowerCase().trim();
                this.renderItems();
            });
        }

        // Show files toggle
        const showFilesCheckbox = document.getElementById("browser-show-files");
        if (showFilesCheckbox) {
            showFilesCheckbox.addEventListener("change", (e) => {
                this.showFiles = e.target.checked;
                this.refresh();
            });
        }

        // Create New Folder
        document.getElementById("btn-browser-mkdir")?.addEventListener("click", () => this.createNewFolder());

        // Native OS Picker
        document.getElementById("btn-browser-native")?.addEventListener("click", () => this.openNativePicker());

        // Confirm Selection
        document.getElementById("btn-browser-confirm")?.addEventListener("click", () => this.confirmSelection());

        // Select Current Directory button
        document.getElementById("btn-browser-select-current")?.addEventListener("click", () => {
            if (this.currentPath) {
                this.selectedPath = this.currentPath;
                this.selectedIsDir = true;
                this.confirmSelection();
            }
        });
    },

    open({ targetInputId, protocol, isDestination, initialPath, sftpCreds }) {
        this.targetInputId = targetInputId;
        this.protocol = protocol || "robocopy";
        this.isDestination = !!isDestination;
        this.filterText = "";
        const filterInput = document.getElementById("browser-filter-input");
        if (filterInput) filterInput.value = "";

        // Set show files: default true for source; for destination, can still show files if user wants
        this.showFiles = !isDestination;
        const showFilesCheckbox = document.getElementById("browser-show-files");
        if (showFilesCheckbox) showFilesCheckbox.checked = this.showFiles;

        this.sftpCreds = sftpCreds || { host: "", port: 22, username: "", password: "" };

        const targetName = isDestination ? "Destination Path" : "Source Path";
        const protoName = protocol === "sftp" ? "SFTP" : (protocol === "udp" ? "UDP" : "Robocopy");
        
        document.getElementById("browser-title").textContent = `Browse ${targetName}`;
        document.getElementById("browser-subtitle").textContent = `${protoName} Transfer Protocol • Select a folder or file`;

        const modeSwitcher = document.getElementById("browser-mode-switcher");
        const btnNative = document.getElementById("btn-browser-native");
        const btnMkdir = document.getElementById("btn-browser-mkdir");

        // Remote SFTP handling
        if (this.protocol === "sftp" && this.isDestination) {
            modeSwitcher.classList.remove("hidden");
            // Set Remote SFTP active by default
            this.setTabActive("remote");
            this.mode = "remote";
            if (btnNative) btnNative.classList.add("hidden");
            if (btnMkdir) btnMkdir.classList.add("hidden");

            if (this.sftpCreds.host && this.sftpCreds.username) {
                this.navigateSFTP(initialPath || "");
            } else {
                this.showSFTPCredentialsPrompt();
            }
        } else {
            modeSwitcher.classList.add("hidden");
            this.mode = "local";
            if (btnNative) btnNative.classList.remove("hidden");
            if (btnMkdir) btnMkdir.classList.remove("hidden");
            this.navigateLocal(initialPath || "");
        }

        const modal = document.getElementById("modal-file-browser");
        modal.classList.remove("hidden");
    },

    close() {
        const modal = document.getElementById("modal-file-browser");
        if (modal) modal.classList.add("hidden");
    },

    setTabActive(mode) {
        const tabs = document.querySelectorAll(".browser-tab");
        tabs.forEach(t => {
            if (t.getAttribute("data-mode") === mode) t.classList.add("active");
            else t.classList.remove("active");
        });
    },

    switchMode(mode) {
        this.mode = mode;
        const btnNative = document.getElementById("btn-browser-native");
        const btnMkdir = document.getElementById("btn-browser-mkdir");

        if (mode === "remote") {
            if (btnNative) btnNative.classList.add("hidden");
            if (btnMkdir) btnMkdir.classList.add("hidden");
            if (this.sftpCreds.host && this.sftpCreds.username) {
                this.navigateSFTP("");
            } else {
                this.showSFTPCredentialsPrompt();
            }
        } else {
            if (btnNative) btnNative.classList.remove("hidden");
            if (btnMkdir) btnMkdir.classList.remove("hidden");
            this.navigateLocal("");
        }
    },

    showSFTPCredentialsPrompt() {
        this.currentPath = "";
        this.parentPath = null;
        this.items = [];
        this.renderSidebar([], []);
        
        const addressInput = document.getElementById("browser-address-input");
        if (addressInput) addressInput.value = "";

        const tbody = document.getElementById("browser-items-tbody");
        tbody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; padding: 40px 20px;">
                    <div style="max-width: 420px; margin: 0 auto;">
                        <i class="fa-solid fa-server" style="font-size: 2.5rem; color: var(--accent-cyan); margin-bottom: 15px; display: block;"></i>
                        <h4 style="margin-bottom: 8px; color: var(--text-main);">Remote SFTP Connection Required</h4>
                        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 20px;">
                            To browse remote directories on the SFTP server, please provide the Host / IP and Remote Username in the Job form.
                        </p>
                        <div style="display: flex; gap: 10px; justify-content: center;">
                            <button type="button" class="btn btn-primary btn-sm" onclick="Browser.setTabActive('local'); Browser.switchMode('local');">
                                <i class="fa-solid fa-hard-drive"></i> Browse Local Filesystem Instead
                            </button>
                        </div>
                    </div>
                </td>
            </tr>
        `;

        document.getElementById("browser-selected-path").textContent = "None";
        document.getElementById("btn-browser-confirm").disabled = true;
    },

    async navigateLocal(path) {
        this.setLoading(true);
        try {
            const url = `/fs/local?path=${encodeURIComponent(path || "")}&show_files=${this.showFiles}`;
            const res = await App.fetchAPI(url);
            if (!res.ok) {
                const err = await res.json();
                App.showToast(err.detail || "Failed to access local folder", "error");
                this.setLoading(false);
                return;
            }
            const data = await res.json();
            this.currentPath = data.current_path;
            this.parentPath = data.parent_path;
            this.items = data.items || [];
            this.drives = data.drives || [];
            this.shortcuts = data.shortcuts || [];

            // Update address input
            const addrInput = document.getElementById("browser-address-input");
            if (addrInput) addrInput.value = this.currentPath;

            // Update Up button state
            const btnUp = document.getElementById("btn-browser-up");
            if (btnUp) btnUp.disabled = !this.parentPath;

            // Default selection to current directory
            this.setSelectedPath(this.currentPath, true);

            // Render sidebar
            this.renderSidebar(this.drives, this.shortcuts);

            // Render items
            this.renderItems();

            if (data.error) {
                App.showToast(data.error, "warning");
            }
        } catch (e) {
            console.error("Local browse error", e);
            App.showToast("Network error exploring local path", "error");
        } finally {
            this.setLoading(false);
        }
    },

    async navigateSFTP(remotePath) {
        this.setLoading(true);
        try {
            const payload = {
                host: this.sftpCreds.host,
                port: parseInt(this.sftpCreds.port) || 22,
                username: this.sftpCreds.username,
                password: this.sftpCreds.password || null,
                remote_path: remotePath || null,
                show_files: this.showFiles
            };

            const res = await App.fetchAPI("/fs/sftp", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json();
                App.showToast(err.detail || "SFTP connection error", "error");
                this.setLoading(false);
                return;
            }

            const data = await res.json();
            this.currentPath = data.current_path;
            this.parentPath = data.parent_path;
            this.items = data.items || [];

            // Update address input
            const addrInput = document.getElementById("browser-address-input");
            if (addrInput) addrInput.value = this.currentPath;

            // Update Up button state
            const btnUp = document.getElementById("btn-browser-up");
            if (btnUp) btnUp.disabled = !this.parentPath;

            // Default selection to current directory
            this.setSelectedPath(this.currentPath, true);

            // Remote SFTP shortcuts
            const sftpShortcuts = [
                { name: "Root (/)", path: "/", icon: "fa-server" },
                { name: "Default / Home", path: "", icon: "fa-house" }
            ];
            this.renderSidebar([], sftpShortcuts, true);

            // Render items
            this.renderItems();
        } catch (e) {
            console.error("SFTP browse error", e);
            App.showToast("Network error connecting to SFTP server", "error");
        } finally {
            this.setLoading(false);
        }
    },

    navigateTo(path) {
        if (this.mode === "sftp") {
            this.navigateSFTP(path);
        } else {
            this.navigateLocal(path);
        }
    },

    goUp() {
        if (this.parentPath) {
            this.navigateTo(this.parentPath);
        }
    },

    refresh() {
        this.navigateTo(this.currentPath);
    },

    goHome() {
        this.navigateTo("");
    },

    renderSidebar(drives, shortcuts, isRemote = false) {
        const sidebar = document.getElementById("browser-sidebar");
        if (!sidebar) return;

        const drivesContainer = document.getElementById("browser-drives-list");
        const shortcutsContainer = document.getElementById("browser-shortcuts-list");
        const drivesSection = drivesContainer ? drivesContainer.closest(".sidebar-section") : null;

        if (drivesSection) {
            if (isRemote || !drives.length) {
                drivesSection.classList.add("hidden");
            } else {
                drivesSection.classList.remove("hidden");
            }
        }

        if (drivesContainer) {
            drivesContainer.innerHTML = drives.map(d => `
                <div class="sidebar-item ${this.currentPath.startsWith(d.path) ? 'active' : ''}" 
                     onclick="Browser.navigateTo('${this.escapeQuotes(d.path)}')">
                    <i class="fa-solid fa-hard-drive sidebar-icon text-accent-cyan"></i>
                    <span class="sidebar-label" title="${this.escapeHtml(d.path)}">${this.escapeHtml(d.name)}</span>
                </div>
            `).join("");
        }

        if (shortcutsContainer) {
            shortcutsContainer.innerHTML = shortcuts.map(s => `
                <div class="sidebar-item" onclick="Browser.navigateTo('${this.escapeQuotes(s.path)}')">
                    <i class="fa-solid ${s.icon || 'fa-folder'} sidebar-icon text-accent-purple"></i>
                    <span class="sidebar-label" title="${this.escapeHtml(s.path)}">${this.escapeHtml(s.name)}</span>
                </div>
            `).join("");
        }
    },

    renderItems() {
        const tbody = document.getElementById("browser-items-tbody");
        const emptyState = document.getElementById("browser-empty");
        if (!tbody) return;

        let filtered = this.items;
        if (this.filterText) {
            filtered = this.items.filter(item => item.name.toLowerCase().includes(this.filterText));
        }

        if (filtered.length === 0) {
            tbody.innerHTML = "";
            if (emptyState) emptyState.classList.remove("hidden");
            return;
        }

        if (emptyState) emptyState.classList.add("hidden");

        tbody.innerHTML = filtered.map(item => {
            const isSelected = this.selectedPath === item.path;
            const iconClass = item.is_dir ? "fa-folder text-accent-amber" : this.getFileIconClass(item.extension);
            const typeLabel = item.is_dir ? "Folder" : (item.extension ? item.extension.toUpperCase().replace(".", "") : "File");
            const sizeLabel = item.is_dir ? "—" : this.formatBytes(item.size);

            return `
                <tr class="browser-row ${isSelected ? 'selected' : ''}" 
                    onclick="Browser.handleItemClick('${this.escapeQuotes(item.path)}', ${item.is_dir})"
                    ondblclick="Browser.handleItemDblClick('${this.escapeQuotes(item.path)}', ${item.is_dir})">
                    <td class="browser-cell-name">
                        <i class="fa-solid ${iconClass} item-icon"></i>
                        <span class="item-name" title="${this.escapeHtml(item.name)}">${this.escapeHtml(item.name)}</span>
                    </td>
                    <td class="browser-cell-type">${typeLabel}</td>
                    <td class="browser-cell-size">${sizeLabel}</td>
                    <td class="browser-cell-date">${item.modified || "—"}</td>
                </tr>
            `;
        }).join("");
    },

    handleItemClick(path, isDir) {
        this.setSelectedPath(path, isDir);
        // Highlight active row in table
        document.querySelectorAll(".browser-row").forEach(r => r.classList.remove("selected"));
        const clickedRow = event?.currentTarget;
        if (clickedRow) clickedRow.classList.add("selected");
    },

    handleItemDblClick(path, isDir) {
        if (isDir) {
            this.navigateTo(path);
        } else {
            this.setSelectedPath(path, false);
            this.confirmSelection();
        }
    },

    setSelectedPath(path, isDir) {
        this.selectedPath = path;
        this.selectedIsDir = isDir;

        const display = document.getElementById("browser-selected-path");
        const confirmBtn = document.getElementById("btn-browser-confirm");

        if (display) {
            display.textContent = path || "None";
            display.title = path || "";
        }

        if (confirmBtn) {
            confirmBtn.disabled = !path;
            if (isDir) {
                confirmBtn.innerHTML = `<i class="fa-solid fa-folder-check"></i> Select Folder`;
            } else {
                confirmBtn.innerHTML = `<i class="fa-solid fa-file-check"></i> Select File`;
            }
        }
    },

    async createNewFolder() {
        if (this.mode === "sftp") {
            App.showToast("Creating remote folders via SFTP browse is not enabled", "info");
            return;
        }

        const name = prompt(`Enter new folder name in:\n${this.currentPath}`);
        if (!name || !name.trim()) return;

        try {
            const res = await App.fetchAPI("/fs/mkdir", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    parent_path: this.currentPath,
                    folder_name: name.trim()
                })
            });

            if (res.ok) {
                const data = await res.json();
                App.showToast(`Folder '${name.trim()}' created!`, "success");
                await this.refresh();
                this.setSelectedPath(data.new_path, true);
            } else {
                const err = await res.json();
                App.showToast(err.detail || "Failed to create folder", "error");
            }
        } catch (e) {
            App.showToast("Network error creating folder", "error");
        }
    },

    async openNativePicker() {
        const mode = this.isDestination ? "directory" : (this.showFiles ? "file" : "directory");
        App.showToast("Opening native OS dialog...", "info");
        try {
            const res = await App.fetchAPI("/fs/native-picker", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    mode: mode,
                    initial_path: this.currentPath
                })
            });

            if (res.ok) {
                const data = await res.json();
                if (data.selected_path) {
                    this.setSelectedPath(data.selected_path, true);
                    this.confirmSelection();
                } else if (data.cancelled) {
                    App.showToast("Native picker cancelled", "info");
                }
            } else {
                App.showToast("Native dialog failed to launch", "warning");
            }
        } catch (e) {
            App.showToast("Error launching native picker", "error");
        }
    },

    confirmSelection() {
        if (!this.selectedPath) {
            App.showToast("Please select a valid folder or file", "warning");
            return;
        }

        const target = document.getElementById(this.targetInputId);
        if (target) {
            target.value = this.selectedPath;
            // Dispatch input event for form validation or reactive bindings
            target.dispatchEvent(new Event("input", { bubbles: true }));
        }

        App.showToast(`Selected: ${this.selectedPath}`, "success");
        this.close();
    },

    setLoading(loading) {
        this.isLoading = loading;
        const spinner = document.getElementById("browser-loading");
        const tbody = document.getElementById("browser-items-tbody");
        if (spinner) {
            if (loading) spinner.classList.remove("hidden");
            else spinner.classList.add("hidden");
        }
        if (tbody && loading) {
            tbody.innerHTML = "";
        }
    },

    getFileIconClass(ext) {
        if (!ext) return "fa-file text-text-muted";
        ext = ext.toLowerCase();
        if ([".txt", ".log", ".md", ".json", ".xml", ".csv"].includes(ext)) return "fa-file-lines text-accent-cyan";
        if ([".zip", ".tar", ".gz", ".7z", ".rar"].includes(ext)) return "fa-file-zipper text-accent-amber";
        if ([".exe", ".bat", ".cmd", ".sh", ".ps1"].includes(ext)) return "fa-file-code text-accent-emerald";
        if ([".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"].includes(ext)) return "fa-file-image text-accent-purple";
        if ([".pdf", ".doc", ".docx", ".xls", ".xlsx"].includes(ext)) return "fa-file-pdf text-accent-rose";
        return "fa-file text-text-muted";
    },

    formatBytes(bytes) {
        if (bytes === null || bytes === undefined || isNaN(bytes)) return "—";
        if (bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    },

    escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    escapeQuotes(str) {
        if (!str) return "";
        return String(str).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    }
};

window.Browser = Browser;
document.addEventListener("DOMContentLoaded", () => Browser.init());
