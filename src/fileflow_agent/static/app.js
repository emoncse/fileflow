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


    setInterval(loadDashboardData, 5000);

    async function loadDashboardData() {
        if(document.getElementById('view-dashboard').style.display === 'none') return;
        try {
            const res = await fetch('/stats/summary');
            const data = await res.json();
            document.getElementById('stat-total-jobs').textContent = data.total_jobs.toLocaleString();
            document.getElementById('stat-success').textContent = data.successful_transfers.toLocaleString();
            document.getElementById('stat-skipped').textContent = data.duplicate_skips.toLocaleString();
            document.getElementById('stat-failed').textContent = data.failed_transfers.toLocaleString();

            const transfersRes = await fetch('/transfers?limit=10');
            const transfersData = await transfersRes.json();
            populateTransfersTable(transfersData.transfers);
        } catch (e) {
            console.error("Failed to load dashboard data", e);
        }
    }

    function populateTransfersTable(transfers) {
        const tbody = document.getElementById('transfers-tbody');
        tbody.innerHTML = '';
        if (transfers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">No transfers recorded yet</td></tr>';
            return;
        }
        transfers.forEach(t => {
            const tr = document.createElement('tr');
            const truncSrc = t.source_path.length > 20 ? '...' + t.source_path.slice(-20) : t.source_path;
            const truncDest = t.destination_path.length > 20 ? '...' + t.destination_path.slice(-20) : t.destination_path;
            const date = new Date(t.execution_time).toLocaleString();
            tr.innerHTML = `
                <td><strong>${t.job_id}</strong></td>
                <td>${t.file_name}</td>
                <td><span class="badge ${t.transfer_status}">${t.transfer_status}</span></td>
                <td style="color: var(--text-secondary); font-size: 0.875rem;">${date}</td>
                <td><span style="border: 1px solid var(--border); padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">${t.source_type}</span> ${truncSrc}</td>
                <td><span style="border: 1px solid var(--border); padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">${t.destination_type}</span> ${truncDest}</td>
            `;
            tbody.appendChild(tr);
        });
    }


    let jobsData = []; // In-memory representation of jobs

    const connectorTypes = ['local', 'sftp', 's3', 'scp', 'hdfs'];
    const verificationMethods = ['size_match', 'file_exists', 'checksum_match'];
    const processingSteps = ['compress', 'decompress', 'rename'];

    async function loadConfig() {
        try {
            const res = await fetch('/jobs');
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
                        <div class="field-group">
                            <label>Steps (comma-separated)</label>
                            <input type="text" data-field="processing.steps" value="${(job.processing?.steps || []).join(', ')}" placeholder="compress, rename">
                        </div>
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

        // Toggle SFTP fields visibility based on Type
        card.querySelector('select[data-field="source.type"]').addEventListener('change', (e) => {
            card.querySelector('.source-sftp-fields').style.display = e.target.value === 'sftp' ? 'grid' : 'none';
        });
        card.querySelector('select[data-field="destination.type"]').addEventListener('change', (e) => {
            card.querySelector('.dest-sftp-fields').style.display = e.target.value === 'sftp' ? 'grid' : 'none';
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

            const stepsRaw = getValue('processing.steps');
            const steps = stepsRaw ? stepsRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
            const retDays = getValue('backup.retention_days');

            const job = {
                job_id: getValue('job_id'),
                enabled: getValue('enabled'),
                schedule: getValue('schedule'),
                source: {
                    type: getValue('source.type'),
                    path: getValue('source.path'),
                    file_pattern: getValue('source.file_pattern') || null,
                    config_ref: getValue('source.config_ref') || null,
                    connection: getValue('source.type') === 'sftp' ? {
                        host: getValue('source.connection.host'),
                        port: parseInt(getValue('source.connection.port')) || 22,
                        username: getValue('source.connection.username'),
                        password: getValue('source.connection.password')
                    } : null
                },
                destination: {
                    type: getValue('destination.type'),
                    path: getValue('destination.path'),
                    bucket: getValue('destination.bucket') || null,
                    config_ref: getValue('destination.config_ref') || null,
                    connection: getValue('destination.type') === 'sftp' ? {
                        host: getValue('destination.connection.host'),
                        port: parseInt(getValue('destination.connection.port')) || 22,
                        username: getValue('destination.connection.username'),
                        password: getValue('destination.connection.password')
                    } : null
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
            if (job.source.connection) {
                Object.keys(job.source.connection).forEach(k => { if (!job.source.connection[k]) delete job.source.connection[k]; });
                if (Object.keys(job.source.connection).length === 0) delete job.source.connection;
            }
            if (job.destination.connection) {
                Object.keys(job.destination.connection).forEach(k => { if (!job.destination.connection[k]) delete job.destination.connection[k]; });
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
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: yamlContent })
            });
            const result = await res.json();
            if (res.ok) {
                showMessage(result.message, 'success');
                // Reload to reflect any adjustments
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
            const res = await fetch('/logs/recent');
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

    // Initial Load
    loadDashboardData();
});
