# ToolkitDevelopment-Vault

Reusable development guides, patterns, and templates distilled from Toolkit projects.

ToolkitDevelopment-Vault は、Toolkit Development に属する文書プロジェクトです。Toolkit 配下にある複数プロジェクトの `AGENTS.md`、`DESIGN.md`、検証記録、引継ぎ文書から、再利用できる判断基準と文書テンプレートを抽出します。リポジトリ全体を Obsidian Vault として開けますが、標準 Markdown のリンクだけを使うため GitHub でも読めます。

## 収録するもの

- 複数の案件で再利用できる指示設計、設計記録、検証、引継ぎの方法
- 適用条件、失敗条件、検証レベルが明示された実務パターン
- 新規プロジェクトへコピーして具体化できるテンプレート
- 抽出元を匿名化して追跡するソース台帳

生の作業ログ、秘密情報、絶対パス、顧客・端末固有情報、第三者著作物、案件固有の数値やハッシュは収録しません。元文書の保管庫ではなく、そこから得た再利用可能な知識の保管庫です。

## 読み始める

- [HOME.md](HOME.md): Obsidian 用の入口
- [DESIGN.md](DESIGN.md): この Vault 自体の設計
- [文書システム](guides/document-system.md): 文書種別の使い分け
- [証拠と検証](guides/evidence-and-validation.md): 主張を検証結果へ結び付ける方法
- [テンプレート一覧](templates/README.md): 新規文書の雛形

## 保守

同期は macOS/Linux の Shell、または Windows の PowerShell 7 だけで動作し、Python は不要です。以下の文書検査と回帰テストを実行する保守担当者だけが Python を使用します。

Python 3.11 以降で次を実行すると、リンク、見出し、端末固有の絶対パス、末尾空白、HOME から active 文書への到達性を確認できます。外部 Python パッケージは不要です。

```sh
python3 scripts/check-vault.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Windows では PowerShell 7 の `./scripts/check-vault.ps1` も同じ検査を呼び出します。GitHub Actions は Windows / macOS / Linux で文書検査と回帰テストを行います。

### Toolkit の `AGENTS.md` と同期する

正本はこのリポジトリ直下の `AGENTS.md`、コピーは親 Toolkit 直下の同名ファイルです。対象はこの2ファイルだけです。

```sh
sh scripts/sync-agents.sh --mode Check
sh scripts/sync-agents.sh --mode RepoToWorkspace --dry-run
sh scripts/sync-agents.sh --mode RepoToWorkspace
```

コピーを先に編集した場合は `--mode WorkspaceToRepo` で取り込み、差分をレビューします。Windows の `scripts/sync-agents.ps1` は従来の `-Mode` と `-WorkspaceRoot` を維持します。別配置、バックアップ、復旧、指針の適用範囲は[同期手順](guides/instruction-synchronization.md)を参照してください。

## ライセンス

[MIT License](LICENSE)。案件固有の元文書や第三者資料には、それぞれの権利条件が引き続き適用されます。
