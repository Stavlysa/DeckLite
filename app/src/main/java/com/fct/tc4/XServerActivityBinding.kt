package com.fct.tc4

import android.app.Activity
import android.app.Application
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import android.util.Log
import java.util.IdentityHashMap

/**
 * The embedded X11 renderer is a separate Android process. A started, unbound
 * service can be put in the background cpuset even while its surface is visible.
 * Use normal Activity/service importance inheritance, not CPU IDs, task profiles,
 * foreground-service exemptions or a permanent background boost.
 */
class XServerActivityBinding : Application.ActivityLifecycleCallbacks {
    private val bindings = IdentityHashMap<Activity, ServiceConnection>()

    override fun onActivityStarted(activity: Activity) {
        if (activity !is com.termux.x11.MainActivity || bindings.containsKey(activity)) return

        val connection = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                Log.d(TAG, "Visible X11 activity bound to renderer")
            }

            override fun onServiceDisconnected(name: ComponentName) {
                // Android retains the binding and reconnects if the started
                // service returns. Do not launch another server without args.
                Log.w(TAG, "X11 renderer disconnected")
            }

            override fun onBindingDied(name: ComponentName) = release(activity)
            override fun onNullBinding(name: ComponentName) = release(activity)
        }

        // Deliberately omit AUTO_CREATE: the container owns server startup and
        // its environment/arguments. Opening an unconnected viewer must not
        // create or restart an empty renderer process.
        try {
            val bound = activity.bindService(
                Intent(activity, XServerService::class.java), connection,
                Context.BIND_IMPORTANT or Context.BIND_ADJUST_WITH_ACTIVITY
            )
            if (bound) {
                bindings[activity] = connection
            } else {
                // Context may retain its dispatcher even when bindService
                // returns false; release that unsuccessful registration too.
                try {
                    activity.unbindService(connection)
                } catch (_: IllegalArgumentException) {
                    // No registration was retained by this Android version.
                }
                Log.w(TAG, "No started X11 renderer available to bind")
            }
        } catch (error: SecurityException) {
            Log.w(TAG, "Cannot bind X11 renderer", error)
        }
    }

    private fun release(activity: Activity) {
        val connection = bindings.remove(activity) ?: return
        activity.unbindService(connection)
        Log.d(TAG, "Hidden X11 activity released renderer binding")
    }

    // STARTED covers multi-window/PiP visibility without keeping the renderer
    // boosted when the viewer has actually stopped or the screen is locked.
    override fun onActivityStopped(activity: Activity) = release(activity)
    override fun onActivityDestroyed(activity: Activity) = release(activity)
    override fun onActivityCreated(activity: Activity, state: Bundle?) = Unit
    override fun onActivityResumed(activity: Activity) = Unit
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = Unit

    private companion object {
        const val TAG = "DeckLiteX11Binding"
    }
}
