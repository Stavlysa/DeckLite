package com.fct.tc4

import com.fct.tc4.ui.misc.BundledRootfs
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.IOException
import java.security.MessageDigest

class BundledRootfsTest {
    @get:Rule val folder = TemporaryFolder()
    private val bytes = "a verified container".toByteArray()
    private fun sha(data: ByteArray) = MessageDigest.getInstance("SHA-256")
        .digest(data).joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun manifestText(size: Long = bytes.size.toLong(), part: Int = 7,
                             code: String = "decklitesteamarm64") =
        "format=1\nbytes=$size\npart_bytes=$part\nsha256=${sha(bytes)}\nminimum_free_bytes=23622320128\ncode=${code.replace("\\", "\\\\")}\n"
    private fun parse(text: String = manifestText()) =
        BundledRootfs.readManifest(text.byteInputStream())
    private fun parts() = bytes.toList().chunked(7).mapIndexed { index, data ->
        BundledRootfs.partName(index) to data.toByteArray()
    }.toMap()
    private fun copy(manifest: BundledRootfs.Manifest = parse(),
                     data: Map<String, ByteArray> = parts(),
                     target: File = File(folder.root, "rootfs.tar.zst"),
                     progress: (Long, Long) -> Unit = { _, _ -> }) =
        BundledRootfs.copyVerified(manifest, {
            (data[it] ?: throw IOException("Missing asset")).inputStream()
        }, target, progress)

    @Test fun usesLongArithmeticForActualLargeContainer() {
        val m = parse(manifestText(3510205065L, 536870912))
        assertEquals(7, m.parts)
        assertEquals(3510205065L, m.bytes)
        assertEquals("builtin/rootfs.part006", BundledRootfs.partName(6))
    }

    @Test fun rejectsMalformedManifests() {
        val valid = manifestText()
        listOf(valid.replace("format=1", "format=2"),
            valid.replace("part_bytes=7", "part_bytes=0"),
            valid.replace("part_bytes=7", "part_bytes=536870913"),
            valid.replace("bytes=${bytes.size}\n", "bytes=4294967296\n"),
            valid.replace("minimum_free_bytes=23622320128", "minimum_free_bytes=1"),
            valid.replace(sha(bytes), "no-hash"),
            manifestText(100, 1), manifestText(-1, 7)).forEach { text ->
            assertThrows(IllegalArgumentException::class.java) { parse(text) }
        }
    }

    @Test fun rejectsUnsafeAndReservedContainerPaths() {
        listOf("", "..", "/tmp", "a/b", "a\\b", "a;id", "files", "cache",
            "code_cache", "shared_prefs", "no_backup", "databases", "lib",
            "app_webview", "a".repeat(65)).forEach {
            assertFalse(it, BundledRootfs.validCode(it))
            assertThrows(IllegalArgumentException::class.java) { parse(manifestText(code = it)) }
        }
        listOf("decklitesteamarm64", "user-1_backup").forEach {
            assertTrue(BundledRootfs.validCode(it))
        }
    }

    @Test fun verifiesAndJoinsPartsWithBoundedProgress() {
        val target = File(folder.root, "rootfs.tar.zst")
        val progress = mutableListOf<Pair<Long, Long>>()
        copy(target = target) { copied, total -> progress.add(copied to total) }
        assertArrayEquals(bytes, target.readBytes())
        assertEquals(0L to bytes.size.toLong(), progress.first())
        assertEquals(bytes.size.toLong() to bytes.size.toLong(), progress.last())
        assertFalse(File(target.path + ".part").exists())
    }

    @Test fun rejectsMissingTruncatedOversizedAndCorruptParts() {
        val first = BundledRootfs.partName(0)
        val original = parts()
        listOf(original - first,
            original + (first to byteArrayOf(1)),
            original + (first to ByteArray(8)),
            original + (first to ByteArray(7))).forEach { broken ->
            val target = File(folder.root, "rootfs.tar.zst")
            assertThrows(IOException::class.java) { copy(data = broken, target = target) }
            assertFalse(target.exists())
            assertFalse(File(target.path + ".part").exists())
        }
    }

    @Test fun hashFailurePreservesExistingDestinationAndRetrySucceeds() {
        val target = folder.newFile("rootfs.tar.zst")
        val previous = "previous cache".toByteArray()
        target.writeBytes(previous)
        assertThrows(IOException::class.java) {
            copy(manifest = parse().copy(sha256 = "0".repeat(64)), target = target)
        }
        assertArrayEquals(previous, target.readBytes())
        copy(target = target)
        assertArrayEquals(bytes, target.readBytes())
        assertFalse(File(target.path + ".part").exists())
    }
}
