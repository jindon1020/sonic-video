let audioFile = null;
let videoFiles = [];

function switchView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
}

// --- Upload Logic ---
const audioInput = document.getElementById('audio-input');
const videoInput = document.getElementById('video-input');
const audioCard = document.getElementById('audio-card');
const videoCard = document.getElementById('video-card');

// Support full card click
audioCard.addEventListener('click', (e) => {
    // 只有点击“删除”按钮时才不触发上传
    if (e.target.id === 'remove-audio' || e.target.closest('#remove-audio')) {
        return;
    }
    audioInput.click();
});

videoCard.addEventListener('click', () => {
    videoInput.click();
});

async function processMediaFiles(files) {
    for (const file of Array.from(files)) {
        const isVideo = file.type.startsWith('video/') || file.name.toLowerCase().endsWith('.mov');
        const isImage = file.type.startsWith('image/') ||
            file.name.toLowerCase().endsWith('.heic') ||
            file.name.toLowerCase().endsWith('.heif');

        if (isVideo || isImage) {
            videoFiles.push(file);
            await addMediaThumbnail(file, isImage);
        }
    }
}

audioInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file && file.type.startsWith('audio/')) {
        audioFile = file;
        renderAudioState();
    }
    e.target.value = ''; // Support continuous re-selection
});

videoInput.addEventListener('change', async (e) => {
    await processMediaFiles(e.target.files);
    e.target.value = ''; // Support continuous addition
});

// Drag & Drop animations and logic
['dragenter', 'dragover'].forEach(name => {
    audioCard.addEventListener(name, (e) => {
        e.preventDefault(); e.stopPropagation();
        audioCard.classList.add('highlight');
    }, false);
    videoCard.addEventListener(name, (e) => {
        e.preventDefault(); e.stopPropagation();
        videoCard.classList.add('highlight');
    }, false);
});

['dragleave', 'drop'].forEach(name => {
    audioCard.addEventListener(name, (e) => {
        e.preventDefault(); e.stopPropagation();
        audioCard.classList.remove('highlight');
    }, false);
    videoCard.addEventListener(name, (e) => {
        e.preventDefault(); e.stopPropagation();
        videoCard.classList.remove('highlight');
    }, false);
});

audioCard.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('audio/')) {
        audioFile = file;
        renderAudioState();
    }
});

videoCard.addEventListener('drop', async (e) => {
    await processMediaFiles(e.dataTransfer.files);
});

function renderAudioState() {
    const empty = document.querySelector('#audio-card .empty-state');
    const info = document.getElementById('audio-info');
    const name = document.getElementById('audio-name');
    if (audioFile) {
        empty.style.display = 'none';
        info.style.display = 'flex';
        name.textContent = audioFile.name;
    } else {
        empty.style.display = 'flex';
        info.style.display = 'none';
    }
}

document.getElementById('remove-audio').addEventListener('click', (e) => {
    e.stopPropagation();
    audioFile = null;
    renderAudioState();
});

async function addMediaThumbnail(file, isImage = false) {
    const thumbGrid = document.getElementById('video-thumbs');
    const empty = document.querySelector('#video-card .empty-state');
    empty.style.display = 'none';

    const item = document.createElement('div');
    item.className = 'thumb-item';

    // Determine media type for badge
    const isLivePhotoVideo = file.name.toLowerCase().endsWith('.mov');
    const isHeic = file.name.toLowerCase().endsWith('.heic') || file.name.toLowerCase().endsWith('.heif');

    if (isImage && !isLivePhotoVideo) {
        // For images, create thumbnail locally
        item.innerHTML = '<div style="font-size:10px; padding:4px;">处理中...</div>';
        thumbGrid.appendChild(item);

        if (isHeic) {
            // HEIC files need server-side processing
            const formData = new FormData();
            formData.append('image', file);
            try {
                const res = await fetch('/image-thumbnail', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.thumbnail_url) {
                    item.innerHTML = `
                        <img src="${data.thumbnail_url}" alt="thumb">
                        <span class="media-badge image-badge">📷</span>
                    `;
                }
            } catch (e) {
                item.innerHTML = '<div style="font-size:10px; color:red;">HEIC 处理失败</div>';
            }
        } else {
            // Regular images - use FileReader for instant preview
            const reader = new FileReader();
            reader.onload = (e) => {
                item.innerHTML = `
                    <img src="${e.target.result}" alt="thumb">
                    <span class="media-badge image-badge">📷</span>
                `;
            };
            reader.onerror = () => {
                item.innerHTML = '<div style="font-size:10px; color:red;">预览失败</div>';
            };
            reader.readAsDataURL(file);
        }
    } else if (isLivePhotoVideo) {
        // Live Photo MOV file - show special badge
        item.innerHTML = '<div style="font-size:10px; padding:4px;">提取中...</div>';
        thumbGrid.appendChild(item);

        const formData = new FormData();
        formData.append('video', file);
        try {
            const res = await fetch('/thumbnail', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.thumbnail_url) {
                item.innerHTML = `
                    <img src="${data.thumbnail_url}" alt="thumb">
                    <span class="media-badge live-badge">📱 Live</span>
                `;
            }
        } catch (e) {
            item.innerHTML = '<div style="font-size:10px; color:red;">失败</div>';
        }
    } else {
        // Regular video
        item.innerHTML = '<div style="font-size:10px; padding:4px;">提取中...</div>';
        thumbGrid.appendChild(item);

        const formData = new FormData();
        formData.append('video', file);
        try {
            const res = await fetch('/thumbnail', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.thumbnail_url) {
                item.innerHTML = `
                    <img src="${data.thumbnail_url}" alt="thumb">
                    <span class="media-badge video-badge">🎬</span>
                `;
            }
        } catch (e) {
            item.innerHTML = '<div style="font-size:10px; color:red;">失败</div>';
        }
    }
}

// --- Processing Logic ---
const startBtn = document.getElementById('start-btn');
startBtn.addEventListener('click', startProject);
document.getElementById('intent-input').addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') startProject();
});

function updateThinkingText(text) {
    const el = document.getElementById('thinking-text');
    if (el) {
        // 去掉前面的符号和 LOG: 前缀
        const cleanText = text.replace(/^[^\w\u4e00-\u9fa5]+/, '').replace(/^LOG: /, '');
        el.textContent = cleanText;
    }
}

function toggleLogs() {
    const container = document.getElementById('logs-container');
    const icon = document.getElementById('expand-icon');
    if (container.classList.contains('hidden')) {
        container.classList.remove('hidden');
        icon.textContent = '△';
    } else {
        container.classList.add('hidden');
        icon.textContent = '▽';
    }
}

// --- Video Processing View ---
let socket = null;

function initWebSocket() {
    if (socket) socket.close();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

    socket.onmessage = (event) => {
        const log = event.data;
        processLog(log);
        updateThinkingText(log);
        addThinkingLog(log);

        // 如果任务完成，自动刷新结果
        if (log.includes('制作任务圆满完成')) {
            updateProgress(100);
            updateThinkingText("✨ 制作任务圆满完成！");
            setTimeout(() => {
                document.getElementById('final-video').src = '/static/processed/final_video.mp4?t=' + Date.now();
                switchView('result-view');
            }, 1000);
        }
    };

    socket.onclose = () => {
        console.log("WebSocket disconnected. Retrying in 2s...");
        setTimeout(initWebSocket, 2000);
    };
}

// 页面加载即初始化 WS
initWebSocket();

async function startProject() {
    const intent = document.getElementById('intent-input').value;
    const lyrics = document.getElementById('lyrics-input').value;
    const videoDescription = document.getElementById('video-description-input').value;
    const allowAiGen = document.getElementById('ai-video-toggle').checked;

    if (!intent || (!audioFile && videoFiles.length === 0)) return;

    switchView('process-view');
    // 清空旧日志
    document.getElementById('thinking-logs').innerHTML = '';
    updateThinkingText("🚀 引擎初始化中...");
    updateProgress(5);

    const formData = new FormData();
    if (audioFile) formData.append('audio', audioFile);
    videoFiles.forEach(v => formData.append('media', v));
    formData.append('intent', intent);
    formData.append('lyrics', lyrics);
    formData.append('video_description', videoDescription);
    formData.append('allow_ai_generation', allowAiGen);

    try {
        await fetch('/upload', { method: 'POST', body: formData });
        // WS 会自动接收后续日志，不再需要轮询
    } catch (e) {
        console.error(e);
        updateThinkingText("❌ 启动失败");
    }
}

function updateProgress(pct) {
    const bar = document.getElementById('task-progress');
    if (bar) bar.style.width = pct + '%';
}

function addThinkingLog(text) {
    const container = document.getElementById('thinking-logs');
    if (!container) return;
    const entry = document.createElement('div');
    entry.className = 'log-entry-clean';
    const cleanText = text.replace(' LOG: ', '');
    entry.textContent = cleanText;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function processLog(log) {
    // Progress Mapping
    if (log.includes('[STEP 1/4]')) { updateProgress(15); setStageState('stage-audio', 'active'); }
    if (log.includes('📊 音频分析完成')) { updateProgress(30); setStageState('stage-audio', 'done'); }

    if (log.includes('[STEP 2/4]')) { updateProgress(35); setStageState('stage-video', 'active'); }
    if (log.includes('✅ 素材库构建完成')) { updateProgress(55); setStageState('stage-video', 'done'); }

    if (log.includes('[STEP 3/4]')) { updateProgress(60); setStageState('stage-logic', 'active'); }
    if (log.includes('🎯 匹配成功')) {
        // 在编排阶段，根据匹配次数微调进度 (假设有 10 段左右)
        const currentPct = parseInt(document.getElementById('task-progress').style.width);
        if (currentPct < 90) updateProgress(currentPct + 2);
    }

    if (log.includes('[STEP 4/4]')) { updateProgress(92); setStageState('stage-logic', 'done'); }

    // Original summary logic (still useful for displaying details)
    // Stage 1: Audio
    if (log.includes('📊 音频分析完成')) {
        const countMatch = log.match(/识别到 (\d+)/);
        if (countMatch) addTag('audio-results', `${countMatch[1]} 段片段`);
        const bpmMatch = log.split('BPM 测量值: ')[1];
        if (bpmMatch) addTag('audio-results', `BPM: ${bpmMatch}`);
    }
    // Stage 2: Video
    if (log.includes('✅ 素材库构建完成')) {
        const countMatch = log.match(/索引容量: (\d+)/);
        if (countMatch) addTag('video-results', `${countMatch[1]} 个视频片段`);
    }
    // Stage 3: Logic (Creative Matching)
    if (log.includes('🎯 匹配成功:')) {
        // Format: 🎯 匹配成功: "reasoning" -> 选中 [clip_name] (相关度: score)
        const parts = log.split(' -> ');
        const reasoning = parts[0].replace('🎯 匹配成功: "', '').replace('"', '');
        const target = parts[1].split(' (')[0].replace('选中 [', '').replace(']', '');
        addMatchCard('logic-results', reasoning, target);
    }
}

function setStageState(id, state) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('active', 'done');
    el.classList.add(state);
}

function addTag(containerId, text) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const span = document.createElement('span');
    span.className = 'segment-tag';
    span.textContent = text;
    container.appendChild(span);
}

function addMatchCard(containerId, lyric, target) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const card = document.createElement('div');
    card.className = 'match-card-mini';
    card.innerHTML = `<h6>${lyric}</h6><p>🎞️ ${target}</p>`;
    container.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
