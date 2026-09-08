package com.fct.tc4.ui.misc

import android.content.Context
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat

object AppLanguage {
    private const val CHOSEN = "app_language_chosen"

    fun hasChosen(context: Context): Boolean =
        context.getSharedPreferences("tc4", Context.MODE_PRIVATE).getBoolean(CHOSEN, false)

    fun currentTag(context: Context): String {
        val explicit = AppCompatDelegate.getApplicationLocales()[0]
        // English is preselected on the welcome page; an existing OS app-language
        // choice is respected. Do not silently follow the device on first launch.
        val tag = explicit?.toLanguageTag() ?: if (hasChosen(context)) {
            context.resources.configuration.locales[0]?.toLanguageTag()
        } else null
        return AppLanguageOptions.matchingTag(tag)
    }

    fun markChosen(context: Context, tag: String): Boolean {
        require(AppLanguageOptions.isSupported(tag))
        return context.getSharedPreferences("tc4", Context.MODE_PRIVATE)
            .edit().putBoolean(CHOSEN, true).commit()
    }

    fun apply(tag: String) {
        require(AppLanguageOptions.isSupported(tag))
        // Framework persistence on API 33+, AppCompat autoStoreLocales below 33.
        // No Locale.setDefault, shell environment, Wine registry or container edits.
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(tag))
    }
}
