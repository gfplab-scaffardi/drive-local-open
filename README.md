# Drive Local Open

Chrome で開いている Google ドライブのフォルダを、PC 内の同期済みパスとして **Finder / エクスプローラー**（任意でターミナル）で開く無料ツールです。

- データは PC 内の Google Drive for Desktop のみ参照（I-S3 サーバへ Drive 内容は送りません）
- 公式案内: https://www.i-s3.com/tools/drive-local-open.html
- ソース: https://github.com/suomimasuda/drive-local-open
- 配布: https://github.com/suomimasuda/drive-local-open/releases/latest

## インストール（おすすめ）

### macOS

1. [DriveLocalOpen-0.2.0.dmg](https://github.com/suomimasuda/drive-local-open/releases/latest) を開く
2. `Drive Local Open.app` を Applications へドラッグ
3. 案内ページのブックマークレットを追加

未署名ビルドの初回だけ、右クリック → 「開く」が必要な場合があります（[署名手順](docs/macos-signing.md)）。

### Windows

1. [DriveLocalOpen-Setup-0.2.0.exe](https://github.com/suomimasuda/drive-local-open/releases/latest) を実行
2. スマートスクリーンが出たら「詳細情報」→「実行」
3. 案内ページのブックマークレットを追加

## 要件

- Google Drive for Desktop（サインイン済み）
- macOS または Windows（開発ビルドは Python 3.10+）

## インストール（開発・ソース）

```bash
git clone https://github.com/suomimasuda/drive-local-open.git
cd drive-local-open

# macOS: CLI + URL scheme app（開発）
./apps/macos/install_local.sh

# Windows: プロトコル登録（開発）
apps\windows\register_protocol.bat

# 配布用バイナリ生成
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
./packaging/macos/build_dmg.sh          # → dist/DriveLocalOpen-*.dmg
./scripts/make_dist_zip.sh              # → dist/drive-local-open-*.zip
```

## 使い方

```bash
# Finder / Explorer で開く（既定）
drive-local-open 'https://drive.google.com/drive/folders/XXXX'

# パスだけ表示
drive-local-open --print-only 'https://drive.google.com/drive/u/0/my-drive'

# ターミナルも開く（2行の任意リンクを表示）
drive-local-open --open both 'https://drive.google.com/drive/folders/XXXX'

# 未同期時に親フォルダへフォールバックしない
drive-local-open --no-fallback-parent URL

# 通知・プロモ抑制
DRIVE_LOCAL_OPEN_QUIET=1 drive-local-open --open files URL
```

## ブックマークレット

案内ページのボタンを Chrome のブックマークバーへドラッグしてください。

## テスト

```bash
python3 -m unittest discover -s tests -v
```
