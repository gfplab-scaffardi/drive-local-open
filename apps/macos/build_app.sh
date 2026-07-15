#!/bin/zsh
# Build / refresh macOS URL-scheme applet for Drive Local Open.
set -euo pipefail

APP="${HOME}/Applications/Drive Local Open.app"
CLI="${HOME}/.local/bin/drive-local-open"

if [[ ! -x "$CLI" ]]; then
  echo "Missing $CLI — run apps/macos/install_local.sh first" >&2
  exit 1
fi

mkdir -p "${HOME}/Applications"
rm -rf "$APP"

osacompile -s -o "$APP" <<'APPLESCRIPT'
on decodeURL(theURL)
	if theURL does not contain "url=" then return theURL
	set AppleScript's text item delimiters to {"url="}
	set u to item 2 of (text items of theURL)
	set AppleScript's text item delimiters to {"&"}
	set u to item 1 of (text items of u)
	set AppleScript's text item delimiters to {""}
	return do shell script "/usr/bin/python3 -c 'import sys,urllib.parse; print(urllib.parse.unquote(sys.argv[1]))' " & quoted form of u
end decodeURL

on chromeURL()
	tell application "Google Chrome"
		if (count of windows) is 0 then return ""
		return URL of active tab of front window
	end tell
end chromeURL

on runOpen(theURL)
	set cmd to (POSIX path of (path to home folder)) & ".local/bin/drive-local-open --open files --no-notify "
	if theURL is not "" then set cmd to cmd & quoted form of theURL
	do shell script cmd
end runOpen

on processURL(theURL)
	try
		if theURL is "" then error "Chrome の Drive タブで実行するか、ブックマークレットを使ってください。"
		runOpen(theURL)
	on error errMsg
		display alert "Drive Local Open" message errMsg as critical
	end try
end processURL

on idle
	return 60
end idle

on run
	processURL(chromeURL())
end run

on open location theURL
	processURL(decodeURL(theURL))
end open location
APPLESCRIPT

INFO="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.is3.DriveLocalOpen" "$INFO" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.is3.DriveLocalOpen" "$INFO"
/usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string Drive Local Open" "$INFO" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName Drive Local Open" "$INFO"
/usr/libexec/PlistBuddy -c "Set :CFBundleName Drive Local Open" "$INFO" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Delete :CFBundleURLTypes" "$INFO" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes array" "$INFO"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0 dict" "$INFO"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLName string Drive Local Open" "$INFO"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" "$INFO"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string drive-local-open" "$INFO"

xattr -cr "$APP"
codesign --force --deep -s - "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
echo "Built: $APP"
echo "Scheme: drive-local-open://open?url=..."
