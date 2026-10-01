// Jobs Manager Module
const Jobs = {
    selectedCSVFile: null,

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // Filter changes
        document.getElementById("jobs-filter-status").addEventListener("change", () => this.load());
        document.getElementById("jobs-filter-type").addEventListener("change", () => this.load());
        document.getElementById("jobs-filter-start-date").addEventListener("change", () => this.load());
        document.getElementById("jobs-filter-end-date").addEventListener("change", () => this.load());
        
        let searchTimer = null;
        document.getElementById("jobs-search-input").addEventListener("input", () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => this.load(), 300);
        });

        document.getElementById("btn-reset-job-filters").addEventListener("click", () => {
            document.getElementById("jobs-filter-status").value = "all";
            document.getElementById("jobs-filter-type").value = "all";
            document.getElementById("jobs-filter-start-date").value = "";
            document.getElementById("jobs-filter-end-date").value = "";
            document.getElementById("jobs-search-input").value = "";
            this.load();
        });

        // Bulk buttons
        document.getElementById("btn-jobs-start-all").addEventListener("click", () => this.bulkAction("start-all"));
        document.getElementById("btn-jobs-pause-all").addEventListener("click", () => this.bulkAction("pause-all"));
        document.getElementById("btn-jobs-stop-all").addEventListener("click", () => this.bulkAction("stop-all"));

        // Create job modal & browse buttons
        document.getElementById("btn-create-job-modal").addEventListener("click", () => this.openCreateModal());
        document.getElementById("job-type").addEventListener("change", (e) => this.toggleProtocolFields(e.target.value));
        document.getElementById("job-form").addEventListener("submit", (e) => this.handleSaveJob(e));

        document.getElementById("btn-browse-source")?.addEventListener("click", () => {
            const proto = document.getElementById("job-type").value;
            Browser.open({
                targetInputId: "job-source",
                protocol: proto,
                isDestination: false,
                initialPath: document.getElementById("job-source").value.trim(),
                sftpCreds: {
                    host: document.getElementById("job-host").value.trim(),
                    port: document.getElementById("job-port").value.trim() || 22,
                    username: document.getElementById("job-username").value.trim(),
                    password: document.getElementById("job-password").value
                }
            });
        });

        document.getElementById("btn-browse-dest")?.addEventListener("click", () => {
            const proto = document.getElementById("job-type").value;
            Browser.open({
                targetInputId: "job-dest",
                protocol: proto,
                isDestination: true,
                initialPath: document.getElementById("job-dest").value.trim(),
                sftpCreds: {
                    host: document.getElementById("job-host").value.trim(),
                    port: document.getElementById("job-port").value.trim() || 22,
                    username: document.getElementById("job-username").value.trim(),
                    password: document.getElementById("job-password").value
                }
            });
        });

        // Import CSV modal
        document.getElementById("btn-import-csv-modal").addEventListener("click", () => this.openImportCSVModal());
        this.setupCSVDragDrop();
        document.getElementById("import-csv-form").addEventListener("submit", (e) => this.handleUploadCSV(e));
    },

    async load() {
        const status = document.getElementById("jobs-filter-status").value;
        const type = document.getElementById("jobs-filter-type").value;
        const search = document.getElementById("jobs-search-input").value.trim();
        const startDate = document.getElementById("jobs-filter-start-date").value;
        const endDate = document.getElementById("jobs-filter-end-date").value;

        let query = "?limit=100";
        if (status !== "all") query += `&status=${encodeURIComponent(status)}`;
        if (type !== "all") query += `&transfer_type=${encodeURIComponent(type)}`;
        if (search) query += `&search=${encodeURIComponent(search)}`;
        if (startDate) query += `&start_date=${encodeURIComponent(startDate)}`;
        if (endDate) query += `&end_date=${encodeURIComponent(endDate)}`;

        try {
            const res = await App.fetchAPI(`/jobs${query}`);
            if (res.ok) {
                const data = await res.json();
                this.renderJobs(data.jobs);
            }
        } catch (e) {
            console.error("Failed to fetch jobs", e);
        }
    },

    renderJobs(jobs) {
        const tbody = document.getElementById("jobs-full-tbody");
        if (!tbody) return;

        if (!jobs || jobs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-muted">No data sync jobs found matching filters.</td></tr>`;
            return;
        }

        tbody.innerHTML = jobs.map(j => `
            <tr id="job-row-${j.id}">
                <td>
                    <strong>${this.escapeHtml(j.name)}</strong>
                    <div class="text-muted" style="font-size: 0.75rem;">ID: #${j.id}</div>
                </td>
                <td>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                        <span class="badge badge-protocol badge-${j.transfer_type}">${j.transfer_type.toUpperCase()}</span>
                        <span class="badge ${j.overwrite_mode === 'always' ? 'badge-warning' : 'badge-neutral'}" style="font-size: 0.65rem;" title="${j.overwrite_mode === 'always' ? 'Always Overwrite Files' : 'Overwrite Only Newer Files'}">
                            <i class="fa-solid ${j.overwrite_mode === 'always' ? 'fa-bolt' : 'fa-clock'}"></i> ${j.overwrite_mode === 'always' ? 'Always Overwrite' : 'Newer Only'}
                        </span>
                    </div>
                </td>
                <td>
                    <span class="path-line src" title="${this.escapeHtml(j.source_path)}"><i class="fa-solid fa-folder-open"></i> ${this.escapeHtml(j.source_path)}</span>
                </td>
                <td>
                    <span class="path-line dst" title="${this.escapeHtml(j.dest_path)}"><i class="fa-solid fa-folder-tree"></i> ${this.escapeHtml(j.dest_path)}</span>
                </td>
                <td>
                    <span id="job-status-badge-${j.id}" class="badge ${this.getStatusBadgeClass(j.status)}">${j.status.toUpperCase()}</span>
                </td>
                <td>
                    <div class="progress-bar-container">
                        <div class="progress-bar-bg">
                            <div id="job-prog-fill-${j.id}" class="progress-bar-fill ${j.status}" style="width: ${j.progress}%;"></div>
                        </div>
                        <div class="progress-label">
                            <span id="job-prog-pct-${j.id}">${j.progress.toFixed(1)}%</span>
                            <span id="job-prog-file-${j.id}" style="max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${j.current_file || ''}</span>
                        </div>
                    </div>
                </td>
                <td>
                    <div style="font-family: var(--font-mono); font-size: 0.8rem;">
                        <span id="job-speed-${j.id}">${j.speed_mbps ? j.speed_mbps.toFixed(1) + ' MB/s' : '--'}</span>
                        <div class="text-muted" id="job-bytes-${j.id}">${j.bytes_copied ? (j.bytes_copied / (1024*1024)).toFixed(1) + ' MB' : ''}</div>
                    </div>
                </td>
                <td>
                    <div class="btn-group">
                        <button class="btn btn-icon btn-sm" onclick="Jobs.startSingleJob(${j.id})" title="Start / Resume">
                            <i class="fa-solid fa-play" style="color: var(--accent-emerald)"></i>
                        </button>
                        <button class="btn btn-icon btn-sm" onclick="Jobs.pauseSingleJob(${j.id})" title="Pause">
                            <i class="fa-solid fa-pause" style="color: var(--accent-amber)"></i>
                        </button>
                        <button class="btn btn-icon btn-sm" onclick="Jobs.stopSingleJob(${j.id})" title="Stop">
                            <i class="fa-solid fa-stop" style="color: var(--accent-rose)"></i>
                        </button>
                        <button class="btn btn-icon btn-sm btn-danger-hover" onclick="Jobs.deleteJob(${j.id})" title="Delete">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join("");
    },

    updateJobLive(msg) {
        const jobId = msg.job_id;
        const progFill = document.getElementById(`job-prog-fill-${jobId}`);
        const progPct = document.getElementById(`job-prog-pct-${jobId}`);
        const progFile = document.getElementById(`job-prog-file-${jobId}`);
        const speedEl = document.getElementById(`job-speed-${jobId}`);
        const bytesEl = document.getElementById(`job-bytes-${jobId}`);
        const statusBadge = document.getElementById(`job-status-badge-${jobId}`);

        if (msg.type === "job_progress") {
            if (progFill) progFill.style.width = `${msg.progress}%`;
            if (progPct) progPct.textContent = `${msg.progress}%`;
            if (progFile && msg.current_file) progFile.textContent = msg.current_file;
            if (speedEl && msg.speed_mbps !== undefined) speedEl.textContent = `${msg.speed_mbps.toFixed(1)} MB/s`;
            if (bytesEl && msg.bytes_copied !== undefined) bytesEl.textContent = `${(msg.bytes_copied / (1024*1024)).toFixed(1)} MB`;
        } else if (msg.type === "job_status") {
            if (statusBadge) {
                statusBadge.className = `badge ${this.getStatusBadgeClass(msg.status)}`;
                statusBadge.textContent = msg.status.toUpperCase();
            }
            if (progFill) {
                progFill.className = `progress-bar-fill ${msg.status}`;
                if (msg.status === "completed") progFill.style.width = "100%";
            }
        }
    },

    async startSingleJob(jobId) {
        try {
            const res = await App.fetchAPI(`/jobs/${jobId}/start`, { method: "POST" });
            const data = await res.json();
            if (res.ok) {
                App.showToast(`Job #${jobId} started`, "success");
            } else {
                App.showToast(data.detail || "Could not start job", "error");
            }
        } catch (e) {
            App.showToast("Failed to request job start", "error");
        }
    },

    async pauseSingleJob(jobId) {
        try {
            const res = await App.fetchAPI(`/jobs/${jobId}/pause`, { method: "POST" });
            const data = await res.json();
            if (res.ok) {
                App.showToast(`Job #${jobId} paused`, "info");
            } else {
                App.showToast(data.detail || "Job is not running", "warning");
            }
        } catch (e) {
            App.showToast("Failed to request job pause", "error");
        }
    },

    async stopSingleJob(jobId) {
        try {
            const res = await App.fetchAPI(`/jobs/${jobId}/stop`, { method: "POST" });
            if (res.ok) {
                App.showToast(`Job #${jobId} stopped`, "warning");
            }
        } catch (e) {
            App.showToast("Failed to request job stop", "error");
        }
    },

    async deleteJob(jobId) {
        if (!confirm(`Are you sure you want to delete Job #${jobId}?`)) return;
        try {
            const res = await App.fetchAPI(`/jobs/${jobId}`, { method: "DELETE" });
            if (res.ok) {
                App.showToast("Job deleted successfully", "info");
                this.load();
            }
        } catch (e) {
            App.showToast("Failed to delete job", "error");
        }
    },

    async bulkAction(action) {
        try {
            const res = await App.fetchAPI(`/jobs/bulk/${action}`, { method: "POST" });
            if (res.ok) {
                App.showToast(`Bulk action '${action}' initiated.`, "success");
                this.load();
            }
        } catch (e) {
            App.showToast("Bulk command failed", "error");
        }
    },

    openCreateModal() {
        document.getElementById("job-id").value = "";
        document.getElementById("job-modal-title").textContent = "Create Data Sync Job";
        document.getElementById("job-form").reset();
        this.toggleProtocolFields("robocopy");
        document.getElementById("modal-job").classList.remove("hidden");
    },

    toggleProtocolFields(proto) {
        const container = document.getElementById("remote-fields-container");
        const authRow = document.getElementById("remote-auth-row");
        const portInput = document.getElementById("job-port");

        if (proto === "sftp") {
            container.classList.remove("hidden");
            authRow.classList.remove("hidden");
            portInput.placeholder = "22";
            if (!portInput.value) portInput.value = "22";
        } else if (proto === "udp") {
            container.classList.remove("hidden");
            authRow.classList.add("hidden");
            portInput.placeholder = "9999";
            if (!portInput.value) portInput.value = "9999";
        } else {
            container.classList.add("hidden");
        }
    },

    async handleSaveJob(e) {
        e.preventDefault();
        const payload = {
            name: document.getElementById("job-name").value.trim(),
            transfer_type: document.getElementById("job-type").value,
            source_path: document.getElementById("job-source").value.trim(),
            dest_path: document.getElementById("job-dest").value.trim(),
            overwrite_mode: document.getElementById("job-overwrite-mode")?.value || "newer",
            host: document.getElementById("job-host").value.trim() || null,
            port: document.getElementById("job-port").value ? parseInt(document.getElementById("job-port").value) : null,
            remote_username: document.getElementById("job-username").value.trim() || null,
            remote_password: document.getElementById("job-password").value || null
        };

        try {
            const res = await App.fetchAPI("/jobs", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                App.showToast("Job created successfully!", "success");
                document.getElementById("modal-job").classList.add("hidden");
                this.load();
            } else {
                const data = await res.json();
                App.showToast(data.detail || "Failed to create job", "error");
            }
        } catch (err) {
            App.showToast("Network error creating job", "error");
        }
    },

    // CSV Import handling
    openImportCSVModal() {
        this.selectedCSVFile = null;
        document.getElementById("selected-file-name").classList.add("hidden");
        document.getElementById("btn-submit-csv").disabled = true;
        document.getElementById("csv-import-results").classList.add("hidden");
        document.getElementById("modal-import-csv").classList.remove("hidden");
    },

    setupCSVDragDrop() {
        const dropZone = document.getElementById("csv-drop-zone");
        const fileInput = document.getElementById("csv-file-input");

        dropZone.addEventListener("click", () => fileInput.click());

        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelected(e.target.files[0]);
            }
        });

        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });

        dropZone.addEventListener("dragleave", () => {
            dropZone.classList.remove("dragover");
        });

        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            if (e.dataTransfer.files.length > 0) {
                this.handleFileSelected(e.dataTransfer.files[0]);
            }
        });
    },

    handleFileSelected(file) {
        if (!file.name.endsWith(".csv")) {
            App.showToast("Please select a valid .csv file", "error");
            return;
        }
        this.selectedCSVFile = file;
        const badge = document.getElementById("selected-file-name");
        badge.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        badge.classList.remove("hidden");
        document.getElementById("btn-submit-csv").disabled = false;
    },

    async handleUploadCSV(e) {
        e.preventDefault();
        if (!this.selectedCSVFile) return;

        const formData = new FormData();
        formData.append("file", this.selectedCSVFile);

        const btnSubmit = document.getElementById("btn-submit-csv");
        btnSubmit.disabled = true;
        btnSubmit.textContent = "Importing...";

        try {
            const res = await fetch("/api/jobs/import-csv", {
                method: "POST",
                headers: { "Authorization": `Bearer ${App.token}` },
                body: formData
            });

            const data = await res.json();
            btnSubmit.disabled = false;
            btnSubmit.textContent = "Upload & Import";

            const resultsContainer = document.getElementById("csv-import-results");
            resultsContainer.classList.remove("hidden");

            if (res.ok) {
                let msg = `<p style="color: var(--accent-emerald)"><strong>✓ Imported ${data.imported_count} jobs successfully!</strong></p>`;
                if (data.errors && data.errors.length > 0) {
                    msg += `<p style="color: var(--accent-rose); margin-top: 6px;">Errors (${data.errors.length}):<br>${data.errors.join('<br>')}</p>`;
                }
                resultsContainer.innerHTML = msg;
                App.showToast(`Imported ${data.imported_count} jobs`, "success");
                this.load();
            } else {
                resultsContainer.innerHTML = `<p style="color: var(--accent-rose)">✗ Import failed: ${data.detail || 'Unknown error'}</p>`;
            }
        } catch (err) {
            btnSubmit.disabled = false;
            btnSubmit.textContent = "Upload & Import";
            App.showToast("Failed to upload CSV", "error");
        }
    },

    getStatusBadgeClass(status) {
        switch (status) {
            case "running": return "badge-info";
            case "completed": return "badge-success";
            case "paused": return "badge-warning";
            case "failed": return "badge-danger";
            case "cancelled": return "badge-danger";
            default: return "badge-neutral";
        }
    },

    escapeHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
};

window.Jobs = Jobs;
document.addEventListener("DOMContentLoaded", () => Jobs.init());
