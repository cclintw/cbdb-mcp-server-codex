# CBDB MCP Annotation Demo 工作指引

本專案示範「AI 與史學研究：MCP 的應用——以 CBDB 為例」。Codex 的任務不是重建 CBDB，也不是建立新的權威資料庫，而是在使用者已自行放置 CBDB SQLite 的前提下，透過 MCP 查詢 CBDB，協助建立本次標註用的 authority table。

## Codex 工作流程

1. 閱讀 `data/input/sample.txt`。
2. 判斷疑似歷史實體候選：
   - `person`
   - `place`
   - `office`
   - `reign`
3. 對每個候選實體呼叫 CBDB MCP tools：
   - `search_person`
   - `search_place`
   - `search_office`
   - `search_reign`
   - 必要時可用 `resolve_entity`
4. 將確認後的結果寫入 `data/output/authority_table.json`。
5. 執行：

   ```bash
   python src/main.py --input data/input/sample.txt
   ```

6. 產生 `data/output/annotated.html`。

## Authority Table 格式

```json
[
  {
    "authority_id": "auth_000001",
    "entity_text": "蘇子瞻",
    "entity_type": "person",
    "canonical_name": "蘇軾",
    "source": "CBDB",
    "source_id": "1234",
    "source_url": "https://input.cbdb.fas.harvard.edu/cbdbapi/person.php?id=1234",
    "note": "由 Codex 判斷為人物候選，經 CBDB MCP 查詢比對"
  }
]
```

## 明確不要做的事

- 不要自建詞表。
- 不要建立規則表。
- 不要呼叫 OpenAI API。
- 不要加入額外 LLM API client。
- 不要做 CKIP、jieba、斷詞或分句。
- 不要重建 CBDB。
- 不要下載、提交或重新發布 CBDB SQLite。
- 不要建立大型衍生資料庫。

本專案只示範 AI + MCP + CBDB 的歷史文本標註 workflow。Python 程式只負責分章、分段，以及依 `authority_table.json` 輸出類似 MARKUS 的 annotated HTML。
