/**
 * BillAI Frontend
 * Single-call pipeline: POST /api/process → full result
 */
class BillAI {
    constructor() {
        this.requestId = null;
        this.currentFile = null;
        this.activeTab = 'detect';
        this.stepUrls = { detect: null, proc: null, ocr: null };
        this.isLoading = false;

        // DOM cache
        this.dropZone       = document.getElementById('drop-zone');
        this.fileInput      = document.getElementById('file-input');
        this.btnExtract     = document.getElementById('btn-extract');
        this.btnClear       = document.getElementById('btn-clear');
        this.btnExport      = document.getElementById('btn-export');
        this.statusBar      = document.getElementById('status-bar');
        this.tbody          = document.getElementById('result-tbody');
        this.itemsSection   = document.getElementById('items-section');
        this.itemsBody      = document.getElementById('items-body');
        this.jsonOut         = document.getElementById('json-out');
        this.reqIdDisplay   = document.getElementById('req-id-display');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.loadingText    = document.getElementById('loading-text');
        this.progressBar    = document.getElementById('progress-bar');
        this.extractLabel   = this.btnExtract?.textContent || 'Trích xuất';

        this.init();
    }

    init() {
        this.bindEvents();
        this.setStatus('Trạng thái: Chờ ảnh');
    }

    bindEvents() {
        // Drag-and-drop
        ['dragover', 'dragenter'].forEach(ev =>
            this.dropZone.addEventListener(ev, e => { e.preventDefault(); this.dropZone.classList.add('drag-over'); })
        );
        ['dragleave', 'drop'].forEach(ev =>
            this.dropZone.addEventListener(ev, e => { e.preventDefault(); this.dropZone.classList.remove('drag-over'); })
        );
        this.dropZone.addEventListener('drop', e => {
            const file = e.dataTransfer?.files?.[0];
            if (file) this.setFile(file);
        });
        this.dropZone.addEventListener('click', () => { if (!this.isLoading) this.fileInput.click(); });
        this.fileInput.addEventListener('change', () => {
            const file = this.fileInput.files?.[0];
            if (file) this.setFile(file);
        });

        // Buttons
        this.btnExtract.addEventListener('click', () => this.runPipeline());
        this.btnExport.addEventListener('click', () => this.exportCsv());
        this.btnClear.addEventListener('click', () => this.reset());

        // Tab switching (exposed globally for inline onclick)
        window.switchTab = (btn, step) => this.handleTabSwitch(btn, step);
    }

    setFile(file) {
        if (this.isLoading) return;
        this.currentFile = file;
        this.requestId = null;
        this.btnExtract.disabled = false;
        this.btnExport.disabled = true;

        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('placeholder').style.display = 'none';
            let img = this.dropZone.querySelector('img.preview');
            if (!img) { img = document.createElement('img'); img.className = 'preview'; this.dropZone.prepend(img); }
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
        this.setStatus(`Đã tải: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`);
    }

    // ── Main pipeline — SINGLE fetch call ────────────────────────────────

    async runPipeline() {
        if (!this.currentFile || this.isLoading) return;

        this.btnExtract.disabled = true;
        this.btnClear.disabled = true;
        this.btnExport.disabled = true;
        this.statusBar.innerHTML = '';

        this.setLoading(true, 'Đang tải lên và xử lý…', 10);
        this.setStatus('Đang gửi ảnh và chạy AI Pipeline…', 'running');

        // Simulate progress while waiting for the single call
        let progress = 10;
        const progressInterval = setInterval(() => {
            if (progress < 90) { progress += Math.random() * 6; this.setProgress(progress); }
        }, 700);

        try {
            const fd = new FormData();
            fd.append('file', this.currentFile);

            const res = await fetch('/api/process', { method: 'POST', body: fd });

            clearInterval(progressInterval);
            this.setProgress(100);

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Lỗi server' }));
                throw new Error(err.detail || 'Lỗi xử lý');
            }

            const data = await res.json();
            this.requestId = data.request_id;
            this.reqIdDisplay.textContent = `ID: ${this.requestId}`;

            this.stepUrls = {
                detect: data.detect_image,
                proc:   data.detect_image ? data.detect_image.replace('_detect.jpg', '_proc.jpg') : null,
                ocr:    data.ocr_image,
            };

            this.renderSteps();
            this.renderResult(data);

            const label = data.status === 'success' ? 'Hoàn tất' : data.status;
            this.setStatus(`${label} (ID: ${this.requestId.substring(0, 8)}…)`, 'done');
            this.btnExport.disabled = false;

        } catch (err) {
            clearInterval(progressInterval);
            this.setProgress(0);
            this.setStatus(`Lỗi: ${err.message}`, 'error');
        } finally {
            this.setLoading(false);
            this.btnExtract.disabled = !this.currentFile;
            this.btnClear.disabled = false;
        }
    }

    // ── Tab switching ────────────────────────────────────────────────────

    handleTabSwitch(btn, step) {
        document.querySelectorAll('.step-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        this.activeTab = step;
        this.showStep(step);
    }

    renderSteps() {
        document.getElementById('step-placeholder').style.display = 'none';
        ['detect', 'proc', 'ocr'].forEach(step => {
            const img = document.getElementById(`img-${step}`);
            if (img && this.stepUrls[step]) img.src = `${this.stepUrls[step]}?t=${Date.now()}`;
        });
        this.showStep(this.activeTab);
    }

    showStep(step) {
        ['detect', 'proc', 'ocr'].forEach(name => {
            const img   = document.getElementById(`img-${name}`);
            const badge = document.getElementById(`badge-${name}`);
            if (img)   img.style.display   = name === step ? 'block' : 'none';
            if (badge) badge.style.display = name === step ? 'inline-block' : 'none';
        });
    }

    // ── Render result table ──────────────────────────────────────────────

    renderResult(data) {
        const result = data.result || {};
        this.tbody.innerHTML = '';

        if (data.status === 'no_bill_detected') {
            this.tbody.innerHTML = `<tr><td colspan="2" style="color:#f87171;text-align:center;padding:20px">Không tìm thấy hóa đơn trong ảnh</td></tr>`;
            this.itemsSection.style.display = 'none';
            this.jsonOut.textContent = JSON.stringify(data, null, 2);
            return;
        }

        const fields = [
            { key: 'SELLER',     label: 'Tên cửa hàng' },
            { key: 'ADDRESS',    label: 'Địa chỉ' },
            { key: 'TIMESTAMP',  label: 'Ngày/Giờ' },
            { key: 'TOTAL_COST', label: 'Tổng tiền' },
        ];

        fields.forEach(({ key, label }) => {
            const val = result[key];
            const display = key === 'TOTAL_COST' && typeof val === 'number'
                ? `${val.toLocaleString('vi-VN')} VND`
                : (val || '-');
            const tr = document.createElement('tr');
            tr.innerHTML = `<td style="font-weight:500;white-space:nowrap">${label}</td><td><input value="${String(display).replace(/"/g, '&quot;')}" placeholder="-"/></td>`;
            this.tbody.appendChild(tr);
        });

        const products = result.PRODUCTS || [];
        this.itemsBody.innerHTML = '';
        if (products.length) {
            this.itemsSection.style.display = 'block';
            products.forEach(item => {
                const row = document.createElement('div');
                row.className = 'item-row';
                const val = item.VALUE != null && item.VALUE !== 0
                    ? `${Number(item.VALUE).toLocaleString('vi-VN')} VND` : '-';
                row.innerHTML = `<span>${item.PRODUCT || '-'}</span><span>${item.NUM ?? '-'}</span><span>${val}</span>`;
                this.itemsBody.appendChild(row);
            });
        } else {
            this.itemsSection.style.display = 'none';
        }

        this.jsonOut.textContent = JSON.stringify(result, null, 2);
    }

    // ── CSV export ───────────────────────────────────────────────────────

    async exportCsv() {
        if (!this.requestId || this.isLoading) return;
        try {
            const res = await fetch('/api/export-csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request_ids: [this.requestId] }),
            });
            if (!res.ok) throw new Error('Xuất file thất bại');
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `invoice_${this.requestId.substring(0, 8)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
            this.setStatus('CSV đã được tải xuống', 'done');
        } catch (err) {
            this.setStatus(`Lỗi xuất file: ${err.message}`, 'error');
        }
    }

    // ── Reset ────────────────────────────────────────────────────────────

    reset() {
        if (this.isLoading) return;
        this.currentFile = null;
        this.requestId = null;
        this.fileInput.value = '';
        this.dropZone.querySelectorAll('img.preview').forEach(n => n.remove());
        document.getElementById('placeholder').style.display = 'block';

        this.tbody.innerHTML = `<tr><td colspan="2" style="color:var(--muted);text-align:center;padding:20px">Chưa có dữ liệu</td></tr>`;
        this.itemsSection.style.display = 'none';
        this.itemsBody.innerHTML = '';
        this.jsonOut.textContent = '{}';
        this.reqIdDisplay.textContent = '';

        document.getElementById('step-placeholder').style.display = 'block';
        ['detect', 'proc', 'ocr'].forEach(step => {
            const img   = document.getElementById(`img-${step}`);
            const badge = document.getElementById(`badge-${step}`);
            if (img) { img.style.display = 'none'; img.removeAttribute('src'); }
            if (badge) badge.style.display = 'none';
        });

        this.stepUrls = { detect: null, proc: null, ocr: null };
        this.btnExtract.disabled = true;
        this.btnExport.disabled = true;
        this.statusBar.innerHTML = '';
        this.setLoading(false);
        this.setStatus('Trạng thái: Chờ ảnh');
    }

    // ── UI helpers ───────────────────────────────────────────────────────

    setStatus(msg, state = 'running') {
        const t = new Date().toLocaleTimeString('vi-VN');
        this.statusBar.className = state;
        this.statusBar.innerHTML += `<div>[${t}] ${msg}</div>`;
        this.statusBar.scrollTop = this.statusBar.scrollHeight;
    }

    setProgress(pct) {
        if (this.progressBar) this.progressBar.style.width = `${pct}%`;
    }

    setLoading(active, message = 'AI đang phân tích ảnh…', progress = null) {
        this.isLoading = active;
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.toggle('active', active);
            this.loadingOverlay.setAttribute('aria-hidden', active ? 'false' : 'true');
        }
        if (this.loadingText) this.loadingText.textContent = message;
        if (this.btnExtract) {
            this.btnExtract.classList.toggle('loading', active);
            this.btnExtract.textContent = active ? 'Đang trích xuất…' : this.extractLabel;
        }
        if (progress !== null) this.setProgress(progress);
        else if (!active) setTimeout(() => this.setProgress(0), 400);
    }
}

document.addEventListener('DOMContentLoaded', () => { window.app = new BillAI(); });
