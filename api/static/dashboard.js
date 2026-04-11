/**
 * BillAI Admin Dashboard JS
 */

// ── Config ────────────────────────────────────────────────────────────────────
Chart.defaults.color = '#71717A';
Chart.defaults.font.family = "'Inter', sans-serif";
const POLL_MS = 30_000;

// ── State ─────────────────────────────────────────────────────────────────────
let refreshTimer = null;
let countdownSec = POLL_MS / 1000;
let charts = {};
let latestData = []; // Store raw data for modal

const $ = id => document.getElementById(id);

// ── Init Charts ───────────────────────────────────────────────────────────────
function initCharts() {
    // 1. Processing Time (Bar/Line)
    const ctxTime = $('chartTime').getContext('2d');
    charts.time = new Chart(ctxTime, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#E5E7EB' } },
                x: { grid: { display: false }, ticks: { display: false } }
            },
            elements: { point: { radius: 2 }, line: { tension: 0.3 } }
        }
    });

    // 2. OCR Confidence (Bar)
    const ctxConf = $('chartConf').getContext('2d');
    charts.conf = new Chart(ctxConf, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { min: 0, max: 100, grid: { color: '#E5E7EB' } },
                x: { grid: { display: false }, ticks: { display: false } }
            }
        }
    });

    // 3. Category (Doughnut)
    const ctxCat = $('chartCategory').getContext('2d');
    charts.cat = new Chart(ctxCat, {
        type: 'doughnut',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { color: '#4B5563', boxWidth: 12 } }
            },
            cutout: '65%',
            borderWidth: 0
        }
    });
}

// ── Fetch & Render ────────────────────────────────────────────────────────────
async function fetchStats() {
    try {
        const res = await fetch(`/dashboard/stats`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        showToast(`⚠️ Lỗi kết nối: ${e.message}`, 'amber');
        return null;
    }
}

function fmt(n) { return n == null ? '—' : Number(n).toLocaleString('vi-VN'); }
function relTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const diff = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diff < 60) return `${diff}s trước`;
    if (diff < 3600) return `${Math.floor(diff/60)}m trước`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h trước`;
    return d.toLocaleDateString('vi-VN');
}
function tStamp(iso) { return iso ? new Date(iso).toLocaleString('vi-VN') : ''; }

function updateDashboard(d) {
    if (!d) return;
    latestData = d.recent || [];

    // 1. Stats Top
    $('statTotal').textContent = fmt(d.total);
    $('statToday').textContent = fmt(d.today_total);
    $('statSuccess').textContent = `${d.success_rate}%`;
    $('statCompleted').textContent = fmt(d.completed);
    $('statFailed').textContent = fmt(d.failed);
    $('statAvgMs').textContent = d.avg_ms > 0 ? fmt(d.avg_ms) : '—';
    $('statAvgConf').textContent = d.avg_conf > 0 ? `${fmt(d.avg_conf)}%` : '—';

    // Header Badges
    $('sysInfoModel').textContent = d.groq_model || '—';
    $('sysInfoVersion').textContent = d.pipeline_ver || '—';
    
    const bDb = $('badgeDb');
    bDb.textContent = d.supabase_ok ? 'DB: OK' : 'DB: ERR';
    bDb.className = `badge ${d.supabase_ok ? 'ok' : 'err'}`;
    
    const bGroq = $('badgeGroq');
    bGroq.textContent = d.groq_ok ? 'LLM: OK' : 'LLM: ERR';
    bGroq.className = `badge ${d.groq_ok ? 'ok' : 'err'}`;

    // 2. Charts Update
    if (latestData.length > 0) {
        // Reverse for left-to-right chronological
        const chartData = [...latestData].reverse();
        const labels = chartData.map(r => tStamp(r.created_at));
        
        // Time Trend
        charts.time.data.labels = labels;
        charts.time.data.datasets = [{
            label: 'Processing Time (ms)',
            data: chartData.map(r => r.processing_time_ms || 0),
            borderColor: '#6366F1', backgroundColor: 'rgba(99,102,241,0.1)',
            fill: true
        }];
        charts.time.update('none');

        // Conf Trend
        charts.conf.data.labels = labels;
        charts.conf.data.datasets = [{
            label: 'OCR Confidence (%)',
            data: chartData.map(r => Math.round((r.ocr_confidence || 0) * 100)),
            backgroundColor: ctx => {
                const val = ctx.raw || 0;
                return val > 75 ? '#10B981' : val > 40 ? '#F59E0B' : '#EF4444';
            },
            borderRadius: 2
        }];
        charts.conf.update('none');
    }

    // Category Doughnut
    if (d.cat_counts) {
        const cats = Object.keys(d.cat_counts);
        const vals = Object.values(d.cat_counts);
        charts.cat.data.labels = cats;
        charts.cat.data.datasets = [{
            data: vals,
            backgroundColor: ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#6B7280']
        }];
        charts.cat.update('none');
    }

    // 3. Data Table
    const tBody = $('tableBody');
    if (latestData.length === 0) {
        tBody.innerHTML = `<tr><td colspan="7" class="text-center p-4 text-faint">Không có dữ liệu hóa đơn</td></tr>`;
    } else {
        tBody.innerHTML = latestData.map((row, i) => {
            let chip = `<span class="status-chip chip-wait">⏳ ${row.status}</span>`;
            if (row.status === 'completed') chip = `<span class="status-chip chip-ok">✓ OK</span>`;
            if (row.status === 'failed') chip = `<span class="status-chip chip-fail">✕ Lỗi</span>`;
            
            const conf = Math.round((row.ocr_confidence || 0) * 100);
            const ms = row.processing_time_ms ? Math.round(row.processing_time_ms) : '—';
            
            return `
            <tr onclick="openModal(${i})">
                <td class="text-faint">${relTime(row.created_at)}</td>
                <td style="max-width:250px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                    <strong>${row.store_name || '—'}</strong>
                </td>
                <td class="text-green font-bold">${row.total_amount ? fmt(row.total_amount) + 'đ' : '—'}</td>
                <td>${row.category || '—'}</td>
                <td>${conf}%</td>
                <td>${ms}</td>
                <td>${chip}</td>
            </tr>`;
        }).join('');
    }
}

// ── Modal UI ──────────────────────────────────────────────────────────────────
function openModal(index) {
    const row = latestData[index];
    if (!row) return;

    $('popupId').textContent = row.id.split('-')[0] + '...';
    
    // Image
    const imgEl = $('popupImg');
    const emptyEl = $('popupImgEmpty');
    if (row.cropped_image_url) {
        imgEl.src = row.cropped_image_url;
        imgEl.style.display = 'block';
        emptyEl.style.display = 'none';
    } else {
        imgEl.style.display = 'none';
        emptyEl.style.display = 'flex';
    }

    // Stats
    let st = `<span class="status-chip chip-wait">⏳ ${row.status}</span>`;
    if (row.status === 'completed') st = `<span class="status-chip chip-ok">✓ Thành công</span>`;
    if (row.status === 'failed')    st = `<span class="status-chip chip-fail">✕ Lỗi</span>`;
    $('popupStatus').innerHTML = st;

    $('popupStore').textContent = row.store_name || 'Không có tên';
    $('popupTotal').textContent = row.total_amount ? fmt(row.total_amount) + ' ₫' : '—';
    $('popupCat').textContent = row.category || '—';
    $('popupConf').textContent = `${Math.round((row.ocr_confidence||0)*100)}%`;

    // Error handling
    if (row.status === 'failed') {
        $('popupErrorGroup').style.display = 'flex';
        $('popupFailStep').textContent = row.failed_step || 'Unknown';
        $('popupErrorMsg').textContent = row.error_message || 'No error message provided';
    } else {
        $('popupErrorGroup').style.display = 'none';
    }

    // JSON/Raw Text
    $('popupOcrText').value = row.ocr_raw_text || 'Không có dữ liệu OCR Text';
    
    // LLM Summary
    const llmBox = $('popupLlmText');
    if (row.summary) {
        try {
            // Check if it's already a string or object
            const obj = typeof row.summary === 'string' ? JSON.parse(row.summary) : row.summary;
            llmBox.value = JSON.stringify(obj, null, 2);
        } catch(e) {
            llmBox.value = String(row.summary);
        }
    } else {
        llmBox.value = 'Chưa có output từ LLM / Không hợp lệ';
    }

    $('billModal').classList.add('show');
}

$('btnCloseModal').addEventListener('click', () => {
    $('billModal').classList.remove('show');
    $('popupImg').src = ''; // free memory
});
$('billModal').addEventListener('click', (e) => {
    if (e.target === $('billModal')) $('btnCloseModal').click();
});

$('btnCopyData').addEventListener('click', async () => {
    const store = $('popupStore').textContent;
    const total = $('popupTotal').textContent;
    const cat = $('popupCat').textContent;
    const jsonStr = $('popupLlmText').value;
    
    const textToShare = `🧾 BillAI Extraction\n🏪 Cửa hàng: ${store}\n💰 Tổng tiền: ${total}\n🏷️ Danh mục: ${cat}\n\n🤖 LLM Output:\n${jsonStr}`;
    
    try {
        await navigator.clipboard.writeText(textToShare);
        showToast('✅ Đã copy dữ liệu vào Clipboard!', 'green');
    } catch (err) {
        showToast('❌ Copy thất bại, trình duyệt không hỗ trợ', 'red');
    }
});

// ── Runners ───────────────────────────────────────────────────────────────────
async function refresh() {
    // Không làm mới dữ liệu nếu người dùng đang mở xem chi tiết một hóa đơn
    // Để tránh chớp màn hình hoặc mất context
    if ($('billModal').classList.contains('show')) {
        countdownSec = POLL_MS / 1000;
        return;
    }

    const btn = $('btnRefresh');
    if (btn) btn.style.transform = 'rotate(180deg)';
    
    const d = await fetchStats();
    updateDashboard(d);
    
    if (btn) setTimeout(() => btn.style.transform = 'rotate(0deg)', 300);
    
    countdownSec = POLL_MS / 1000;
}

function updateClock() {
    const now = new Date();
    $('headerClock').textContent = now.toLocaleTimeString('vi-VN');
}

setInterval(() => {
    countdownSec--;
    $('refreshCountdown').textContent = `Auto refresh in 0:${countdownSec.toString().padStart(2, '0')}`;
    if (countdownSec <= 0) refresh();
}, 1000);
setInterval(updateClock, 1000);

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    $('btnRefresh').addEventListener('click', refresh);
    updateClock();
    refresh();
});

// Utilities
function showToast(msg, type = 'default') {
    const container = $('toastContainer');
    const el = document.createElement('div');
    el.className = 'toast';
    if (type === 'red') el.style.borderLeft = '4px solid var(--red)';
    if (type === 'green') el.style.borderLeft = '4px solid var(--green)';
    if (type === 'amber') el.style.borderLeft = '4px solid var(--amber)';
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => {
        el.classList.add('fade-out');
        setTimeout(() => el.remove(), 350);
    }, 3000);
}
