# Genie TTS 部署指南

本文说明如何把已 clone 的仓库部署为常驻服务。Cloudflare 资源名称、资源 ID 和凭据均由部署方自行创建并保存在部署环境中，不提交到仓库。

```text
客户端
  -> Cloudflare Worker
       -> /audio/wav/*、/audio/ogg/* -> R2
       -> 其他请求 -> Workers VPC Service
                      -> Cloudflare Tunnel
                      -> 127.0.0.1:12451 Genie API
```

计算节点不需要开放入站端口，`cloudflared` 会主动连接 Cloudflare。

## 1. 准备 Cloudflare 资源

需要一个支持 Workers VPC 的 Cloudflare 账户，并创建以下资源：

- 一个 R2 bucket，用于保存生成的 WAV 和 OGG 文件；
- 一个 Cloudflare Tunnel；
- 一个指向该 Tunnel 的 VPC Service；
- 一个 R2 API token，仅授予上述 bucket 的 Object Read & Write 权限。

创建 VPC Service 时使用以下目标：

| 配置 | 值 |
| --- | --- |
| 类型 | HTTP |
| Host/IP | `127.0.0.1` |
| Port | `12451` |

保存 Cloudflare 生成的 VPC Service ID。Tunnel 不需要配置 public hostname 或 DNS 记录。

部署过程中会使用以下私有值：

| 值 | 保存位置 |
| --- | --- |
| Worker 名称、R2 bucket 名称、VPC Service ID | `worker/wrangler.jsonc` |
| R2 Account ID、Access Key ID、Secret Access Key | 项目根目录 `.env` |
| Tunnel token | 仅传给 `cloudflared service install` |

`worker/wrangler.jsonc` 和 `.env` 均已被 Git 忽略。

## 2. 部署 Worker

部署机器需要 Node.js 22 或更高版本。在仓库中执行：

```bash
cd worker
npm ci
npx wrangler login
cp -n wrangler.example.jsonc wrangler.jsonc
```

编辑 `wrangler.jsonc`，替换以下占位符：

- `<WORKER_NAME>`：Worker 名称；
- `<R2_BUCKET_NAME>`：R2 bucket 名称；
- `<VPC_SERVICE_ID>`：Cloudflare 生成的 VPC Service ID；
- 两个 `<...RATE_LIMIT_NAMESPACE_ID>`：同一账户内互不相同的正整数命名空间 ID。

绑定名 `AUDIO`、`GENIE_API`、`CREATE_TASK_RATE_LIMITER` 和 `TASK_STATUS_RATE_LIMITER` 是代码接口，不要修改。

如果 R2 bucket 尚未创建：

```bash
npx wrangler r2 bucket create <R2_BUCKET_NAME>
```

配置自动清理规则：

```bash
npx wrangler r2 bucket lifecycle add <R2_BUCKET_NAME> expire-wav wav/ --expire-days 14
npx wrangler r2 bucket lifecycle add <R2_BUCKET_NAME> expire-ogg ogg/ --expire-days 30
```

运行检查并部署：

```bash
npm test
npm run types
npm run deploy
```

记录部署输出中的 `workers.dev` 地址，后文记作 `<WORKER_URL>`。

## 3. 安装 API 依赖

本文以使用 systemd 的 Ubuntu 为例。在计算节点的仓库根目录执行：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl ffmpeg git jq libgomp1 libsndfile1
ffmpeg -hide_banner -encoders 2>/dev/null | grep libopus
```

最后一条命令应显示 `libopus` 编码器。

安装 `uv` 并同步锁定依赖：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.10
~/.local/bin/uv sync --locked --python 3.10
```

## 4. 放置模型

模型不在 Git 仓库中。把完整的 `models/` 目录放到仓库根目录：

```text
<REPO_PATH>/models/
├── <角色目录>/
│   ├── t2s_first_stage_decoder_fp32.onnx
│   └── ...
└── ...
```

## 5. 配置 API

复制环境变量模板：

```bash
cp .env.example .env
chmod 600 .env
```

填写 `.env`：

```dotenv
MODEL_BASE_DIR=./models
TMP_REFERENCE_DIR=./tmp_references
REFERENCE_RESOURCE_SERVER=https://service.sc-viewer.top/convert/direct/sounds/voice/events
OUTPUT_DIR=./output
CLEANUP_INTERVAL_SECONDS=3600
CLEANUP_AGE_SECONDS=86400
MAX_CACHED_CHARACTER_MODELS=1
MAX_CACHED_REFERENCE_AUDIO=1
MAX_PENDING_TASKS=20

R2_ACCOUNT_ID=<CLOUDFLARE_ACCOUNT_ID>
R2_BUCKET=<R2_BUCKET_NAME>
R2_ACCESS_KEY_ID=<R2_ACCESS_KEY_ID>
R2_SECRET_ACCESS_KEY=<R2_SECRET_ACCESS_KEY>

BASE_STATIC_URL=<WORKER_URL>/audio
```

`BASE_STATIC_URL` 不要带末尾 `/`。创建运行目录：

```bash
mkdir -p output tmp_references
```

## 6. 配置 API 服务

创建 `/etc/systemd/system/genie.service`，替换 `<LINUX_USER>` 和 `<REPO_PATH>`：

```ini
[Unit]
Description=Genie TTS API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<LINUX_USER>
WorkingDirectory=<REPO_PATH>
EnvironmentFile=<REPO_PATH>/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=<REPO_PATH>/.venv/bin/uvicorn server:app --host 127.0.0.1 --port 12451 --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

保持一个 Uvicorn worker。任务队列、任务状态和每日限流计数保存在进程内，增加 worker 会产生独立状态并重复占用模型内存。

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now genie
sudo systemctl status genie --no-pager
curl -fsS http://127.0.0.1:12451/health
```

健康检查应返回：

```json
{"status":"ok"}
```

## 7. 安装 Tunnel connector

安装 `cloudflared`：

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install -y cloudflared
cloudflared --version
```

在 Cloudflare Dashboard 打开此前创建的 Tunnel，选择添加 connector/replica，复制安装 token：

```bash
read -rsp 'Tunnel token: ' TUNNEL_TOKEN
echo
sudo cloudflared service install "$TUNNEL_TOKEN"
unset TUNNEL_TOKEN
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
```

Dashboard 中的 Tunnel connector 应显示为 Healthy。网络需要允许出站 TCP 443；为获得最佳连接效果，同时允许出站 UDP 7844。

## 8. 验证部署

验证 Worker 能通过 VPC 访问 API：

```bash
WORKER_URL='https://<WORKER_NAME>.<ACCOUNT_SUBDOMAIN>.workers.dev'
curl -fsS "$WORKER_URL/health"
```

创建一个推理任务：

```bash
curl -fsS -X POST "$WORKER_URL/tasks" \
  -H 'content-type: application/json' \
  -d '{
    "character_name": "<models 下的角色目录名>",
    "reference_audio_id": "<有效的参考音频 ID>",
    "reference_audio_text": "<参考音频原文>",
    "text": "<短测试文本>"
  }'
```

使用响应中的 `task_id` 查询状态：

```bash
curl -fsS "$WORKER_URL/tasks/<task_id>" | jq .
```

任务完成后，确认 `save_path` 的 WAV 和 `save_path_compressed` 的 Opus/OGG 地址均可访问。

## 9. 更新

更新 API 会中断正在执行的任务并清空进程内任务状态，应先停止提交新任务：

```bash
git pull --ff-only
~/.local/bin/uv sync --locked --python 3.10
sudo systemctl restart genie
curl -fsS http://127.0.0.1:12451/health
```

更新 Worker：

```bash
cd worker
npm ci
npm test
npm run deploy
```

本地的 `worker/wrangler.jsonc` 会保留，不受 `git pull` 影响。

## 访问限制

当前 Worker 没有身份认证。请求按客户端 IP 限流，但知道 Worker URL 的人仍可创建任务、查询任务和读取音频。

## 参考资料

- [Workers VPC 入门](https://developers.cloudflare.com/workers-vpc/get-started/)
- [Workers VPC Tunnel](https://developers.cloudflare.com/workers-vpc/configuration/tunnel/)
- [R2 生命周期](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
