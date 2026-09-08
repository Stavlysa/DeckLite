package com.fct.tc4

import com.fct.tc4.ui.misc.LauncherCommandVault
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class LauncherCommandVaultTest {
    @get:Rule val temporary = TemporaryFolder()
    private fun vault() = LauncherCommandVault(File(temporary.root, "vault"))

    @Test fun capabilitiesResolveOnlyPrivateCommands() {
        val token = vault().create("deckliteautodisplay", "printf safe")
        assertTrue(token.matches(Regex("[0-9a-f]{64}")))
        assertEquals(LauncherCommandVault.Command("deckliteautodisplay", "printf safe"), vault().resolve(token))
        assertNull(vault().resolve(null))
        assertNull(vault().resolve("shortcut_command"))
        assertNull(vault().resolve("0".repeat(64)))
    }

    @Test fun traversalAndMalformedRecordsFailClosed() {
        val token = vault().create("test", "true")
        assertNull(vault().resolve("../$token"))
        File(temporary.root, "vault/$token").writeText("untrusted")
        assertNull(vault().resolve(token))
    }

    @Test fun deletionRevokesOnlyMatchingContainer() {
        val first = vault().create("test", "true")
        val second = vault().create("other", "false")
        assertNotEquals(first, second)
        vault().revokeContainer("test")
        assertNull(vault().resolve(first))
        assertNotNull(vault().resolve(second))
    }

    @Test(expected = IllegalArgumentException::class)
    fun unsafeContainerCodeIsRejected() { vault().create("../files", "true") }

    @Test(expected = IllegalArgumentException::class)
    fun nulCommandIsRejected() { vault().create("test", "echo\u0000bad") }
}
