let equityChart = null;

document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    fetchAccountInfo();
    loadStrategies();
    initChart();
    refreshDataInfo();  // 加载历史数据信息

    // 设置默认日期
    const today = new Date().toISOString().split('T')[0];
    const syncEndDate = document.getElementById('sync-end-date');
    const endDate = document.getElementById('end-date');
    if (syncEndDate) syncEndDate.value = today;
    if (endDate) endDate.value = today;

    // Refresh account info every 10 seconds
    setInterval(fetchAccountInfo, 10000);
});

function formatNumber(val) {
    const num = parseFloat(val);
    if (isNaN(num)) return '0.00';
    return num.toFixed(2);
}

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-links li').forEach(el => el.classList.remove('active'));

    document.getElementById(sectionId).classList.add('active');
    document.querySelector(`li[onclick="showSection('${sectionId}')"]`).classList.add('active');
}

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        const form = document.getElementById('config-form');
        for (const [key, value] of Object.entries(config)) {
            if (form.elements[key]) {
                form.elements[key].value = value;
            }
        }
    } catch (error) {
        console.error('Failed to load config:', error);
    }
}

async function saveConfig(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        alert(result.msg);
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

async function resetDatabase() {
    if (!confirm('⚠️ 警告：此操作将清空所有策略日志、交易记录、K线历史数据等。\n\n此操作不可恢复，是否继续？')) {
        return;
    }

    // Double confirmation for safety
    if (!confirm('🔴 再次确认：真的要初始化数据库吗？所有数据将被永久删除！')) {
        return;
    }

    try {
        const response = await fetch('/api/reset_database', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();

        if (result.status === 'success') {
            let details = '';
            if (result.details) {
                details = '\n\n详细信息：\n';
                for (const [table, count] of Object.entries(result.details)) {
                    details += `- ${table}: ${count} 条\n`;
                }
            }
            alert('✅ ' + result.msg + details);
            // Refresh the page to reflect changes
            location.reload();
        } else {
            alert('❌ ' + result.msg);
        }
    } catch (error) {
        alert('❌ 操作失败: ' + error.message);
    }
}

async function fetchAccountInfo() {
    try {
        const response = await fetch('/api/account');
        const data = await response.json();

        if (data.status === 'success') {
            if (data.balance && data.balance.data && data.balance.data.length > 0) {
                const balance = data.balance.data[0];
                document.getElementById('total-equity').textContent = formatNumber(balance.totalEq);
                document.getElementById('available-balance').textContent = formatNumber(balance.availEq);
                updateChart(parseFloat(balance.totalEq) || 0);
            }

            if (data.positions && data.positions.data) {
                const positions = data.positions.data;
                document.getElementById('position-count').textContent = positions.length;
                updatePositionsTable(positions);
            }
        } else {
            console.error('API Error:', data.msg);
        }
    } catch (error) {
        console.error('Failed to fetch account info:', error);
    }
}

function updatePositionsTable(positions) {
    const tbody = document.querySelector('#positions-table tbody');
    tbody.innerHTML = '';

    positions.forEach(pos => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${pos.instId}</td>
            <td style="color: ${pos.posSide === 'long' ? '#10b981' : '#ef4444'}">${pos.posSide.toUpperCase()}</td>
            <td>${pos.lever}x</td>
            <td>${pos.pos}</td>
            <td>${pos.avgPx}</td>
            <td style="color: ${parseFloat(pos.upl) >= 0 ? '#10b981' : '#ef4444'}">${pos.upl}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadStrategies() {
    try {
        const response = await fetch('/api/strategies');
        const data = await response.json();

        // Update Select Options
        const select = document.getElementById('strategy-select');
        const backtestSelect = document.getElementById('backtest-strategy-select');
        select.innerHTML = '';
        backtestSelect.innerHTML = '';

        data.strategies.forEach(strategy => {
            const option = new Option(strategy.name, strategy.name);
            select.add(option.cloneNode(true));
            backtestSelect.add(option);
        });

        // Update Strategy Table
        const tbody = document.querySelector('#strategies-table tbody');
        tbody.innerHTML = '';

        data.strategies.forEach(strategy => {
            const tr = document.createElement('tr');
            const isRunning = strategy.status === 'RUNNING';
            const pnl = strategy.total_pnl || 0;
            const pnlColor = pnl >= 0 ? '#10b981' : '#ef4444';

            tr.innerHTML = `
                <td>${strategy.name}</td>
                <td><span class="status-badge ${isRunning ? 'status-running' : 'status-stopped'}">${strategy.status}</span></td>
                <td>${strategy.symbol}</td>
                <td>${strategy.last_heartbeat}</td>
                <td style="color: ${pnlColor}; font-weight: bold;">${pnl.toFixed(2)}</td>
                <td>
                    <button onclick="viewStrategyDetails('${strategy.name}')" class="btn primary small">查看</button>
                    <button onclick="editStrategy('${strategy.name}')" class="btn small" style="background:#6366f1;color:white;">编辑</button>
                    ${isRunning
                    ? `<button onclick="stopStrategy('${strategy.name}')" class="btn danger small">停止</button>`
                    : `<button onclick="document.getElementById('strategy-select').value='${strategy.name}'; document.querySelector('.control-panel').scrollIntoView({behavior: 'smooth'});" class="btn success small">启动</button>`
                    }
                    <button onclick="deleteStrategy('${strategy.name}')" class="btn danger small" ${isRunning ? 'disabled title="请先停止策略"' : ''}>删除</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error('Failed to load strategies:', error);
    }
}

async function stopStrategy(strategyName) {
    if (!confirm(`确定要停止策略 ${strategyName} 吗？`)) return;

    try {
        const response = await fetch('/api/stop_strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy_name: strategyName })
        });
        const result = await response.json();
        alert(result.msg);
        loadStrategies();
    } catch (error) {
        alert('停止失败: ' + error.message);
    }
}

async function editStrategy(strategyName) {
    try {
        const response = await fetch(`/api/get_strategy_code/${strategyName}`);
        const result = await response.json();

        if (result.status === 'success') {
            document.getElementById('edit-strategy-name').value = strategyName;
            document.getElementById('edit-strategy-code').value = result.code;
            document.getElementById('edit-strategy-modal').style.display = 'block';
        } else {
            alert('加载策略失败: ' + result.msg);
        }
    } catch (error) {
        alert('加载失败: ' + error.message);
    }
}

async function saveEditedStrategy() {
    const name = document.getElementById('edit-strategy-name').value;
    const code = document.getElementById('edit-strategy-code').value;

    if (!code.trim()) {
        alert('策略代码不能为空');
        return;
    }

    try {
        const response = await fetch('/api/update_strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, code: code })
        });
        const result = await response.json();

        if (result.status === 'success') {
            alert(result.msg);
            closeEditStrategyModal();
            loadStrategies();
        } else {
            alert('保存失败: ' + result.msg);
        }
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

function closeEditStrategyModal() {
    document.getElementById('edit-strategy-modal').style.display = 'none';
}

async function deleteStrategy(strategyName) {
    if (!confirm(`⚠️ 确定要删除策略 ${strategyName} 吗？\n\n此操作将同时删除该策略的所有日志和交易记录！`)) {
        return;
    }

    if (!confirm(`🔴 再次确认：真的要永久删除策略 ${strategyName} 吗？`)) {
        return;
    }

    try {
        const response = await fetch('/api/delete_strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: strategyName })
        });
        const result = await response.json();

        if (result.status === 'success') {
            alert('✅ ' + result.msg);
            loadStrategies();
        } else {
            alert('❌ ' + result.msg);
        }
    } catch (error) {
        alert('删除失败: ' + error.message);
    }
}

async function runStrategy() {
    const strategyName = document.getElementById('strategy-select').value;
    const symbol = document.getElementById('trade-symbol').value;
    const leverage = document.getElementById('leverage').value;
    const interval = document.getElementById('strategy-interval').value;

    if (!strategyName) {
        alert('请选择策略');
        return;
    }

    try {
        const response = await fetch('/api/run_strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                strategy_name: strategyName,
                symbol: symbol,
                leverage: leverage,
                interval: interval
            })
        });
        const result = await response.json();
        const logDiv = document.getElementById('strategy-logs-viewer');
        const statusClass = result.status === 'success' ? 'log-success' : 'log-error';
        if (logDiv) {
            logDiv.innerHTML += `<div class="${statusClass}">[${new Date().toLocaleTimeString()}] ${result.msg}</div>`;
            logDiv.scrollTop = logDiv.scrollHeight;
        }

        // Show message
        if (result.status === 'success') {
            alert(result.msg);
        } else {
            alert('错误: ' + result.msg);
        }

        // Refresh list
        setTimeout(loadStrategies, 1000);
    } catch (error) {
        alert('启动失败: ' + error.message);
    }
}

async function generateStrategy() {
    const prompt = document.getElementById('ai-prompt').value;
    if (!prompt) return alert('请输入策略描述');

    const btn = document.querySelector('#ai-generator .btn.primary');
    const originalText = btn.textContent;
    btn.textContent = '生成中...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/ai_generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        });
        const result = await response.json();

        if (result.status === 'success') {
            document.getElementById('generated-code-container').style.display = 'block';
            document.getElementById('generated-code').textContent = result.code;
        } else {
            alert('生成失败: ' + result.msg);
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function saveGeneratedStrategy() {
    const code = document.getElementById('generated-code').textContent;
    const name = prompt('请输入策略文件名 (例如: my_strategy.py):');
    if (!name) return;

    try {
        const response = await fetch('/api/save_strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, code: code })
        });
        const result = await response.json();
        alert(result.msg);
        loadStrategies();
        document.getElementById('generated-code-container').style.display = 'none';
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

function discardGeneratedStrategy() {
    document.getElementById('generated-code-container').style.display = 'none';
    document.getElementById('generated-code').textContent = '';
}

function initChart() {
    const ctx = document.getElementById('equityChart').getContext('2d');
    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '总权益',
                data: [],
                borderColor: '#3b82f6',
                tension: 0.4,
                fill: true,
                backgroundColor: 'rgba(59, 130, 246, 0.1)'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

function updateChart(equity) {
    if (!equityChart) return;

    const now = new Date().toLocaleTimeString();
    equityChart.data.labels.push(now);
    equityChart.data.datasets[0].data.push(equity);

    if (equityChart.data.labels.length > 20) {
        equityChart.data.labels.shift();
        equityChart.data.datasets[0].data.shift();
    }

    equityChart.update();
}

// ========== 市场数据管理 ==========

async function syncMarketData() {
    const symbol = document.getElementById('sync-symbol').value;
    const bar = document.getElementById('sync-bar').value;
    const startDate = document.getElementById('sync-start-date').value;
    const endDate = document.getElementById('sync-end-date').value;

    if (!startDate) {
        return alert('请选择开始日期');
    }

    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = '同步中...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/market_data/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: symbol,
                bar: bar,
                start_date: startDate,
                end_date: endDate || null
            })
        });
        const result = await response.json();

        if (result.status === 'success') {
            alert(result.msg);
            refreshDataInfo();
        } else {
            alert('同步失败: ' + result.msg);
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function refreshDataInfo() {
    try {
        const response = await fetch('/api/market_data/info');
        const result = await response.json();

        const infoDiv = document.getElementById('data-info');
        if (result.data && result.data.length > 0) {
            let html = '<table style="width: 100%;"><thead><tr><th>交易对</th><th>周期</th><th>数据量</th><th>开始时间</th><th>结束时间</th><th>操作</th></tr></thead><tbody>';
            result.data.forEach(item => {
                html += `<tr>
                    <td>${item.symbol}</td>
                    <td>${item.bar}</td>
                    <td>${item.count} 条</td>
                    <td>${item.start_date || '-'}</td>
                    <td>${item.end_date || '-'}</td>
                    <td><button class="btn danger" style="padding: 4px 8px; font-size: 12px;" onclick="deleteMarketData('${item.symbol}', '${item.bar}')">删除</button></td>
                </tr>`;
            });
            html += '</tbody></table>';
            infoDiv.innerHTML = html;
        } else {
            infoDiv.innerHTML = '<p style="color: #94a3b8;">暂无存储的历史数据，请先同步数据后再进行回测</p>';
        }
    } catch (error) {
        console.error('获取数据信息失败:', error);
    }
}

async function deleteMarketData(symbol, bar) {
    if (!confirm(`确定要删除 ${symbol} ${bar} 的数据吗？`)) return;

    try {
        const response = await fetch('/api/market_data/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, bar })
        });
        const result = await response.json();

        if (result.status === 'success') {
            alert(result.msg);
            refreshDataInfo();
        } else {
            alert('删除失败: ' + result.msg);
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    }
}

// ========== 策略回测 ==========

async function runBacktest() {
    const strategyName = document.getElementById('backtest-strategy-select').value;
    const symbol = document.getElementById('backtest-symbol').value;
    const mode = document.getElementById('backtest-mode').value;
    const bar = document.getElementById('backtest-bar').value;
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    const initialBalance = parseFloat(document.getElementById('initial-balance').value) || 10000;

    if (!strategyName || !startDate || !endDate) {
        return alert('请填写完整的回测参数');
    }

    const btns = document.querySelectorAll('#backtest .btn.primary');
    const btn = btns[btns.length - 1];  // 获取回测按钮
    const originalText = btn.textContent;
    btn.textContent = '回测中...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                strategy_name: strategyName,
                symbol: symbol,
                mode: mode,
                bar: bar,
                start_date: startDate,
                end_date: endDate,
                initial_balance: initialBalance
            })
        });
        const result = await response.json();

        const resultsDiv = document.getElementById('backtest-results');
        if (result.status === 'success') {
            const modeText = result.mode === 'database' ? '数据库模式' : '实时获取模式';
            let html = `
                <div class="card" style="margin-top: 20px;">
                    <h3>📈 回测结果</h3>
                    <p style="color: #94a3b8; margin-bottom: 15px;">模式: ${modeText} | 周期: ${result.bar} | 数据点: ${result.data_points}</p>
                    <div style="display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap;">
                        <div class="stat-item">
                            <div style="color: #94a3b8;">初始资金</div>
                            <div style="font-size: 20px; font-weight: bold;">${result.initial_balance.toFixed(2)} USDT</div>
                        </div>
                        <div class="stat-item">
                            <div style="color: #94a3b8;">最终权益</div>
                            <div style="font-size: 20px; font-weight: bold; color: ${result.final_equity >= result.initial_balance ? '#10b981' : '#ef4444'}">${result.final_equity.toFixed(2)} USDT</div>
                        </div>
                        <div class="stat-item">
                            <div style="color: #94a3b8;">盈亏</div>
                            <div style="font-size: 20px; font-weight: bold; color: ${result.pnl >= 0 ? '#10b981' : '#ef4444'}">
                                ${result.pnl >= 0 ? '+' : ''}${result.pnl.toFixed(2)} USDT
                            </div>
                        </div>
                        <div class="stat-item">
                            <div style="color: #94a3b8;">收益率</div>
                            <div style="font-size: 20px; font-weight: bold; color: ${result.pnl_ratio >= 0 ? '#10b981' : '#ef4444'}">
                                ${result.pnl_ratio >= 0 ? '+' : ''}${result.pnl_ratio.toFixed(2)}%
                            </div>
                        </div>
                        <div class="stat-item">
                            <div style="color: #94a3b8;">交易次数</div>
                            <div style="font-size: 20px; font-weight: bold;">${result.total_orders}</div>
                        </div>
                    </div>

                    <h4>交易记录 (${result.orders.length} 笔)</h4>
                    <div style="max-height: 300px; overflow-y: auto;">
                        <table style="width: 100%;">
                            <thead>
                                <tr>
                                    <th>时间</th>
                                    <th>方向</th>
                                    <th>价格</th>
                                    <th>数量</th>
                                    <th>余额</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

            result.orders.forEach(order => {
                const date = new Date(order.time).toLocaleString();
                html += `
                    <tr>
                        <td>${date}</td>
                        <td style="color: ${order.side === 'buy' ? '#10b981' : '#ef4444'}">${order.side.toUpperCase()}</td>
                        <td>${parseFloat(order.price).toFixed(2)}</td>
                        <td>${parseFloat(order.qty).toFixed(6)}</td>
                        <td>${order.balance.toFixed(2)}</td>
                    </tr>
                `;
            });

            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            resultsDiv.innerHTML = html;
        } else {
            resultsDiv.innerHTML = `<div class="card" style="margin-top: 20px; border-color: #ef4444;"><h3 style="color: #ef4444;">❌ 回测失败</h3><p>${result.msg}</p></div>`;
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Strategy Monitoring Functions
let currentStrategyName = null;
let strategyRefreshInterval = null;

async function viewStrategyDetails(strategyName) {
    currentStrategyName = strategyName;

    // Show modal
    document.getElementById('strategy-details-modal').style.display = 'block';
    document.getElementById('modal-strategy-name').textContent = `策略详情 - ${strategyName}`;

    // Load initial data
    await refreshStrategyDetails();

    // Auto-refresh every 5 seconds
    if (strategyRefreshInterval) {
        clearInterval(strategyRefreshInterval);
    }
    strategyRefreshInterval = setInterval(refreshStrategyDetails, 5000);
}

function closeStrategyDetails() {
    document.getElementById('strategy-details-modal').style.display = 'none';
    currentStrategyName = null;

    if (strategyRefreshInterval) {
        clearInterval(strategyRefreshInterval);
        strategyRefreshInterval = null;
    }
}

async function refreshStrategyDetails() {
    if (!currentStrategyName) return;

    try {
        const response = await fetch(`/api/strategy_status/${currentStrategyName}`);
        const data = await response.json();

        if (data.status === 'success') {
            // Update metrics
            const metrics = data.metrics;
            document.getElementById('metric-total-pnl').textContent =
                (metrics.total_pnl || 0).toFixed(2) + ' USDT';
            document.getElementById('metric-total-pnl').style.color =
                metrics.total_pnl >= 0 ? '#10b981' : '#ef4444';

            document.getElementById('metric-total-trades').textContent = metrics.total_trades || 0;
            document.getElementById('metric-win-rate').textContent =
                (metrics.win_rate || 0).toFixed(2) + '%';
            document.getElementById('metric-winning-trades').textContent =
                `${metrics.winning_trades || 0} / ${metrics.losing_trades || 0}`;

            // Update logs
            const logsViewer = document.getElementById('strategy-logs-viewer');
            logsViewer.innerHTML = '';

            if (data.logs && data.logs.length > 0) {
                data.logs.reverse().forEach(log => {
                    const logEntry = document.createElement('div');
                    logEntry.className = `log-entry log-${log.level.toLowerCase()}`;

                    const timestamp = new Date(log.timestamp).toLocaleString();
                    logEntry.innerHTML = `
                        <span class="log-time">[${timestamp}]</span>
                        <span class="log-level">[${log.level}]</span>
                        <span class="log-type">[${log.event_type}]</span>
                        <span class="log-message">${log.message}</span>
                    `;
                    logsViewer.appendChild(logEntry);
                });
            } else {
                logsViewer.innerHTML = '<div style="color: #94a3b8; padding: 20px; text-align: center;">暂无日志</div>';
            }

            // Update trades
            const tradesTable = document.querySelector('#strategy-trades-table tbody');
            tradesTable.innerHTML = '';

            if (data.trades && data.trades.length > 0) {
                data.trades.forEach(trade => {
                    const tr = document.createElement('tr');
                    const timestamp = new Date(trade.timestamp).toLocaleString();
                    const sideColor = trade.side === 'buy' ? '#10b981' : '#ef4444';
                    const pnlColor = (trade.pnl || 0) >= 0 ? '#10b981' : '#ef4444';

                    tr.innerHTML = `
                        <td>${timestamp}</td>
                        <td>${trade.symbol}</td>
                        <td style="color: ${sideColor}; font-weight: bold;">${trade.side.toUpperCase()}</td>
                        <td>${trade.price}</td>
                        <td>${trade.quantity}</td>
                        <td>${trade.status}</td>
                        <td style="color: ${pnlColor};">${trade.pnl ? trade.pnl.toFixed(2) : '-'}</td>
                    `;
                    tradesTable.appendChild(tr);
                });
            } else {
                tradesTable.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #94a3b8;">暂无交易记录</td></tr>';
            }
        }
    } catch (error) {
        console.error('Failed to refresh strategy details:', error);
    }
}

// Close modal when clicking outside
window.onclick = function (event) {
    const modal = document.getElementById('strategy-details-modal');
    if (event.target == modal) {
        closeStrategyDetails();
    }
}
