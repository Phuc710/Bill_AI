/**
 * BillAI Premium Frontend
 * Handles single-call pipeline with full performance tracking.
 */
class BillAI {
    constructor() {
        this.requestId = null;
        this.currentFile = null;
        this.activeTab = 'detect';
        
        // DOM Elements
        this.dropZone       = document.getElementById('drop-zone');
        this.fileInput      = document.getElementById('file-input');
        this.btnExtract     = document.getElementById('btn-extract');
        this.btnClear       = document.getElementById('btn-clear');
        this.btnExport      = document.getElementById('btn-export');
        this.statusBar      = document.getElementById('status-bar');
        this.tbody          = document.getElementById('result-tbody');
        this.itemsSection   = document.getElementById('items-section');
        this.itemsBody      = document.getElementById('items-body');
        this.jsonOut        = document.getElementById('json-out');
        this.reqIdDisplay   = document.getElementById('req-id-display');
        this.perfGrid       = document.getElementById('perf-grid');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.loadingText    = document.getElementById('loading-text');
        this.progressBar    = document.getElementById('progress-bar');
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.setStatus('Hệ thống sẵn sàng — Chờ tệp tin');
    }

    bindEvents() {
        // Drag and Drop
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

        // External switch
        window.switchTab = (btn, step) => this.handleTabSwitch(btn, step);
    }

    setFile(file) {
        if (this.isLoading) return;
        this.currentFile = file;
        this.btnExtract.disabled = false;
        this.btnExport.disabled = true;

        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('placeholder').style.display = 'none';
            let img = this.dropZone.querySelector('img.preview');
            if (!img) { 
                img = document.createElement('img'); 
                img.className = 'preview'; 
                this.dropZone.appendChild(img); 
            }
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
        this.setStatus(`Đã tải: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`);
    }

    async runPipeline() {
        if (!this.currentFile || this.isLoading) return;

        this.setLoading(true, 'Đang phân tích hình ảnh...', 10);
        this.statusBar.innerHTML = '';
        this.setStatus('Bắt đầu quy trình xử lý AI...', 'running');

        // Progress mock
        let progress = 10;
        const progressInterval = setInterval(() => {
            if (progress < 90) { 
               progress += Math.random() * 5; 
               this.setProgress(progress); 
            }
        }, 800);

        try {
            const fd = new FormData();
            fd.append('file', this.currentFile);

            const res = await fetch('/api/process', { method: 'POST', body: fd });
            clearInterval(progressInterval);
            this.setProgress(100);

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Lỗi máy chủ rỗng' }));
                throw new Error(err.detail || 'Không thể xử lý pipeline');
            }

            const data = await res.json();
            this.requestId = data.request_id;
            this.reqIdDisplay.textContent = `UID: ${this.requestId}`;
            
            this.renderImages(data);
            this.renderResult(data.structured || {}, data.result || {});
            
            this.jsonOut.textContent = JSON.stringify(data.structured || {}, null, 2);
            this.setStatus('Hoàn tất trích xuất thành công', 'done');
            this.btnExport.disabled = false;

        } catch (err) {
            clearInterval(progressInterval);
            this.setProgress(0);
            this.setStatus(`Lỗi: ${err.message}`, 'error');
            console.error(err);
        } finally {
            this.setLoading(false);
        }
    }

    renderImages(data) {
        document.getElementById('step-placeholder').style.display = 'none';
        
        const urls = {
            detect: data.detect_image, // Red BBox
            proc:   data.proc_image   // Cropped/Filtered
        };

        ['detect', 'proc'].forEach(step => {
            const img = document.getElementById(`img-${step}`);
            if (img) {
                if (urls[step]) {
                    img.src = `${urls[step]}?t=${Date.now()}`;
                    if (this.activeTab === step) img.style.display = 'block';
                } else {
                    img.style.display = 'none';
                }
            }
        });

        // OCR Text View
        const ocrView = document.getElementById('ocr-text-view');
        const rawText = data.structured?.raw_text || '';
        if (ocrView) {
            ocrView.textContent = rawText;
            if (this.activeTab === 'ocr') ocrView.style.display = 'block';
        }
    }

    // renderPerf removed as requested 

    renderResult(s, legacy) {
        this.tbody.innerHTML = '';
        
        const rows = [
            { l: 'Cửa hàng', v: s.store_name || legacy.SELLER },
            { l: 'Địa chỉ', v: s.address || legacy.ADDRESS },
            { l: 'Số HĐ', v: s.invoice_id },
            { l: 'Ngày giờ', v: s.datetime_in || legacy.TIMESTAMP },
            { l: 'Thu ngân', v: s.cashier },
            { l: 'Tổng tiền', v: s.total != null ? `${s.total.toLocaleString('vi-VN')} VND` : null }
        ];

        rows.forEach(r => {
            if (r.v == null && r.l !== 'Tổng tiền') return; 
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${r.l}</td><td><input value="${r.v || ''}" spellcheck="false" /></td>`;
            this.tbody.appendChild(tr);
        });

        // Items
        const items = s.items || [];
        this.itemsBody.innerHTML = '';
        if (items.length) {
            this.itemsSection.style.display = 'block';
            items.forEach(it => {
                const div = document.createElement('div');
                div.className = 'item-row';
                const total = it.total_price ? `${it.total_price.toLocaleString('vi-VN')} ₫` : '--';
                div.innerHTML = `<span>${it.name}</span><span style="text-align:center">${it.quantity}</span><span style="text-align:right">${total}</span>`;
                this.itemsBody.appendChild(div);
            });
        } else {
            this.itemsSection.style.display = 'none';
        }
    }

    handleTabSwitch(btn, step) {
        document.querySelectorAll('.step-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        this.activeTab = step;
        
        const isOCR = step === 'ocr';
        const ocrView = document.getElementById('ocr-text-view');
        
        ['detect', 'proc'].forEach(s => {
            const img = document.getElementById(`img-${s}`);
            if (img) img.style.display = (!isOCR && s === step && img.getAttribute('src')) ? 'block' : 'none';
        });

        if (ocrView) ocrView.style.display = isOCR ? 'block' : 'none';
    }

    setStatus(msg, state = 'running') {
        const time = new Date().toLocaleTimeString('vi-VN');
        const div = document.createElement('div');
        div.textContent = `[${time}] ${msg}`;
        this.statusBar.appendChild(div);
        this.statusBar.scrollTop = this.statusBar.scrollHeight;
    }

    setProgress(pct) {
        if (this.progressBar) this.progressBar.style.width = `${pct}%`;
    }

    setLoading(active, text = '', progress = null) {
        this.isLoading = active;
        this.loadingOverlay.classList.toggle('active', active);
        if (text) this.loadingText.textContent = text;
        if (progress !== null) this.setProgress(progress);
        this.btnExtract.textContent = active ? 'Đang trích xuất...' : '🚀 Chạy Pipeline';
        this.btnExtract.disabled = active || !this.currentFile;
    }

    reset() {
        window.location.reload();
    }

    async exportCsv() {
        if (!this.requestId) return;
        this.setStatus('Đang chuẩn bị tệp CSV...');
        try {
            const res = await fetch('/api/export-csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request_ids: [this.requestId] }),
            });
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `BillAI_${this.requestId.substring(0,8)}.csv`;
            a.click();
            this.setStatus('Xuất tệp thành công!', 'done');
        } catch (e) {
            this.setStatus('Lỗi khi xuất tệp', 'error');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => { window.app = new BillAI(); });
