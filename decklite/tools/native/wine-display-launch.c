/* Shared desktop observer. No EXE matching, injected hooks, mode changes or
 * resizing. A private Wine desktop also contains a bootstrapper's descendants.
 * Keep the previous focus/borderless helper as an explicit rollback path. */
#define mainCRTStartup legacy_mainCRTStartup
#include "wine-game-launch.c"
#undef mainCRTStartup
API BOOL MoveFileExW(const WCHAR *, const WCHAR *, DWORD);
API BOOL DeleteFileW(const WCHAR *);
API BOOL IsIconic(HWND);
static WCHAR mode_path[100], pending_path[104];
static DWORD desktop_pid, observer_pid;
static unsigned int live_windows;
static RECT screen, fullscreen_rect;
static BOOL fullscreen;

static BOOL observe(HWND window, LPARAM unused) {
    DWORD pid = 0;
    RECT rect;
    (void)unused;
    GetWindowThreadProcessId(window, &pid);
    if (!pid || pid == desktop_pid || pid == observer_pid) return 1;
    ++live_windows; /* Includes a live game's hidden IME/loading windows. */
    if (!IsWindowVisible(window) || IsIconic(window) || !GetWindowRect(window, &rect)) return 1;
    if (rect.right-rect.left < 100 || rect.bottom-rect.top < 100) return 1;
    if (!candidate && IsWindowEnabled(window)) candidate = window;
    long long style = GetWindowLongPtrW(window, -16);
    // Framed/maximized/windowed games are never made fullscreen. A popup must
    // actually cover its Wine monitor, not merely have a familiar game size.
    if (!(style & 0x00c40000LL) &&
            rect.left == 0 && rect.top == 0 && rect.right == screen.right &&
            rect.bottom == screen.bottom && GetForegroundWindow() == window) {
        fullscreen = 1;
        fullscreen_rect = rect;
    }
    return 1;
}

static void publish_mode(void) {
    unsigned int fields[7] = {fullscreen, screen.right, screen.bottom,
        fullscreen_rect.left, fullscreen_rect.top,
        fullscreen_rect.right-fullscreen_rect.left,
        fullscreen_rect.bottom-fullscreen_rect.top};
    char data[100]; unsigned int offset = 0;
    DWORD written;
    for (unsigned int f=0; f<7; ++f) {
        char digits[12]; unsigned int n=0, v=fields[f];
        do { digits[n++]=(char)('0'+v%10); v/=10; } while(v);
        while(n) data[offset++]=digits[--n];
        data[offset++]=f==6 ? '\n' : ' ';
    }
    HANDLE file=CreateFileW(pending_path,0x40000000,3,0,2,0x80,0);
    if(file==(HANDLE)-1) return;
    BOOL ok=WriteFile(file,data,offset,&written,0);
    CloseHandle(file);
    if(ok && written==offset) MoveFileExW(pending_path,mode_path,1);
}

void mainCRTStartup(void) {
    WCHAR *args = GetCommandLineW();
    if (*args=='"') { ++args; while(*args && *args!='"') ++args; if(*args) ++args; }
    else while(*args && *args!=' ' && *args!='\t') ++args;
    while(*args==' ' || *args=='\t') ++args;
    const WCHAR *flag=(const WCHAR *)L"--decklite-observe=";
    unsigned int n=0;
    while(flag[n] && args[n]==flag[n]) ++n;
    if(flag[n]) { legacy_mainCRTStartup(); return; }
    args+=n;
    const WCHAR *base=(const WCHAR *)L"Z:\\tmp\\decklite-launch-";
    unsigned int pathn=0, digits=0;
    while(base[pathn]) { mode_path[pathn]=base[pathn]; ++pathn; }
    while(*args>='0' && *args<='9' && digits<10) { mode_path[pathn++]=*args++; ++digits; }
    if(!digits || (*args!=' ' && *args!='\t')) ExitProcess(2);
    const WCHAR *suffix=(const WCHAR *)L".mode";
    n=0; while(suffix[n]) mode_path[pathn++]=suffix[n++];
    n=0; while(mode_path[n]) { pending_path[n]=mode_path[n]; ++n; }
    pending_path[n++]='.'; pending_path[n++]='n'; pending_path[n++]='e'; pending_path[n++]='w';
    while(*args==' ' || *args=='\t') ++args;
    if(args[0]!='-' || args[1]!='-' || (args[2]!=' ' && args[2]!='\t')) ExitProcess(2);
    args+=2; while(*args==' ' || *args=='\t') ++args;
    n=0; while(args[n] && n<32767) { command[n]=args[n]; ++n; }
    if(!n || args[n]) ExitProcess(2);
    GetWindowThreadProcessId(GetDesktopWindow(), &desktop_pid);
    observer_pid=GetCurrentProcessId();
    startup.cb=sizeof(startup);
    if(!CreateProcessW(0,command,0,0,1,0,0,0,&startup,&child)) ExitProcess(GetLastError());
    CloseHandle(child.thread);
    DWORD started=GetTickCount(), last_live=started, exit_code=0;
    WCHAR focus_setting[2];
    BOOL focus_disabled=GetEnvironmentVariableW((const WCHAR *)L"DECKLITE_WINE_STARTUP_FOCUS",focus_setting,2)==1 && focus_setting[0]=='0';
    BOOL seen=0, focus_repaired=0;
    HWND paint_candidate=0;
    DWORD paint_after=0;
    BOOL was_fullscreen=0;
    while(1) {
        candidate=0; live_windows=0; fullscreen=0;
        fullscreen_rect.left=fullscreen_rect.top=fullscreen_rect.right=fullscreen_rect.bottom=0;
        if(!GetClientRect(GetDesktopWindow(),&screen)) break;
        EnumWindows(observe,0);
        DWORD now=GetTickCount();
        if (!fullscreen && candidate && (candidate != paint_candidate || was_fullscreen)) {
            paint_candidate=candidate;
            paint_after=now+1000;
        }
        // Legacy GL engines can leave non-client controls white after their
        // display transition. One settled repaint restores the normal frame;
        // no resize, refocus, per-frame repaint or game-specific matching.
        if (!fullscreen && candidate && candidate==paint_candidate && paint_after &&
                (long)(now-paint_after)>=0) {
            if(GetWindowLongPtrW(candidate,-16)&0x00c00000LL)
                RedrawWindow(candidate,0,0,0x0585);
            paint_after=0;
        }
        was_fullscreen=fullscreen;
        if(live_windows) { last_live=now; seen=1; }
        if(!focus_disabled && !focus_repaired && now-started<15000 && candidate && !GetForegroundWindow()) {
            SetForegroundWindow(candidate);
            focus_repaired=1;
        }
        publish_mode();
        if(WaitForSingleObject(child.process,0)!=258 && !live_windows &&
                now-last_live > (seen ? 3000U : 150000U)) break;
        Sleep(500);
    }
    DeleteFileW(mode_path); DeleteFileW(pending_path);
    GetExitCodeProcess(child.process,&exit_code);
    CloseHandle(child.process);
    ExitProcess(exit_code==259 ? 0 : exit_code);
}
