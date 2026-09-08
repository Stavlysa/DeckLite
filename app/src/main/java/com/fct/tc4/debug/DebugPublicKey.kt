package com.fct.tc4.debug

import java.io.ByteArrayInputStream
import java.io.DataInputStream
import java.util.Base64

/** Only a single plain Ed25519 public key, never authorized_keys options. */
object DebugPublicKey {
    fun normalize(value: String): String? {
        return try {
            if (value.length > 1024 || '\n' in value.trim() || '\r' in value.trim()) return null
            val parts = value.trim().split(Regex("[ \\t]+"), limit = 3)
            if (parts.size < 2 || parts[0] != "ssh-ed25519") return null
            val bytes = Base64.getDecoder().decode(parts[1])
            DataInputStream(ByteArrayInputStream(bytes)).use { input ->
                if (input.readInt() != 11) return null
                val algorithm = ByteArray(11).also(input::readFully).toString(Charsets.US_ASCII)
                if (algorithm != "ssh-ed25519" || input.readInt() != 32) return null
                input.readFully(ByteArray(32))
                if (input.read() != -1) null
                else "ssh-ed25519 ${Base64.getEncoder().encodeToString(bytes)}"
            }
        } catch (_: Exception) { null }
    }
}
