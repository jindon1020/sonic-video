# SonicVideo 服务器部署指南

本指南提供三种部署方式：一键脚本部署、Docker 部署、systemd 服务部署。

---

## 🚀 方案一：一键脚本部署（推荐快速部署）

### 1. 准备服务器

**系统要求**：
- Ubuntu 20.04+ / CentOS 7+ / Debian 10+
- Python 3.10+
- FFmpeg
- 至少 4GB RAM
- 至少 10GB 磁盘空间

**安装依赖**：

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg git curl

# CentOS/RHEL
sudo yum install -y python3 python3-pip ffmpeg git curl

# 验证安装
python3 --version
ffmpeg -version
```

### 2. 克隆代码

```bash
# 创建部署目录
sudo mkdir -p /opt/sonicvideo
sudo chown -R $USER:$USER /opt/sonicvideo

# 克隆代码
cd /opt/sonicvideo
git clone https://github.com/jindon1020/sonic-video.git .

# 或者拉取最新代码
git pull
```

### 3. 配置 API 密钥

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
nano .env
```

在 `.env` 中填写至少一个 API 密钥：

```bash
# 至少配置一个 LLM Provider
DASHSCOPE_API_KEY=sk-your-qwen-api-key        # 阿里云通义千问
GEMINI_API_KEY=your-gemini-api-key            # Google Gemini
OPENAI_API_KEY=sk-your-openai-api-key         # OpenAI GPT-4
ANTHROPIC_API_KEY=sk-your-anthropic-api-key   # Anthropic Claude
```

### 4. 一键部署启动

**方式 1: 使用传统工作流（v1）**
```bash
./deploy.sh
```

**方式 2: 使用 LangGraph 工作流（v2，推荐）**
```bash
./deploy.sh --langgraph
```

**方式 3: 指定端口**
```bash
./deploy.sh --langgraph --port 9000
```

### 5. 验证部署

```bash
# 检查服务状态
curl http://localhost:8000/

# 查看 API 文档
curl http://localhost:8000/docs

# 查看日志
tail -f /var/log/sonicvideo/sonicvideo.log
```

### 6. 管理服务

```bash
# 查看进程
ps aux | grep uvicorn

# 停止服务
kill $(cat /var/run/sonicvideo.pid)

# 重启服务
./deploy.sh --langgraph
```

---

## 🐳 方案二：Docker 部署（推荐生产环境）

### 1. 安装 Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# .env
USE_LANGGRAPH=true
DASHSCOPE_API_KEY=sk-your-key
GEMINI_API_KEY=your-key
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-your-key
```

### 3. 构建并启动

```bash
# 构建镜像
docker-compose build

# 启动服务（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f sonicvideo
```

### 4. 管理 Docker 服务

```bash
# 查看运行状态
docker-compose ps

# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 更新代码并重启
git pull
docker-compose up -d --build

# 清理容器
docker-compose down
```

### 5. Docker 健康检查

```bash
# 检查容器健康状态
docker ps

# 查看健康检查日志
docker inspect sonicvideo | grep -A 10 Health
```

---

## ⚙️ 方案三：Systemd 服务部署（推荐长期运行）

### 1. 安装依赖并配置

```bash
# 克隆代码到指定目录
sudo mkdir -p /opt/sonicvideo
cd /opt/sonicvideo
git clone https://github.com/jindon1020/sonic-video.git .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置 .env
cp .env.example .env
nano .env
```

### 2. 安装 Systemd 服务

```bash
# 复制服务文件
sudo cp sonicvideo.service /etc/systemd/system/

# 根据实际情况修改服务文件
sudo nano /etc/systemd/system/sonicvideo.service

# 重要：修改 User 和 Group 为你的用户
# User=your-username
# Group=your-group

# 创建日志目录
sudo mkdir -p /var/log/sonicvideo
sudo chown -R your-username:your-group /var/log/sonicvideo

# 重载 systemd
sudo systemctl daemon-reload
```

### 3. 启动服务

```bash
# 启动服务
sudo systemctl start sonicvideo

# 设置开机自启
sudo systemctl enable sonicvideo

# 查看状态
sudo systemctl status sonicvideo

# 查看日志
sudo journalctl -u sonicvideo -f
```

### 4. 管理 Systemd 服务

```bash
# 停止服务
sudo systemctl stop sonicvideo

# 重启服务
sudo systemctl restart sonicvideo

# 重新加载配置
sudo systemctl reload sonicvideo

# 查看完整日志
sudo journalctl -u sonicvideo --no-pager

# 禁用开机自启
sudo systemctl disable sonicvideo
```

---

## 🔧 生产环境优化

### 1. Nginx 反向代理

创建 Nginx 配置 `/etc/nginx/sites-available/sonicvideo`:

```nginx
upstream sonicvideo {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # 请求体大小限制（支持大文件上传）
    client_max_body_size 500M;

    location / {
        proxy_pass http://sonicvideo;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;

        # WebSocket 支持
        proxy_set_header Connection "upgrade";
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # 静态文件
    location /static {
        alias /opt/sonicvideo/app/static;
        expires 30d;
    }

    location /uploads {
        alias /opt/sonicvideo/uploads;
        expires 7d;
    }
}
```

启用配置：

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/sonicvideo /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### 2. SSL 证书（使用 Let's Encrypt）

```bash
# 安装 Certbot
sudo apt-get install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期测试
sudo certbot renew --dry-run
```

### 3. 防火墙配置

```bash
# Ubuntu UFW
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw enable

# CentOS Firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### 4. 性能调优

**修改 systemd 服务配置**：

```ini
[Service]
# 增加工作进程数（根据 CPU 核心数调整）
ExecStart=/opt/sonicvideo/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 8

# 资源限制
LimitNOFILE=65536
LimitNPROC=4096
```

**系统参数调优**：

```bash
# 编辑 /etc/sysctl.conf
sudo nano /etc/sysctl.conf

# 添加以下内容
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
fs.file-max = 100000

# 应用配置
sudo sysctl -p
```

---

## 📊 监控和日志

### 1. 实时监控

```bash
# CPU 和内存使用
htop

# 磁盘使用
df -h

# 网络连接
netstat -tunlp | grep 8000

# Docker 资源使用
docker stats sonicvideo
```

### 2. 日志管理

```bash
# 查看实时日志
tail -f /var/log/sonicvideo/sonicvideo.log

# 查看错误日志
tail -f /var/log/sonicvideo/error.log

# 查看 systemd 日志
sudo journalctl -u sonicvideo -f --lines 100

# 日志轮转配置 /etc/logrotate.d/sonicvideo
/var/log/sonicvideo/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
}
```

### 3. 健康检查脚本

创建 `healthcheck.sh`:

```bash
#!/bin/bash
ENDPOINT="http://localhost:8000/"
TIMEOUT=10

if curl -sf --max-time $TIMEOUT "$ENDPOINT" > /dev/null; then
    echo "✅ Service is healthy"
    exit 0
else
    echo "❌ Service is down"
    # 可选：发送告警通知
    # ./send_alert.sh "SonicVideo service is down"
    exit 1
fi
```

配置 crontab 定期检查：

```bash
# 每 5 分钟检查一次
*/5 * * * * /opt/sonicvideo/healthcheck.sh
```

---

## 🔄 自动更新部署

创建自动更新脚本 `auto-update.sh`:

```bash
#!/bin/bash
cd /opt/sonicvideo

# 拉取最新代码
git pull

# 安装依赖
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
sudo systemctl restart sonicvideo

# 验证
sleep 5
if curl -sf http://localhost:8000/ > /dev/null; then
    echo "✅ 更新成功"
else
    echo "❌ 更新失败，回滚代码"
    git reset --hard HEAD~1
    sudo systemctl restart sonicvideo
fi
```

---

## 🐛 故障排查

### 常见问题

**1. 服务无法启动**
```bash
# 检查日志
sudo journalctl -u sonicvideo -n 50

# 检查端口占用
sudo lsof -i :8000

# 检查权限
ls -la /opt/sonicvideo
```

**2. API 密钥错误**
```bash
# 验证环境变量
source venv/bin/activate
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DASHSCOPE_API_KEY'))"
```

**3. 内存不足**
```bash
# 查看内存使用
free -h

# 清理缓存
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches

# 增加 swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**4. FFmpeg 未找到**
```bash
# 验证 FFmpeg
which ffmpeg
ffmpeg -version

# 如果未安装
sudo apt-get install ffmpeg  # Ubuntu
sudo yum install ffmpeg       # CentOS
```

---

## 📝 快速命令参考

```bash
# 一键部署
./deploy.sh --langgraph

# 查看服务状态
sudo systemctl status sonicvideo

# 重启服务
sudo systemctl restart sonicvideo

# 查看日志
tail -f /var/log/sonicvideo/sonicvideo.log

# Docker 部署
docker-compose up -d

# 更新代码
git pull && ./deploy.sh --langgraph

# 健康检查
curl http://localhost:8000/
```

---

## 🎯 总结

**推荐部署方式**：

- **开发/测试**: 一键脚本部署 (`./deploy.sh`)
- **生产环境**: Systemd + Nginx + SSL
- **容器化**: Docker Compose
- **自动化**: Systemd + 自动更新脚本

选择适合您场景的部署方式，按照步骤操作即可完成部署！

如有问题，请查看日志文件或提交 Issue。
