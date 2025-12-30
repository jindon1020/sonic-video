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
                <span class="card-duration">${shot.duration}</span>
            </div>
            <div class="card-meta">${shot.lyric}</div>
        `;
        card.onclick = () => openReplacementHub(shot);
        container.appendChild(card);
    });
}

function openReplacementHub(shot) {
    const modal = document.getElementById('replacement-modal');
    document.getElementById('segment-info').textContent = `正在编辑：分镜 #${shot.id} | ${shot.lyric} | 时长: ${shot.duration}`;
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
        renderV3Log(log);
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
