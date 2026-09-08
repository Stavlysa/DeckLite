/* Native ARM64 PE, no CRT. General Wine virtual-desktop startup focus repair.
 * Only the launched process's initial visible window may receive focus.
 * Never repeatedly refocus a running game or override a non-null foreground.
 */
typedef void *HANDLE;
typedef void *HWND;
typedef unsigned long DWORD;
typedef unsigned short WORD;
typedef unsigned short WCHAR;
typedef long long LPARAM;
typedef int BOOL;
typedef struct { long left, top, right, bottom; } RECT;
typedef struct {
    DWORD cb;
    WCHAR *reserved, *desktop, *title;
    DWORD x, y, width, height, chars_x, chars_y, fill, flags;
    WORD show, reserved_size;
    unsigned char *reserved_data;
    HANDLE stdin_handle, stdout_handle, stderr_handle;
} STARTUPINFO;
typedef struct { HANDLE process, thread; DWORD pid, tid; } PROCESSINFO;
#define API __declspec(dllimport)
API WCHAR *GetCommandLineW(void);
API BOOL CreateProcessW(const WCHAR *, WCHAR *, void *, void *, BOOL, DWORD,
                       void *, const WCHAR *, STARTUPINFO *, PROCESSINFO *);
API DWORD WaitForSingleObject(HANDLE, DWORD);
API DWORD WaitForInputIdle(HANDLE, DWORD);
API BOOL GetExitCodeProcess(HANDLE, DWORD *);
API BOOL CloseHandle(HANDLE);
API DWORD GetTickCount(void);
API void Sleep(DWORD);
API void ExitProcess(unsigned int);
API DWORD GetLastError(void);
API HANDLE GetStdHandle(DWORD);
API BOOL WriteFile(HANDLE, const void *, DWORD, DWORD *, void *);
API HWND GetForegroundWindow(void);
API BOOL EnumWindows(BOOL (*)(HWND, LPARAM), LPARAM);
API BOOL IsWindowVisible(HWND);
API BOOL IsWindowEnabled(HWND);
API BOOL GetWindowRect(HWND, RECT *);
API DWORD GetWindowThreadProcessId(HWND, DWORD *);
API BOOL SetForegroundWindow(HWND);
API DWORD GetEnvironmentVariableW(const WCHAR *, WCHAR *, DWORD);
API BOOL GetClientRect(HWND, RECT *);
API HWND GetDesktopWindow(void);
API long long GetWindowLongPtrW(HWND, int);
API long long SetWindowLongPtrW(HWND, int, long long);
API BOOL SetWindowPos(HWND, HWND, int, int, int, int, unsigned int);
API int GetClassNameW(HWND, WCHAR *, int);
API HANDLE CreateFileW(const WCHAR *, DWORD, DWORD, void *, DWORD, DWORD, HANDLE);
API DWORD GetTempPathW(DWORD, WCHAR *);
API DWORD GetCurrentProcessId(void);
static WCHAR command[32768];
static STARTUPINFO startup;
static PROCESSINFO child;
static HWND candidate;
static unsigned int fit_width, fit_height;
static HANDLE trace;
API BOOL RedrawWindow(HWND,const RECT *,HANDLE,unsigned int);

static void open_trace(void) {
    WCHAR path[300];
    const WCHAR *name=(const WCHAR *)L"decklite-borderless-";
    DWORD n=GetTempPathW(240,path), pid=GetCurrentProcessId();
    WCHAR digits[12]; unsigned int i=0, count=0;
    if (!n || n>=240) return;
    while(name[i]) path[n++]=name[i++];
    do { digits[count++]=(WCHAR)('0'+pid%10); pid/=10; } while(pid);
    while(count) path[n++]=digits[--count];
    path[n++]='.'; path[n++]='l'; path[n++]='o'; path[n++]='g'; path[n]=0;
    trace=CreateFileW(path,0x40000000,3,0,2,0x80,0);
    if(trace==(HANDLE)-1) trace=0;
}

/* Shared integer layout, no renderer hooks or game-name matching. */
static BOOL fit_rect(unsigned int sw, unsigned int sh, unsigned int bw, unsigned int bh, RECT *r) {
    unsigned int w, h;
    if (!sw || !sh || !bw || !bh || sw>32767 || sh>32767 || bw>32767 || bh>32767) return 0;
    if ((unsigned long long)bw*sh <= (unsigned long long)bh*sw) { w=bw; h=(unsigned int)((unsigned long long)bw*sh/sw); }
    else { h=bh; w=(unsigned int)((unsigned long long)bh*sw/sh); }
    if (!w || !h) return 0;
    r->left=(bw-w)/2; r->top=(bh-h)/2; r->right=r->left+w; r->bottom=r->top+h;
    return 1;
}

static BOOL layout_selftest(void) {
    RECT r;
    if (!fit_rect(640,480,1400,876,&r) || r.left!=116 || r.top!=0 || r.right!=1284 || r.bottom!=876) return 0;
    if (!fit_rect(640,480,876,1400,&r) || r.left!=0 || r.top!=371 || r.right!=876 || r.bottom!=1028) return 0;
    if (!fit_rect(1920,1080,1280,720,&r) || r.left!=0 || r.top!=0 || r.right!=1280 || r.bottom!=720) return 0;
    if (fit_rect(0,480,1400,876,&r) || fit_rect(640,480,40000,876,&r)) return 0;
    return 1;
}

static void parse_fit_size(const WCHAR *value) {
    unsigned int i=0, w=0, h=0;
    while (value[i]>='0' && value[i]<='9' && w<=32767) w=w*10+value[i++]-'0';
    if (value[i++]!='x') return;
    while (value[i]>='0' && value[i]<='9' && h<=32767) h=h*10+value[i++]-'0';
    if (value[i] || w<100 || h<100 || w>32767 || h>32767) return;
    fit_width=w; fit_height=h;
}

static void log_line(const char *s) {
    DWORD n = 0, written;
    while (s[n]) ++n;
    WriteFile(GetStdHandle((DWORD)-12), s, n, &written, 0);
    if(trace) WriteFile(trace,s,n,&written,0);
}
static void log_number(const char *label, DWORD value) {
    char out[14], digits[12]; unsigned int n=0, i=0;
    log_line(label);
    do { digits[n++]=(char)('0'+value%10); value/=10; } while(value);
    while(n) out[i++]=digits[--n]; out[i++]='\n'; out[i]=0; log_line(out);
}

/* Return 1 only for a transient stale-handle startup failure. */
static BOOL fit_game_window(HWND window) {
    RECT client, desktop, original, fitted;
    long long style;
    HWND root=GetDesktopWindow();
    if (!fit_width) return 0;
    if (!GetClientRect(window,&client) || !GetClientRect(root,&desktop)) {
        log_line("DeckLite borderless: could not read client geometry.\n"); return 0;
    }
    /* A game's exclusive mode switch shrinks the virtual monitor. Never fight
     * it in a resize loop: retain safe mode and explain the required setting. */
    if (desktop.right!=(long)fit_width || desktop.bottom!=(long)fit_height) {
        log_line("DeckLite borderless: choose Windowed in the game's own settings; safe desktop retained.\n");
        return 0;
    }
    if (!fit_rect(client.right,client.bottom,fit_width,fit_height,&fitted) || !GetWindowRect(window,&original)) return 0;
    style=GetWindowLongPtrW(window,-16);
    log_number("DeckLite borderless: original style=",(DWORD)style);
    SetWindowLongPtrW(window,-16,(style & ~0x00cf0000LL) | 0x80000000LL);
    log_number("DeckLite borderless: client width=",client.right);
    log_number("DeckLite borderless: client height=",client.bottom);
    if (!SetWindowPos(window,0,fitted.left,fitted.top,fitted.right-fitted.left,fitted.bottom-fitted.top,0x0034)) {
        DWORD error=GetLastError(); log_number("DeckLite borderless: SetWindowPos error=",error);
        SetWindowLongPtrW(window,-16,style);
        SetWindowPos(window,0,original.left,original.top,original.right-original.left,original.bottom-original.top,0x0034);
        log_line("DeckLite borderless: resize failed; original window restored.\n");
        return error==1400;
    }
    /* No overlay windows: Wine can give even NOACTIVATE bars the DirectInput
     * foreground. The prefix's black desktop paints its own letterboxing. */
    RedrawWindow(root,0,0,0x0145); /* INVALIDATE | ERASE | NOCHILDREN | UPDATENOW */
    log_line("DeckLite borderless: aspect-preserving fullscreen applied (application controls render resolution).\n");
    return 0;
}

static void wait_for_game(void) {
    WaitForSingleObject(child.process,0xffffffff);
}
static BOOL inspect(HWND window, LPARAM unused) {
    DWORD pid;
    RECT rect;
    (void)unused;
    GetWindowThreadProcessId(window, &pid);
    if (pid != child.pid || !IsWindowVisible(window) || !IsWindowEnabled(window)) return 1;
    if (!GetWindowRect(window, &rect) || rect.right - rect.left < 64 || rect.bottom - rect.top < 64) return 1;
    if (fit_width) {
        WCHAR cls[32];
        GetClassNameW(window,cls,32);
        /* Startup dialogs are not game viewports. */
        if (cls[0]=='#' || !GetClientRect(window,&rect) || rect.right<320 || rect.bottom<200) return 1;
        char printable[34]; unsigned int j=0;
        while(cls[j] && j<31) { printable[j]=(char)cls[j]; ++j; }
        printable[j++]='\n'; printable[j]=0; log_line(printable);
    }
    candidate = window;
    return 0;
}
void mainCRTStartup(void) {
    WCHAR *args = GetCommandLineW();
    DWORD length = 0, started, exit_code = 1;
    WCHAR test[2];
    if (GetEnvironmentVariableW((const WCHAR *)L"DECKLITE_WINE_LAYOUT_SELFTEST",test,2)==1 && test[0]=='1') {
        BOOL ok=layout_selftest(); log_line(ok ? "Layout tests passed.\n" : "Layout tests failed.\n"); ExitProcess(ok ? 0 : 1);
    }
    /* Skip our own executable, preserving the child's Windows quoting exactly. */
    if (*args == '"') { ++args; while (*args && *args != '"') ++args; if (*args) ++args; }
    else { while (*args && *args != ' ' && *args != '\t') ++args; }
    while (*args == ' ' || *args == '\t') ++args;
    /* Explorer may reuse a Win32 environment distinct from native /proc/env.
     * Pass display geometry as a helper argument, preserving child quoting. */
    const WCHAR *flag=(const WCHAR *)L"--decklite-fit=";
    unsigned int matched=0;
    while(flag[matched] && args[matched]==flag[matched]) ++matched;
    if(!flag[matched]) {
        WCHAR size[40]; unsigned int i=0; args+=matched;
        while(*args && *args!=' ' && *args!='\t' && i<39) size[i++]=*args++;
        size[i]=0; parse_fit_size(size);
        if(!fit_width || (*args && *args!=' ' && *args!='\t')) ExitProcess(2);
        while(*args==' ' || *args=='\t') ++args;
        if(args[0]!='-' || args[1]!='-' || (args[2]!=' ' && args[2]!='\t')) ExitProcess(2);
        args+=2; while(*args==' ' || *args=='\t') ++args;
        open_trace();
        log_line("DeckLite borderless: waiting for the launched game's window.\n");
    }
    while (args[length] && length < 32767) { command[length] = args[length]; ++length; }
    if (!length || args[length]) { log_line("DeckLite Wine: missing/oversized game command.\n"); ExitProcess(2); }
    startup.cb = sizeof(startup);
    if (!CreateProcessW(0, command, 0, 0, 1, 0, 0, 0, &startup, &child)) {
        DWORD error = GetLastError();
        log_line("DeckLite Wine: could not create the game process.\n");
        ExitProcess(error ? error : 1);
    }
    CloseHandle(child.thread);
    started = GetTickCount();
    WaitForInputIdle(child.process, 1000);
    while (GetTickCount() - started < (fit_width ? 120000U : 15000U) && WaitForSingleObject(child.process, 100) == 258) {
        candidate = 0;
        EnumWindows(inspect, 0);
        if (!candidate) continue;
        if(fit_width) log_line("DeckLite borderless: found the launched game's window.\n");
        /* Allow the initial fullscreen mode/window transition to settle. */
        Sleep(500);
        candidate=0; EnumWindows(inspect,0);
        if(!candidate) continue;
        unsigned int attempt=0;
        while(fit_game_window(candidate) && ++attempt<15 && WaitForSingleObject(child.process,2000)==258) {
            candidate=0; EnumWindows(inspect,0); if(!candidate) break;
        }
        WCHAR focus_setting[2];
        BOOL focus_disabled=GetEnvironmentVariableW((const WCHAR *)L"DECKLITE_WINE_STARTUP_FOCUS",focus_setting,2)==1 && focus_setting[0]=='0';
        HWND foreground=GetForegroundWindow(); DWORD foreground_pid=0;
        if(foreground) GetWindowThreadProcessId(foreground,&foreground_pid);
        /* Repair missing startup focus without overriding another application. */
        if (!focus_disabled && (!foreground || (fit_width && foreground_pid==GetCurrentProcessId())) && IsWindowVisible(candidate)) {
            if (SetForegroundWindow(candidate))
                log_line("DeckLite Wine: restored missing initial game foreground.\n");
            else log_line("DeckLite Wine: initial game foreground repair was refused.\n");
        }
        break;
    }
    if(fit_width && !candidate) log_line("DeckLite borderless: no eligible game window found.\n");
    wait_for_game();
    GetExitCodeProcess(child.process, &exit_code);
    CloseHandle(child.process);
    if(trace) CloseHandle(trace);
    ExitProcess(exit_code);
}
