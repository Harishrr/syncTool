// Log Explorer Module (Admin Only)
const Logs = {
    init() {
        this.bindEvents();
    },

    bindEvents() {
        const btnRefresh = document.getElementById("btn-refresh-logs");
        if (btnRefresh) {
            btnRefresh.addEventListener("click", () => this.load());
        }

        const filterLevel = document.getElementById("logs-filter-level");
        if (filterLevel) {
            filterLevel.addEventListener("change", () => this.load());
        }

        const filterCat = document.getElementById("logs-filter-category");
        if (filterCat) {
            filterCat.addEventListener("change", () => this.load());
        }

        const filterStart = document.getElementById("logs-filter-start-date");
        if (filterStart) {
            filterStart.addEventListener("change", () => this.load());
        }

        const filterEnd = document.getElementById("logs-filter-end-date");
        if (filterEnd) {
            filterEnd.addEventListener("change", () => this.load());
        }

        let searchTimer = null;
        const searchInput = document.getElementById("logs-search-input");
        if (searchInput) {
            searchInput.addEventListener("input", () => {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(() => this.load(), 300);
            });
        }
    },

    async load() {
        if (!App.currentUser || App.currentUser.role !== "admin") return;

        const level = document.getElementById("logs-filter-level").value;
        const cat = document.getElementById("logs-filter-category").value;
        const search = document.getElementById("logs-search-input").value.trim();
        const start = document.getElementById("logs-filter-start-date").value;
        const end = document.getElementById("logs-filter-end-date").value;

        let query = "?limit=150";
        if (level !== "ALL") query += `&level=${encodeURIComponent(level)}`;
        if (cat !== "ALL") query += `&category=${encodeURIComponent(cat)}`;
        if (search) query += `&search=${encodeURIComponent(search)}`;
        if (start) query += `&start_date=${encodeURIComponent(start)}`;
        if (end) query += `&end_date=${encodeURIComponent(end)}`;

        try {
            const res = await App.fetchAPI(`/logs${query}`);
            if (res.ok) {
                const data = await res.json();
                this.renderLogs(data.logs);
            }
        } catch (e) {
            console.error("Failed to fetch logs", e);
        }
    },

    renderLogs(logs) {
        const tbody = document.getElementById("logs-tbody");
        if (!tbody) return;

        if (!logs || logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">No log entries found.</td></tr>`;
            return;
        }

        tbody.innerHTML = logs.map(l => `
            <tr>
                <td style="white-space: nowrap; color: var(--text-muted);">${new Date(l.timestamp).toLocaleString()}</td>
                <td><span class="badge ${this.getLevelBadgeClass(l.level)}">${l.level}</span></td>
                <td><span class="badge badge-neutral">${l.category}</span></td>
                <td><strong>${this.escapeHtml(l.action)}</strong></td>
                <td>${l.username ? `<span style="color: var(--accent-cyan); font-weight: 500;">${this.escapeHtml(l.username)}</span>` : '<span class="text-muted">SYSTEM</span>'}</td>
                <td style="color: var(--text-main); word-break: break-all;">${this.escapeHtml(l.details || '')}</td>
            </tr>
        `).join("");
    },

    getLevelBadgeClass(level) {
        switch (level) {
            case "INFO": return "badge-info";
            case "WARNING": return "badge-warning";
            case "ERROR": return "badge-danger";
            case "CRITICAL": return "badge-danger";
            default: return "badge-neutral";
        }
    },

    escapeHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
};

window.Logs = Logs;
document.addEventListener("DOMContentLoaded", () => Logs.init());
