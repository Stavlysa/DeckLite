"""Wine Manager UI language only; never changes Wine locale or process environment."""
from __future__ import annotations

import os
from pathlib import Path

LANGUAGES = {
    "en": "English",
    "zh_TW": "繁體中文",
    "zh_CN": "简体中文",
    "ja": "日本語",
    "ru": "Русский",
}
TRANSLATION_COLUMNS = {code: index for index, code in enumerate(LANGUAGES) if code != "en"}
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "decklite/wine-manager-language"

# English message IDs, followed by Traditional Chinese, Simplified Chinese,
# Japanese and Russian. Technical identifiers and diagnostic paths stay intact.
CATALOG = {
    "Hangover 11.16 · Win32 + Win64 on ARM64": ("Hangover 11.16 · 在 ARM64 執行 Win32 + Win64", "Hangover 11.16 · 在 ARM64 运行 Win32 + Win64", "Hangover 11.16 · ARM64 で Win32 + Win64 を実行", "Hangover 11.16 · Win32 + Win64 на ARM64"),
    "DeckLite Wine Manager": ("DeckLite Wine 管理員", "DeckLite Wine 管理器", "DeckLite Wine マネージャー", "Менеджер Wine DeckLite"),
    "Interface language": ("介面語言", "界面语言", "表示言語", "Язык интерфейса"),
    "Changes this manager only; Windows language is configured separately.": ("僅變更管理介面；Windows 語言另行設定。", "仅更改管理界面；Windows 语言单独设置。", "この管理画面のみ変更します。Windows の言語は別に設定します。", "Меняется только интерфейс менеджера. Язык Windows задаётся отдельно."),
    "Wine prefix": ("Wine 環境", "Wine 环境", "Wine プレフィックス", "Префикс Wine"),
    "New prefix": ("新增環境", "新建环境", "新規作成", "Новый префикс"),
    "32-bit backend": ("32 位元執行後端", "32 位执行后端", "32 ビット実行方式", "Движок 32-битных приложений"),
    "Automatic (FEX compatibility)": ("自動（FEX 相容模式）", "自动（FEX 兼容模式）", "自動（FEX 互換モード）", "Автоматически (совместимость FEX)"),
    "Game display": ("遊戲顯示模式", "游戏显示模式", "ゲームの表示モード", "Режим экрана игры"),
    "Automatic: fullscreen or windowed as selected in the game": ("自動：依遊戲設定顯示全螢幕或窗口", "自动：按照游戏设置显示全屏或窗口", "自動：ゲームの全画面／ウィンドウ設定に従う", "Автоматически: по настройкам экрана в игре"),
    "Safe virtual desktop (compatibility fallback)": ("安全虛擬桌面（相容性後備）", "安全虚拟桌面（兼容性后备）", "安全な仮想デスクトップ（互換性優先）", "Безопасный виртуальный рабочий стол"),
    "Borderless fullscreen (set game to Windowed)": ("無邊框全螢幕（遊戲需設為窗口）", "无边框全屏（游戏需设为窗口）", "ボーダーレス全画面（ゲームをウィンドウに設定）", "Безрамочный экран (в игре выбрать оконный режим)"),
    "Native fullscreen (can black-screen old games)": ("原生全螢幕（舊遊戲可能黑屏）", "原生全屏（旧游戏可能黑屏）", "ネイティブ全画面（古いゲームは黒画面になる場合あり）", "Нативный полный экран (возможен чёрный экран)"),
    "Windows language": ("Windows 環境語言", "Windows 环境语言", "Windows 環境の言語", "Язык среды Windows"),
    "Time zone (UTC)": ("時區（UTC）", "时区（UTC）", "タイムゾーン（UTC）", "Часовой пояс (UTC)"),
    "UTC+00:00 (GMT / Greenwich)": ("UTC+00:00（GMT／格林威治時間）", "UTC+00:00（GMT／格林尼治时间）", "UTC+00:00（GMT／グリニッジ標準時）", "UTC+00:00 (GMT / по Гринвичу)"),
    "Interface, Windows language and time zone are independent. Restart Wine apps after changing Windows language or time zone. UTC offsets are fixed (no daylight saving).": ("介面、Windows 語言與時區分開設定。變更 Windows 語言或時區後，請關閉並重開 Wine 程式。UTC 時差固定，不使用夏令時間。", "界面、Windows 语言与时区独立设置。更改 Windows 语言或时区后，请关闭并重新打开 Wine 程序。UTC 时差固定，不使用夏令时。", "表示言語・Windows の言語・時刻設定は独立しています。Windows の言語や時刻設定を変更した後は Wine アプリを再起動してください。UTC オフセットは固定で、夏時間は適用しません。", "Язык интерфейса, язык Windows и часовой пояс независимы. После смены языка Windows или часового пояса перезапустите приложения Wine. Смещение UTC фиксированное, без летнего времени."),
    "Could not save time zone: {error}": ("無法儲存時區：{error}", "无法保存时区：{error}", "タイムゾーンを保存できません：{error}", "Не удалось сохранить часовой пояс: {error}"),
    "Wine time zone saved: {zone}. Close all Wine apps and reopen them to apply.": ("已儲存 Wine 時區：{zone}。關閉所有 Wine 程式並重開後套用。", "已保存 Wine 时区：{zone}。关闭所有 Wine 程序并重新打开后生效。", "Wine のタイムゾーンを保存：{zone}。すべての Wine アプリを終了して再起動すると適用されます。", "Часовой пояс Wine сохранён: {zone}. Закройте все приложения Wine и откройте их заново."),
    "Traditional Chinese": ("繁體中文", "繁体中文", "中国語（繁体字）", "Китайский (традиционный)"),
    "Simplified Chinese": ("簡體中文", "简体中文", "中国語（簡体字）", "Китайский (упрощённый)"),
    "Japanese": ("日文", "日语", "日本語", "Японский"),
    "Russian": ("俄文", "俄语", "ロシア語", "Русский"),
    "English": ("英文", "英语", "英語", "Английский"),
    "CPU cores": ("CPU 核心", "CPU 核心", "CPU コア", "Ядра CPU"),
    "Choose CPU cores…": ("選擇 CPU 核心…", "选择 CPU 核心…", "CPU コアを選択…", "Выбрать ядра CPU…"),
    "Run EXE / MSI": ("執行 EXE / MSI", "运行 EXE / MSI", "EXE / MSI を実行", "Запустить EXE / MSI"),
    "Wine configuration": ("Wine 設定", "Wine 设置", "Wine 設定", "Настройки Wine"),
    "Registry editor": ("登錄編輯器", "注册表编辑器", "レジストリエディター", "Редактор реестра"),
    "Uninstall programs": ("解除安裝程式", "卸载程序", "プログラムの削除", "Удаление программ"),
    "Windows file manager": ("Windows 檔案管理員", "Windows 文件管理器", "Windows ファイル管理", "Файловый менеджер Windows"),
    "Open drive C": ("開啟 C 槽", "打开 C 盘", "C ドライブを開く", "Открыть диск C"),
    "Enable / refresh DXVK": ("啟用／更新 DXVK", "启用／更新 DXVK", "DXVK を有効化／更新", "Включить / обновить DXVK"),
    "Disable DXVK": ("停用 DXVK", "禁用 DXVK", "DXVK を無効化", "Отключить DXVK"),
    "Install common game runtimes": ("安裝常用遊戲執行庫", "安装常用游戏运行库", "一般的なゲームランタイムを導入", "Установить игровые библиотеки"),
    "Install legacy audio / video": ("安裝舊版音訊／視訊元件", "安装旧版音频／视频组件", "旧式の音声／映像ライブラリを導入", "Установить старые аудио/видеокомпоненты"),
    "Install .NET 4.8 + XNA 4": ("安裝 .NET 4.8 + XNA 4", "安装 .NET 4.8 + XNA 4", ".NET 4.8 + XNA 4 を導入", "Установить .NET 4.8 + XNA 4"),
    "Stop Wine processes": ("停止 Wine 程序", "停止 Wine 进程", "Wine プロセスを停止", "Остановить процессы Wine"),
    "Refresh status": ("重新整理狀態", "刷新状态", "状態を更新", "Обновить состояние"),
    "Activity": ("活動紀錄", "活动记录", "実行ログ", "Журнал действий"),
    "Interface language saved.": ("已儲存介面語言。", "已保存界面语言。", "表示言語を保存しました。", "Язык интерфейса сохранён."),
    "Could not save interface language: {error}": ("無法儲存介面語言：{error}", "无法保存界面语言：{error}", "表示言語を保存できません：{error}", "Не удалось сохранить язык интерфейса: {error}"),
    "Global game display mode saved: {mode}": ("已儲存全域遊戲顯示模式：{mode}", "已保存全局游戏显示模式：{mode}", "全体のゲーム表示モードを保存：{mode}", "Общий режим экрана сохранён: {mode}"),
    "Global Windows language saved: {locale}": ("已儲存全域 Windows 語言：{locale}", "已保存全局 Windows 语言：{locale}", "全体の Windows 言語を保存：{locale}", "Общий язык Windows сохранён: {locale}"),
    "Default (~/.wine)": ("預設（~/.wine）", "默认（~/.wine）", "既定（~/.wine）", "По умолчанию (~/.wine)"),
    "Wine CPU cores": ("Wine CPU 核心", "Wine CPU 核心", "Wine の CPU コア", "Ядра CPU для Wine"),
    "Cancel": ("取消", "取消", "キャンセル", "Отмена"),
    "Save": ("儲存", "保存", "保存", "Сохранить"),
    "Open": ("開啟", "打开", "開く", "Открыть"),
    "Create": ("建立", "创建", "作成", "Создать"),
    "OK": ("確定", "确定", "OK", "ОК"),
    "Automatic: all big + prime cores": ("自動：所有大核＋超大核", "自动：所有大核＋超大核", "自動：すべての大コア＋プライムコア", "Автоматически: все большие и сверхбольшие ядра"),
    "All available cores": ("所有可用核心", "所有可用核心", "利用可能な全コア", "Все доступные ядра"),
    "Custom: tick cores below": ("自訂：勾選下方核心", "自定义：勾选下方核心", "カスタム：以下のコアを選択", "Вручную: отметьте ядра ниже"),
    "Applies to every Wine prefix. Save, close all Wine apps, then restart the container.": ("套用至所有 Wine 環境。儲存後，關閉所有 Wine 程式並重啟容器。", "适用于所有 Wine 环境。保存后，关闭所有 Wine 程序并重启容器。", "すべての Wine 環境に適用します。保存後、Wine アプリを終了してコンテナを再起動してください。", "Для всех префиксов Wine. Сохраните, закройте приложения Wine и перезапустите контейнер."),
    "Big/prime cores detected automatically.": ("已自動辨識大核與超大核。", "已自动识别大核与超大核。", "大コアとプライムコアを自動検出しました。", "Большие и сверхбольшие ядра определены автоматически."),
    "Cannot distinguish core tiers; Automatic uses available cores.": ("無法辨識核心類型；自動模式使用可用核心。", "无法识别核心类型；自动模式使用可用核心。", "コアの種類を判別できません。自動モードでは利用可能なコアを使います。", "Типы ядер не определены. Автоматический режим использует доступные ядра."),
    "big/prime": ("大核／超大核", "大核／超大核", "大／プライム", "большое/сверхбольшое"),
    " · max {frequency:.2f} GHz": (" · 最高 {frequency:.2f} GHz", " · 最高 {frequency:.2f} GHz", " · 最大 {frequency:.2f} GHz", " · макс. {frequency:.2f} ГГц"),
    " · unavailable": (" · 系統未開放", " · 系统未开放", " · 利用不可", " · недоступно"),
    "Select at least one available CPU.": ("請至少勾選一個可用核心。", "请至少勾选一个可用核心。", "利用可能な CPU を一つ以上選択してください。", "Выберите хотя бы одно доступное ядро CPU."),
    "Could not save CPU settings: {error}": ("無法儲存 CPU 設定：{error}", "无法保存 CPU 设置：{error}", "CPU 設定を保存できません：{error}", "Не удалось сохранить настройки CPU: {error}"),
    "Global CPU policy saved: {mode}; cores {cores}. Close all Wine apps and restart the container to apply.": ("已儲存全域 CPU 策略：{mode}；核心 {cores}。關閉所有 Wine 程式並重啟容器後套用。", "已保存全局 CPU 策略：{mode}；核心 {cores}。关闭所有 Wine 程序并重启容器后生效。", "CPU 方針を保存：{mode}、コア {cores}。Wine アプリを終了し、コンテナを再起動すると適用されます。", "Настройки CPU сохранены: {mode}; ядра {cores}. Закройте Wine и перезапустите контейнер."),
    "No Wine prefix is selected": ("尚未選擇 Wine 環境", "尚未选择 Wine 环境", "Wine プレフィックスが未選択です", "Префикс Wine не выбран"),
    "Started {label} in {prefix} (PID {pid})": ("已在 {prefix} 啟動 {label}（PID {pid}）", "已在 {prefix} 启动 {label}（PID {pid}）", "{prefix} で {label} を起動（PID {pid}）", "Запущено {label} в {prefix} (PID {pid})"),
    "Running {label}. Detailed log: {path}": ("正在執行 {label}。詳細紀錄：{path}", "正在运行 {label}。详细日志：{path}", "{label} を実行中。詳細ログ：{path}", "Выполняется {label}. Подробный журнал: {path}"),
    "Game runtimes ({profile})": ("遊戲執行庫（{profile}）", "游戏运行库（{profile}）", "ゲームランタイム（{profile}）", "Игровые библиотеки ({profile})"),
    "Choose a Windows program": ("選擇 Windows 程式", "选择 Windows 程序", "Windows プログラムを選択", "Выберите программу Windows"),
    "Windows programs (*.exe, *.msi)": ("Windows 程式（*.exe、*.msi）", "Windows 程序（*.exe、*.msi）", "Windows プログラム（*.exe、*.msi）", "Программы Windows (*.exe, *.msi)"),
    "All files": ("所有檔案", "所有文件", "すべてのファイル", "Все файлы"),
    "Create Wine prefix": ("建立 Wine 環境", "创建 Wine 环境", "Wine プレフィックスを作成", "Создать префикс Wine"),
    "Example: game-name": ("例如：game-name", "例如：game-name", "例：game-name", "Пример: game-name"),
    "Game Complete (VC++/DirectX/audio; recommended)": ("完整遊戲環境（VC++／DirectX／音訊；建議）", "完整游戏环境（VC++／DirectX／音频；推荐）", "ゲーム完全版（VC++／DirectX／音声、推奨）", "Игровой набор (VC++/DirectX/аудио; рекомендуется)"),
    ".NET/XNA Complete (separate compatibility template)": ("完整 .NET/XNA 環境（獨立相容模板）", "完整 .NET/XNA 环境（独立兼容模板）", ".NET/XNA 完全版（独立した互換テンプレート）", ".NET/XNA (отдельный шаблон совместимости)"),
    "Clean Hangover prefix": ("乾淨 Hangover 環境", "干净 Hangover 环境", "追加構成なしの Hangover 環境", "Чистый префикс Hangover"),
    "Prefix name (letters, numbers, dot, dash or underscore)": ("環境名稱（英文字母、數字、點、連字號或底線）", "环境名称（英文字母、数字、点、连字符或下划线）", "環境名（英数字、ピリオド、ハイフン、アンダースコア）", "Имя (латиница, цифры, точка, дефис или подчёркивание)"),
    "Offline template": ("離線模板", "离线模板", "オフラインテンプレート", "Офлайн-шаблон"),
    "Invalid prefix name": ("環境名稱無效", "环境名称无效", "環境名が無効です", "Недопустимое имя префикса"),
    "Initialize {name}": ("初始化 {name}", "初始化 {name}", "{name} を初期化", "Инициализация {name}"),
    "Stopped Wine processes in {prefix}": ("已停止 {prefix} 的 Wine 程序", "已停止 {prefix} 的 Wine 进程", "{prefix} の Wine プロセスを停止しました", "Процессы Wine в {prefix} остановлены"),
    "installed": ("已安裝", "已安装", "導入済み", "установлен"),
    "missing": ("未安裝", "未安装", "未導入", "не установлен"),
    "ready": ("就緒", "就绪", "準備完了", "готов"),
    "not initialized": ("未初始化", "未初始化", "未初期化", "не инициализирован"),
    "enabled": ("已啟用", "已启用", "有効", "включён"),
    "disabled": ("已停用", "已禁用", "無効", "отключён"),
    "not added": ("未加入", "未添加", "未追加", "не добавлены"),
    "custom": ("自訂", "自定义", "カスタム", "свой"),
    "Hangover: {installed} · Prefix: {ready} · Template: {template} · DXVK: {dxvk} · Runtimes: {runtimes} · Global display: {display} · CPU policy: {cpu} · Windows language: {locale}": ("Hangover：{installed} · 環境：{ready} · 模板：{template} · DXVK：{dxvk} · 執行庫：{runtimes} · 全域顯示：{display} · CPU 策略：{cpu} · Windows 語言：{locale}", "Hangover：{installed} · 环境：{ready} · 模板：{template} · DXVK：{dxvk} · 运行库：{runtimes} · 全局显示：{display} · CPU 策略：{cpu} · Windows 语言：{locale}", "Hangover：{installed} · 環境：{ready} · テンプレート：{template} · DXVK：{dxvk} · ランタイム：{runtimes} · 全体の表示：{display} · CPU 方針：{cpu} · Windows 言語：{locale}", "Hangover: {installed} · Префикс: {ready} · Шаблон: {template} · DXVK: {dxvk} · Библиотеки: {runtimes} · Экран: {display} · CPU: {cpu} · Язык Windows: {locale}"),
}


def load_language(path: Path = CONFIG_FILE) -> str:
    try:
        value = path.read_text(encoding="ascii").strip()
        return value if value in LANGUAGES else "en"
    except (OSError, UnicodeError):
        return "en"


def save_language(value: str, path: Path = CONFIG_FILE) -> None:
    if value not in LANGUAGES:
        raise ValueError("Unsupported interface language")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value + "\n", encoding="ascii")
    temporary.replace(path)


def translate(language: str, message: str, **values: object) -> str:
    column = TRANSLATION_COLUMNS.get(language)
    rendered = CATALOG[message][column - 1] if column and message in CATALOG else message
    return rendered.format(**values) if values else rendered
