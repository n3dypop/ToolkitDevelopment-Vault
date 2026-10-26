# [対象] の検証

## 対象と基準版

- 対象: [artifact]
- 版・fingerprint: [識別方法]
- 環境: [OS、runtime、device 等]
- 実行日: [日付が意味を持つ場合]

## Claim matrix

| Claim | Conditions | Evidence | Level | Result | Remaining uncertainty |
| --- | --- | --- | --- | --- | --- |
| [主張] | [条件] | [手順・観測] | [static/local/runtime/end-to-end] | [pass/fail/not-run] | [まだ言えないこと] |

## 今回実行した検証

```text
[command または操作]
```

[観測結果と artifact を書く。秘密情報や原本は貼らない。]

## 比較する場合

- 同等性の契約: [比較する出力・除外する診断と理由]
- 基準版と候補版: [入力・ソース・依存・ビルド条件の識別方法]
- 測定区間: [含む処理と含まない処理]
- 集計: [ウォームアップ・反復・実行順・指標・生サンプル]
- 悪化・不採用・ばらつき: [該当条件と判断]

[比較しない変更なら、この節を削除する。]

## 継承した結果

[過去結果を使う場合、基準版と今回再実行していないことを明記する。]

## 失敗と切り分け

| Failure | Reproduction | Cause or hypothesis | Next falsifiable check |
| --- | --- | --- | --- |
| [失敗] | [再現] | [原因または仮説] | [次の確認] |

## 未実行・対象外

- [未実行の検証、理由、残るリスク]

## 結論

[確認できた範囲だけを要約する。]
