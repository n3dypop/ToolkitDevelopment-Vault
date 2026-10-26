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

PowerShell 7 で次を実行すると、Markdown のリンク、見出し、絶対パス、末尾空白を確認できます。

```powershell
./scripts/check-vault.ps1
```

## ライセンス

[MIT License](LICENSE)。案件固有の元文書や第三者資料には、それぞれの権利条件が引き続き適用されます。
