---
title: Versioned Data Editing
tags:
  - pattern
  - binary
  - safety
status: active
---

# 版固定データの安全な読み書き

## 使う条件

仕様が不完全な binary、save、firmware、独自 container、版ごとに layout が変わるデータを読む・変更するときに使う。

## 読み取り契約

- 拡張子や一つの magic だけで形式を信頼しない。
- size、複数 field、不変条件、checksum、fingerprint を組み合わせて対応版を識別する。
- length、offset、加算・乗算 overflow、endianness、上限を明示する。
- 未知版、切り詰め、破損、過大入力を安全に拒否する。
- 観測した事実と field 意味の推測を分ける。

## 書き込み契約

- 対応 fingerprint と、書き込み可能な field を allowlist にする。
- 未知 byte と未対象領域をそのまま保持する。
- 原本を上書きせず、新しい出力へ書く。
- checksum や依存 field は、根拠が閉じた場合だけ再計算する。
- 出力を再読込し、変更範囲、round-trip、不変条件を検査する。
- 一部しか理解していない構造を、繰り返し文字列や見かけの規則だけで一般化しない。

## 証拠の依存閉包

field 単体ではなく、その producer、consumer、ID 対応、validation、checksum、保存経路まで追う。安全な書き込みに必要な依存が未解決なら read-only に留める。

対応表には `safe_reuse` と `unsafe_until_resolved` を分ける。タイトルや製品名が一致しても fingerprint が違えば別 profile として扱う。

## 使わない条件

公開仕様と互換性契約が十分にあり、通常の serializer が安全に処理できる形式では、この重い手順を一律に要求しない。

## 確認方法

- 対応版を一意に識別できる。
- 未知版を誤って書き換えない。
- writer が指定範囲以外を変更しない。
- 破損入力と失敗時に原本が残る。
- local、runtime、end-to-end のどこまで確認したかが分かる。
