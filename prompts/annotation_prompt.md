# CBDB MCP Annotation Prompt

請閱讀 `data/input/sample.txt`，只以史學文本標註示範為目的，判斷疑似歷史實體候選：

- person
- place
- office
- reign

對每個候選呼叫 CBDB MCP tools 查詢：

- `search_person`
- `search_place`
- `search_office`
- `search_reign`

確認後，將本次標註需要的結果寫入 `data/output/authority_table.json`。不要自建詞表，不要建立規則表，不要做斷詞或分句，不要呼叫 OpenAI API，不要重建 CBDB。

完成後執行：

```bash
python src/main.py --input data/input/sample.txt
```
