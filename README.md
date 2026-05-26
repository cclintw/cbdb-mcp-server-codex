# 自建 CBDB MCP Server

本專案示範如何在本機自建一個 CBDB MCP server，讓 Codex 或其他支援 MCP 的 AI 工具能夠查詢使用者自行下載的 CBDB SQLite。

CBDB 目前提供 API 與可下載資料，但尚未提供官方 MCP server。本專案因此提供一個本地實作：使用者把 CBDB SQLite 放到指定位置後，即可透過 MCP tools 查詢人物、地名、職官與年號，並用附帶的示範文本展示 AI + MCP + CBDB 的文本標註流程。

本專案不重新發布 CBDB SQLite，也不建立自有大型權威資料庫。

## 專案用途

本 repo 主要提供：

- CBDB MCP server 程式
- Codex MCP client 設定範例
- 一份合成示範文本 `sample-1.txt`
- 一個最小標註輸出流程，用於展示 MCP server 的應用效果

專案重點是「如何讓 AI 工具透過 MCP 使用 CBDB」，不是建立完整 NLP pipeline，也不是替代 MARKUS。

## 為什麼需要下載 CBDB SQLite

如果 CBDB 未來提供官方 MCP server，使用者只需要套用官方 MCP client 設定，即可直接讓 Codex 連到 CBDB 官方服務。

但在目前情況下，CBDB 尚未提供官方 MCP server。為了示範 MCP 在史學資料庫中的應用，本專案使用 CBDB 可下載 SQLite 的特性，在本機自建 MCP server。

```mermaid
flowchart LR
    A["CBDB SQLite<br>使用者自行下載"] --> B["本地 CBDB MCP server"]
    B --> C["Codex / MCP client"]
    C --> D["查詢 CBDB / 建立標註"]
```

## 功能

MCP server 使用 `FastMCP`，提供以下 tools：

| Tool | 功能 |
|---|---|
| `inspect_schema()` | 檢查 SQLite tables、views、columns |
| `search_person(name, limit=10)` | 查詢 CBDB 人物 |
| `search_place(name, limit=10)` | 查詢 CBDB 地名 |
| `search_office(name, limit=10)` | 查詢 CBDB 職官 |
| `search_reign(name, limit=10)` | 查詢 CBDB 年號 |
| `resolve_entity(name, entity_type, limit=10)` | 依類型或 auto 模式解析實體 |

查詢層會優先使用 CBDB convenience views；若 view 不存在，會 fallback 到原始表。

## 安裝

建議使用 Python 3.11 以上。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 準備 CBDB SQLite

請依 CBDB 官方 `cbdb_sqlite` repo 下載 SQLite，並放在：

```text
data/cbdb/cbdb.sqlite
```

本專案不內附 CBDB SQLite。`data/cbdb/README.md` 有放置說明。

## 啟動 MCP server

```bash
CBDB_SQLITE_PATH=data/cbdb/cbdb.sqlite python mcp_server/server.py
```

如果 SQLite 不存在，`inspect_schema()` 會回傳 `sqlite_exists: false`，查詢 tools 會回傳錯誤訊息。

## Codex MCP 設定

Codex client 設定範例：

```json
{
  "mcpServers": {
    "cbdb": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "env": {
        "CBDB_SQLITE_PATH": "data/cbdb/cbdb.sqlite"
      }
    }
  }
}
```

範例檔位於：

```text
config/codex-mcp-example.json
```

請依實際環境調整 `command` 的 Python 路徑。

## 示範文本與標註流程

本 repo 附一份合成示範文本：

```text
data/input/sample-1.txt
```

此文本經亂數處理，目的只是展示 CBDB MCP server 的查詢與標註效果，不作為可靠文本版本。

重新產生示範文本與 authority table：

```bash
python src/generate_demo_corpus.py
```

產生 annotated HTML：

```bash
python src/main.py --input data/input/sample-1.txt
```

輸出位於：

```text
data/output/
```

產生的 `annotated.html` 可直接用瀏覽器開啟，包含：

- 左側章節列表
- 中央標註文本
- 上方實體類型 badge
- 右側 CBDB 詳情
- 人物 CBDB API 參考來源
- 地名 GIS marker，使用 Leaflet + OpenStreetMap

## Codex 標註任務概念

本 repo 不把一次性的 Codex prompt 或本機任務備忘錄納入版本控制。使用 Codex 進行標註時，核心任務概念是：

1. 讀取文本。
2. 透過 MCP tools 查詢 CBDB。
3. 建立 `data/output/authority_table.json`。
4. 執行 Python 產生 annotated HTML。

## 專案結構

```text
cbdb-mcp-server-codex/
├── README.md
├── requirements.txt
├── config/
│   ├── cbdb_schema_notes.json
│   └── codex-mcp-example.json
├── data/
│   ├── cbdb/
│   │   └── README.md
│   └── input/
│       └── sample-1.txt
├── mcp_server/
│   ├── cbdb_sqlite.py
│   └── server.py
└── src/
```

`data/output/`、`doc/`、`prompts/`、`templates/`、`*.html` 與下載後的 CBDB SQLite 都屬本機工作檔或產物，不納入 repo。

## 不包含的功能

本專案刻意不實作：

- CKIP
- jieba
- 斷詞
- 分句
- 自建詞表
- 規則表
- ontology pipeline
- OpenAI API 呼叫
- 額外 LLM API client

Python 程式只負責分章、分段與 HTML 輸出。AI 判斷由 Codex 完成；CBDB 查詢由 MCP server 完成。

## 資料與授權聲明

CBDB SQLite 與相關資料權利屬其原資料提供者與維護者。使用者應依 CBDB 官方授權與引用規範自行下載、使用與引用。

本專案不重新發布 CBDB SQLite，不把 CBDB SQLite 放入 repo，也不建立大型衍生資料庫。
