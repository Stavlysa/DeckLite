package com.fct.tc4.ui.misc

import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.security.SecureRandom

/** Private, non-backed-up capabilities. Intents never supply executable text. */
class LauncherCommandVault(private val directory: File) {
    data class Command(val code: String, val text: String)

    @Synchronized
    fun create(code: String, command: String): String {
        require(code.matches(Regex("[a-zA-Z0-9]{1,32}")))
        require(command.isNotBlank() && command.length <= 16000 && '\u0000' !in command)
        check(directory.isDirectory || directory.mkdirs())
        val random = SecureRandom()
        while (true) {
            val token = ByteArray(32).also(random::nextBytes)
                .joinToString("") { "%02x".format(it.toInt() and 255) }
            val record = File(directory, token)
            if (!record.createNewFile()) continue
            try {
                record.setReadable(false, false)
                record.setWritable(false, false)
                record.setReadable(true, true)
                record.setWritable(true, true)
                DataOutputStream(record.outputStream()).use {
                    it.writeInt(1)
                    it.writeUTF(code)
                    it.writeUTF(command)
                }
                return token
            } catch (error: Exception) {
                record.delete()
                throw error
            }
        }
    }

    fun resolve(token: String?): Command? {
        if (token == null || !token.matches(Regex("[0-9a-f]{64}"))) return null
        return try {
            val record = File(directory, token)
            if (record.canonicalFile.parentFile != directory.canonicalFile ||
                !record.isFile || record.length() !in 10..65536) return null
            DataInputStream(record.inputStream()).use {
                if (it.readInt() != 1) return null
                val code = it.readUTF()
                val command = it.readUTF()
                if (!code.matches(Regex("[a-zA-Z0-9]{1,32}")) || command.isBlank() ||
                    command.length > 16000 || '\u0000' in command || it.read() != -1) return null
                Command(code, command)
            }
        } catch (_: Exception) { null }
    }

    fun revoke(token: String) {
        if (!token.matches(Regex("[0-9a-f]{64}"))) return
        val record = File(directory, token)
        if (record.canonicalFile.parentFile == directory.canonicalFile) record.delete()
    }

    fun revokeContainer(code: String) {
        directory.listFiles()?.forEach { file ->
            if (resolve(file.name)?.code == code) revoke(file.name)
        }
    }

    companion object {
        const val EXTRA_TOKEN = "shortcut_token_v1"
    }
}
