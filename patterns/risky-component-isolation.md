---
title: Risky Component Isolation
tags:
  - pattern
  - architecture
  - reliability
status: active
---

# 不安定なコンポーネントの隔離

## 使う条件

第三者 plugin、未知の parser、native module、driver、外部 process など、crash、hang、過大入力、real-time deadline 違反を起こし得る部品を組み込むときに使う。

## 境界

責任を次の面へ分ける。

- `control plane`: UI、設定、状態保存、route 構成、worker 監視
- `discovery worker`: scan、metadata 取得、互換性検査
- `processing worker`: 実データ処理
- `I/O backend`: device、transport、buffer、timestamp

未知の module を control plane へ直接 load しない。scan と processing は crash し得る処理として隔離し、timeout、heartbeat、quarantine、失敗理由を持たせる。process 分離は完全な security sandbox と同義ではないので、その限界も記す。

## Real-time 経路

処理開始前に buffer と metric 領域を確保する。deadline がある thread では allocation、file I/O、logging、UI、blocking lock、再構成を行わない。構成変更要求は control plane へ通知し、安全に停止・無音化してから作り直す。

失敗時に壊れた出力を流さず、silent output、route stop、直前の既知良好状態など明示した方針へ遷移する。同じ crash を無限に自動再試行しない。

## 指標を分ける

次を一つの「遅延」や「性能」へ潰さない。

- コンポーネントが宣言する algorithmic latency
- 各処理の CPU time と deadline miss
- transport、buffer、queue の滞留
- 入力から利用者が観測する出力までの end-to-end latency

比較では backend、period、buffer 条件をそろえ、component を呼ばない hard bypass を用意する。component 自身の bypass parameter と hard bypass は別である。

## 使わない条件

信頼できる純粋関数を同期的に呼ぶだけで、crash domain や deadline を分ける必要がない場合は、process 分離の複雑さを持ち込まない。

## 確認方法

- scan、processing、UI のどれかが落ちても他を巻き込まない。
- hang を有限時間で検知し、安全に停止できる。
- dynamic reconfiguration を処理 thread 内で行わない。
- microbenchmark と end-to-end の結果を別々に報告する。
