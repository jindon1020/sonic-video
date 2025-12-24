let audioFile = null;
let videoFiles = [];

function switchView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
}

// File Upload
const fileInput = document.getElementById('file-input');
fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleFiles(files) {
    Array.from(files).forEach(file => {
        if (file.type.startsWith('audio/')) audioFile = file;
        else if (file.type.startsWith('video/')) videoFiles.push(file);
    });
    renderFileTags();
}

function renderFileTags() {
    const list = document.getElementById('file-list');
    list.innerHTML = '';
    const all = audioFile ? [audioFile, ...videoFiles] : videoFiles;
    all.forEach(f => {
        const span = document.createElement('span');
        span.className = 'file-tag';
        span.textContent = f.name;
        list.appendChild(span);
    });
}

// Start Click
document.getElementById('start-btn').addEventListener('click', startProject);
document.getElementById('intent-input').addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') startProject();
});

async function startProject() {
    const intent = document.getElementById('intent-input').value;
    if (!intent || (!audioFile && videoFiles.length === 0)) return;

    switchView('process-view');
    addReasoningCard('SYSTEM', '初始化流程', '正在上传素材并启动 AI 剪辑引擎...');

    const formData = new FormData();
    if (audioFile) formData.append('audio', audioFile);
    videoFiles.forEach(v => formData.append('videos', v));
    formData.append('intent', intent);

    try {
        const res = await fetch('/upload', { method: 'POST', body: formData });
        pollProgress();
    } catch (e) {
        addReasoningCard('ERROR', '出错', e.message);
    }
}

async function pollProgress() {
    let lastLogCount = 0;
    const interval = setInterval(async () => {
        const res = await fetch('/progress');
        const data = await res.json();

        if (data.logs.length > lastLogCount) {
            for (let i = lastLogCount; i < data.logs.length; i++) {
                const log = data.logs[i];
                if (log.includes('🔍 匹配逻辑:')) {
                    const parts = log.split(' -> ');
                    const lyric = parts[0].replace('🔍 匹配逻辑: 歌词[', '').replace(']', '');
                    const logic = parts[1];
                    const target = parts[2];
                    addReasoningCard('STORYBOARD', `歌词匹配: ${lyric}`, `${logic}`, target);
                } else {
                    addReasoningCard('SYSTEM', '执行任务', log);
                }
            }
            lastLogCount = data.logs.length;
        }

        if (data.logs.some(m => m.includes('制作完成'))) {
            clearInterval(interval);
            setTimeout(() => {
                document.getElementById('final-video').src = '/static/processed/final_video.mp4';
                switchView('result-view');
            }, 1500);
        }
    }, 1200);
}

function addReasoningCard(label, title, content, meta = '') {
    const log = document.getElementById('reasoning-log');
    const card = document.createElement('div');
    card.className = 'reasoning-card';
    card.innerHTML = `
        <div class="label">${label}</div>
        <h4>${title}</h4>
        <p>${content}</p>
        ${meta ? `<div class="match-info">${meta}</div>` : ''}
    `;
    log.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth' });
}
