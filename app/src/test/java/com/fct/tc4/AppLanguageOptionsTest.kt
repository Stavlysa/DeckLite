package com.fct.tc4

import com.fct.tc4.ui.misc.AppLanguageOptions
import org.junit.Assert.*
import org.junit.Test

class AppLanguageOptionsTest {
    @Test fun exactlyFiveRequestedLanguages() {
        assertEquals(listOf("en", "zh-TW", "zh-CN", "ja", "ru"),
            AppLanguageOptions.choices.map { it.tag })
        assertEquals(5, AppLanguageOptions.choices.map { it.nativeName }.distinct().size)
    }

    @Test fun defaultAndUnknownLanguagesUseEnglish() {
        listOf(null, "", "de", "en-AU").forEach {
            assertEquals("en", AppLanguageOptions.matchingTag(it))
        }
    }

    @Test fun chineseScriptTakesPrecedenceOverRegion() {
        listOf("zh-TW", "zh-HK", "zh-MO", "zh-Hant-CN").forEach {
            assertEquals("zh-TW", AppLanguageOptions.matchingTag(it))
        }
        listOf("zh", "zh-CN", "zh-SG", "zh-Hans-TW").forEach {
            assertEquals("zh-CN", AppLanguageOptions.matchingTag(it))
        }
    }

    @Test fun acceptsOnlyExactPickerTags() {
        AppLanguageOptions.choices.forEach { assertTrue(AppLanguageOptions.isSupported(it.tag)) }
        listOf("", "de", "en;reboot", "zh-Hant", "EN").forEach {
            assertFalse(AppLanguageOptions.isSupported(it))
        }
        assertEquals("ja", AppLanguageOptions.matchingTag("ja-JP"))
        assertEquals("ru", AppLanguageOptions.matchingTag("ru-RU"))
    }
}
