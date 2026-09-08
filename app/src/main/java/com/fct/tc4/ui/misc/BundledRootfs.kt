package com.fct.tc4.ui.misc

import java.io.File
import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest
import java.util.Properties

/** Bounded streaming reads: no individual APK asset or byte array exceeds 512 MiB. */
object BundledRootfs {
    const val MANIFEST = "builtin/rootfs.properties"
    data class Manifest(val bytes: Long, val partBytes: Int, val sha256: String,
                        val minimumFreeBytes: Long, val code: String) {
        val parts: Int get() = ((bytes + partBytes - 1) / partBytes).toInt()
    }

    fun readManifest(input: InputStream): Manifest {
        val p = Properties().apply { load(input) }
        require(p.getProperty("format") == "1") { "Unsupported bundled container format" }
        val bytes = p.getProperty("bytes")?.toLongOrNull() ?: 0
        val partBytes = p.getProperty("part_bytes")?.toIntOrNull() ?: 0
        val sha = p.getProperty("sha256", "")
        val free = p.getProperty("minimum_free_bytes")?.toLongOrNull() ?: 0
        val code = p.getProperty("code", "")
        require(bytes in 1..0xffff_ffffL && partBytes in 1..(512 * 1024 * 1024)) { "Invalid bundled container size" }
        require((bytes + partBytes - 1) / partBytes <= 64 && free >= bytes) { "Invalid bundled container layout" }
        require(sha.matches(Regex("[0-9a-f]{64}")) && validCode(code)) { "Invalid bundled container manifest" }
        return Manifest(bytes, partBytes, sha, free, code)
    }

    fun validCode(code: String): Boolean = code.matches(Regex("[A-Za-z0-9_-]{1,64}")) &&
        code !in setOf("files", "cache", "code_cache", "databases", "no_backup", "shared_prefs", "lib", "app_webview")

    fun partName(index: Int): String = "builtin/rootfs.part" + index.toString().padStart(3, '0')

    fun copyVerified(manifest: Manifest, openAsset: (String) -> InputStream,
                     destination: File, progress: (Long, Long) -> Unit) {
        val partial = File(destination.parentFile, destination.name + ".part")
        val digest = MessageDigest.getInstance("SHA-256")
        var copied = 0L
        var lastReported = 0L
        try {
            partial.outputStream().buffered(1024 * 1024).use { output ->
                val buffer = ByteArray(1024 * 1024)
                progress(0, manifest.bytes)
                repeat(manifest.parts) { index ->
                    val expected = minOf(manifest.partBytes.toLong(), manifest.bytes - copied)
                    var readPart = 0L
                    openAsset(partName(index)).use { input ->
                        while (true) {
                            if (Thread.currentThread().isInterrupted) throw IOException("Copy interrupted")
                            val count = input.read(buffer)
                            if (count < 0) break
                            if (count == 0) throw IOException("Invalid zero-length asset read")
                            readPart += count
                            if (readPart > expected) throw IOException("Bundled container part is oversized")
                            output.write(buffer, 0, count)
                            digest.update(buffer, 0, count)
                            copied += count
                            if (copied - lastReported >= 16 * 1024 * 1024 || copied == manifest.bytes) {
                                progress(copied, manifest.bytes)
                                lastReported = copied
                            }
                        }
                    }
                    if (readPart != expected) throw IOException("Bundled container part is truncated")
                }
            }
            val actual = digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
            if (copied != manifest.bytes || actual != manifest.sha256) throw IOException("Bundled container SHA-256 mismatch")
            if (destination.exists() && !destination.delete()) throw IOException("Cannot replace container cache")
            if (!partial.renameTo(destination)) throw IOException("Cannot finalize verified container cache")
        } finally {
            partial.delete()
        }
    }
}
