# DeckLite 使用與建置

這是 Tiny Container 的非官方修改版：在 Android 的 PRoot 容器內運行
Debian 13（Trixie）ARM64 與 XFCE 桌面，不是 SteamOS，也不會替換 Android。

容器預裝原生 ARM64 Steam、Hangover 11.16、GE-Proton、Wine Manager，並整合
X11 輸入／顯示、音效、MIDI、全螢幕和 CPU 選擇等修正。不能保證所有 Windows
遊戲、反作弊或顯示晶片都相容，也不是保證任何遊戲達到特定 FPS。

目前版本基準是 APK 4.4.1／容器 4.3.4。最新介面採緊湊排版，Run EXE / MSI
以醒目主按鈕顯示；小螢幕下可捲動，最大化和檔案選擇視窗底部按鈕可操作。

## 下載與匯入

從 [DeckLite Release](https://github.com/Stavlysa/DeckLite/releases/tag/v4.4.1)
下載獨立 APK，以及完整容器的 `.7z.001` 和 `.7z.002` 兩卷。把兩卷放在同一
資料夾，以 ZArchiver 或 7-Zip 開啟 `.001` 解出 `.tar.zst`。安裝 APK 後，在
容器管理頁右上角選擇「匯入新容器」，選取 `.tar.zst`，完成後啟動桌面。

下載、重組後建議仍保留至少 22 GiB 空間供匯入。容器約 2.62 GB 壓縮、13.78 GB
解壓後 tar；分卷不改變原完整容器內容。這次發行不使用刪減版，也不內嵌於 APK。
詳細操作與校驗碼見 Release 說明。

## 語言與安全預設

App 和 Wine Manager 支援英語、繁體中文、簡體中文、日語與俄語。Wine 的
Windows 語言與管理介面分開，預設英語；時區預設 UTC+00:00。
Debugging 預設關閉；啟用後需另外配對公鑰才可使用本機 USB SSH。

本原始碼不包含個人簽章私鑰、SSH 私鑰、Steam 帳號、手機日誌、遊戲或存檔。
不要把整個開發工作區、cache、diagnostics 或個人容器匯出檔拖進 GitHub。

## 建置

準備 JDK 21、Android SDK 37、CMake 和相容 NDK。設定自己的 ANDROID_HOME
或 local.properties；修改過的 X11 模組已放在 third_party，不需要旁邊另有專案。

Windows 執行 `gradlew.bat :app:assembleRelease :app:testDebugUnitTest :app:lintVitalRelease`；
Linux 使用 `bash gradlew` 加上相同參數。發行組態不可除錯，但目前沿用本機
Android 開發簽章；不附維護者私鑰，因此自行建置的 APK 不一定能覆蓋既有 APK。

建好的普通 APK 不內含容器。若自行製作內嵌版本，可依
[完整建置說明](DECKLITE.md) 使用乾淨 rootfs 進行內嵌、對齊、簽章和校驗，
並選擇可接收較大檔案的下載服務。APK 覆蓋更新不會取代已匯入的容器。

GitHub 原始碼和 APK／容器下載是不同項目；fork 或上傳原始碼不代表安裝包
已發布。不要把上游 Tiny Container 的 Release 誤認為包含本修改版。
