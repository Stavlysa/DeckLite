// Tc4Application.kt -- This file is part of tiny_container.
//
// Copyright (C) 2026 Caten Hu
//
// Tiny Container is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published
// by the Free Software Foundation, either version 3 of the License,
// or any later version.
//
// Tiny Container is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty
// of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
// See the GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see http://www.gnu.org/licenses/.

package com.fct.tc4

import android.app.Application
import androidx.preference.PreferenceManager
import com.fct.tc4.ui.misc.Global
import com.google.android.material.color.DynamicColors

class Tc4Application : Application() {
    override fun onCreate() {
        super.onCreate()
        DynamicColors.applyToActivitiesIfAvailable(this)
        registerActivityLifecycleCallbacks(XServerActivityBinding())

        // Games running through Wine commonly consume physical keyboard input
        // as hardware scancodes. Termux:X11 defaults this off, which can make
        // letter keys appear unresponsive on Samsung keyboards and similar
        // devices. Only set the initial value so an explicit user choice is
        // still preserved.
        val x11Preferences = PreferenceManager.getDefaultSharedPreferences(this)
        val x11Defaults = x11Preferences.edit()
        var x11DefaultsChanged = false
        if (!x11Preferences.contains("preferScancodes")) {
            x11Defaults.putBoolean("preferScancodes", true)
            x11DefaultsChanged = true
        }

        // Termux:X11 otherwise defaults captured pointer movement to "No".
        // Automatic mode follows the current display rotation for touchpads,
        // which keeps relative movement aligned in Android landscape mode.
        // Preserve an existing choice when upgrading.
        if (!x11Preferences.contains("transformCapturedPointer")) {
            x11Defaults.putString("transformCapturedPointer", "at")
            x11DefaultsChanged = true
        }
        if (x11DefaultsChanged) {
            // Termux:X11 also has an xserver process. Commit before that
            // process can start so its first preference read cannot race the
            // asynchronous SharedPreferences disk write.
            x11Defaults.commit()
        }

        Global.init(this)
        if (getProcessName() == packageName) com.fct.tc4.debug.DebugController.initialize(this)
    }
}
