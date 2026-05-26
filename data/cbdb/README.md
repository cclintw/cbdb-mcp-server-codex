# CBDB SQLite 放置說明

本資料夾用來放 CBDB SQLite。

本專案不附 CBDB SQLite，也不重新發布 CBDB 資料。使用者需自行依 CBDB 官方管道下載 SQLite，並建議將檔名改為：

```text
cbdb.sqlite
```

最後路徑應為：

```text
data/cbdb/cbdb.sqlite
```

若有需要，可依 CBDB 官方 `cbdb_sqlite` repo 指示執行 `scripts/create_views.sh` 建立 convenience views。若有需要，也可執行 `scripts/create_addresses_table.py` 建立 `ADDRESSES` 表。
