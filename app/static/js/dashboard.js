// Dashboard Module
const Dashboard = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        const btnStartAll = document.getElementById("btn-dash-start-all");
        if (btnStartAll) {
            btnStartAll.addEventListener("click", () => this.bulkAction("start-all"));
        }
        const btnPauseAll = document.getElementById("btn-dash-pause-all");
        if (btnPauseAll) {
            btnPauseAll.addEventListener("click", () => this.bulkAction("pause-all"));
        }
        const btnStopAll = document.getElementById("btn-dash-stop-all");
        if (btnStopAll) {
            btnStopAll.addEventListener("click", () => this.bulkAction("stop-all"));
        }

        const btnNew = document.getElementById("btn-quick-new-job");
        if (btnNew) {
            btnNew.addEventListener("click", () => {
                if (window.Jobs) Jobs.openCreateModal();
            });
        }

        const btnImport = document.getElementById("btn-quick-import-csv");
        if (btnImport) {
            btnImport.addEventListener("click", () => {
                if (window.Jobs) Jobs.openImportCSVModal();
            });
        }
    },

    async load() {
        await Promise.all([
            this.loadMetrics(),
            this.loadRecentJobs()
        ]);
    },

    async loadMetrics() {
        try {
            const res = await App.fetchAPI("/reports/summary");
            if (res.ok) {
                const data = await res.json();
                document.getElementById("stat-active-jobs").textContent = data.running_jobs;
                document.getElementById("stat-success-runs").textContent = data.successful_runs;
                document.getElementById("stat-failed-runs").textContent = data.failed_runs;
                
                const mb = (data.total_bytes_transferred / (1024 * 1024)).toFixed(1);
                document.getElementById("stat-bytes-transferred").textContent = `${mb} MB`;
            }
        } catch (e) {
            console.error("Failed to load dashboard metrics", e);
        }
    },

    async loadRecentJobs() {
        try {
            const res = await App.fetchAPI("/jobs?limit=5");
            if (res.ok) {
                const data = await res.json();
                this.renderJobsTable(data.jobs);
            }
        } catch (e) {
            console.error("Failed to load dashboard jobs", e);
        }
    },

    renderJobsTable(jobs) {
        const tbody = document.getElementById("dashboard-jobs-tbody");
        if (!tbody) return;

        if (!jobs || jobs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No sync jobs configured yet. Create one to get started!</td></tr>`;
            return;
        }

        tbody.innerHTML = jobs.map(j => `
            <tr id="dash-job-row-${j.id}">
                <td>
                    <strong>${this.escapeHtml(j.name)}</strong>
                    <div class="text-muted" style="font-size: 0.75rem;">ID: #${j.id}</div>
                </td>
                <td>
                    <span class="badge badge-protocol badge-${j.transfer_type}">${j.transfer_type.toUpperCase()}</span>
                </td>
                <td>
                    <div class="path-display">
                        <span class="path-line src" title="${this.escapeHtml(j.source_path)}"><i class="fa-solid fa-arrow-up"></i> ${this.escapeHtml(j.source_path)}</span>
                        <span class="path-line dst" title="${this.escapeHtml(j.dest_path)}"><i class="fa-solid fa-arrow-down"></i> ${this.escapeHtml(j.dest_path)}</span>
                    </div>
                </td>
                <td>
                    <span id="dash-status-badge-${j.id}" class="badge ${this.getStatusBadgeClass(j.status)}">${j.status.toUpperCase()}</span>
                </td>
                <td>
                    <div class="progress-bar-container">
                        <div class="progress-bar-bg">
                            <div id="dash-prog-fill-${j.id}" class="progress-bar-fill ${j.status}" style="width: ${j.progress}%;"></div>
                        </div>
                        <div class="progress-label">
                            <span id="dash-prog-pct-${j.id}">${j.progress.toFixed(1)}%</span>
                            <span id="dash-prog-file-${j.id}" style="max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${j.current_file || ''}</span>
                        </div>
                    </div>
                </td>
                <td>
                    <span id="dash-speed-${j.id}" style="font-family: var(--font-mono); font-size: 0.8rem;">${j.speed_mbps ? j.speed_mbps.toFixed(1) + ' MB/s' : '--'}</span>
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
                    </div>
                </td>
            </tr>
        `).join("");
    },

    updateJobLive(msg) {
        const jobId = msg.job_id;
        const progFill = document.getElementById(`dash-prog-fill-${jobId}`);
        const progPct = document.getElementById(`dash-prog-pct-${jobId}`);
        const progFile = document.getElementById(`dash-prog-file-${jobId}`);
        const speedEl = document.getElementById(`dash-speed-${jobId}`);
        const statusBadge = document.getElementById(`dash-status-badge-${jobId}`);

        if (msg.type === "job_progress") {
            if (progFill) progFill.style.width = `${msg.progress}%`;
            if (progPct) progPct.textContent = `${msg.progress}%`;
            if (progFile && msg.current_file) progFile.textContent = msg.current_file;
            if (speedEl && msg.speed_mbps !== undefined) speedEl.textContent = `${msg.speed_mbps.toFixed(1)} MB/s`;
        } else if (msg.type === "job_status") {
            if (statusBadge) {
                statusBadge.className = `badge ${this.getStatusBadgeClass(msg.status)}`;
                statusBadge.textContent = msg.status.toUpperCase();
            }
            if (progFill) {
                progFill.className = `progress-bar-fill ${msg.status}`;
                if (msg.status === "completed") progFill.style.width = "100%";
            }
            // Refresh metrics counter
            this.loadMetrics();
        }
    },

    async bulkAction(action) {
        try {
            const res = await App.fetchAPI(`/jobs/bulk/${action}`, { method: "POST" });
            if (res.ok) {
                App.showToast(`Action '${action}' executed successfully`, "success");
                this.load();
            }
        } catch (e) {
            App.showToast(`Failed to execute ${action}`, "error");
        }
    },

    getStatusBadgeClass(status) {
        switch (status) {
            case "running": return "badge-info";
            case "completed": return "badge-success";
            case "paused": return "badge-warning";
            case "failed": return "badge-danger";
            default: return "badge-neutral";
        }
    },

    escapeHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
};

window.Dashboard = Dashboard;
document.addEventListener("DOMContentLoaded", () => Dashboard.init());
