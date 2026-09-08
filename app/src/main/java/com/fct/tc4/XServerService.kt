package com.fct.tc4

import android.content.Intent
import android.os.Binder
import android.os.IBinder
import com.termux.x11.CmdEntryPointService

/** Keep the upstream X11 startup protocol, with a bindable lifecycle endpoint. */
class XServerService : CmdEntryPointService() {
    private val lifecycleBinder = Binder()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Even "0" starts an upstream collector. Use bounded optional APK logs.
        android.system.Os.unsetenv("TERMUX_X11_DEBUG")
        return super.onStartCommand(intent, flags, startId)
    }

    override fun onBind(intent: Intent?): IBinder = lifecycleBinder
}
