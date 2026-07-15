# Apple Developer Program / signing

Click-to-open macOS DMGs without Gatekeeper warnings require:

1. Enroll in the [Apple Developer Program](https://developer.apple.com/programs/) (paid)
2. Create a **Developer ID Application** certificate (CSR: `~/Downloads/DriveLocalOpen.certSigningRequest` if already generated)
3. Import the `.cer` into Keychain
4. Store notary credentials:

```bash
xcrun notarytool store-credentials drive-local-open-notary \
  --apple-id YOUR_APPLE_ID \
  --team-id YOUR_TEAM_ID
```

5. Rebuild:

```bash
./packaging/macos/build_dmg.sh
```

Without a Developer ID identity, `build_dmg.sh` still produces a DMG with an **ad-hoc** signature. Users open the app the first time via **右クリック → 開く**.
