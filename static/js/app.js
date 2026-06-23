/**
 * Auto-Bump Dashboard — JavaScript Application
 * 
 * Manages all dashboard state, API communication, and UI updates.
 */

class DashboardApp {
    constructor() {
        this.refreshInterval = null;
        this.countdownInterval = null;
        this.channels = [];
        this.init();
    }

    // ── Initialization ────────────────────────────────────────────

    init() {
        this.bindElements();
        this.bindEvents();
        this.startAutoRefresh();
        this.startCountdownTimer();
        this.refresh();
    }

    bindElements() {
        // Stats
        this.elTotalAccounts = document.getElementById('val-total-accounts');
        this.elActiveAccounts = document.getElementById('val-active-accounts');
        this.elChannels = document.getElementById('val-channels');
        this.elSuccessRate = document.getElementById('val-success-rate');
        this.elTotalBumps = document.getElementById('val-total-bumps');
        this.elNextBump = document.getElementById('val-next-bump');
        this.elNextBumpChannel = document.getElementById('val-next-bump-channel');

        // Tables
        this.elAccountsTbody = document.getElementById('accounts-tbody');
        this.elChannelsTbody = document.getElementById('channels-tbody');

        // Logs
        this.elLogFeed = document.getElementById('log-feed');
        this.elLogCount = document.getElementById('log-count');

        // Scheduler
        this.elSchedulerIndicator = document.getElementById('scheduler-indicator');
        this.elSchedulerLabel = document.getElementById('scheduler-label');
        this.elSchedulerToggle = document.getElementById('scheduler-toggle');
        this.elUptimeValue = document.getElementById('uptime-value');

        // Modal
        this.elModalOverlay = document.getElementById('modal-overlay');
        this.elForm = document.getElementById('form-add-account');
        this.elInputName = document.getElementById('input-name');
        this.elInputToken = document.getElementById('input-token');
        this.elInputChannels = document.getElementById('input-channels');
    }

    bindEvents() {
        // Add account modal
        document.getElementById('btn-add-account').addEventListener('click', () => this.openModal());
        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        document.getElementById('btn-cancel').addEventListener('click', () => this.closeModal());
        this.elModalOverlay.addEventListener('click', (e) => {
            if (e.target === this.elModalOverlay) this.closeModal();
        });

        // Form submit
        this.elForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.addAccount();
        });

        // Token visibility toggle
        document.getElementById('btn-toggle-token').addEventListener('click', () => {
            const input = this.elInputToken;
            input.type = input.type === 'password' ? 'text' : 'password';
        });

        // Scheduler toggle
        this.elSchedulerToggle.addEventListener('click', () => this.toggleScheduler());

        // Keyboard shortcut: Escape to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });
    }

    // ── Auto Refresh ──────────────────────────────────────────────

    startAutoRefresh() {
        this.refreshInterval = setInterval(() => this.refresh(), 10000);
    }

    startCountdownTimer() {
        this.countdownInterval = setInterval(() => this.updateCountdowns(), 1000);
    }

    async refresh() {
        try {
            await Promise.all([
                this.fetchStats(),
                this.fetchAccounts(),
                this.fetchChannels(),
                this.fetchLogs(),
                this.fetchSchedulerStatus(),
            ]);
        } catch (err) {
            console.error('Refresh error:', err);
        }
    }

    // ── API Helpers ───────────────────────────────────────────────

    async api(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(`/api${path}`, opts);
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || `API error ${res.status}`);
        }
        return res.json();
    }

    // ── Stats ─────────────────────────────────────────────────────

    async fetchStats() {
        const stats = await this.api('GET', '/stats');

        this.elTotalAccounts.textContent = stats.total_accounts;
        this.elActiveAccounts.textContent = stats.active_accounts;
        this.elChannels.textContent = stats.total_channels;
        this.elTotalBumps.textContent = stats.total_bumps;

        if (stats.total_bumps > 0) {
            const rate = Math.round((stats.successful_bumps / stats.total_bumps) * 100);
            this.elSuccessRate.textContent = `${rate}%`;
        } else {
            this.elSuccessRate.textContent = '—';
        }

        if (stats.next_bump_time) {
            this.elNextBump.textContent = this.formatCountdown(stats.next_bump_time);
            this.elNextBumpChannel.textContent = stats.next_bump_channel || '';
        } else {
            this.elNextBump.textContent = '—';
            this.elNextBumpChannel.textContent = '';
        }
    }

    // ── Accounts ──────────────────────────────────────────────────

    async fetchAccounts() {
        const accounts = await this.api('GET', '/accounts');
        this.renderAccounts(accounts);
    }

    renderAccounts(accounts) {
        if (accounts.length === 0) {
            this.elAccountsTbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="7">
                        <div class="empty-state">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                                <circle cx="9" cy="7" r="4"/>
                            </svg>
                            <p>No accounts configured</p>
                            <p class="empty-hint">Click "Add Account" to get started</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        this.elAccountsTbody.innerHTML = accounts.map(acc => {
            const statusBadge = this.getAccountStatusBadge(acc);
            const cooldownBadge = this.getAccountCooldownBadge(acc);
            const channelTags = acc.channel_ids.map(id =>
                `<span class="channel-tag">${id}</span>`
            ).join('');
            const lastBump = acc.last_bump > 0
                ? this.formatRelativeTime(acc.last_bump * 1000)
                : 'Never';

            return `
                <tr data-account-id="${acc.id}">
                    <td>${statusBadge}</td>
                    <td><strong>${this.escapeHtml(acc.name || `Account ${acc.id}`)}</strong></td>
                    <td><span class="token-display">${this.escapeHtml(acc.token_hint)}</span></td>
                    <td><div class="channel-tags">${channelTags || '<span style="color:var(--text-tertiary)">None</span>'}</div></td>
                    <td>${lastBump}</td>
                    <td>${cooldownBadge}</td>
                    <td>
                        <div class="actions-cell">
                            <label class="toggle" title="${acc.enabled ? 'Disable' : 'Enable'} account">
                                <input type="checkbox" ${acc.enabled ? 'checked' : ''}
                                       onchange="app.toggleAccount(${acc.id}, this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                            <button class="btn-icon btn-danger" title="Remove account"
                                    onclick="app.removeAccount(${acc.id}, '${this.escapeHtml(acc.name || `Account ${acc.id}`)}')">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3 6 5 6 21 6"/>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                </svg>
                            </button>
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    getAccountStatusBadge(acc) {
        if (!acc.enabled) {
            return '<span class="badge badge-disabled"><span class="badge-dot"></span>Disabled</span>';
        }
        if (acc.error_status) {
            return `<span class="badge badge-error" title="${this.escapeHtml(acc.error_status)}"><span class="badge-dot"></span>Error</span>`;
        }
        if (acc.connected) {
            return '<span class="badge badge-online"><span class="badge-dot"></span>Online</span>';
        }
        return '<span class="badge badge-offline"><span class="badge-dot"></span>Offline</span>';
    }

    getAccountCooldownBadge(acc) {
        if (acc.last_bump <= 0) return '<span style="color:var(--text-tertiary)">—</span>';
        const now = Date.now() / 1000;
        const elapsed = now - acc.last_bump;
        const cooldownSec = 30 * 60; // 30 minutes
        if (elapsed < cooldownSec) {
            const remaining = Math.ceil((cooldownSec - elapsed) / 60);
            return `<span class="badge badge-cooldown">${remaining}m</span>`;
        }
        return '<span class="badge badge-online">Ready</span>';
    }

    // ── Channels ──────────────────────────────────────────────────

    async fetchChannels() {
        this.channels = await this.api('GET', '/channels');
        this.renderChannels(this.channels);
    }

    renderChannels(channels) {
        if (channels.length === 0) {
            this.elChannelsTbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="5">
                        <div class="empty-state">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                                <path d="M4 11a9 9 0 0 1 9 9"/>
                                <path d="M4 4a16 16 0 0 1 16 16"/>
                                <circle cx="5" cy="19" r="1"/>
                            </svg>
                            <p>No channels configured</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        this.elChannelsTbody.innerHTML = channels.map(ch => {
            const lastBump = ch.last_bump > 0
                ? this.formatRelativeTime(ch.last_bump * 1000)
                : 'Never';
            const nextBump = ch.next_bump > 0
                ? this.formatAbsoluteTime(ch.next_bump * 1000)
                : '—';
            const countdown = ch.next_bump > 0
                ? this.formatCountdown(ch.next_bump)
                : '—';
            const countdownClass = this.getCountdownClass(ch.next_bump);

            return `
                <tr data-channel-id="${ch.channel_id}">
                    <td><span class="channel-tag">${ch.channel_id}</span></td>
                    <td>${lastBump}</td>
                    <td>${nextBump}</td>
                    <td><span class="countdown ${countdownClass}" data-next="${ch.next_bump}">${countdown}</span></td>
                    <td>${ch.assigned_accounts}</td>
                </tr>`;
        }).join('');
    }

    updateCountdowns() {
        document.querySelectorAll('.countdown[data-next]').forEach(el => {
            const nextBump = parseFloat(el.dataset.next);
            if (nextBump > 0) {
                el.textContent = this.formatCountdown(nextBump);
                el.className = `countdown ${this.getCountdownClass(nextBump)}`;
            }
        });

        // Also update the stats next-bump
        // (refreshed on full refresh, but keep countdown live)
    }

    getCountdownClass(nextBumpTimestamp) {
        if (!nextBumpTimestamp || nextBumpTimestamp <= 0) return '';
        const now = Date.now() / 1000;
        const remaining = nextBumpTimestamp - now;
        if (remaining <= 0) return 'ready';
        if (remaining < 300) return 'soon';    // < 5 min
        if (remaining < 1800) return 'waiting'; // < 30 min
        return 'far';
    }

    // ── Logs ──────────────────────────────────────────────────────

    async fetchLogs() {
        const logs = await this.api('GET', '/logs?limit=50');
        this.renderLogs(logs);
    }

    renderLogs(logs) {
        this.elLogCount.textContent = `${logs.length} entries`;

        if (logs.length === 0) {
            this.elLogFeed.innerHTML = `
                <div class="empty-state">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <p>No activity yet</p>
                </div>`;
            return;
        }

        this.elLogFeed.innerHTML = logs.map(log => {
            const icon = log.success ? '✅' : '❌';
            const iconClass = log.success ? 'success' : 'failure';
            const action = log.success ? 'Bumped' : 'Failed to bump';
            const time = this.formatRelativeTime(log.timestamp * 1000);
            const reason = log.reason
                ? `<div class="log-reason">↳ ${this.escapeHtml(log.reason)}</div>`
                : '';

            return `
                <div class="log-entry">
                    <div class="log-icon ${iconClass}">${icon}</div>
                    <div class="log-content">
                        <div class="log-message">
                            ${action} channel <span class="log-channel">${log.channel_id}</span>
                            with <span class="log-account">${this.escapeHtml(log.account_name)}</span>
                        </div>
                        ${reason}
                        <div class="log-meta">
                            <span>${time}</span>
                        </div>
                    </div>
                </div>`;
        }).join('');
    }

    // ── Scheduler ─────────────────────────────────────────────────

    async fetchSchedulerStatus() {
        const status = await this.api('GET', '/scheduler/status');
        this.renderSchedulerStatus(status);
    }

    renderSchedulerStatus(status) {
        if (status.running) {
            this.elSchedulerIndicator.className = 'scheduler-status active';
            this.elSchedulerLabel.textContent = 'Running';
            this.elSchedulerToggle.classList.add('running');
            this.elSchedulerToggle.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="6" y="4" width="4" height="16"/>
                    <rect x="14" y="4" width="4" height="16"/>
                </svg>`;
        } else {
            this.elSchedulerIndicator.className = 'scheduler-status inactive';
            this.elSchedulerLabel.textContent = 'Stopped';
            this.elSchedulerToggle.classList.remove('running');
            this.elSchedulerToggle.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>`;
        }

        this.elUptimeValue.textContent = this.formatDuration(status.uptime);
    }

    async toggleScheduler() {
        try {
            const result = await this.api('POST', '/scheduler/toggle');
            this.toast(result.running ? 'Scheduler started' : 'Scheduler stopped',
                       result.running ? 'success' : 'info');
            await this.fetchSchedulerStatus();
        } catch (err) {
            this.toast(`Failed to toggle scheduler: ${err.message}`, 'error');
        }
    }

    // ── Account Actions ───────────────────────────────────────────

    async addAccount() {
        const token = this.elInputToken.value.trim();
        const name = this.elInputName.value.trim();
        const channelsRaw = this.elInputChannels.value.trim();

        if (!token) {
            this.toast('Token is required', 'error');
            return;
        }
        if (!channelsRaw) {
            this.toast('At least one channel ID is required', 'error');
            return;
        }

        // Parse channel IDs (comma or newline separated)
        const channelIds = channelsRaw
            .split(/[\s,]+/)
            .map(s => s.trim())
            .filter(s => s.length > 0);

        try {
            await this.api('POST', '/accounts', { token, name, channel_ids: channelIds });
            this.toast(`Account "${name || 'New Account'}" added successfully`, 'success');
            this.closeModal();
            this.elForm.reset();
            await this.refresh();
        } catch (err) {
            this.toast(`Failed to add account: ${err.message}`, 'error');
        }
    }

    async toggleAccount(accountId, enabled) {
        try {
            await this.api('PATCH', `/accounts/${accountId}`, { enabled });
            this.toast(`Account ${enabled ? 'enabled' : 'disabled'}`, 'success');
            await this.refresh();
        } catch (err) {
            this.toast(`Failed to update account: ${err.message}`, 'error');
        }
    }

    async removeAccount(accountId, name) {
        if (!confirm(`Remove account "${name}"? This cannot be undone.`)) return;

        try {
            await this.api('DELETE', `/accounts/${accountId}`);
            this.toast(`Account "${name}" removed`, 'success');
            await this.refresh();
        } catch (err) {
            this.toast(`Failed to remove account: ${err.message}`, 'error');
        }
    }

    // ── Modal ─────────────────────────────────────────────────────

    openModal() {
        this.elModalOverlay.classList.add('visible');
        this.elInputName.focus();
    }

    closeModal() {
        this.elModalOverlay.classList.remove('visible');
    }

    // ── Toast Notifications ───────────────────────────────────────

    toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const icons = { success: '✅', error: '❌', info: 'ℹ️' };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span>${this.escapeHtml(message)}</span>`;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('removing');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ── Formatting Helpers ────────────────────────────────────────

    formatRelativeTime(timestampMs) {
        const now = Date.now();
        const diff = now - timestampMs;
        const seconds = Math.floor(diff / 1000);

        if (seconds < 5) return 'Just now';
        if (seconds < 60) return `${seconds}s ago`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ${minutes % 60}m ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    }

    formatAbsoluteTime(timestampMs) {
        const date = new Date(timestampMs);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    formatCountdown(nextBumpTimestamp) {
        const now = Date.now() / 1000;
        const remaining = nextBumpTimestamp - now;

        if (remaining <= 0) return 'Ready!';

        const hours = Math.floor(remaining / 3600);
        const minutes = Math.floor((remaining % 3600) / 60);
        const seconds = Math.floor(remaining % 60);

        if (hours > 0) return `${hours}h ${minutes}m`;
        if (minutes > 0) return `${minutes}m ${seconds}s`;
        return `${seconds}s`;
    }

    formatDuration(totalSeconds) {
        if (totalSeconds <= 0) return '0m';
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// ── Bootstrap ─────────────────────────────────────────────────────
const app = new DashboardApp();
