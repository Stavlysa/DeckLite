package com.fct.tc4.ui.misc

import java.io.File
import java.io.FileNotFoundException

/** A SAF document must stay in its selected installed container/public root. */
object DocumentPathGuard {
    fun resolve(data: File, public: File, installed: Set<String>, type: String, relative: String): File {
        if (relative.startsWith('/') || '\\' in relative || '\u0000' in relative ||
            relative.split('/').any { it == "." || it == ".." }) denied()
        val base = when (type) {
            "public" -> public
            "containers" -> data
            else -> denied()
        }
        val boundary = if (type == "containers" && relative.isNotEmpty()) {
            val code = relative.substringBefore('/')
            if (!code.matches(Regex("[A-Za-z0-9]{1,32}")) || code !in installed) denied()
            File(data, code).also { if (it.canonicalFile != File(data.canonicalFile, code)) denied() }
        } else base
        val target = File(base, relative).canonicalFile
        val root = boundary.canonicalFile
        if (target != root && !target.path.startsWith(root.path + File.separator)) denied()
        return target
    }

    fun requireName(name: String) {
        if (name.isBlank() || name == "." || name == ".." || '/' in name || '\\' in name || '\u0000' in name) denied()
    }

    private fun denied(): Nothing = throw FileNotFoundException("Document is outside the granted root")
}
