// ─── Auth Session ───────────────────────────────────────────────────────────

const SESSION_KEY = 'fileflow_session';

function getSession() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); } catch { return null; }
}
function saveSession(data) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
}
function clearSession() {
    sessionStorage.removeItem(SESSION_KEY);
}

/** All API calls go through authFetch so the Bearer token is always sent. */
async function authFetch(url, options = {}) {
    const session = getSession();
    if (session?.token) {
        options.headers = { ...(options.headers || {}), Authorization: `Bearer ${session.token}` };
    }
    const res = await fetch(url, options);
    if (res.status === 401) {
        clearSession();
        showLoginPage();
        throw new Error('Session expired — please log in again');
    }
    return res;
}

function showLoginPage()    { document.getElementById('login-overlay').classList.remove('hidden'); }
function hideLLoginPage()   { document.getElementById('login-overlay').classList.add('hidden'); }

/** Disable all write controls for viewer role */
function applyRole(role) {
    if (role === 'admin') return;  // admin sees everything

    // Hide Save + Add Job buttons
    const saveBtn    = document.getElementById('save-config-btn');
    const addJobBtn  = document.getElementById('add-job-btn');
    if (saveBtn)   { saveBtn.style.display   = 'none'; }
    if (addJobBtn) { addJobBtn.style.display = 'none'; }

    // We'll also lock cards after they're rendered — see renderJobCards patch
    document.body.setAttribute('data-role', 'viewer');
}

/** After job cards render, lock all inputs/buttons for viewers */
function lockCardsForViewer() {
    if (document.body.getAttribute('data-role') !== 'viewer') return;
    document.querySelectorAll('.job-card input, .job-card select, .job-card textarea').forEach(el => {
        el.setAttribute('readonly', 'true');
        el.setAttribute('disabled', 'true');
    });
    document.querySelectorAll('.job-card .toggle, .job-card .step-pill, .job-card .delete-job-btn, .job-card .btn').forEach(el => {
        el.setAttribute('disabled', 'true');
        el.style.pointerEvents = 'none';
        el.style.opacity = '0.5';
    });
}

// ── Login form handler ───────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const loginForm      = document.getElementById('login-form');
    const loginError     = document.getElementById('login-error');
    const userBadge      = document.getElementById('user-badge');
    const userBadgeName  = document.getElementById('user-badge-name');
    const userBadgeRole  = document.getElementById('user-badge-role');
    const logoutBtn      = document.getElementById('logout-btn');

    // Check existing session
    const existingSession = getSession();
    if (existingSession?.token) {
        hideLLoginPage();
        renderUserBadge(existingSession.username, existingSession.role);
        applyRole(existingSession.role);
    } else {
        showLoginPage();
    }

    loginForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginError.textContent = '';
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;
        const submitBtn = loginForm.querySelector('button[type="submit"]');
        submitBtn.textContent = 'Signing in…';
        submitBtn.disabled = true;

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            const data = await res.json();
            if (!res.ok) {
                loginError.textContent = data.detail || 'Login failed';
                return;
            }
            saveSession({ token: data.token, username: data.username, role: data.role });
            hideLLoginPage();
            renderUserBadge(data.username, data.role);
            applyRole(data.role);
            // Trigger dashboard load
            loadDashboardData();
        } catch (err) {
            loginError.textContent = 'Network error — server unreachable';
        } finally {
            submitBtn.textContent = 'Sign In';
            submitBtn.disabled = false;
        }
    });

    logoutBtn?.addEventListener('click', () => {
        clearSession();
        showLoginPage();
        document.getElementById('login-username').value = '';
        document.getElementById('login-password').value = '';
        loginError.textContent = '';
    });

    function renderUserBadge(username, role) {
        if (userBadge) userBadge.classList.remove('hidden');
        const avatarEl = document.getElementById('user-avatar-initial');
        if (avatarEl) avatarEl.textContent = username.charAt(0).toUpperCase();
        if (userBadgeName) userBadgeName.textContent = username;
        if (userBadgeRole) userBadgeRole.textContent = role === 'admin' ? '⚡ Admin' : '👁 Viewer';
        if (userBadgeRole) userBadgeRole.style.color = role === 'admin' ? 'var(--accent)' : 'var(--warning)';
    }
});

document.addEventListener('DOMContentLoaded', () => {


    const navLinks = document.querySelectorAll('.nav-links li');
    const sections = document.querySelectorAll('.view-section');
    const headerTitle = document.querySelector('.topbar h2');

    const viewTitles = {
        'dashboard': 'Overview',
        'config': 'Configuration Management',
        'logs': 'System Console'
    };

    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            const viewId = link.getAttribute('data-view');
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            headerTitle.textContent = viewTitles[viewId];
            sections.forEach(sec => sec.style.display = 'none');
            document.getElementById(`view-${viewId}`).style.display = 'block';
            if(viewId === 'dashboard') loadDashboardData();
            if(viewId === 'config') loadConfig();
            if(viewId === 'logs') loadLogs();
        });
    });


    // ── Transfers: filter state & pagination ─────────────────────────────────
    let transferPage    = 1;
    const PAGE_SIZE     = 20;
    let totalPages      = 1;

    function getFilters() {
        return {
            job_id:      document.getElementById('filter-job-id')?.value.trim()       || '',
            file_name:   document.getElementById('filter-file-name')?.value.trim()    || '',
            status:      document.getElementById('filter-status')?.value              || '',
            source_type: document.getElementById('filter-source-type')?.value         || '',
            dest_type:   document.getElementById('filter-dest-type')?.value           || '',
            date_from:   document.getElementById('filter-date-from')?.value           || '',
            date_to:     document.getElementById('filter-date-to')?.value             || '',
        };
    }

    async function loadTransfers(page = 1) {
        transferPage = page;
        const f = getFilters();
        const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
        if (f.job_id)      params.set('job_id',      f.job_id);
        if (f.file_name)   params.set('file_name',   f.file_name);
        if (f.status)      params.set('status',      f.status);
        if (f.source_type) params.set('source_type', f.source_type);
        if (f.dest_type)   params.set('dest_type',   f.dest_type);
        if (f.date_from)   params.set('date_from',   f.date_from);
        if (f.date_to)     params.set('date_to',     f.date_to);

        try {
            const res  = await authFetch(`/transfers?${params}`);
            const data = await res.json();
            totalPages = data.pages || 1;
            populateTransfersTable(data.transfers || []);
            renderPagination(data.page, data.pages, data.total, data.page_size);
        } catch(e) {
            console.error('Failed to load transfers', e);
        }
    }

    function renderPagination(page, pages, total, pageSize) {
        const info      = document.getElementById('pagination-info');
        const numbers   = document.getElementById('page-numbers');
        const prevBtn   = document.getElementById('page-prev');
        const nextBtn   = document.getElementById('page-next');
        if (!info) return;

        const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
        const to   = Math.min(page * pageSize, total);
        info.textContent = total === 0
            ? 'No records found'
            : `Showing ${from}–${to} of ${total} record${total !== 1 ? 's' : ''}`;

        prevBtn.disabled = page <= 1;
        nextBtn.disabled = page >= pages;

        // Build page number buttons (show up to 7 slots with ellipsis)
        numbers.innerHTML = '';
        const makeBtn = (n) => {
            const b = document.createElement('button');
            b.className = 'page-num-btn' + (n === page ? ' active' : '');
            b.textContent = n;
            b.addEventListener('click', () => loadTransfers(n));
            return b;
        };
        const ellipsis = () => {
            const s = document.createElement('span');
            s.className = 'page-ellipsis';
            s.textContent = '…';
            return s;
        };

        if (pages <= 7) {
            for (let i = 1; i <= pages; i++) numbers.appendChild(makeBtn(i));
        } else {
            numbers.appendChild(makeBtn(1));
            if (page > 3) numbers.appendChild(ellipsis());
            const start = Math.max(2, page - 1);
            const end   = Math.min(pages - 1, page + 1);
            for (let i = start; i <= end; i++) numbers.appendChild(makeBtn(i));
            if (page < pages - 2) numbers.appendChild(ellipsis());
            numbers.appendChild(makeBtn(pages));
        }
    }

    // ── Stats-only auto-refresh (transfers have their own refresh) ────────────
    setInterval(async () => {
        if(document.getElementById('view-dashboard').style.display === 'none') return;
        try {
            const res  = await authFetch('/stats/summary');
            const data = await res.json();
            document.getElementById('stat-total-jobs').textContent = data.total_jobs.toLocaleString();
            document.getElementById('stat-success').textContent    = data.successful_transfers.toLocaleString();
            document.getElementById('stat-skipped').textContent    = data.duplicate_skips.toLocaleString();
            document.getElementById('stat-failed').textContent     = data.failed_transfers.toLocaleString();
        } catch(e) { /* silent */ }
    }, 5000);

    // Transfers auto-refresh (respects current filters & page)
    setInterval(() => {
        if(document.getElementById('view-dashboard').style.display !== 'none') loadTransfers(transferPage);
    }, 15000);

    async function loadDashboardData() {
        if(document.getElementById('view-dashboard').style.display === 'none') return;
        try {
            const res  = await authFetch('/stats/summary');
            const data = await res.json();
            document.getElementById('stat-total-jobs').textContent = data.total_jobs.toLocaleString();
            document.getElementById('stat-success').textContent    = data.successful_transfers.toLocaleString();
            document.getElementById('stat-skipped').textContent    = data.duplicate_skips.toLocaleString();
            document.getElementById('stat-failed').textContent     = data.failed_transfers.toLocaleString();
        } catch(e) {
            console.error('Failed to load dashboard stats', e);
        }
        loadTransfers(1);
    }

    // Filter controls
    document.getElementById('filter-search-btn')?.addEventListener('click', () => loadTransfers(1));
    document.getElementById('filter-clear-btn')?.addEventListener('click', () => {
        ['filter-job-id','filter-file-name','filter-status',
         'filter-source-type','filter-dest-type','filter-date-from','filter-date-to']
            .forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
        loadTransfers(1);
    });
    ['filter-job-id','filter-file-name'].forEach(id => {
        document.getElementById(id)?.addEventListener('keydown', e => {
            if (e.key === 'Enter') loadTransfers(1);
        });
    });
    document.getElementById('refresh-transfers-btn')?.addEventListener('click', () => loadTransfers(transferPage));
    document.getElementById('page-prev')?.addEventListener('click', () => loadTransfers(transferPage - 1));
    document.getElementById('page-next')?.addEventListener('click', () => loadTransfers(transferPage + 1));

    // ── Status label map ──────────────────────────────────────────────────────
    // Maps raw DB status values to user-friendly display labels.
    const STATUS_LABELS = {
        success:    'Sent',
        failed:     'Failed',
        pending:    'Pending',
        skipped:    'Skipped',
        uploaded:   'Sent (Unverified)',
        unverified: 'Sent (Unverified)',
    };

    function populateTransfersTable(transfers) {
        const tbody = document.getElementById('transfers-tbody');
        tbody.innerHTML = '';
        if (transfers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No records match your filters</td></tr>';
            return;
        }
        transfers.forEach(t => {
            const tr = document.createElement('tr');

            const srcBasename = t.source_path.split('/').pop() || t.source_path;
            const srcDisplay  = srcBasename.length > 28 ? '...' + srcBasename.slice(-25) : srcBasename;

            const destIsPath  = t.destination_path && t.destination_path.includes('/');
            const destBasename = destIsPath ? t.destination_path.split('/').pop() : t.destination_path;
            const destDisplay  = destBasename || t.destination_path || '—';

            const utcString = t.execution_time.replace(' ', 'T') + 'Z';
            const date = new Date(utcString).toLocaleString();
            tr.innerHTML = `
                <td><strong>${t.job_id}</strong></td>
                <td>${t.file_name}</td>
                <td><span class="badge ${t.transfer_status}">${STATUS_LABELS[t.transfer_status] || t.transfer_status}</span></td>
                <td style="color: var(--text-secondary); font-size: 0.875rem;">${date}</td>
                <td title="${t.source_path}"><span style="border: 1px solid var(--border); padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">${t.source_type}</span> ${srcDisplay}</td>
                <td title="${t.destination_path}"><span style="border: 1px solid var(--border); padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">${t.destination_type}</span> ${destDisplay}</td>
            `;
            tbody.appendChild(tr);
        });
    }


    let jobsData = []; // In-memory representation of jobs

    const connectorTypes = ['local', 'sftp', 's3', 'scp', 'hdfs'];
    const verificationMethods = ['size_match', 'file_exists', 'checksum_match'];

    // S3 provider presets — quick-fill for endpoint/region/path-style.
    // AWS S3 is the default (empty endpoint => boto3 uses AWS automatically).
    // Each preset only sets the listed fields; user can still override anything by hand.
    const S3_PROVIDERS = {
        aws:        { label: 'AWS S3 (default)',                endpoint: '',                                                  region: 'us-east-1', pathStyle: false },
        do_nyc3:    { label: 'DigitalOcean Spaces - NYC3',      endpoint: 'https://nyc3.digitaloceanspaces.com',                region: 'nyc3',      pathStyle: false },
        do_sfo3:    { label: 'DigitalOcean Spaces - SFO3',      endpoint: 'https://sfo3.digitaloceanspaces.com',                region: 'sfo3',      pathStyle: false },
        do_ams3:    { label: 'DigitalOcean Spaces - AMS3',      endpoint: 'https://ams3.digitaloceanspaces.com',                region: 'ams3',      pathStyle: false },
        do_fra1:    { label: 'DigitalOcean Spaces - FRA1',      endpoint: 'https://fra1.digitaloceanspaces.com',                region: 'fra1',      pathStyle: false },
        do_sgp1:    { label: 'DigitalOcean Spaces - SGP1',      endpoint: 'https://sgp1.digitaloceanspaces.com',                region: 'sgp1',      pathStyle: false },
        do_blr1:    { label: 'DigitalOcean Spaces - BLR1',      endpoint: 'https://blr1.digitaloceanspaces.com',                region: 'blr1',      pathStyle: false },
        do_syd1:    { label: 'DigitalOcean Spaces - SYD1',      endpoint: 'https://syd1.digitaloceanspaces.com',                region: 'syd1',      pathStyle: false },
        r2:         { label: 'Cloudflare R2 (fill <account_id>)', endpoint: 'https://<account_id>.r2.cloudflarestorage.com',     region: 'auto',      pathStyle: false },
        b2:         { label: 'Backblaze B2 (S3 API)',           endpoint: 'https://s3.us-west-002.backblazeb2.com',             region: 'us-west-002', pathStyle: false },
        minio:      { label: 'MinIO / self-hosted',             endpoint: 'http://localhost:9000',                              region: 'us-east-1', pathStyle: true  },
        custom:     { label: 'Custom (no preset)',              endpoint: null,                                                 region: null,        pathStyle: null  },
    };

    /** Detect which preset (if any) matches the current connection values. Used to set
     * the dropdown's selected value when re-rendering an existing job. */
    function detectS3Provider(conn) {
        if (!conn) return 'aws';
        const ep = conn.endpoint_url || '';
        for (const [key, p] of Object.entries(S3_PROVIDERS)) {
            if (key === 'custom') continue;
            if (p.endpoint === ep && (p.region == null || p.region === conn.region)) return key;
        }
        return ep ? 'custom' : 'aws';
    }

    // Processing step definitions: value sent to backend, label shown in UI, tooltip description.
    const PROCESSING_STEPS = [
        { value: 'compress',     label: 'GZ Compress',   desc: 'Compress file with gzip (.gz)' },
        { value: 'decompress',   label: 'GZ Decompress', desc: 'Decompress a .gz gzip file' },
        { value: 'zip',          label: 'ZIP Archive',   desc: 'Package file into a .zip archive' },
        { value: 'compress_bz2', label: 'BZ2 Compress',  desc: 'Compress file with bzip2 (.bz2)' },
        { value: 'rename',       label: 'Prefix Rename', desc: 'Prepend job-id prefix to filename' },
        { value: 'timestamp',    label: 'Timestamp',     desc: 'Prepend YYYYMMDD_ date to filename' },
        { value: 'bash_script',  label: '⚙️ Custom Script', desc: 'Paste a bash script — receives file path as $1' },
    ];

    async function loadConfig() {
        try {
            const res = await authFetch('/jobs');
            if (res.ok) {
                const data = await res.json();
                jobsData = data.jobs || [];
                renderJobCards();
            }
        } catch(e) {
            console.error(e);
        }
    }

    function renderJobCards() {
        const container = document.getElementById('jobs-list');
        container.innerHTML = '';
        if (jobsData.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 3rem;">No jobs configured. Click <strong>+ Add Job</strong> to create one.</p>';
            return;
        }
        jobsData.forEach((job, index) => {
            container.appendChild(createJobCard(job, index));
        });
        lockCardsForViewer(); // disable controls if viewer role
    }

    function createJobCard(job, index) {
        const card = document.createElement('div');
        card.className = 'job-card';
        card.dataset.index = index;

        const enabledClass = job.enabled ? 'on' : 'off';
        const enabledText = job.enabled ? 'Enabled' : 'Disabled';

        card.innerHTML = `
            <div class="job-card-header">
                <div class="job-card-title">
                    <h4>${job.job_id || 'new_job'}</h4>
                    <span class="job-enabled-badge ${enabledClass}">${enabledText}</span>
                    <span style="color: var(--text-secondary); font-size: 0.8rem;">⏱ ${job.schedule || ''}</span>
                </div>
                <div class="job-card-actions">
                    <button class="btn-icon delete-job-btn" title="Delete Job">🗑</button>
                    <span class="chevron">▼</span>
                </div>
            </div>
            <div class="job-card-body">
                <!-- General -->
                <div class="field-section">
                    <div class="field-section-title">General</div>
                    <div class="field-row">
                        <div class="field-group">
                            <label>Job ID</label>
                            <input type="text" data-field="job_id" value="${job.job_id || ''}">
                        </div>
                        <div class="field-group">
                            <label>Cron Schedule</label>
                            <input type="text" data-field="schedule" value="${job.schedule || ''}" placeholder="*/5 * * * *">
                        </div>
                        <div class="field-group">
                            <label>Enabled</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.enabled ? 'active' : ''}" data-field="enabled"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.enabled ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Source -->
                <div class="field-section">
                    <div class="field-section-title">Source</div>
                    <div class="field-row">
                        <div class="field-group">
                            <label>Type</label>
                            <select data-field="source.type">
                                ${connectorTypes.map(t => `<option value="${t}" ${(job.source?.type === t) ? 'selected' : ''}>${t.toUpperCase()}</option>`).join('')}
                            </select>
                        </div>
                        <div class="field-group">
                            <label>Path</label>
                            <input type="text" data-field="source.path" value="${job.source?.path || ''}">
                        </div>
                        <div class="field-group">
                            <label title="Glob: *.csv | Regex: re:^report_\\d+\\.csv$">File Pattern</label>
                            <input type="text" data-field="source.file_pattern" value="${job.source?.file_pattern || ''}" placeholder="*.csv  or  re:^report_\\d+\\.csv$" title="Glob pattern (e.g. *.csv) or regex with re: prefix (e.g. re:^report_\\d{4}\\.csv$)">
                            <small style="color:var(--text-secondary);font-size:0.72rem;margin-top:3px;display:block;">Glob: <code>*.csv</code> &nbsp;|&nbsp; Regex: <code>re:^report_\\d+\\.log$</code></small>
                        </div>
                        <div class="field-group">
                            <label>Config Ref</label>
                            <input type="text" data-field="source.config_ref" value="${job.source?.config_ref || ''}" placeholder="optional">
                        </div>
                    </div>
                    <div class="field-row sftp-fields source-sftp-fields" style="margin-top: 10px; display: ${job.source?.type === 'sftp' ? 'grid' : 'none'};">
                        <div class="field-group">
                            <label>SFTP Host</label>
                            <input type="text" data-field="source.connection.host" value="${job.source?.connection?.host || ''}" placeholder="sftp.example.com">
                        </div>
                        <div class="field-group">
                            <label>Port</label>
                            <input type="number" data-field="source.connection.port" value="${job.source?.connection?.port || 22}">
                        </div>
                        <div class="field-group">
                            <label>Username</label>
                            <input type="text" data-field="source.connection.username" value="${job.source?.connection?.username || ''}">
                        </div>
                        <div class="field-group">
                            <label>Password</label>
                            <input type="password" data-field="source.connection.password" value="${job.source?.connection?.password || ''}">
                        </div>
                    </div>
                    <div class="field-row s3-fields source-s3-fields" style="margin-top: 10px; display: ${job.source?.type === 's3' ? 'grid' : 'none'};">
                        <div style="grid-column: 1 / -1; padding: 10px 12px; background: var(--bg-main); box-shadow: var(--shadow-inner-sm); border-radius: 8px; font-size: 0.78rem; color: var(--text-secondary);">
                            <strong style="color: var(--text-primary); display:block; margin-bottom:6px;">Equivalent .s3cfg</strong>
                            <code style="display:block; white-space:pre; overflow-x:auto; font-family:monospace; color:var(--text-primary);">[default]
access_key   = &lt;access_key&gt;
secret_key   = &lt;secret_key&gt;
host_base    = nyc3.digitaloceanspaces.com
host_bucket  = %(bucket)s.nyc3.digitaloceanspaces.com
use_https    = True
bucket_location = nyc3</code>
                            <details style="margin-top:8px;">
                                <summary style="cursor:pointer; color:var(--accent);">How each field maps to the form below</summary>
                                <ul style="margin:8px 0 0 18px; padding:0; line-height:1.6;">
                                    <li><strong>AWS S3 is the default</strong> &mdash; leave Endpoint URL blank to talk to AWS (boto3 picks the right host from Region)</li>
                                    <li><strong>Multiple S3 setups</strong> &mdash; each job has its own connection, so you can have one job pushing to AWS, another to DO Spaces, another to MinIO, all running on the same scheduler. Click <em>+ Add Job</em> to create another.</li>
                                    <li><code>access_key</code> &rarr; <strong>Access Key</strong></li>
                                    <li><code>secret_key</code> &rarr; <strong>Secret Key</strong> &mdash; for production, leave blank here and set <code>AWS_SECRET_ACCESS_KEY</code> in <code>.env</code></li>
                                    <li><code>host_base</code> + <code>use_https</code> &rarr; <strong>Endpoint URL</strong> as a single field, e.g. <code>https://nyc3.digitaloceanspaces.com</code> (omit for AWS S3)</li>
                                    <li><code>bucket_location</code> &rarr; <strong>Region</strong> (e.g. <code>nyc3</code>, <code>us-east-1</code>)</li>
                                    <li>Bucket name &rarr; <strong>Bucket</strong> field; the source <strong>Path</strong> above acts as the key prefix to list under</li>
                                    <li>Self-signed cert (e.g. local MinIO) &rarr; turn <strong>Verify SSL = No</strong></li>
                                </ul>
                            </details>
                        </div>
                        <div class="field-group" style="grid-column: 1 / -1;">
                            <label>Provider Preset <small style="color:var(--text-secondary);font-weight:400;">&mdash; quick-fills Endpoint URL + Region; you can still override</small></label>
                            <select class="s3-provider-preset" data-target="source">
                                ${Object.entries(S3_PROVIDERS).map(([k, p]) => `<option value="${k}" ${detectS3Provider(job.source?.connection) === k ? 'selected' : ''}>${p.label}</option>`).join('')}
                            </select>
                        </div>
                        <div class="field-group">
                            <label>Endpoint URL <small style="color:var(--text-secondary);font-weight:400;">(blank &rarr; AWS S3)</small></label>
                            <input type="text" data-field="source.connection.endpoint_url" value="${job.source?.connection?.endpoint_url || ''}" placeholder="leave blank for AWS S3">
                        </div>
                        <div class="field-group">
                            <label>Region</label>
                            <input type="text" data-field="source.connection.region" value="${job.source?.connection?.region || ''}" placeholder="nyc3 / us-east-1">
                        </div>
                        <div class="field-group">
                            <label>Bucket</label>
                            <input type="text" data-field="source.connection.bucket" value="${job.source?.connection?.bucket || ''}" placeholder="my-bucket">
                        </div>
                        <div class="field-group">
                            <label>Access Key</label>
                            <input type="text" data-field="source.connection.access_key" value="${job.source?.connection?.access_key || ''}" placeholder="AWS_ACCESS_KEY_ID env if blank">
                        </div>
                        <div class="field-group">
                            <label>Secret Key</label>
                            <input type="password" data-field="source.connection.secret_key" value="${job.source?.connection?.secret_key || ''}" placeholder="AWS_SECRET_ACCESS_KEY env if blank">
                        </div>
                        <div class="field-group">
                            <label>Verify SSL</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.source?.connection?.verify_ssl !== false ? 'active' : ''}" data-field="source.connection.verify_ssl"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.source?.connection?.verify_ssl !== false ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label title="Use path-style URLs instead of virtual-host-style. Needed for MinIO and some older servers.">Path-Style</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.source?.connection?.addressing_style === 'path' ? 'active' : ''}" data-field="source.connection.addressing_style"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.source?.connection?.addressing_style === 'path' ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                    </div>
                    <div class="field-row hdfs-fields source-hdfs-fields" style="margin-top: 10px; display: ${job.source?.type === 'hdfs' ? 'grid' : 'none'};">
                        <div style="grid-column: 1 / -1; padding: 10px 12px; background: var(--bg-main); box-shadow: var(--shadow-inner-sm); border-radius: 8px; font-size: 0.78rem; color: var(--text-secondary);">
                            <strong style="color: var(--text-primary); display:block; margin-bottom:6px;">Equivalent curl (download)</strong>
                            <code style="display:block; white-space:pre-wrap; word-break:break-all; font-family:monospace; color:var(--text-primary);">curl -L -k --negotiate -u : -X GET "&lt;namenode&gt;/webhdfs/v1&lt;path&gt;/&lt;file&gt;?op=OPEN" -o &lt;local-file&gt;</code>
                            <details style="margin-top:8px;">
                                <summary style="cursor:pointer; color:var(--accent);">What each flag means &amp; how to configure it</summary>
                                <ul style="margin:8px 0 0 18px; padding:0; line-height:1.6;">
                                    <li><code>-L</code> &mdash; follow the 307 redirect from namenode to datanode (handled automatically)</li>
                                    <li><code>-k</code> &mdash; skip TLS certificate verification &rarr; set <strong>Verify SSL = No</strong></li>
                                    <li><code>--negotiate -u :</code> &mdash; SPNEGO/Kerberos using the <code>kinit</code> ticket cache &rarr; set <strong>Kerberos = Yes</strong></li>
                                    <li><code>op=OPEN</code> &mdash; WebHDFS read operation (used by source connector when listing/downloading)</li>
                                    <li><code>&lt;namenode&gt;</code> &rarr; <strong>Namenode URL</strong> field below (e.g. <code>https://st-c01r01-m03.bigdata.domain_example.com:9871</code>)</li>
                                    <li><code>&lt;path&gt;</code> &rarr; <strong>Path</strong> field in the Source header (e.g. <code>/external/nextapp/eventlog</code>)</li>
                                    <li>Non-Kerberos clusters: turn <strong>Kerberos = No</strong> and put a username in <strong>User</strong> &mdash; this appends <code>?user.name=&lt;user&gt;</code></li>
                                </ul>
                            </details>
                        </div>
                        <div class="field-group">
                            <label>Namenode URL</label>
                            <input type="text" data-field="source.connection.namenode" value="${job.source?.connection?.namenode || ''}" placeholder="https://nn.example.com:9871">
                        </div>
                        <div class="field-group">
                            <label title="curl --negotiate -u :  uses the kinit ticket cache">Kerberos</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.source?.connection?.kerberos !== false ? 'active' : ''}" data-field="source.connection.kerberos"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.source?.connection?.kerberos !== false ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label title="Off matches curl -k (skip TLS verify)">Verify SSL</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.source?.connection?.verify_ssl ? 'active' : ''}" data-field="source.connection.verify_ssl"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.source?.connection?.verify_ssl ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label>User <small style="color:var(--text-secondary);font-weight:400;">(non-Kerberos)</small></label>
                            <input type="text" data-field="source.connection.user" value="${job.source?.connection?.user || ''}" placeholder="optional">
                        </div>
                    </div>
                </div>

                <!-- Destination -->
                <div class="field-section">
                    <div class="field-section-title">Destination</div>
                    <div class="field-row">
                        <div class="field-group">
                            <label>Type</label>
                            <select data-field="destination.type">
                                ${connectorTypes.map(t => `<option value="${t}" ${(job.destination?.type === t) ? 'selected' : ''}>${t.toUpperCase()}</option>`).join('')}
                            </select>
                        </div>
                        <div class="field-group">
                            <label>Path</label>
                            <input type="text" data-field="destination.path" value="${job.destination?.path || ''}">
                        </div>
                        <div class="field-group">
                            <label>Bucket (S3)</label>
                            <input type="text" data-field="destination.bucket" value="${job.destination?.bucket || ''}" placeholder="optional">
                        </div>
                        <div class="field-group">
                            <label>Config Ref</label>
                            <input type="text" data-field="destination.config_ref" value="${job.destination?.config_ref || ''}" placeholder="optional">
                        </div>
                    </div>
                    <div class="field-row sftp-fields dest-sftp-fields" style="margin-top: 10px; display: ${job.destination?.type === 'sftp' ? 'grid' : 'none'};">
                        <div class="field-group">
                            <label>SFTP Host</label>
                            <input type="text" data-field="destination.connection.host" value="${job.destination?.connection?.host || ''}" placeholder="sftp.example.com">
                        </div>
                        <div class="field-group">
                            <label>Port</label>
                            <input type="number" data-field="destination.connection.port" value="${job.destination?.connection?.port || 22}">
                        </div>
                        <div class="field-group">
                            <label>Username</label>
                            <input type="text" data-field="destination.connection.username" value="${job.destination?.connection?.username || ''}">
                        </div>
                        <div class="field-group">
                            <label>Password</label>
                            <input type="password" data-field="destination.connection.password" value="${job.destination?.connection?.password || ''}">
                        </div>
                    </div>
                    <div class="field-row s3-fields dest-s3-fields" style="margin-top: 10px; display: ${job.destination?.type === 's3' ? 'grid' : 'none'};">
                        <div style="grid-column: 1 / -1; padding: 10px 12px; background: var(--bg-main); box-shadow: var(--shadow-inner-sm); border-radius: 8px; font-size: 0.78rem; color: var(--text-secondary);">
                            <strong style="color: var(--text-primary); display:block; margin-bottom:6px;">Equivalent .s3cfg</strong>
                            <code style="display:block; white-space:pre; overflow-x:auto; font-family:monospace; color:var(--text-primary);">[default]
access_key   = &lt;access_key&gt;
secret_key   = &lt;secret_key&gt;
host_base    = nyc3.digitaloceanspaces.com
host_bucket  = %(bucket)s.nyc3.digitaloceanspaces.com
use_https    = True
bucket_location = nyc3</code>
                            <details style="margin-top:8px;">
                                <summary style="cursor:pointer; color:var(--accent);">How each field maps to the form below</summary>
                                <ul style="margin:8px 0 0 18px; padding:0; line-height:1.6;">
                                    <li><strong>AWS S3 is the default</strong> &mdash; leave Endpoint URL blank to talk to AWS (boto3 picks the right host from Region)</li>
                                    <li><strong>Multiple S3 setups</strong> &mdash; each job has its own connection, so you can ship to AWS in one job and DO Spaces in another. Click <em>+ Add Job</em> to create another.</li>
                                    <li><code>access_key</code> &rarr; <strong>Access Key</strong></li>
                                    <li><code>secret_key</code> &rarr; <strong>Secret Key</strong> &mdash; for production, leave blank here and set <code>AWS_SECRET_ACCESS_KEY</code> in <code>.env</code></li>
                                    <li><code>host_base</code> + <code>use_https</code> &rarr; <strong>Endpoint URL</strong> as a single field, e.g. <code>https://nyc3.digitaloceanspaces.com</code> (omit for AWS S3)</li>
                                    <li><code>bucket_location</code> &rarr; <strong>Region</strong> (e.g. <code>nyc3</code>, <code>us-east-1</code>)</li>
                                    <li>Bucket name &rarr; <strong>Bucket</strong> field below (or the legacy <strong>Bucket (S3)</strong> field at the top of Destination)</li>
                                    <li>The destination <strong>Path</strong> at the top is the key prefix &mdash; final S3 key is <code>&lt;path&gt;/&lt;file&gt;</code></li>
                                    <li>MinIO / older servers that need path-style URLs: turn <strong>Path-Style</strong> = Yes</li>
                                </ul>
                            </details>
                        </div>
                        <div class="field-group" style="grid-column: 1 / -1;">
                            <label>Provider Preset <small style="color:var(--text-secondary);font-weight:400;">&mdash; quick-fills Endpoint URL + Region; you can still override</small></label>
                            <select class="s3-provider-preset" data-target="destination">
                                ${Object.entries(S3_PROVIDERS).map(([k, p]) => `<option value="${k}" ${detectS3Provider(job.destination?.connection) === k ? 'selected' : ''}>${p.label}</option>`).join('')}
                            </select>
                        </div>
                        <div class="field-group">
                            <label>Endpoint URL <small style="color:var(--text-secondary);font-weight:400;">(blank &rarr; AWS S3)</small></label>
                            <input type="text" data-field="destination.connection.endpoint_url" value="${job.destination?.connection?.endpoint_url || ''}" placeholder="leave blank for AWS S3">
                        </div>
                        <div class="field-group">
                            <label>Region</label>
                            <input type="text" data-field="destination.connection.region" value="${job.destination?.connection?.region || ''}" placeholder="nyc3 / us-east-1">
                        </div>
                        <div class="field-group">
                            <label>Bucket</label>
                            <input type="text" data-field="destination.connection.bucket" value="${job.destination?.connection?.bucket || ''}" placeholder="my-bucket">
                        </div>
                        <div class="field-group">
                            <label>Access Key</label>
                            <input type="text" data-field="destination.connection.access_key" value="${job.destination?.connection?.access_key || ''}" placeholder="AWS_ACCESS_KEY_ID env if blank">
                        </div>
                        <div class="field-group">
                            <label>Secret Key</label>
                            <input type="password" data-field="destination.connection.secret_key" value="${job.destination?.connection?.secret_key || ''}" placeholder="AWS_SECRET_ACCESS_KEY env if blank">
                        </div>
                        <div class="field-group">
                            <label>Verify SSL</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.destination?.connection?.verify_ssl !== false ? 'active' : ''}" data-field="destination.connection.verify_ssl"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.destination?.connection?.verify_ssl !== false ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label title="Use path-style URLs (s3.amazonaws.com/bucket/key) instead of virtual-host-style. Needed for MinIO and a few older servers.">Path-Style</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.destination?.connection?.addressing_style === 'path' ? 'active' : ''}" data-field="destination.connection.addressing_style"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.destination?.connection?.addressing_style === 'path' ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                    </div>
                    <div class="field-row hdfs-fields dest-hdfs-fields" style="margin-top: 10px; display: ${job.destination?.type === 'hdfs' ? 'grid' : 'none'};">
                        <div style="grid-column: 1 / -1; padding: 10px 12px; background: var(--bg-main); box-shadow: var(--shadow-inner-sm); border-radius: 8px; font-size: 0.78rem; color: var(--text-secondary);">
                            <strong style="color: var(--text-primary); display:block; margin-bottom:6px;">Equivalent curl (upload)</strong>
                            <code style="display:block; white-space:pre-wrap; word-break:break-all; font-family:monospace; color:var(--text-primary);">curl -L -k --negotiate -u : -X PUT -T &lt;local-file&gt; "&lt;namenode&gt;/webhdfs/v1&lt;path&gt;/&lt;file&gt;?op=CREATE&amp;overwrite=true"</code>
                            <details style="margin-top:8px;">
                                <summary style="cursor:pointer; color:var(--accent);">What each flag means &amp; how to configure it</summary>
                                <ul style="margin:8px 0 0 18px; padding:0; line-height:1.6;">
                                    <li><code>-L</code> &mdash; follow the namenode's 307 redirect to the datanode. The connector does this as a two-step PUT (namenode &rarr; datanode), nothing to configure.</li>
                                    <li><code>-k</code> &mdash; skip TLS certificate verification (insecure) &rarr; set <strong>Verify SSL = No</strong></li>
                                    <li><code>--negotiate -u :</code> &mdash; SPNEGO/Kerberos auth using the ambient <code>kinit</code> ticket; the empty <code>:</code> means &ldquo;no explicit principal&rdquo; &rarr; set <strong>Kerberos = Yes</strong>. Run <code>kinit</code> on the host before the job fires.</li>
                                    <li><code>-X PUT -T &lt;local-file&gt;</code> &mdash; upload the local file as the request body. The local file comes from the <strong>Source</strong> section.</li>
                                    <li><code>op=CREATE</code> &mdash; WebHDFS write operation (always used for uploads)</li>
                                    <li><code>overwrite=true</code> &mdash; replace existing file at the destination &rarr; set <strong>Overwrite = Yes</strong> (turn off to fail if the file already exists)</li>
                                    <li><code>&lt;namenode&gt;</code> &rarr; <strong>Namenode URL</strong> field below (e.g. <code>https://st-c01r01-m03.bigdata.domain_example.com:9871</code>)</li>
                                    <li><code>&lt;path&gt;</code> &rarr; <strong>Path</strong> field above in the Destination header (e.g. <code>/external/nextapp/eventlog</code>) &mdash; the connector calls <code>MKDIRS</code> first to ensure the parent exists</li>
                                    <li>Non-Kerberos clusters: turn <strong>Kerberos = No</strong> and put a username in <strong>User</strong> &mdash; this appends <code>?user.name=&lt;user&gt;</code> to every WebHDFS request</li>
                                </ul>
                                <div style="margin-top:8px; padding-top:8px; border-top: 1px solid rgba(0,0,0,0.08);">
                                    <strong style="color:var(--text-primary);">Worked example:</strong> the curl
                                    <code style="display:block; margin-top:4px; white-space:pre-wrap; word-break:break-all;">curl -L -k --negotiate -u : -X PUT -T /var/tmp/test-1.txt "https://st-c01r01-m03.bigdata.domain_example.com:9871/webhdfs/v1/external/nextapp/eventlog/test.txt?op=CREATE&amp;overwrite=true"</code>
                                    becomes: Source = local <code>/var/tmp</code> + pattern <code>test-*.txt</code>; Destination Path = <code>/external/nextapp/eventlog</code>; Namenode URL = <code>https://st-c01r01-m03.bigdata.domain_example.com:9871</code>; Kerberos = Yes; Verify SSL = No; Overwrite = Yes.
                                </div>
                            </details>
                        </div>
                        <div class="field-group">
                            <label>Namenode URL</label>
                            <input type="text" data-field="destination.connection.namenode" value="${job.destination?.connection?.namenode || ''}" placeholder="https://nn.example.com:9871">
                        </div>
                        <div class="field-group">
                            <label title="curl --negotiate -u :  uses the kinit ticket cache">Kerberos</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.destination?.connection?.kerberos !== false ? 'active' : ''}" data-field="destination.connection.kerberos"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.destination?.connection?.kerberos !== false ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label title="Off matches curl -k (skip TLS verify)">Verify SSL</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.destination?.connection?.verify_ssl ? 'active' : ''}" data-field="destination.connection.verify_ssl"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.destination?.connection?.verify_ssl ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label title="op=CREATE&overwrite=true">Overwrite</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.destination?.connection?.overwrite !== false ? 'active' : ''}" data-field="destination.connection.overwrite"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.destination?.connection?.overwrite !== false ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label>User <small style="color:var(--text-secondary);font-weight:400;">(non-Kerberos)</small></label>
                            <input type="text" data-field="destination.connection.user" value="${job.destination?.connection?.user || ''}" placeholder="optional">
                        </div>
                    </div>
                </div>

                <!-- Processing -->
                <div class="field-section">
                    <div class="field-section-title">Processing</div>
                    <div class="field-row">
                        <div class="field-group">
                            <label>Enabled</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.processing?.enabled ? 'active' : ''}" data-field="processing.enabled"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.processing?.enabled ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                    </div>

                    <div class="field-group" style="margin-top:16px;">
                        <label>Pipeline Steps <span style="font-size:0.72rem;color:var(--text-secondary);font-weight:400;">&mdash; click to toggle, order matters</span></label>
                        <div class="step-pill-selector"
                             data-field="processing.steps"
                             data-selected="${JSON.stringify((job.processing?.steps || []).filter(s => !s.startsWith('bash_script:')))}"
                             data-bash-active="${(job.processing?.steps || []).some(s => s.startsWith('bash_script:'))}"
                             data-bash-path="${(job.processing?.steps || []).find(s => s.startsWith('bash_script:'))?.replace('bash_script:', '') || ''}">
                            ${PROCESSING_STEPS.map(s => `
                                <button type="button" class="step-pill ${
                                    s.value === 'bash_script'
                                        ? (job.processing?.steps || []).some(st => st.startsWith('bash_script:')) ? 'active' : ''
                                        : (job.processing?.steps || []).includes(s.value) ? 'active' : ''
                                }" data-step="${s.value}" title="${s.desc}">${s.label}</button>
                            `).join('')}
                        </div>
                        <div class="step-order-preview"></div>
                    </div>

                    <!-- Script path: only shown when Custom Script is active -->
                    <div class="bash-path-field field-group ${(job.processing?.steps || []).some(s => s.startsWith('bash_script:')) ? '' : 'hidden'}" style="margin-top:12px;">
                        <label>Script Path <span style="font-size:0.72rem;color:var(--text-secondary);font-weight:400;">&mdash; absolute path &bull; <code>$1</code> = file &bull; print new path to stdout to chain</span></label>
                        <input type="text" class="script-path-input"
                            value="${(job.processing?.steps || []).find(s => s.startsWith('bash_script:'))?.replace('bash_script:', '') || ''}"
                            placeholder="/path/to/my_script.sh">
                    </div>
                </div>

                <!-- Backup -->
                <div class="field-section">
                    <div class="field-section-title">Backup</div>
                    <div class="field-row">
                        <div class="field-group">
                            <label>Enabled</label>
                            <div class="toggle-container">
                                <button class="toggle ${job.backup?.enabled ? 'active' : ''}" data-field="backup.enabled"></button>
                                <span style="font-size:0.8rem; color:var(--text-secondary);">${job.backup?.enabled ? 'Yes' : 'No'}</span>
                            </div>
                        </div>
                        <div class="field-group">
                            <label>Location</label>
                            <input type="text" data-field="backup.location" value="${job.backup?.location || ''}" placeholder="backups/local">
                        </div>
                        <div class="field-group">
                            <label>Retention (days)</label>
                            <input type="number" data-field="backup.retention_days" value="${job.backup?.retention_days || ''}">
                        </div>
                    </div>
                </div>

                <!-- Verification -->
                <div class="field-section">
                    <div class="field-section-title">Verification</div>
                    <div class="field-row">
                        <div class="field-group">
                            <label>Method</label>
                            <select data-field="verification.method">
                                ${verificationMethods.map(m => `<option value="${m}" ${(job.verification?.method === m) ? 'selected' : ''}>${m.replace('_', ' ').toUpperCase()}</option>`).join('')}
                            </select>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Toggle expand/collapse
        card.querySelector('.job-card-header').addEventListener('click', (e) => {
            if (e.target.closest('.delete-job-btn')) return;
            card.classList.toggle('expanded');
        });

        // Toggle SFTP / HDFS / S3 fields visibility based on Type
        card.querySelector('select[data-field="source.type"]').addEventListener('change', (e) => {
            card.querySelector('.source-sftp-fields').style.display = e.target.value === 'sftp' ? 'grid' : 'none';
            card.querySelector('.source-hdfs-fields').style.display = e.target.value === 'hdfs' ? 'grid' : 'none';
            card.querySelector('.source-s3-fields').style.display = e.target.value === 's3' ? 'grid' : 'none';
        });
        card.querySelector('select[data-field="destination.type"]').addEventListener('change', (e) => {
            card.querySelector('.dest-sftp-fields').style.display = e.target.value === 'sftp' ? 'grid' : 'none';
            card.querySelector('.dest-hdfs-fields').style.display = e.target.value === 'hdfs' ? 'grid' : 'none';
            card.querySelector('.dest-s3-fields').style.display = e.target.value === 's3' ? 'grid' : 'none';
        });

        // S3 provider preset: picking one auto-fills endpoint_url, region, and the
        // Path-Style toggle. "Custom" leaves everything alone.
        card.querySelectorAll('.s3-provider-preset').forEach(sel => {
            sel.addEventListener('change', (e) => {
                const target = e.target.dataset.target;  // 'source' or 'destination'
                const preset = S3_PROVIDERS[e.target.value];
                if (!preset || preset.endpoint == null) return;  // 'custom' — no-op

                const epInput  = card.querySelector(`input[data-field="${target}.connection.endpoint_url"]`);
                const regInput = card.querySelector(`input[data-field="${target}.connection.region"]`);
                const psToggle = card.querySelector(`button.toggle[data-field="${target}.connection.addressing_style"]`);

                if (epInput)  epInput.value  = preset.endpoint;
                if (regInput) regInput.value = preset.region;
                if (psToggle && preset.pathStyle != null) {
                    psToggle.classList.toggle('active', preset.pathStyle);
                    const lbl = psToggle.parentElement.querySelector('span');
                    if (lbl) lbl.textContent = preset.pathStyle ? 'Yes' : 'No';
                }
            });
        });

        // Delete button
        card.querySelector('.delete-job-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm(`Delete job "${job.job_id}"?`)) {
                jobsData.splice(index, 1);
                renderJobCards();
            }
        });

        // Toggle switches
        card.querySelectorAll('.toggle').forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                toggle.classList.toggle('active');
                const label = toggle.parentElement.querySelector('span');
                label.textContent = toggle.classList.contains('active') ? 'Yes' : 'No';
            });
        });

        // Processing step pill selector
        const pillSelector  = card.querySelector('.step-pill-selector');
        const orderPreview  = card.querySelector('.step-order-preview');
        const bashPathField = card.querySelector('.bash-path-field');
        const scriptPathInput = card.querySelector('.script-path-input');

        function syncPillState() {
            const selected  = JSON.parse(pillSelector.dataset.selected || '[]');
            const bashActive = pillSelector.dataset.bashActive === 'true';

            pillSelector.querySelectorAll('.step-pill').forEach(pill => {
                const isActive = pill.dataset.step === 'bash_script'
                    ? bashActive
                    : selected.includes(pill.dataset.step);
                pill.classList.toggle('active', isActive);
            });

            // Show/hide script path input
            if (bashPathField) bashPathField.classList.toggle('hidden', !bashActive);

            // Order preview
            const allSteps = [...selected, ...(bashActive ? ['bash_script'] : [])];
            if (allSteps.length > 0) {
                orderPreview.innerHTML = allSteps.map((s, i) =>
                    `<span class="order-step">${i + 1}. <strong>${s === 'bash_script' ? '&#x2699;&#xFE0F;&nbsp;script' : s}</strong>${i < allSteps.length - 1 ? ' &rarr; ' : ''}</span>`
                ).join('');
            } else {
                orderPreview.innerHTML = '<span class="order-step muted">No steps — file sent as-is</span>';
            }
        }

        pillSelector.querySelectorAll('.step-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const step = pill.dataset.step;
                if (step === 'bash_script') {
                    pillSelector.dataset.bashActive = String(pillSelector.dataset.bashActive !== 'true');
                } else {
                    let sel = JSON.parse(pillSelector.dataset.selected || '[]');
                    sel = sel.includes(step) ? sel.filter(s => s !== step) : [...sel, step];
                    pillSelector.dataset.selected = JSON.stringify(sel);
                }
                syncPillState();
            });
        });

        // Live-sync bash path into data attribute
        if (scriptPathInput) {
            scriptPathInput.addEventListener('input', () => {
                pillSelector.dataset.bashPath = scriptPathInput.value.trim();
            });
        }

        syncPillState();
        return card;
    }

    // Collect all form data from the rendered cards into a YAML-compatible structure
    function collectJobsFromUI() {
        const cards = document.querySelectorAll('.job-card');
        const jobs = [];
        cards.forEach(card => {
            const getValue = (field) => {
                const el = card.querySelector(`[data-field="${field}"]`);
                if (!el) return '';
                if (el.classList.contains('toggle')) return el.classList.contains('active');
                return el.value.trim();
            };

            // Steps: regular pills from data-selected + bash_script:path if active
            const pillSel    = card.querySelector('[data-field="processing.steps"]');
            const regularSteps = pillSel ? JSON.parse(pillSel.dataset.selected || '[]') : [];
            const bashActive   = pillSel?.dataset.bashActive === 'true';
            const bashPath     = card.querySelector('.script-path-input')?.value.trim() || '';
            const steps = bashActive && bashPath
                ? [...regularSteps, `bash_script:${bashPath}`]
                : [...regularSteps];
            const retDays = getValue('backup.retention_days');

            const sourceType = getValue('source.type');
            const destType   = getValue('destination.type');
            // S3 uses a string-or-omit for addressing_style; the toggle returns a boolean,
            // so convert: true -> 'path', false -> undefined (cleanup drops it).
            const s3Addr = (v) => v === true ? 'path' : null;
            const sourceConn = sourceType === 'sftp' ? {
                    host: getValue('source.connection.host'),
                    port: parseInt(getValue('source.connection.port')) || 22,
                    username: getValue('source.connection.username'),
                    password: getValue('source.connection.password')
                } : sourceType === 'hdfs' ? {
                    namenode: getValue('source.connection.namenode'),
                    kerberos: getValue('source.connection.kerberos'),
                    verify_ssl: getValue('source.connection.verify_ssl'),
                    user: getValue('source.connection.user'),
                } : sourceType === 's3' ? {
                    endpoint_url: getValue('source.connection.endpoint_url'),
                    region: getValue('source.connection.region'),
                    bucket: getValue('source.connection.bucket'),
                    access_key: getValue('source.connection.access_key'),
                    secret_key: getValue('source.connection.secret_key'),
                    verify_ssl: getValue('source.connection.verify_ssl'),
                    addressing_style: s3Addr(getValue('source.connection.addressing_style')),
                } : null;
            const destConn = destType === 'sftp' ? {
                    host: getValue('destination.connection.host'),
                    port: parseInt(getValue('destination.connection.port')) || 22,
                    username: getValue('destination.connection.username'),
                    password: getValue('destination.connection.password')
                } : destType === 'hdfs' ? {
                    namenode: getValue('destination.connection.namenode'),
                    kerberos: getValue('destination.connection.kerberos'),
                    verify_ssl: getValue('destination.connection.verify_ssl'),
                    overwrite: getValue('destination.connection.overwrite'),
                    user: getValue('destination.connection.user'),
                } : destType === 's3' ? {
                    endpoint_url: getValue('destination.connection.endpoint_url'),
                    region: getValue('destination.connection.region'),
                    bucket: getValue('destination.connection.bucket'),
                    access_key: getValue('destination.connection.access_key'),
                    secret_key: getValue('destination.connection.secret_key'),
                    verify_ssl: getValue('destination.connection.verify_ssl'),
                    addressing_style: s3Addr(getValue('destination.connection.addressing_style')),
                } : null;

            const job = {
                job_id: getValue('job_id'),
                enabled: getValue('enabled'),
                schedule: getValue('schedule'),
                source: {
                    type: sourceType,
                    path: getValue('source.path'),
                    file_pattern: getValue('source.file_pattern') || null,
                    config_ref: getValue('source.config_ref') || null,
                    connection: sourceConn,
                },
                destination: {
                    type: destType,
                    path: getValue('destination.path'),
                    bucket: getValue('destination.bucket') || null,
                    config_ref: getValue('destination.config_ref') || null,
                    connection: destConn,
                },
                processing: {
                    enabled: getValue('processing.enabled'),
                    steps: steps,
                },
                backup: {
                    enabled: getValue('backup.enabled'),
                    location: getValue('backup.location') || null,
                    retention_days: retDays ? parseInt(retDays) : null,
                },
                verification: {
                    method: getValue('verification.method'),
                },
            };

            // Clean nulls
            Object.keys(job.source).forEach(k => { if (job.source[k] === null) delete job.source[k]; });
            Object.keys(job.destination).forEach(k => { if (job.destination[k] === null) delete job.destination[k]; });
            // Preserve `false` (meaningful for hdfs verify_ssl/kerberos/overwrite); only drop empty strings & nulls.
            const isEmpty = (v) => v === '' || v == null;
            if (job.source.connection) {
                Object.keys(job.source.connection).forEach(k => { if (isEmpty(job.source.connection[k])) delete job.source.connection[k]; });
                if (Object.keys(job.source.connection).length === 0) delete job.source.connection;
            }
            if (job.destination.connection) {
                Object.keys(job.destination.connection).forEach(k => { if (isEmpty(job.destination.connection[k])) delete job.destination.connection[k]; });
                if (Object.keys(job.destination.connection).length === 0) delete job.destination.connection;
            }
            if (!job.backup.location) delete job.backup.location;
            if (!job.backup.retention_days) delete job.backup.retention_days;

            jobs.push(job);
        });
        return jobs;
    }

    // Convert jobs to YAML manually (simple approach)
    function jobsToYaml(jobs) {
        let yaml = 'jobs:\n';
        jobs.forEach(job => {
            yaml += `  - job_id: ${job.job_id}\n`;
            yaml += `    enabled: ${job.enabled}\n`;
            yaml += `    schedule: "${job.schedule}"\n`;
            yaml += `\n`;
            yaml += `    source:\n`;
            yaml += `      type: ${job.source.type}\n`;
            yaml += `      path: ${job.source.path}\n`;
            if (job.source.file_pattern) yaml += `      file_pattern: "${job.source.file_pattern}"\n`;
            if (job.source.config_ref) yaml += `      config_ref: ${job.source.config_ref}\n`;
            if (job.source.connection) {
                yaml += `      connection:\n`;
                if (job.source.connection.host) yaml += `        host: ${job.source.connection.host}\n`;
                if (job.source.connection.port) yaml += `        port: ${job.source.connection.port}\n`;
                if (job.source.connection.username) yaml += `        username: ${job.source.connection.username}\n`;
                if (job.source.connection.password) yaml += `        password: "${job.source.connection.password}"\n`;
                if (job.source.connection.namenode) yaml += `        namenode: "${job.source.connection.namenode}"\n`;
                if (typeof job.source.connection.kerberos === 'boolean') yaml += `        kerberos: ${job.source.connection.kerberos}\n`;
                if (typeof job.source.connection.verify_ssl === 'boolean') yaml += `        verify_ssl: ${job.source.connection.verify_ssl}\n`;
                if (job.source.connection.user) yaml += `        user: ${job.source.connection.user}\n`;
                if (job.source.connection.endpoint_url) yaml += `        endpoint_url: "${job.source.connection.endpoint_url}"\n`;
                if (job.source.connection.region) yaml += `        region: ${job.source.connection.region}\n`;
                if (job.source.connection.bucket) yaml += `        bucket: ${job.source.connection.bucket}\n`;
                if (job.source.connection.access_key) yaml += `        access_key: "${job.source.connection.access_key}"\n`;
                if (job.source.connection.secret_key) yaml += `        secret_key: "${job.source.connection.secret_key}"\n`;
                if (job.source.connection.addressing_style) yaml += `        addressing_style: ${job.source.connection.addressing_style}\n`;
            }
            yaml += `\n`;
            yaml += `    destination:\n`;
            yaml += `      type: ${job.destination.type}\n`;
            yaml += `      path: ${job.destination.path}\n`;
            if (job.destination.bucket) yaml += `      bucket: ${job.destination.bucket}\n`;
            if (job.destination.config_ref) yaml += `      config_ref: ${job.destination.config_ref}\n`;
            if (job.destination.connection) {
                yaml += `      connection:\n`;
                if (job.destination.connection.host) yaml += `        host: ${job.destination.connection.host}\n`;
                if (job.destination.connection.port) yaml += `        port: ${job.destination.connection.port}\n`;
                if (job.destination.connection.username) yaml += `        username: ${job.destination.connection.username}\n`;
                if (job.destination.connection.password) yaml += `        password: "${job.destination.connection.password}"\n`;
                if (job.destination.connection.namenode) yaml += `        namenode: "${job.destination.connection.namenode}"\n`;
                if (typeof job.destination.connection.kerberos === 'boolean') yaml += `        kerberos: ${job.destination.connection.kerberos}\n`;
                if (typeof job.destination.connection.verify_ssl === 'boolean') yaml += `        verify_ssl: ${job.destination.connection.verify_ssl}\n`;
                if (typeof job.destination.connection.overwrite === 'boolean') yaml += `        overwrite: ${job.destination.connection.overwrite}\n`;
                if (job.destination.connection.user) yaml += `        user: ${job.destination.connection.user}\n`;
                if (job.destination.connection.endpoint_url) yaml += `        endpoint_url: "${job.destination.connection.endpoint_url}"\n`;
                if (job.destination.connection.region) yaml += `        region: ${job.destination.connection.region}\n`;
                if (job.destination.connection.bucket) yaml += `        bucket: ${job.destination.connection.bucket}\n`;
                if (job.destination.connection.access_key) yaml += `        access_key: "${job.destination.connection.access_key}"\n`;
                if (job.destination.connection.secret_key) yaml += `        secret_key: "${job.destination.connection.secret_key}"\n`;
                if (job.destination.connection.addressing_style) yaml += `        addressing_style: ${job.destination.connection.addressing_style}\n`;
            }
            yaml += `\n`;
            yaml += `    processing:\n`;
            yaml += `      enabled: ${job.processing.enabled}\n`;
            if (job.processing.steps.length > 0) {
                yaml += `      steps:\n`;
                job.processing.steps.forEach(s => { yaml += `        - ${s}\n`; });
            }
            yaml += `\n`;
            yaml += `    backup:\n`;
            yaml += `      enabled: ${job.backup.enabled}\n`;
            if (job.backup.location) yaml += `      location: ${job.backup.location}\n`;
            if (job.backup.retention_days) yaml += `      retention_days: ${job.backup.retention_days}\n`;
            yaml += `\n`;
            yaml += `    verification:\n`;
            yaml += `      method: ${job.verification.method}\n`;
            yaml += `\n`;
        });
        return yaml;
    }

    // Add Job
    document.getElementById('add-job-btn').addEventListener('click', () => {
        const newJob = {
            job_id: 'new_job_' + (jobsData.length + 1),
            enabled: true,
            schedule: '0 * * * *',
            source: { type: 'local', path: '/tmp/source' },
            destination: { type: 'local', path: '/tmp/dest' },
            processing: { enabled: false, steps: [] },
            backup: { enabled: false },
            verification: { method: 'size_match' },
        };
        jobsData.push(newJob);
        renderJobCards();

        // Auto-expand the new card
        const cards = document.querySelectorAll('.job-card');
        const last = cards[cards.length - 1];
        if (last) {
            last.classList.add('expanded');
            last.scrollIntoView({ behavior: 'smooth' });
        }
    });

    // Save
    const saveBtn = document.getElementById('save-config-btn');
    const configMessage = document.getElementById('config-message');

    saveBtn.addEventListener('click', async () => {
        const jobs = collectJobsFromUI();
        const yamlContent = jobsToYaml(jobs);
        const previousText = saveBtn.textContent;
        saveBtn.textContent = 'Saving...';
        saveBtn.disabled = true;

        try {
            const res = await authFetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: yamlContent })
            });
            const result = await res.json();
            if (res.ok) {
                showMessage(result.message, 'success');
                await loadConfig();
            } else {
                showMessage(result.detail || 'Failed to save', 'error');
            }
        } catch (e) {
            showMessage(e.message, 'error');
        } finally {
            saveBtn.textContent = previousText;
            saveBtn.disabled = false;
        }
    });

    function showMessage(msg, type) {
        configMessage.textContent = msg;
        configMessage.className = `message-banner ${type}`;
        setTimeout(() => configMessage.className = 'message-banner', 5000);
    }


    const logsDisplay = document.getElementById('logs-display');
    const refreshLogsBtn = document.getElementById('refresh-logs-btn');

    async function loadLogs() {
        if(document.getElementById('view-logs').style.display === 'none') return;
        try {
            const res = await authFetch('/logs/recent');
            if(res.ok) {
                const data = await res.json();
                logsDisplay.textContent = data.logs.join('');
                logsDisplay.parentElement.scrollTop = logsDisplay.parentElement.scrollHeight;
            }
        } catch(e) {
            console.error(e);
            logsDisplay.textContent = "Error loading logs from server.";
        }
    }

    refreshLogsBtn.addEventListener('click', loadLogs);
    setInterval(loadLogs, 3000);

    // Initial Load — deferred to after login if not yet authenticated
    if (getSession()?.token) loadDashboardData();
});
