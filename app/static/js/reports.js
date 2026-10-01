// Reports & Analytics Module
const Reports = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        const btnRefresh = document.getElementById("btn-refresh-reports");
        if (btnRefresh) {
            btnRefresh.addEventListener("click", () => this.load());
        }

        const btnExport = document.getElementById("btn-export-reports-csv");
        if (btnExport) {
            btnExport.addEventListener("click", () => this.exportCSV());
        }
    },

    async load() {
        const status = document.getElementById("reports-filter-status").value;
        const start = document.getElementById("reports-filter-start-date").value;
        const end = document.getElementById("reports-filter-end-date").value;

        let query = "?limit=150";
        if (status !== "all") query += `&status=${encodeURIComponent(status)}`;
        if (start) query += `&start_date=${encodeURIComponent(start)}`;
        if (end) query += `&end_date=${encodeURIComponent(end)}`;

        try {
            const res = await App.fetchAPI(`/reports/history${query}`);
            if (res.ok) {
                const data = await res.json();
                this.renderReports(data.runs, data.total);
            }
        } catch (e) {
            console.error("Failed to fetch reports", e);
        }
    },

    renderReports(runs, total) {
        const tbody = document.getElementById("reports-tbody");
        const countBadge = document.getElementById("reports-total-count");
        if (countBadge) countBadge.textContent = `${total} Records`;
        if (!tbody) return;

        if (!runs || runs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-muted">No historical execution records found.</td></tr>`;
            return;
        }

        tbody.innerHTML = runs.map(r => `
            <tr>
                <td><strong>#${r.id}</strong></td>
                <td>
                    <strong>${this.escapeHtml(r.job_name)}</strong>
                    <div class="text-muted" style="font-size: 0.75rem;">Job #${r.job_id}</div>
                </td>
                <td><span class="badge badge-protocol badge-${r.transfer_type}">${(r.transfer_type || 'unknown').toUpperCase()}</span></td>
                <td><span style="color: var(--accent-cyan); font-weight: 500;">${this.escapeHtml(r.username || 'System')}</span></td>
                <td><span class="badge ${this.getStatusBadgeClass(r.status)}">${r.status.toUpperCase()}</span></td>
                <td style="white-space: nowrap; color: var(--text-muted);">${r.start_time ? new Date(r.start_time).toLocaleString() : '--'}</td>
                <td style="font-family: var(--font-mono);">${r.duration_seconds ? r.duration_seconds + 's' : '0s'}</td>
                <td style="font-family: var(--font-mono);">${(r.bytes_transferred / (1024 * 1024)).toFixed(2)} MB</td>
                <td>${r.files_copied || 0}</td>
                <td><code>${r.exit_code}</code></td>
            </tr>
        `).join("");
    },

    async exportCSV() {
        const status = document.getElementById("reports-filter-status").value;
        const start = document.getElementById("reports-filter-start-date").value;
        const end = document.getElementById("reports-filter-end-date").value;

        let query = "?";
        if (status !== "all") query += `&status=${encodeURIComponent(status)}`;
        if (start) query += `&start_date=${encodeURIComponent(start)}`;
        if (end) query += `&end_date=${encodeURIComponent(end)}`;

        try {
            const res = await App.fetchAPI(`/reports/export${query}`);
            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `sync_tool_report_${new Date().toISOString().slice(0,10)}.csv`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                App.showToast("Report CSV downloaded", "success");
            }
        } catch (e) {
            App.showToast("Failed to export report CSV", "error");
        }
    },

    getStatusBadgeClass(status) {
        switch (status) {
            case "completed": return "badge-success";
            case "failed": return "badge-danger";
            case "cancelled": return "badge-warning";
            default: return "badge-neutral";
        }
    },

    escapeHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
};

window.Reports = Reports;
document.addEventListener("DOMContentLoaded", () => Reports.init());
