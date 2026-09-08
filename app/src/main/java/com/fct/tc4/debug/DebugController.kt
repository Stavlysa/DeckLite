package com.fct.tc4.debug

import android.content.Context
import android.os.Process
import android.util.Log
import com.fct.tc4.ui.misc.Global
import java.io.File
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Optional diagnostics, separate from Android's immutable debuggable flag. */
object DebugController {
    private const val PREF = "debugging_enabled"
    private var collector: java.lang.Process? = null
    private fun prefs(context: Context) = context.getSharedPreferences("tc4", Context.MODE_PRIVATE)
    fun enabled(context: Context) = prefs(context).getBoolean(PREF, false)
    private fun root(context: Context) = File(context.noBackupFilesDir, "debugging")

    @Synchronized
    fun initialize(context: Context) {
        syncAll(context)
        if (enabled(context)) startLogs(context)
    }

    @Synchronized
    fun setEnabled(context: Context, value: Boolean) {
        check(prefs(context).edit().putBoolean(PREF, value).commit())
        if (!value) {
            collector?.destroy()
            collector?.destroyForcibly()
            collector = null
        }
        syncAll(context)
        if (value) startLogs(context)
    }

    @Synchronized
    fun pair(context: Context, publicKey: String): Boolean {
        if (!enabled(context)) return false
        val normalized = DebugPublicKey.normalize(publicKey) ?: return false
        val directory = root(context).apply { mkdirs() }
        File(directory, "paired.pub").writeText(normalized + "\n")
        syncAll(context)
        return true
    }

    private fun syncAll(context: Context) {
        val controls = File(root(context), "control").apply { mkdirs() }
        val codes = Global.installedContainers + (controls.list()?.toSet() ?: emptySet())
        codes.filter { it.matches(Regex("[A-Za-z0-9]{1,32}")) }.forEach { syncContainer(context, it) }
    }

    @Synchronized
    fun syncContainer(context: Context, code: String): File {
        require(code.matches(Regex("[A-Za-z0-9]{1,32}")))
        val controls = File(root(context), "control").apply { mkdirs() }
        val directory = File(controls, code)
        check(directory.canonicalFile == File(controls.canonicalFile, code))
        directory.mkdirs()
        val flag = File(directory, "enabled")
        val keyFile = File(directory, "authorized_keys")
        // Revoke first. The guest supervisor sees disable within two seconds.
        flag.delete()
        keyFile.delete()
        if (enabled(context) && code in Global.installedContainers) {
            val paired = File(root(context), "paired.pub")
            val key = if (paired.isFile) DebugPublicKey.normalize(paired.readText()) else null
            if (key != null) keyFile.writeText(key + "\n")
            flag.writeText("1\n")
        }
        return directory
    }

    private fun startLogs(context: Context) {
        if (collector?.isAlive == true) return
        val directory = File(root(context), "logs").apply { mkdirs() }
        // App UID plus allowlisted tags: no IME, clipboard or terminal logging.
        collector = try {
            ProcessBuilder("logcat", "-T", "1", "--uid=${Process.myUid()}",
                "-v", "threadtime", "-f", File(directory, "android.log").absolutePath,
                "-r", "1024", "-n", "2", "DeckLiteDebug:I", "ContainerMainVM:W",
                "TinyAudio:W", "AndroidRuntime:E", "*:S")
                .redirectError(File("/dev/null")).start()
        } catch (_: Exception) { null }
        Log.i("DeckLiteDebug", "Optional diagnostics enabled; SSH requires pairing and container restart.")
    }

    @Synchronized
    fun clear(context: Context) {
        setEnabled(context, false)
        File(root(context), "paired.pub").delete()
        logFiles(context).forEach { it.delete() }
    }

    private fun logFiles(context: Context) = File(root(context), "logs").listFiles()?.filter {
        it.isFile && it.name.matches(Regex("android\\.log(?:\\.[0-2])?"))
    }?.sortedBy { it.name } ?: emptyList()

    @Synchronized
    fun export(context: Context, output: OutputStream) {
        ZipOutputStream(output).use { zip ->
            zip.putNextEntry(ZipEntry("status.txt"))
            val version = context.packageManager.getPackageInfo(context.packageName, 0).versionName
            zip.write(("Tiny Computer $version\nDebugging=${enabled(context)}\n" +
                "Selected Android diagnostics only. No keys or account files included.\n").toByteArray())
            zip.closeEntry()
            logFiles(context).forEach { file ->
                zip.putNextEntry(ZipEntry(file.name))
                file.inputStream().use { input ->
                    val buffer = ByteArray(8192)
                    var remaining = 1100 * 1024
                    while (remaining > 0) {
                        val count = input.read(buffer, 0, minOf(buffer.size, remaining))
                        if (count < 0) break
                        zip.write(buffer, 0, count)
                        remaining -= count
                    }
                }
                zip.closeEntry()
            }
        }
    }
}
