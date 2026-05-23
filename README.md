# AI Research Agent System

> Nền tảng AI multi-agent giúp tự động hóa quy trình nghiên cứu khoa học: nhận một câu hỏi nghiên cứu từ người dùng, tự động tách thành các sub-query, tìm paper trên arXiv, tóm tắt từng paper bằng LLM cục bộ, rồi tổng hợp thành báo cáo Markdown hoàn chỉnh kèm trích dẫn — toàn bộ pipeline được điều phối bằng **LangGraph** và phục vụ qua **FastAPI + Next.js**.

---

## 📑 Mục lục

1. [Tổng quan dự án](#-tổng-quan-dự-án)
2. [Các tính năng chính](#-các-tính-năng-chính)
3. [Tech Stack](#-tech-stack)
4. [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
5. [Kiến trúc thư mục](#-kiến-trúc-thư-mục)
6. [Yêu cầu môi trường](#-yêu-cầu-môi-trường)
7. [Hướng dẫn chạy dự án](#-hướng-dẫn-chạy-dự-án)
   - [Cách 1: Docker Compose (đơn giản nhất)](#cách-1-docker-compose-đơn-giản-nhất)
   - [Cách 2: Dev mode — chạy từng service riêng](#cách-2-dev-mode--chạy-từng-service-riêng)
8. [Cách sử dụng](#-cách-sử-dụng)
9. [API Reference](#-api-reference)
10. [Cấu hình môi trường (.env)](#-cấu-hình-môi-trường-env)
11. [Testing](#-testing)
12. [Troubleshooting](#-troubleshooting)

---

## 🎯 Tổng quan dự án

**AI Research Agent System** là một hệ thống AI nhiều tác tử (multi-agent) cho phép người dùng giao một câu hỏi nghiên cứu — ví dụ *"Recent advances in retrieval augmented generation"* — và nhận lại một báo cáo nghiên cứu có cấu trúc, kèm trích dẫn nguồn từ arXiv, **mà không phải đọc thủ công hàng chục paper**.

Hệ thống tự động:

1. **Phân tích** câu hỏi và chia thành các truy vấn con.
2. **Tìm kiếm** các paper liên quan trên arXiv.
3. **Tóm tắt** từng paper bằng LLM cục bộ (Ollama).
4. **Tổng hợp** các tóm tắt thành báo cáo Markdown hoàn chỉnh với introduction → key findings → methods → limitations → conclusion → references.

Ngoài ra, hệ thống còn có **Chat với bộ nhớ dài hạn** dùng pgvector, cho phép trợ lý AI nhớ ngữ cảnh xuyên các cuộc hội thoại của cùng một user.

Toàn bộ chạy **100% cục bộ** (không cần OpenAI/Anthropic API key) nhờ Ollama. Đóng gói trong **Docker Compose** với 6 container và một Nginx reverse proxy đứng trước.

---

## 🧩 Các tính năng chính

### 1. Xác thực người dùng (Authentication)

**Mục đích:** Mỗi user có không gian dữ liệu riêng tư — báo cáo, conversation, memory đều chỉ truy cập được khi đã đăng nhập.

- Đăng ký bằng email + mật khẩu (tối thiểu 8 ký tự).
- Mật khẩu hash bằng **bcrypt**, không lưu plain text.
- Đăng nhập trả về **JWT** (Bearer token, mặc định hết hạn sau 7 ngày).
- Mọi endpoint nghiệp vụ đều yêu cầu `Authorization: Bearer <token>`.

### 2. Research Agent — Tự động sinh báo cáo nghiên cứu

**Phục vụ cho:** Sinh viên, nhà nghiên cứu, kỹ sư R&D — bất kỳ ai cần khảo sát nhanh "tình hình hiện tại" về một chủ đề khoa học mà không muốn dành cả ngày để đọc paper.

**Cách hoạt động:**

```
Người dùng nhập prompt
        ↓
[Planner Agent]  ← LLM phân tích prompt, sinh 3–5 query con (JSON mode)
        ↓
[Search Agent]   ← Gọi arXiv API cho mỗi query, dedupe, lấy tối đa 8 paper
        ↓
[Summarizer]     ← Với mỗi paper: LLM trích key_points + methods + findings
        ↓
[Writer Agent]   ← LLM tổng hợp tất cả tóm tắt thành báo cáo Markdown
        ↓
Báo cáo cuối + trích dẫn
```

**Đặc điểm:**

- **Bất đồng bộ:** Khi user submit, request được đẩy vào hàng đợi **Celery + Redis**, trả về `report_id` ngay lập tức. Worker chạy pipeline ở background.
- **Stream tiến trình real-time:** Mỗi bước (`planner_start`, `search_query_done`, `summarizer_progress`, `writer_done`, …) được publish lên Redis pub/sub. Frontend subscribe qua **Server-Sent Events** (SSE) và hiển thị timeline tiến trình live.
- **Tự fallback:** Nếu LLM lỗi ở bước Writer, hệ thống vẫn sinh báo cáo deterministic từ tóm tắt — người dùng không bao giờ nhận empty result.
- **Persistent:** Báo cáo được lưu trong Postgres, có thể xem lại bất cứ lúc nào.

### 3. Chat with Long-term Memory — Trợ lý có trí nhớ

**Phục vụ cho:** Hỏi-đáp nhanh, theo dõi context xuyên nhiều phiên làm việc. Khác với chatbot thông thường (mất trí nhớ sau mỗi phiên), trợ lý này **nhớ những gì user đã nói trước đây**, ngay cả khi sang conversation mới.

**Cách hoạt động:**

1. User gửi tin nhắn.
2. Hệ thống **embed** tin nhắn bằng `nomic-embed-text` (768 dims).
3. Truy vấn **top-K memory gần nhất** (cosine similarity) trong bảng `memories` qua **pgvector HNSW index**.
4. Inject các memory liên quan vào system prompt của LLM.
5. LLM trả lời.
6. Background task lưu cặp Q&A mới dưới dạng memory (cùng vector embedding) để dùng cho lần sau.

**Ví dụ:**
- Conversation 1: *"Ngôn ngữ lập trình yêu thích của tôi là Rust vì nó memory-safe."*
- Conversation 2 (sau vài ngày): *"Ngôn ngữ tôi thích là gì nhỉ?"* → Trợ lý trả lời đúng "Rust", vì memory cũ được retrieve qua semantic search.

### 4. Live Progress Streaming (SSE)

Khi research job đang chạy (có thể mất vài phút trên CPU-only Ollama), frontend không phải polling. Endpoint `GET /research/{id}/stream` trả về **EventStream** với các sự kiện:

- `snapshot` — trạng thái hiện tại của report
- `planner_start`, `planner_done`
- `search_start`, `search_query_done`, `search_query_failed`, `search_done`
- `summarizer_start`, `summarizer_progress`, `summarizer_done`
- `writer_start`, `writer_done`
- `ping` (heartbeat mỗi 10s để keep-alive)
- `done` (kết thúc stream)

### 5. REST API + Auto-generated Docs

FastAPI tự sinh interactive docs tại `/api/docs` (Swagger UI) và `/api/redoc`. Mọi schema (request/response) được mô tả qua Pydantic, có type validation tự động.

---

## 🛠️ Tech Stack

| Layer | Công nghệ |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, TailwindCSS 4, react-markdown, TypeScript |
| **Backend** | FastAPI, async SQLAlchemy 2, Alembic, Pydantic v2, python-jose (JWT), bcrypt |
| **Orchestration** | LangGraph 1.x (state graph + node-based agents) |
| **LLM** | Ollama (cục bộ): `llama3.1:8b` cho generation, `nomic-embed-text` cho embeddings |
| **Search** | arXiv API (qua thư viện `arxiv`, không cần key) |
| **Storage** | PostgreSQL 16 + pgvector (HNSW index 768-d) |
| **Queue / Pub-Sub** | Celery 5 + Redis 7 |
| **Streaming** | sse-starlette (Server-Sent Events) |
| **Reverse Proxy** | Nginx (Alpine) |
| **Deployment** | Docker Compose |

---

## 🏗️ Kiến trúc hệ thống

```
┌────────────────┐
│    Browser     │
└────────┬───────┘
         │ http://localhost
         ▼
┌─────────────────────────────────────┐
│       Nginx (reverse proxy)         │
│   /api/*  →  backend:8000           │
│   /*      →  frontend:3000          │
└────────┬───────────────────┬────────┘
         │                   │
         ▼                   ▼
  ┌──────────────┐    ┌──────────────┐
  │   Next.js    │    │   FastAPI    │
  │   Frontend   │    │   Backend    │
  │  (port 3000) │    │  (port 8000) │
  └──────────────┘    └──────┬───────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       │                     │                     │
       ▼                     ▼                     ▼
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│  Postgres   │      │    Redis     │      │    Ollama    │
│ + pgvector  │      │  broker +    │      │   (HOST,     │
│             │      │  pub/sub     │      │  port 11434) │
└──────┬──────┘      └──────┬───────┘      └──────▲───────┘
       │                    │                     │
       │                    ▼                     │
       │             ┌──────────────┐             │
       └─────────────│ Celery Worker│─────────────┘
                     │  (LangGraph) │
                     └──────────────┘
```

### Pipeline multi-agent (LangGraph)

```
START → Planner → Search → Summarizer → Writer → END
        (LLM)    (arXiv)     (LLM)       (LLM)
```

Mỗi node publish event lên kênh Redis `research:{report_id}`, được FastAPI forward về frontend qua SSE.

---

## 📁 Kiến trúc thư mục

```
Research_Agent/
│
├── AI_Research_Agent_System_SRS.pdf   # Spec gốc
├── README.md                          # Tài liệu này
├── docker-compose.yml                 # Khai báo 6 services
├── .env.example                       # Mẫu cấu hình
├── .gitignore
│
├── nginx/
│   └── nginx.conf                     # Cấu hình reverse proxy
│
├── backend/                           # FastAPI + Celery worker
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── pyproject.toml                 # Dependencies + tooling
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                     # Alembic environment (async)
│   │   └── versions/
│   │       ├── e499796aabe5_initial_schema_with_pgvector.py
│   │       └── 11e6692420e0_switch_..._hnsw.py
│   ├── app/
│   │   ├── main.py                    # FastAPI app + route wiring
│   │   ├── config.py                  # Pydantic Settings (env-driven)
│   │   ├── core/
│   │   │   ├── logging.py
│   │   │   ├── security.py            # JWT + bcrypt
│   │   │   └── deps.py                # current_user, get_db
│   │   ├── db/
│   │   │   ├── base.py                # SQLAlchemy Base
│   │   │   ├── session.py             # async engine + session factory
│   │   │   └── models.py              # User, Report, Conversation, Message, Memory
│   │   ├── schemas/                   # Pydantic request/response
│   │   │   ├── auth.py
│   │   │   ├── research.py
│   │   │   └── chat.py
│   │   ├── api/                       # Route handlers
│   │   │   ├── auth.py                # /auth/register, /auth/login, /auth/me
│   │   │   ├── research.py            # /research POST/GET/stream
│   │   │   └── chat.py                # /chat POST
│   │   ├── llm/
│   │   │   ├── base.py                # LLMClient protocol
│   │   │   └── ollama_client.py       # async Ollama wrapper
│   │   ├── tools/
│   │   │   └── arxiv_search.py        # arxiv lib wrapper
│   │   ├── agents/                    # LangGraph nodes
│   │   │   ├── state.py               # ResearchState TypedDict
│   │   │   ├── progress.py            # Redis pub/sub publisher
│   │   │   ├── planner.py
│   │   │   ├── search.py
│   │   │   ├── summarizer.py
│   │   │   ├── writer.py
│   │   │   └── graph.py               # build_research_graph()
│   │   ├── memory/
│   │   │   ├── embeddings.py          # Ollama nomic-embed-text wrapper
│   │   │   └── store.py               # pgvector CRUD + semantic search
│   │   └── tasks/
│   │       ├── celery_app.py
│   │       └── research_task.py       # Celery task chạy LangGraph
│   └── tests/
│       ├── conftest.py
│       └── test_auth.py
│
└── frontend/                          # Next.js 16 App Router
    ├── Dockerfile
    ├── .dockerignore
    ├── package.json
    ├── next.config.ts                 # output: 'standalone' cho Docker
    ├── tsconfig.json
    ├── postcss.config.mjs
    └── src/
        ├── app/
        │   ├── layout.tsx             # Root layout + Nav
        │   ├── page.tsx               # Redirect → /research
        │   ├── globals.css            # Tailwind 4 + typography
        │   ├── login/page.tsx
        │   ├── register/page.tsx
        │   ├── research/
        │   │   ├── page.tsx           # List + form submit
        │   │   └── [id]/page.tsx      # Detail + SSE progress + markdown
        │   └── chat/page.tsx          # Chat UI
        ├── components/
        │   └── Nav.tsx                # Top navigation
        └── lib/
            ├── api.ts                 # Typed fetch client
            └── auth.ts                # Token storage (localStorage)
```

---

## ✅ Yêu cầu môi trường

Trước khi bắt đầu, máy của bạn cần có:

| Yêu cầu | Phiên bản tối thiểu | Kiểm tra |
|---|---|---|
| **Docker Engine** | 24+ | `docker --version` |
| **Docker Compose** | v2+ (built-in) | `docker compose version` |
| **Ollama** | Mọi version mới | `ollama --version` |
| **Git** | Mọi version | `git --version` |
| (Tùy chọn) **Python** | 3.11+ | dùng cho dev mode |
| (Tùy chọn) **Node.js** | 22+ | dùng cho dev mode |

### Cài đặt Ollama + tải models

Nếu chưa có Ollama: <https://ollama.com/download>

Sau khi cài, pull 2 models cần thiết (~5 GB tổng):

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Verify đã có:

```bash
ollama list
# Bạn phải thấy: llama3.1:8b   và   nomic-embed-text:latest
```

### ⚠️ Cấu hình Ollama lắng nghe 0.0.0.0 (bắt buộc khi dùng Docker)

Mặc định Ollama (cài qua systemd) chỉ bind `127.0.0.1:11434`, container không reach được qua `host.docker.internal`. **Cần làm bước này một lần duy nhất:**

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

Verify (phải thấy `*:11434`, không phải `127.0.0.1:11434`):

```bash
ss -ltn | grep 11434
```

Nếu output là `0.0.0.0:11434` hoặc `*:11434` → OK. Nếu vẫn `127.0.0.1` → restart chưa xong, đợi vài giây rồi thử lại.

---

## 🚀 Hướng dẫn chạy dự án

Có **2 cách** chạy: Docker Compose (one-command, đơn giản) hoặc Dev mode (chạy từng service riêng để dễ debug / hot-reload).

### Cách 1: Docker Compose (đơn giản nhất)

Phù hợp khi bạn chỉ muốn **chạy thử / demo / production**. Không cần cài Python hay Node trên máy.

#### Bước 1: Clone repo

```bash
git clone <repo-url> Research_Agent
cd Research_Agent
```

#### Bước 2: Tạo file `.env`

```bash
cp .env.example .env
```

Mở `.env` bằng editor và **đổi `JWT_SECRET`** thành một chuỗi random ≥ 32 ký tự (có thể tạo bằng `openssl rand -hex 32`):

```bash
JWT_SECRET=<chuỗi-bí-mật-của-bạn>
```

Các biến khác có thể giữ nguyên cho lần chạy đầu tiên.

#### Bước 3: Build và start toàn bộ stack

```bash
docker compose up -d --build
```

Lệnh này sẽ:
- Pull image `pgvector/pgvector:pg16`, `redis:7-alpine`, `nginx:alpine`
- Build image `research_agent-backend` (Python 3.11 + FastAPI + LangGraph)
- Build image `research_agent-frontend` (Node 22 + Next.js standalone)
- Khởi tạo network và start 6 container theo thứ tự dependency
- Backend sẽ **tự chạy `alembic upgrade head`** trước khi khởi động uvicorn

Thời gian build lần đầu: ~3–5 phút (tùy mạng).

#### Bước 4: Verify stack đã chạy

```bash
docker compose ps
```

Kết quả mong đợi (tất cả `Up` và `(healthy)` khi áp dụng):

```
NAME                  SERVICE     STATUS
research_backend      backend     Up (healthy)
research_celery       worker      Up
research_frontend     frontend    Up
research_nginx        nginx       Up
research_postgres     postgres    Up (healthy)
research_redis        redis       Up (healthy)
```

Test API health qua Nginx:

```bash
curl http://localhost/api/health
# {"status":"ok","env":"production"}
```

#### Bước 5: Mở browser

Truy cập **<http://localhost>** → bạn sẽ thấy trang đăng nhập. Đăng ký account và bắt đầu sử dụng.

#### Quản lý stack

```bash
# Xem log một service cụ thể (vd worker)
docker compose logs -f worker

# Restart một service
docker compose restart backend

# Stop nhưng giữ data (volumes vẫn còn)
docker compose down

# Stop và xóa hết volume (DB, Redis sẽ bị wipe!)
docker compose down -v

# Rebuild khi sửa code
docker compose up -d --build backend worker frontend
```

---

### Cách 2: Dev mode — chạy từng service riêng

Phù hợp khi bạn **đang phát triển**: hot-reload cho backend và frontend, dễ thêm `print()` để debug, không phải rebuild Docker image mỗi lần.

Chiến lược: **Postgres + Redis chạy trong Docker** (vì cài cục bộ phiền), **Backend + Worker + Frontend chạy native trên máy**.

#### Bước 1: Clone repo và tạo `.env`

```bash
git clone <repo-url> Research_Agent
cd Research_Agent
cp .env.example .env
```

**Quan trọng:** Khi chạy backend/worker NATIVE (không trong Docker), chúng sẽ kết nối tới Postgres/Redis qua `localhost` chứ không phải `postgres`/`redis` (đó là internal Docker network). Sửa `.env`:

```bash
# Thay vì @postgres:5432 → dùng localhost:5433 (mapped port)
DATABASE_URL=postgresql+asyncpg://research:research_pw@localhost:5433/research_agent
DATABASE_URL_SYNC=postgresql+psycopg2://research:research_pw@localhost:5433/research_agent

# Thay vì @redis:6379 → dùng localhost:6380 (mapped port)
REDIS_URL=redis://localhost:6380/0
CELERY_BROKER_URL=redis://localhost:6380/1
CELERY_RESULT_BACKEND=redis://localhost:6380/2

# Ollama chạy native cũng trên localhost
OLLAMA_HOST=http://localhost:11434
```

#### Bước 2: Khởi động Postgres + Redis (Docker)

```bash
docker compose up -d postgres redis
```

Kiểm tra:

```bash
docker compose ps postgres redis
# Cả hai phải Up (healthy)
```

Postgres lắng nghe `localhost:5433`, Redis lắng nghe `localhost:6380` từ phía host.

#### Bước 3: Chạy Backend (FastAPI)

Mở **Terminal 1**:

```bash
cd backend

# Tạo virtualenv (tùy chọn nhưng khuyến nghị)
python3.11 -m venv .venv
source .venv/bin/activate

# Cài backend ở chế độ editable + dev deps
pip install -e ".[dev]"

# Chạy migration (lần đầu / khi schema đổi)
alembic upgrade head

# Start uvicorn với hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify:
```bash
curl http://localhost:8000/health
# {"status":"ok","env":"development"}
```

Mở Swagger docs: <http://localhost:8000/docs>

#### Bước 4: Chạy Celery Worker

Mở **Terminal 2** (giữ Terminal 1 chạy uvicorn):

```bash
cd backend
source .venv/bin/activate    # activate cùng venv với backend

# Start worker (concurrency=1 vì LLM nặng, không cần parallel)
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1
```

Bạn sẽ thấy log:
```
celery@yourhost ready.
[tasks]
  . research.run
```

Worker giờ sẽ pick up các research job từ hàng đợi Redis.

#### Bước 5: Chạy Frontend (Next.js)

Mở **Terminal 3**:

```bash
cd frontend

# Cài deps lần đầu
npm install

# Set API URL cho dev (point thẳng tới backend, bỏ qua Nginx)
export NEXT_PUBLIC_API_URL=http://localhost:8000

# Start dev server với hot-reload
npm run dev
```

Frontend sẽ chạy trên <http://localhost:3000> với HMR (Hot Module Replacement). Mở browser truy cập trực tiếp.

#### (Tùy chọn) Bước 6: Chạy Nginx local

Bình thường ở dev mode bạn không cần Nginx — chỉ cần mở `localhost:3000`. Nhưng nếu muốn test path `/api/*` proxy giống production:

```bash
docker compose up -d nginx
```

Lưu ý: Nginx trong compose trỏ tới `backend:8000` và `frontend:3000` (hostname Docker). Khi bạn chạy backend/frontend native, Nginx KHÔNG tới được. Để test thật, dùng Cách 1 (full Docker stack) thay vì dev mode.

#### Tóm tắt 3 terminal dev mode

| Terminal | Lệnh | URL |
|---|---|---|
| 1 | `uvicorn app.main:app --reload` | <http://localhost:8000> |
| 2 | `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1` | (no web) |
| 3 | `npm run dev` (trong `frontend/`) | <http://localhost:3000> |

---

## 💡 Cách sử dụng

Sau khi đã `up` xong (bất kể dùng Cách 1 hay Cách 2):

### 1. Đăng ký account

- Truy cập <http://localhost> (hoặc <http://localhost:3000> nếu dev mode)
- Nhấn **Register** → nhập email + password (≥ 8 ký tự)
- Sau khi tạo, hệ thống tự login và chuyển sang `/research`

### 2. Submit research

- Trên trang `/research`, nhập prompt vào textarea, ví dụ:
  > *"Recent advances in retrieval augmented generation"*
- Nhấn **Start research** → ngay lập tức redirect tới `/research/{id}`
- Quan sát timeline tiến trình live: Planner → Search → Summarizer (1/8, 2/8, …) → Writer
- Khi hoàn tất (~3–8 phút trên CPU), báo cáo Markdown render kèm danh sách Sources có link arXiv

### 3. Chat với memory

- Vào tab **Chat**
- Gõ tin nhắn bất kỳ — ví dụ ghi nhớ một sở thích: *"Tôi rất thích Rust vì memory safety."*
- Nhấn **New conversation** rồi hỏi: *"Ngôn ngữ nào tôi đã đề cập?"*
- Trợ lý sẽ nhớ và trả lời chính xác. Trong UI sẽ có dòng `↪ recalled N memories`.

### 4. Xem lại báo cáo cũ

- Vào `/research` → list các báo cáo gần nhất hiển thị bên dưới form
- Click vào một báo cáo để xem chi tiết

---

## 🌐 API Reference

Khi route qua Nginx, mọi path đều có prefix `/api/`. Swagger UI: <http://localhost/api/docs>.
Khi chạy dev mode (backend native), URL là `http://localhost:8000/docs`.

| Method | Path | Auth | Mô tả |
|---|---|---|---|
| `GET` | `/health` | — | Liveness probe |
| `POST` | `/auth/register` | — | Đăng ký user mới |
| `POST` | `/auth/login` | — | Đăng nhập, trả JWT |
| `GET` | `/auth/me` | ✓ | Thông tin user hiện tại |
| `POST` | `/research` | ✓ | Submit research, trả `report_id` (Celery enqueue) |
| `GET` | `/research` | ✓ | List báo cáo của user |
| `GET` | `/research/{id}` | ✓ | Chi tiết báo cáo (poll status) |
| `GET` | `/research/{id}/stream` | ✓ | **SSE** stream tiến trình |
| `POST` | `/chat` | ✓ | Gửi tin nhắn, recall memory |

### Ví dụ curl

```bash
# Register
curl -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"supersecret"}'

# Login → lấy token
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"supersecret"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Submit research
curl -X POST http://localhost/api/research \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Diffusion models for time series forecasting"}'

# Chat
curl -X POST http://localhost/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"What did we discuss about Rust?"}'
```

---

## ⚙️ Cấu hình môi trường (.env)

Mọi cấu hình điều khiển qua biến môi trường (load bằng Pydantic Settings):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `POSTGRES_USER` | `research` | User của Postgres container |
| `POSTGRES_PASSWORD` | `research_pw` | Mật khẩu Postgres (đổi cho production) |
| `POSTGRES_DB` | `research_agent` | Tên database |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async URL cho FastAPI |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://...` | Sync URL cho Celery + Alembic |
| `REDIS_URL` | `redis://redis:6379/0` | URL Redis cho pub/sub |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Broker của Celery |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Result backend của Celery |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama URL (đổi nếu chạy native) |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model dùng cho generation |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Model embedding (768-d) |
| `EMBEDDING_DIM` | `768` | Số chiều embedding (khớp với model) |
| `JWT_SECRET` | `dev_only_change_me_in_production` | **BẮT BUỘC đổi cho production** |
| `JWT_ALGORITHM` | `HS256` | Thuật toán ký JWT |
| `JWT_EXPIRE_MINUTES` | `10080` (= 7 ngày) | Token expiry |
| `APP_ENV` | `development` | `development` hoặc `production` |
| `LOG_LEVEL` | `INFO` | Mức log (DEBUG/INFO/WARNING/ERROR) |
| `CORS_ORIGINS` | `http://localhost,...` | Allow list (cách nhau bằng dấu phẩy) |
| `NEXT_PUBLIC_API_URL` | `/api` | URL backend được bake vào bundle frontend |

---

## 🧪 Testing

### Backend tests (pytest)

Yêu cầu: Postgres đang chạy (Cách 2 bước 2). Tests sử dụng DB thật cho integration.

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Kết quả mong đợi:
```
tests/test_auth.py::test_health PASSED
tests/test_auth.py::test_register_login_me PASSED
tests/test_auth.py::test_register_validates_email_and_password_length PASSED
```

### Chạy pipeline LangGraph standalone (không cần API/DB)

Tốt để debug agents:

```bash
cd backend
source .venv/bin/activate
python -m app.agents.graph "Graph neural networks for drug discovery"
```

Pipeline sẽ chạy 4 agent tuần tự và in báo cáo Markdown ra stdout. Yêu cầu Ollama đang chạy.

### Build frontend production

```bash
cd frontend
npm run build
```

Kiểm tra lỗi TypeScript và build issues trước khi push.

---

## 🔧 Troubleshooting

| Triệu chứng | Nguyên nhân & giải pháp |
|---|---|
| Worker log: `"All connection attempts failed"` khi gọi Ollama | Ollama vẫn bind `127.0.0.1`. Áp dụng systemd override ở [phần Yêu cầu môi trường](#-yêu-cầu-môi-trường) |
| arXiv trả `HTTP 429` | Bị rate limit do test nhiều lần liên tiếp. Đợi ~1 phút hoặc giảm `TOTAL_CAP` trong `backend/app/agents/search.py` |
| SSE stream stuck ở `pending` rất lâu | Worker đang bận xử lý task khác (concurrency=1). Kiểm tra `docker compose logs -f worker` |
| pgvector trả 0 row mặc dù có memories | IVFFlat cũ cần nhiều row + tuning `probes`. Migration mới đã chuyển sang HNSW — verify bằng `\d ix_memories_embedding_cosine` (phải thấy `hnsw`) |
| `docker compose up` báo conflict port `5433` / `6380` / `80` | Bạn đang có service khác chiếm port. Đổi mapping trong `docker-compose.yml` hoặc stop service đang chiếm |
| Frontend không gọi được backend (Network error trong DevTools) | Kiểm tra `NEXT_PUBLIC_API_URL` đã set đúng khi build/run frontend. Trong Docker mode = `/api`, trong dev mode = `http://localhost:8000` |
| Backend container exit `(1)` ngay sau khi start | Thường do migration thất bại — `docker compose logs backend` để xem stack trace, có thể Postgres chưa healthy hoặc credentials sai |
| `npm install` lỗi do lock file mismatch | Xóa `frontend/node_modules` và `frontend/package-lock.json`, chạy lại `npm install` |

### Reset toàn bộ dữ liệu

Nếu muốn bắt đầu lại từ đầu (xóa hết user, report, memory):

```bash
docker compose down -v
docker compose up -d --build
```

---

## 📌 Out of Scope (v1)

Theo SRS mục §11, các tính năng sau là **future work**, chưa có trong phiên bản này:

- 🎙️ Voice interaction
- 🌐 Browser automation
- 🔧 Code execution agent
- 🖼️ Multimodal AI support (vision/audio)
- 🔍 Web search (Google/Bing/Tavily) — hiện chỉ search arXiv
- 📊 Monitoring stack (Prometheus + Grafana) — đã tạm bỏ qua

---

## 📜 License & Credits

- Built from spec `AI_Research_Agent_System_SRS.pdf`
- Powered by [Ollama](https://ollama.com), [LangGraph](https://langchain-ai.github.io/langgraph/), [FastAPI](https://fastapi.tiangolo.com), [Next.js](https://nextjs.org), [pgvector](https://github.com/pgvector/pgvector), [arXiv API](https://info.arxiv.org/help/api/)
