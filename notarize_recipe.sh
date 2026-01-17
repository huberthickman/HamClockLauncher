# A simple recipe of creating the binaries.
# For arm binaries do the following :
# cd to dist
ditto -c -k --sequesterRsrc --keepParent HamClockLauncher.app HamClockLauncher.app.zip
xcrun notarytool submit HamClockLauncher.app.zip --keychain-profile "your_keychain_key" --wait
rm HamClockLauncher.app.zip

#if successful
xcrun stapler staple "HamClockLauncher.app"
#if not successful
# xcrun notarytool log  <log_id >--keychain-profile "your_keychain_key" output.log

cd ..
rm HamClockLauncher.dmg
ln -s /Applications ./dist/
hdiutil create HamClockLauncher.dmg -volname HamClockLauncher -srcfolder ./dist/
xcrun notarytool submit HamClockLauncher.dmg --keychain-profile "your_keychain_key" --wait

xcrun stapler staple "HamClockLauncher.dmg"

# For intel do the follwing (this is overkill, but works if all python ops (e.g. pip , python , etc are prefixed with arch -x86_64) :
# cd to dist
arch -x86_64 ditto -c -k --sequesterRsrc --keepParent HamClockLauncher.app HamClockLauncher.app.zip
arch -x86_64 xcrun notarytool submit HamClockLauncher.app.zip --keychain-profile "your_keychain_key" --wait
rm HamClockLauncher.app.zip

#if successful
arch -x86_64 xcrun stapler staple "HamClockLauncher.app"
#if not successful
# xcrun notarytool log  <log_id >--keychain-profile "your_keychain_key" output.log

cd ..
rm HamClockLauncherIntel.dmg
ln -s /Applications ./dist/
arch -x86_64 hdiutil create HamClockLauncherIntel.dmg -volname HamClockLauncherIntel -srcfolder ./dist/
arch -x86_64 xcrun notarytool submit HamClockLauncherIntel.dmg --keychain-profile "your_keychain_key" --wait

arch -x86_64 xcrun stapler staple "HamClockLauncherIntel.dmg"

