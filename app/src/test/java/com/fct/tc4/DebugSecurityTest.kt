package com.fct.tc4

import com.fct.tc4.debug.DebugPublicKey
import com.fct.tc4.ui.misc.DocumentPathGuard
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.util.Base64

class DebugSecurityTest {
    @get:Rule val temporary = TemporaryFolder()
    private fun validKey(): String {
        val bytes = ByteArrayOutputStream()
        DataOutputStream(bytes).use { it.writeInt(11); it.writeBytes("ssh-ed25519"); it.writeInt(32); it.write(ByteArray(32) { 7 }) }
        return "ssh-ed25519 " + Base64.getEncoder().encodeToString(bytes.toByteArray())
    }
    @Test fun acceptsOnlyPlainEd25519() {
        val key = validKey()
        assertEquals(key, DebugPublicKey.normalize("$key comment\n"))
        listOf("", "ssh-rsa AAAA", "$key\n$key", "command=\"id\" $key", "ssh-ed25519 AAAA",
            key + "AAAA", "x".repeat(2048)).forEach { assertNull(DebugPublicKey.normalize(it)) }
    }
    @Test fun documentPathsStayInSelectedContainer() {
        val data = temporary.newFolder("data")
        val public = temporary.newFolder("public")
        val installed = setOf("decklite")
        File(data, "decklite").mkdir()
        assertEquals(File(data, "decklite/etc/passwd").canonicalFile,
            DocumentPathGuard.resolve(data, public, installed, "containers", "decklite/etc/passwd"))
        listOf("../secret", "no_backup/launcher-commands", "files/secret", "decklite/../no_backup", "/secret", "decklite/./etc").forEach {
            assertThrows(java.io.FileNotFoundException::class.java) {
                DocumentPathGuard.resolve(data, public, installed, "containers", it)
            }
        }
    }
    @Test fun documentDisplayNamesCannotTraverse() {
        listOf("..", ".", "../secret", "/absolute", "a/b", "a\\b", "\u0000").forEach {
            assertThrows(java.io.FileNotFoundException::class.java) { DocumentPathGuard.requireName(it) }
        }
        DocumentPathGuard.requireName("遊戲.txt")
    }
}
