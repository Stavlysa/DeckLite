// SettingsViewModel.kt -- This file is part of tiny_container.
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

package com.fct.tc4.ui.page

import android.app.Application
import androidx.annotation.StringRes
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.fct.tc4.R
import com.fct.tc4.debug.DebugController
import com.fct.tc4.ui.misc.Global
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

// ===================== Data Models =====================

sealed class SettingsItem {
    abstract val id: String

    @get:StringRes
    abstract val titleRes: Int

    @get:StringRes
    abstract val descriptionRes: Int
}

/** 开关型设置项 */
data class SwitchSetting(
    override val id: String,
    @StringRes override val titleRes: Int,
    @StringRes override val descriptionRes: Int,
    val isChecked: Boolean
) : SettingsItem()

/** 动作型设置项（点击执行跳转/请求，无开关） */
data class ActionSetting(
    override val id: String,
    @StringRes override val titleRes: Int,
    @StringRes override val descriptionRes: Int
) : SettingsItem()

// ===================== ViewModel =====================

class SettingsViewModel(
    application: Application,
    private val code: String
) : AndroidViewModel(application) {

    private val _items = MutableStateFlow<List<SettingsItem>>(emptyList())
    val items: StateFlow<List<SettingsItem>> = _items.asStateFlow()

    init { refresh() }

    /** 切换开关状态并持久化 */
    fun toggle(item: SwitchSetting) {
        val newChecked = !item.isChecked
        when (item.id) {
            "auto_launch" -> Global.autoLaunch = if (newChecked) code else ""
            "auto_launch_gui" -> Global.autoLaunchGui = newChecked
            "reset_bootstrap" -> Global.shouldResetBootstrap = newChecked
            "use_legacy_proot" -> Global.useLegacyProot = newChecked
            "auto_check_update" -> Global.autoCheckUpdate = newChecked
            "debugging" -> DebugController.setEnabled(getApplication(), newChecked)
        }
        refresh()
    }

    fun refresh() {
        _items.value = listOf(
            ActionSetting("app_language", R.string.tc4_language_title, R.string.tc4_language_desc),
            SwitchSetting("debugging", R.string.tc4_debug_title,
                R.string.tc4_debug_desc, DebugController.enabled(getApplication())),
            ActionSetting("debug_export", R.string.tc4_debug_export_title, R.string.tc4_debug_export_desc),
            ActionSetting("debug_clear", R.string.tc4_debug_clear_title, R.string.tc4_debug_clear_desc),
            ActionSetting(
                id = "launcher_shortcut",
                titleRes = R.string.tc4_settings_shortcut_title,
                descriptionRes = R.string.tc4_settings_shortcut_desc
            ),
            SwitchSetting(
                id = "auto_launch",
                titleRes = R.string.tc4_settings_auto_launch_title,
                descriptionRes = R.string.tc4_settings_auto_launch_desc,
                isChecked = code == Global.autoLaunch
            ),
            SwitchSetting(
                id = "auto_launch_gui",
                titleRes = R.string.tc4_settings_auto_launch_gui_title,
                descriptionRes = R.string.tc4_settings_auto_launch_desc,
                isChecked = Global.autoLaunchGui
            ),
            SwitchSetting(
                id = "use_legacy_proot",
                titleRes = R.string.tc4_settings_legacy_proot_title,
                descriptionRes = R.string.tc4_settings_legacy_proot_desc,
                isChecked = Global.useLegacyProot
            ),
            SwitchSetting(
                id = "reset_bootstrap",
                titleRes = R.string.tc4_settings_reset_bootstrap_title,
                descriptionRes = R.string.tc4_settings_reset_bootstrap_desc,
                isChecked = Global.shouldResetBootstrap
            ),
            SwitchSetting(
                id = "auto_check_update",
                titleRes = R.string.tc4_settings_auto_check_update_title,
                descriptionRes = R.string.tc4_settings_auto_check_update_desc,
                isChecked = Global.autoCheckUpdate
            ),
            ActionSetting(
                id = "manage_files",
                titleRes = R.string.tc4_settings_manage_files_title,
                descriptionRes = R.string.tc4_settings_manage_files_desc
            ),
            ActionSetting(
                id = "battery_unlimited",
                titleRes = R.string.tc4_settings_battery_title,
                descriptionRes = R.string.tc4_settings_battery_desc
            )
        )
    }

    class Factory(
        private val application: Application,
        private val code: String
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return SettingsViewModel(application, code) as T
        }
    }
}
