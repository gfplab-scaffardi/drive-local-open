# Drive Local Open

Chrome で開いている Google ドライブのフォルダを、PC 内の同期済みパスとして **Finder / エクスプローラー**（任意でターミナル）で開く無料ツールです。

- データは PC 内の Google Drive for Desktop のみ参照（I-S3 サーバへ Drive 内容は送りません）
- 公式案内: https://www.i-s3.com/tools/drive-local-open.html

## 要件

- Google Drive for Desktop（サインイン済み）
- Python 3.10+
- macOS または Windows

## インストール（開発）

```bash
cd /Users/suomi/I-S3HP/drive-local-open
./apps/macos/install_local.sh   # macOS: CLI + URL scheme app
# Windows: apps\windows\register_protocol.bat
drive-local-open --help
```

公開案内ページ（I-S3 サイト）: `../i-s3home/htdocs/tools/drive-local-open.html` → https://www.i-s3.com/tools/drive-local-open.html

## 使い方

```bash
# Finder / Explorer で開く（既定）
drive-local-open 'https://drive.google.com/drive/folders/XXXX'

# パスだけ表示
drive-local-open --print-only 'https://drive.google.com/drive/u/0/my-drive'

# ターミナルも開く（2行の任意リンクを表示）
drive-local-open --open both 'https://drive.google.com/drive/folders/XXXX'

# 通知・プロモ抑制
DRIVE_LOCAL_OPEN_QUIET=1 drive-local-open --open files URL
```

## ブックマークレット

案内ページのボタンを Chrome のブックマークバーへドラッグしてください。

## テスト

```bash
python3 -m unittest discover -s tests -v
```
