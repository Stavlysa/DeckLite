package com.fct.tc4.debug

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Manifest DUMP permission: authorized adb/system, not ordinary applications. */
class DebugPairingReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != "com.fct.tc4.action.PAIR_DEBUG_SSH") return
        if (!DebugController.enabled(context)) {
            resultCode = 403
            resultData = "Enable Debugging in Settings first."
            return
        }
        val accepted = DebugController.pair(context, intent.getStringExtra("public_key") ?: "")
        resultCode = if (accepted) 200 else 400
        resultData = if (accepted) "Paired. Restart the container to start SSH on localhost:8027."
                     else "Invalid Ed25519 public key."
    }
}
