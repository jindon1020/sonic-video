let audioFile = null;
let videoFiles = [];
let socket = null;
let shotList = []; // Track segments for the editor

const PRO_TEST_PARAMETERS = {
    audio_path: "/Users/geralt/Desktop/5yt - 人生海海.mp3",
    video_paths: ["/Users/geralt/Downloads/飞驰人生.Pegasus.2019.BD720P.X264.AAC.Mandarin.CHS.Mp4Ba/飞驰人生.Pegasus.2019.BD720P.X264.AAC.Mandarin.CHS.Mp4Ba.mp4"],
    intent: "飞驰人生电影混剪：追求梦想，热血飞驰，配合《人生海海》的励志旋律，展现赛车的速度与激情。",
    lyrics: "人生海海 山山而川\n不过尔尔\n我也曾 跌跌撞撞 想要 飞向 远方\n那是我的勋章",
    video_description: "韩寒执导电影《飞驰人生》，沈腾主演。讲述赛车手张驰重返赛场的故事。具有极强的体育竞技精神和幽默元素。"
};

document.addEventListener('DOMContentLoaded', () => {
    initObsidianFlow();
    initWebSocket();
    initEditorFlow();
});

function initObsidianFlow() {
    const cardAudio = document.getElementById('card-audio');
    const cardMedia = document.getElementById('card-media');
    const inputAudio = document.getElementById('input-audio');
    const inputMedia = document.getElementById('input-media');
    const consoleBox = document.getElementById('v3-console');
    const startBtn = document.getElementById('v3-start-btn');
    const debugBtn = document.getElementById('v3-debug-btn');

    cardAudio.addEventListener('click', () => inputAudio.click());
    cardMedia.addEventListener('click', () => inputMedia.click());

    inputAudio.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            audioFile = file;
            document.getElementById('audio-selected').textContent = `✓ ${file.name}`;
            document.getElementById('audio-selected').classList.remove('hidden');
            showConsole();
        }
    });

    inputMedia.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        videoFiles.push(...files);
        document.getElementById('media-counter').textContent = `✓ ${videoFiles.length} 份视觉素材`;
        document.getElementById('media-counter').classList.remove('hidden');
        showConsole();
    });

    function showConsole() {
        consoleBox.classList.remove('hidden');
        consoleBox.style.opacity = '0';
        requestAnimationFrame(() => {
            consoleBox.style.transition = 'opacity 0.6s ease';
            consoleBox.style.opacity = '1';
        });
    }

    startBtn.addEventListener('click', startProjectV3);
    debugBtn.addEventListener('click', startProTest);

    // Keyboard
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') startProjectV3();
    });
}

function initEditorFlow() {
    const editBtn = document.getElementById('v3-edit-btn');
    const closeBtn = document.getElementById('modal-close');
    const modal = document.getElementById('replacement-modal');
    const tabs = document.querySelectorAll('.tab-btn');
    const panes = document.querySelectorAll('.tab-pane');

    if (editBtn) {
        editBtn.addEventListener('click', () => {
            const storyboard = document.getElementById('v3-storyboard');
            storyboard.classList.toggle('hidden');
            if (!storyboard.classList.contains('hidden')) {
                renderStoryboard();
                storyboard.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    }

    // Modal click-outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.add('hidden');
    });

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            tabs.forEach(t => t.classList.remove('active'));
            panes.forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(target).classList.add('active');
        });
    });
}

function renderStoryboard() {
    const container = document.getElementById('storyboard-list');
    container.innerHTML = '';

    // If shotList is empty (e.g. fresh reload), use mock data for demo
    const effectiveList = shotList.length > 0 ? shotList : [
        { id: 1, duration: '3.5s', lyric: '即便 跌跌撞撞', thumb: '/static/processed/thumbnails/thumb_0.jpg' },
        { id: 2, duration: '4.2s', lyric: '也要 飞向 远方', thumb: '/static/processed/thumbnails/thumb_1.jpg' },
        { id: 3, duration: '2.8s', lyric: '那是 我的 勋章', thumb: '/static/processed/thumbnails/thumb_2.jpg' },
        { id: 4, duration: '5.1s', lyric: '人生海海 山山而川', thumb: '/static/processed/thumbnails/thumb_3.jpg' }
    ];

    effectiveList.forEach(shot => {
        const card = document.createElement('div');
        card.className = 'storyboard-card';
        card.innerHTML = `
            <div class="card-thumb">
                <img src="${shot.thumb}" alt="shot">
                <div class="card-play-overlay">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M8 5v14l11-7z"/>
                    </svg>
                </div>
                <span class="card-duration">${shot.duration}</span>
            </div>
            <div class="card-meta">${shot.lyric}</div>
        `;
        card.onclick = (e) => {
            if (e.target.closest('.card-play-overlay')) {
                e.stopPropagation();
                playSegmentAudio(shot);
            } else {
                openReplacementHub(shot);
            }
        };
        container.appendChild(card);
    });
}

function playSegmentAudio(shot) {
    if (!shot.audio_url || shot.start === undefined) return;

    // Create or reuse hidden audio element
    let player = document.getElementById('global-segment-player');
    if (!player) {
        player = document.createElement('audio');
        player.id = 'global-segment-player';
        document.body.appendChild(player);
    }

    // Use media fragment for precision playback
    player.src = `${shot.audio_url}#t=${shot.start},${shot.end}`;
    player.play();
}

function openReplacementHub(shot) {
    const modal = document.getElementById('replacement-modal');

    // Update header with segment details
    document.getElementById('segment-info').textContent = `正在编辑：分镜 #${shot.id} | 时长: ${shot.duration}`;

    // Add Segment Player Area
    let playerArea = modal.querySelector('.segment-player-container');
    if (!playerArea) {
        playerArea = document.createElement('div');
        playerArea.className = 'segment-player-container';
        modal.querySelector('.modal-header').insertAdjacentElement('afterend', playerArea);
    }

    playerArea.innerHTML = `
        <div class="segment-player" style="margin: 0 32px; border-top: none;">
            <button class="play-segment-btn" onclick="playSegmentAudio(${JSON.stringify(shot).replace(/"/g, '&quot;')})">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            </button>
            <div class="lyrics-display">“${shot.lyric}”</div>
        </div>
    `;

    modal.classList.remove('hidden');

    // Sync Library Tab
    const libGrid = document.getElementById('v3-library-grid');
    libGrid.innerHTML = '';

    // Use uploaded files as library items
    if (videoFiles.length > 0) {
        videoFiles.forEach((file, idx) => {
            const item = document.createElement('div');
            item.className = 'lib-thumb';
            // In a real app, we'd use a generated local thumbnail. Here we use a placeholder.
            item.innerHTML = `<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; background:#222; font-size:10px;">MATERIAL #${idx + 1}</div>`;
            item.title = file.name;
            libGrid.appendChild(item);
        });
    } else {
        libGrid.innerHTML = '<p style="grid-column: 1/-1; text-align:center; color:#666; font-size:12px; padding:20px;">素材库为空，请先上传原始视频</p>';
    }
}

function switchStage(stageId) {
    document.querySelectorAll('.stage-view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(stageId);
    target.classList.add('active');
}

async function startProjectV3() {
    const intent = document.getElementById('v3-intent').value;
    const lyrics = document.getElementById('v3-lyrics').value;

    if (!intent) {
        alert("请输入创意导演意图");
        return;
    }

    preProcessUI();

    const formData = new FormData();
    if (audioFile) formData.append('audio', audioFile);
    videoFiles.forEach(v => formData.append('media', v));
    formData.append('intent', intent);
    formData.append('lyrics', lyrics);
    formData.append('allow_ai_generation', 'false');

    try {
        await fetch('/upload', { method: 'POST', body: formData });
    } catch (e) {
        addV3Log("ERROR", `系统集成故障: ${e.message}`);
    }
}

async function startProTest() {
    preProcessUI();
    addV3Log("PRO", "检测到 PRO 调试模式，正在直连本地 4K 原始素材...");

    // Auto-fill UI for visual feedback
    document.getElementById('v3-intent').value = PRO_TEST_PARAMETERS.intent;
    document.getElementById('v3-lyrics').value = PRO_TEST_PARAMETERS.lyrics;

    try {
        const res = await fetch('/debug/run_test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...PRO_TEST_PARAMETERS,
                allow_ai_gen: false
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message);
        addV3Log("SUCCESS", "后端引擎已接管绝对路径资源，开始并行处理...");
    } catch (e) {
        addV3Log("ERROR", `PRO 模式启动失败: ${e.message}`);
    }
}

function preProcessUI() {
    switchStage('stage-thinking');
    document.getElementById('v3-console').classList.add('hidden');
    document.getElementById('v3-logs').innerHTML = '';
    updateV3Progress(0);
}

function initWebSocket() {
    if (socket) socket.close();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

    socket.onmessage = (event) => {
        const log = event.data;
        if (log.startsWith('JSON:')) {
            const data = JSON.parse(log.substring(5));
            if (data.type === 'segment_data') {
                // Update shotList with real data from backend
                const existingIdx = shotList.findIndex(s => s.id == data.id);
                const shotData = {
                    id: data.id,
                    lyric: data.text,
                    duration: data.duration,
                    start: data.start,
                    end: data.end,
                    audio_url: data.audio_url,
                    thumb: `/static/processed/thumbnails/thumb_${data.id % 5}.jpg`
                };
                if (existingIdx !== -1) shotList[existingIdx] = shotData;
                else shotList.push(shotData);
            }
        } else {
            renderV3Log(log);
        }
    };
}



function renderV3Log(log) {
    // Filter out repetitive shot processing logs and redirect to text progress bar
    const shotMatch = log.match(/已处理 (\d+)\/(\d+) 个镜头/);
    if (shotMatch) {
        updateShotProgressBar(parseInt(shotMatch[1]), parseInt(shotMatch[2]));
        return; // Don't push to main terminal
    }

    // Capture shot metadata from logs
    const mbMatch = log.match(/正在构思第 (\d+) 个长镜头 \(歌词: "(.*?)"\)/);
    if (mbMatch) {
        const id = mbMatch[1];
        const lyric = mbMatch[2];
        // Guess duration or wait for a specific log. For now, we seed the list.
        if (!shotList.find(s => s.id == id)) {
            shotList.push({
                id: id,
                lyric: lyric,
                duration: (3 + Math.random() * 3).toFixed(1) + 's',
                thumb: `/static/processed/thumbnails/thumb_${id % 5}.jpg` // Mock thumb path
            });
        }
    }

    let type = "SYSTEM";
    if (log.includes('STEP')) type = "PROCESS";
    if (log.includes('✅')) type = "SUCCESS";
    if (log.includes('🎯')) type = "MATCH";
    if (log.includes('❌')) type = "ERROR";

    addV3Log(type, log.replace(/^ LOG: /, ''));
    syncV3Progress(log);

    if (log.includes('制作任务圆满完成')) {
        updateV3Progress(100);
        document.getElementById('shot-progress-box').classList.add('hidden');
        setTimeout(() => {
            const finalVideo = document.getElementById('final-video-v3');
            finalVideo.src = '/static/processed/final_video.mp4?t=' + Date.now();
            document.getElementById('v3-download').href = '/static/processed/final_video.mp4';
            switchStage('stage-result');
        }, 2000);
    }
}

function updateShotProgressBar(current, total) {
    const box = document.getElementById('shot-progress-box');
    box.classList.remove('hidden');

    const width = 30; // 30 characters wide
    const filled = Math.round((current / total) * width);
    const empty = width - filled;
    const bar = "█".repeat(filled) + "░".repeat(empty);
    const pct = Math.round((current / total) * 100);

    box.textContent = `RENDER PROGRESS: [${bar}] ${pct}% (${current}/${total} SHOTS)`;
}

function addV3Log(type, text) {
    const container = document.getElementById('v3-logs');
    const entry = document.createElement('div');
    entry.className = 'log-entry';

    entry.innerHTML = `
        <span class="log-tag">[${type}]</span>
        <span class="log-content">${text}</span>
    `;

    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;

    // Simplify header text: only show high-level step or key event
    const header = document.getElementById('neural-main-task');
    if (text.includes('[STEP 1/4]')) header.textContent = "音频深度分析开始";
    else if (text.includes('[STEP 2/4]')) header.textContent = "素材库特征工程启动";
    else if (text.includes('[STEP 3/4]')) header.textContent = "AI 创意导演与编排";
    else if (text.includes('[STEP 4/4]')) header.textContent = "后期合成渲染中";
    else if (text.includes('📊 音频分析完成')) header.textContent = "音频解析已完成";
    else if (text.includes('✅ 素材库构建完成')) header.textContent = "素材库准备就绪";
    else if (text.includes('🎯 匹配成功')) header.textContent = "分镜匹配同步中";
    else if (text.includes('❌')) header.textContent = "任务执行异常";
}

function syncV3Progress(log) {
    if (log.includes('[STEP 1/4]')) updateV3Progress(15);
    if (log.includes('📊 音频分析完成')) updateV3Progress(30);
    if (log.includes('[STEP 2/4]')) updateV3Progress(35);
    if (log.includes('✅ 素材库构建完成')) updateV3Progress(55);
    if (log.includes('[STEP 3/4]')) updateV3Progress(60);
    if (log.includes('🎯 匹配成功')) {
        const current = parseInt(document.getElementById('v3-progress-pct').textContent);
        if (current < 90) updateV3Progress(current + 4);
    }
    if (log.includes('[STEP 4/4]')) updateV3Progress(92);
}

function updateV3Progress(pct) {
    document.getElementById('v3-progress-bar').style.width = pct + '%';
    document.getElementById('v3-progress-pct').textContent = pct;
}

// ========== Settings ==========

function openSettings() {
    document.getElementById('settings-modal').classList.remove('hidden');
    loadSettings();
    initSettingsTabs();
}

function closeSettings() {
    document.getElementById('settings-modal').classList.add('hidden');
}

function initSettingsTabs() {
    const tabs = document.querySelectorAll('#settings-tabs .tab-btn');
    const panes = document.querySelectorAll('.settings-pane');
    tabs.forEach(tab => {
        tab.onclick = () => {
            const target = tab.dataset.stab;
            tabs.forEach(t => t.classList.remove('active'));
            panes.forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(target).classList.add('active');
        };
    });
}

async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const cfg = await res.json();

        // API Keys (show masked values as placeholders)
        const dKey = document.getElementById('cfg-dashscope-key');
        const gKey = document.getElementById('cfg-gemini-key');
        dKey.value = '';
        gKey.value = '';
        dKey.placeholder = cfg.api_keys.dashscope_api_key || 'sk-...';
        gKey.placeholder = cfg.api_keys.gemini_api_key || 'AIza...';

        // Models
        setSelectValue('cfg-llm-model', cfg.models.llm_model);
        setSelectValue('cfg-vision-model', cfg.models.vision_model);
        setSelectValue('cfg-gemini-model', cfg.models.gemini_model);
        setSelectValue('cfg-clip-model', cfg.models.clip_model);

        // Advanced
        document.getElementById('cfg-output-width').value = cfg.advanced.output_width;
        document.getElementById('cfg-output-height').value = cfg.advanced.output_height;
        document.getElementById('cfg-output-fps').value = cfg.advanced.output_fps;
        document.getElementById('cfg-scene-threshold').value = cfg.advanced.scene_threshold;
        document.getElementById('cfg-min-scene-len').value = cfg.advanced.min_scene_length;
        document.getElementById('cfg-max-scenes').value = cfg.advanced.max_scenes;
        document.getElementById('cfg-concurrent-workers').value = cfg.advanced.concurrent_workers;
        document.getElementById('cfg-top-k').value = cfg.advanced.vector_search_top_k;
        document.getElementById('cfg-fallback-score').value = cfg.advanced.ai_fallback_score;
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

function setSelectValue(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    for (let i = 0; i < el.options.length; i++) {
        if (el.options[i].value === value) {
            el.selectedIndex = i;
            return;
        }
    }
}

async function saveSettings() {
    const payload = {
        models: {
            llm_model: document.getElementById('cfg-llm-model').value,
            vision_model: document.getElementById('cfg-vision-model').value,
            gemini_model: document.getElementById('cfg-gemini-model').value,
            clip_model: document.getElementById('cfg-clip-model').value
        },
        advanced: {
            output_width: parseInt(document.getElementById('cfg-output-width').value),
            output_height: parseInt(document.getElementById('cfg-output-height').value),
            output_fps: parseInt(document.getElementById('cfg-output-fps').value),
            scene_threshold: parseFloat(document.getElementById('cfg-scene-threshold').value),
            min_scene_length: parseInt(document.getElementById('cfg-min-scene-len').value),
            max_scenes: parseInt(document.getElementById('cfg-max-scenes').value),
            concurrent_workers: parseInt(document.getElementById('cfg-concurrent-workers').value),
            vector_search_top_k: parseInt(document.getElementById('cfg-top-k').value),
            ai_fallback_score: parseFloat(document.getElementById('cfg-fallback-score').value)
        }
    };

    // Only send API keys if user actually typed something new
    const dKey = document.getElementById('cfg-dashscope-key').value.trim();
    const gKey = document.getElementById('cfg-gemini-key').value.trim();
    if (dKey || gKey) {
        payload.api_keys = {};
        if (dKey) payload.api_keys.dashscope_api_key = dKey;
        if (gKey) payload.api_keys.gemini_api_key = gKey;
    }

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closeSettings();
        } else {
            alert('Failed to save settings');
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

function toggleKeyVis(inputId) {
    const input = document.getElementById(inputId);
    const btn = input.parentElement.querySelector('.toggle-vis-btn');
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = 'Hide';
    } else {
        input.type = 'password';
        btn.textContent = 'Show';
    }
}
