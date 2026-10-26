---
title: Instruction Synchronization
tags:
  - guide
  - instructions
  - synchronization
status: active
---

# 指針の正本とワークスペースコピーを同期する

## 対象と正本

このリポジトリの `AGENTS.md` を Git 管理する正本、親の Toolkit 直下の `AGENTS.md` を同期コピーとする。同期するのはこの2ファイルだけであり、開発フォルダのさらに上位や Codex の個人設定を変更しない。

汎用的には「版管理する正本」と「ツールが読む配置」を分けるための方式である。全文コピーを独立に育てず、方向を明示して反映する。更新時刻から新しい方を自動選択せず、内容を比較する。別々の役割や権限範囲を持つ指針は、同じ内容へ同期しない。

## 必要環境

Python 3.11 以降。外部 Python パッケージは不要。Windows のラッパーは PowerShell 7 を使う。従来の PowerShell 版を使っていた環境にも Python が必要になる。

## macOS / Linux

```sh
# 確認のみ。差分または欠落があれば終了コード1
python3 scripts/sync-agents.py --mode Check

# 正本から反映する前に変更予定を確認
python3 scripts/sync-agents.py --mode RepoToWorkspace --dry-run
python3 scripts/sync-agents.py --mode RepoToWorkspace

# コピーを先に編集した場合だけ、正本へ取り込む
python3 scripts/sync-agents.py --mode WorkspaceToRepo
```

同じ引数を `sh scripts/sync-agents.sh` へ渡してもよい。ラッパーは呼び出し元のカレントディレクトリに依存しない。

## Windows

```powershell
./scripts/sync-agents.ps1 -Mode Check
./scripts/sync-agents.ps1 -Mode RepoToWorkspace -DryRun
./scripts/sync-agents.ps1 -Mode RepoToWorkspace
./scripts/sync-agents.ps1 -Mode WorkspaceToRepo
```

親ディレクトリ名が Toolkit でない配置では、確認・書込とも停止する。対象を理解している場合だけ Python の `--workspace-root` または PowerShell の `-WorkspaceRoot` で既存の対象ディレクトリを明示する。任意のディレクトリから呼び出す場合は、スクリプトのパスも指定する。

## 競合と復旧

- Check と dry-run はファイル・ディレクトリ・バックアップを作らない。
- UTF-8 の元バイトを保持し、SHA-256 で比較する。LF/CRLF の違いも差分になる。
- 内容が異なる既存ファイルは、同じ場所へ一意な名前の `.bak` を退避してから一時ファイル経由で置き換える。同じ内容なら書き込まない。
- 不在のコピーは書込モードで作れる。存在する空・不正な UTF-8 のファイルや、symlink・hardlink は拒否する。
- 正本とコピーを同じ実ファイルへ指定しない。書込直前に観測できた変更も拒否する。
- 同時編集を排他制御する仕組みではない。反映前に編集を止め、差分を確認する。
- 逆方向の取り込み後は正本の差分をレビューする。復旧するときもバックアップを別途確認し、内容を選んで反映する。

バックアップはコミット対象にしない。同期はローカル操作だけを行い、commit、push、スケジュール登録は行わない。

## 適用範囲は別に確認する

バイトが揃うことと、エージェントが指針を読み込むことは別である。Codex は起動時に指針を収集し、プロジェクトルートや個別の override によって適用範囲が変わる。子の Git リポジトリから開始した場合、親 Toolkit の指針を自動継承すると決めつけない。[公式の適用規則](https://learn.chatgpt.com/docs/agent-configuration/agents-md)と、実際に読み込まれた指針を確認する。

[文書システム](document-system.md)、[ソース台帳](../catalog/SOURCES.md)の SRC-009 を参照する。
