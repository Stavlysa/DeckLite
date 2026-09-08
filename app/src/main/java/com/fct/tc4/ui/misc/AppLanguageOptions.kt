package com.fct.tc4.ui.misc

import java.util.Locale

/** App UI only; never used to construct a container environment or command. */
object AppLanguageOptions {
    data class Choice(val tag: String, val nativeName: String)

    val choices = listOf(
        Choice("en", "English"),
        Choice("zh-TW", "繁體中文"),
        Choice("zh-CN", "简体中文"),
        Choice("ja", "日本語"),
        Choice("ru", "Русский")
    )

    fun isSupported(tag: String) = choices.any { it.tag == tag }

    fun matchingTag(tag: String?): String {
        val locale = Locale.forLanguageTag(tag.orEmpty())
        return when (locale.language) {
            "zh" -> when {
                locale.script == "Hant" -> "zh-TW"
                locale.script == "Hans" -> "zh-CN"
                locale.country in setOf("TW", "HK", "MO") -> "zh-TW"
                else -> "zh-CN"
            }
            "ja" -> "ja"
            "ru" -> "ru"
            else -> "en"
        }
    }
}
