// TinyDocumentsProvider.kt -- This file is part of tiny_container.
//
// Copyright (C) 2026 Caten Hu
//
// Tiny Container is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published
// by the Free Software Foundation, either version 3 of the License,
// or any later version.
//
// Tiny Container is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty
// of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
// See the GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see http://www.gnu.org/licenses/.

package com.fct.tc4.ui.misc

import android.content.res.AssetFileDescriptor
import android.database.Cursor
import android.database.MatrixCursor
import android.graphics.Point
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.provider.DocumentsContract.Document
import android.provider.DocumentsContract.Root
import android.provider.DocumentsProvider
import android.webkit.MimeTypeMap
import com.fct.tc4.R
import java.io.File
import java.io.FileNotFoundException
import java.io.IOException
import java.util.LinkedList

/**
 * SAF DocumentsProvider，将已安装容器和公共文件夹暴露给系统文件管理器。
 *
 * 暴露两个根：
 * - containers : dataDir 下的每个已安装容器根文件系统
 * - public     : filesDir/public 跨容器共享目录
 *
 * Document ID 格式: "rootType:relativePath"
 * - containers:xfce/etc/passwd → dataDir/xfce/etc/passwd
 * - public:downloads/a.png     → filesDir/public/downloads/a.png
 */
class TinyDocumentsProvider : DocumentsProvider() {

    companion object {
        private const val ROOT_CONTAINERS = "containers"
        private const val ROOT_PUBLIC = "public"
        private const val ALL_MIME_TYPES = "*/*"

        private val DEFAULT_ROOT_PROJECTION = arrayOf(
            Root.COLUMN_ROOT_ID, Root.COLUMN_MIME_TYPES, Root.COLUMN_FLAGS,
            Root.COLUMN_ICON, Root.COLUMN_TITLE, Root.COLUMN_SUMMARY,
            Root.COLUMN_DOCUMENT_ID, Root.COLUMN_AVAILABLE_BYTES
        )

        private val DEFAULT_DOCUMENT_PROJECTION = arrayOf(
            Document.COLUMN_DOCUMENT_ID, Document.COLUMN_MIME_TYPE,
            Document.COLUMN_DISPLAY_NAME, Document.COLUMN_LAST_MODIFIED,
            Document.COLUMN_FLAGS, Document.COLUMN_SIZE
        )
    }

    // ── 路径基础 ──────────────────────────────────

    private val dataDir: File by lazy { context!!.dataDir }
    private val filesDir: File by lazy { context!!.filesDir }

    private val publicDir: File by lazy { File(filesDir, "public") }

    /** 已安装容器目录 */
    private val installedContainerDirs: List<File>
        get() = Global.installedContainers.map { File(dataDir, it) }.filter { it.isDirectory }

    // ── docId ↔ File ──────────────────────────────

    private fun getRootDir(rootType: String): File = when (rootType) {
        ROOT_PUBLIC -> publicDir
        ROOT_CONTAINERS -> dataDir
        else -> throw IllegalArgumentException("Unknown root: $rootType")
    }

    private fun docIdToFile(docId: String): File {
        val sep = docId.indexOf(':')
        if (sep < 0) throw FileNotFoundException("Invalid docId: $docId")
        val rootType = docId.substring(0, sep)
        val relative = docId.substring(sep + 1)
        val file = DocumentPathGuard.resolve(dataDir, publicDir, Global.installedContainers, rootType, relative)
        if (!file.exists()) throw FileNotFoundException(file.absolutePath)
        return file
    }

    /**
     * 不检查存在性的 docId 解析，用于 createDocument 等创建场景。
     * 父目录必须存在，但目标文件尚不存在。
     */
    private fun docIdToParentFile(docId: String): File {
        val sep = docId.indexOf(':')
        if (sep < 0) throw FileNotFoundException("Invalid docId: $docId")
        val rootType = docId.substring(0, sep)
        val relative = docId.substring(sep + 1)
        return DocumentPathGuard.resolve(dataDir, publicDir, Global.installedContainers, rootType, relative)
    }

    private fun fileToDocId(rootType: String, file: File): String {
        val rootDir = getRootDir(rootType)
        val relative = file.absolutePath
            .removePrefix(rootDir.absolutePath)
            .removePrefix("/")
        DocumentPathGuard.resolve(dataDir, publicDir, Global.installedContainers, rootType, relative)
        return "$rootType:$relative"
    }

    /** 规范化：兼容系统直接传 rootId（无冒号） */
    private fun normalizeDocId(raw: String): Pair<String, String> {
        val sep = raw.indexOf(':')
        return if (sep >= 0) raw.substring(0, sep) to raw.substring(sep + 1)
        else raw to ""
    }

    // ── DocumentsProvider 核心 ─────────────────────

    override fun onCreate(): Boolean = true

    override fun queryRoots(projection: Array<out String>?): Cursor {
        val result = MatrixCursor(projection ?: DEFAULT_ROOT_PROJECTION)
        val appName = context!!.getString(R.string.tc4_app_name)

        val ctx = context!!
        result.addRoot(ROOT_CONTAINERS, ctx.getString(R.string.tc4_documents_root_containers_label),
            ctx.getString(R.string.tc4_documents_root_containers),
            Root.FLAG_SUPPORTS_CREATE or Root.FLAG_SUPPORTS_SEARCH or Root.FLAG_SUPPORTS_IS_CHILD,
            "$ROOT_CONTAINERS:", dataDir.freeSpace)

        result.addRoot(ROOT_PUBLIC, ctx.getString(R.string.tc4_documents_root_public_label),
            ctx.getString(R.string.tc4_documents_root_public),
            Root.FLAG_SUPPORTS_CREATE or Root.FLAG_SUPPORTS_SEARCH or Root.FLAG_SUPPORTS_IS_CHILD,
            "$ROOT_PUBLIC:", publicDir.freeSpace)

        return result
    }

    override fun queryDocument(documentId: String, projection: Array<out String>?): Cursor {
        val result = MatrixCursor(projection ?: DEFAULT_DOCUMENT_PROJECTION)
        includeFile(result, documentId, null)
        return result
    }

    override fun queryChildDocuments(
        parentDocumentId: String, projection: Array<out String>?, sortOrder: String?
    ): Cursor {
        val result = MatrixCursor(projection ?: DEFAULT_DOCUMENT_PROJECTION)
        val (rootType, relative) = normalizeDocId(parentDocumentId)

        if (rootType == ROOT_CONTAINERS && relative.isEmpty()) {
            for (dir in installedContainerDirs) {
                includeFile(result, "$ROOT_CONTAINERS:${dir.name}", null)
            }
        } else {
            val parent = docIdToFile("$rootType:$relative")
            parent.listFiles()?.forEach { child ->
                try { includeFile(result, null, child, rootType) } catch (_: FileNotFoundException) { }
            }
        }
        return result
    }

    override fun openDocument(
        documentId: String, mode: String, signal: CancellationSignal?
    ): ParcelFileDescriptor {
        val file = docIdToFile(documentId)
        val accessMode = ParcelFileDescriptor.parseMode(mode)
        return ParcelFileDescriptor.open(file, accessMode)
    }

    override fun getDocumentType(documentId: String): String {
        return getMimeType(docIdToFile(documentId))
    }

    override fun openDocumentThumbnail(
        documentId: String, sizeHint: Point?, signal: CancellationSignal?
    ): AssetFileDescriptor {
        val file = docIdToFile(documentId)
        val pfd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
        return AssetFileDescriptor(pfd, 0, file.length())
    }

    override fun querySearchDocuments(
        rootId: String, query: String, projection: Array<out String>?
    ): Cursor {
        val result = MatrixCursor(projection ?: DEFAULT_DOCUMENT_PROJECTION)
        val rootType = rootId.substringBefore(':')
        val rootDir = getRootDir(rootType)
        val queryLower = query.lowercase()

        val pending = LinkedList<File>()
        if (rootType == ROOT_CONTAINERS) {
            installedContainerDirs.forEach { pending.add(it) }
        } else {
            pending.add(rootDir)
        }

        val maxResults = 50
        val visited = mutableSetOf<String>()
        while (pending.isNotEmpty() && result.count < maxResults) {
            val file = pending.removeFirst()
            try { fileToDocId(rootType, file) } catch (_: FileNotFoundException) { continue }
            if (!visited.add(file.canonicalPath)) continue
            if (file.isDirectory) {
                file.listFiles()?.forEach { pending.add(it) }
            } else if (file.name.lowercase().contains(queryLower)) {
                includeFile(result, null, file, rootType)
            }
        }
        return result
    }

    override fun isChildDocument(parentDocumentId: String, documentId: String): Boolean {
        return try {
            if (parentDocumentId.substringBefore(':') != documentId.substringBefore(':')) return false
            val parent = docIdToFile(parentDocumentId).canonicalPath
            val child = docIdToFile(documentId).canonicalPath
            child == parent || child.startsWith(parent + File.separator)
        } catch (_: FileNotFoundException) { false }
    }

    override fun createDocument(
        parentDocumentId: String, mimeType: String, displayName: String
    ): String {
        DocumentPathGuard.requireName(displayName)
        val parent = docIdToParentFile(parentDocumentId)
        val rootType = parentDocumentId.substringBefore(':')

        if (rootType == ROOT_CONTAINERS && parent.absolutePath == dataDir.absolutePath) {
            throw UnsupportedOperationException(context!!.getString(R.string.tc4_documents_error_create))
        }

        var newFile = File(parent, displayName)
        var suffix = 2
        while (newFile.exists()) {
            val dot = displayName.lastIndexOf('.')
            val base = if (dot >= 0) displayName.substring(0, dot) else displayName
            val ext = if (dot >= 0) displayName.substring(dot) else ""
            newFile = File(parent, "$base ($suffix)$ext")
            suffix++
        }

        val success = if (Document.MIME_TYPE_DIR == mimeType) {
            newFile.mkdirs()
        } else {
            try {
                newFile.createNewFile()
            } catch (e: IOException) {
                throw FileNotFoundException("Failed to create ${newFile.path}: ${e.message}")
            }
        }
        if (!success) throw FileNotFoundException("Failed to create: ${newFile.path}")
        return fileToDocId(rootType, newFile)
    }

    override fun renameDocument(documentId: String, displayName: String): String {
        DocumentPathGuard.requireName(displayName)
        val file = docIdToFile(documentId)
        val rootType = documentId.substringBefore(':')
        if (file.canonicalFile == getRootDir(rootType).canonicalFile) throw FileNotFoundException("Read-only root")

        // 禁止重命名容器/公共根目录本身
        val isRootLevel = when (rootType) {
            ROOT_CONTAINERS -> file.parentFile?.absolutePath == dataDir.absolutePath
            ROOT_PUBLIC -> file.parentFile?.absolutePath == publicDir.absolutePath
            else -> false
        }
        if (isRootLevel) throw UnsupportedOperationException(context!!.getString(R.string.tc4_documents_error_rename_root))

        val newFile = File(file.parentFile!!, displayName)
        if (newFile.exists()) throw FileNotFoundException(context!!.getString(R.string.tc4_documents_error_target_exists, displayName))
        if (!file.renameTo(newFile)) throw FileNotFoundException(context!!.getString(R.string.tc4_documents_error_rename_failed, displayName))

        return fileToDocId(rootType, newFile)
    }

    override fun deleteDocument(documentId: String) {
        val file = docIdToFile(documentId)
        val rootType = documentId.substringBefore(':')
        if (file.canonicalFile == getRootDir(rootType).canonicalFile) throw FileNotFoundException("Read-only root")

        if (rootType == ROOT_CONTAINERS &&
            file.parentFile?.absolutePath == dataDir.absolutePath
        ) {
            throw UnsupportedOperationException(context!!.getString(R.string.tc4_documents_error_delete))
        }
        if (!file.delete()) throw FileNotFoundException("Failed to delete: $documentId")
    }

    // ── 辅助 ──────────────────────────────────────

    private fun includeFile(result: MatrixCursor, docId: String?, file: File?, rootType: String? = null) {
        val f: File
        val id: String

        if (docId != null) {
            id = docId
            f = docIdToFile(docId)
        } else if (file != null && rootType != null) {
            f = file
            id = fileToDocId(rootType, file)
        } else {
            return
        }

        var flags = 0
        if (f.isDirectory) {
            if (f.canWrite()) flags = flags or Document.FLAG_DIR_SUPPORTS_CREATE
        } else if (f.canWrite()) {
            flags = flags or Document.FLAG_SUPPORTS_WRITE
        }
        if (f.parentFile?.canWrite() == true) {
            flags = flags or Document.FLAG_SUPPORTS_DELETE
        }

        val mimeType = getMimeType(f)
        if (mimeType.startsWith("image/")) flags = flags or Document.FLAG_SUPPORTS_THUMBNAIL

        val row = result.newRow()
        row.add(Document.COLUMN_DOCUMENT_ID, id)
        row.add(Document.COLUMN_DISPLAY_NAME, f.name)
        row.add(Document.COLUMN_SIZE, f.length())
        row.add(Document.COLUMN_MIME_TYPE, mimeType)
        row.add(Document.COLUMN_LAST_MODIFIED, f.lastModified())
        row.add(Document.COLUMN_FLAGS, flags)
        row.add(Document.COLUMN_ICON, R.mipmap.ic_launcher)
    }

    private fun getMimeType(file: File): String {
        if (file.isDirectory) return Document.MIME_TYPE_DIR
        val name = file.name
        val dot = name.lastIndexOf('.')
        if (dot >= 0) {
            val mime = MimeTypeMap.getSingleton()
                .getMimeTypeFromExtension(name.substring(dot + 1).lowercase())
            if (mime != null) return mime
        }
        return "application/octet-stream"
    }

    private fun MatrixCursor.addRoot(
        rootId: String, title: String, summary: String, flags: Int,
        docId: String, availableBytes: Long
    ) {
        newRow()
            .add(Root.COLUMN_ROOT_ID, rootId)
            .add(Root.COLUMN_DOCUMENT_ID, docId)
            .add(Root.COLUMN_SUMMARY, summary)
            .add(Root.COLUMN_FLAGS, flags)
            .add(Root.COLUMN_TITLE, title)
            .add(Root.COLUMN_MIME_TYPES, ALL_MIME_TYPES)
            .add(Root.COLUMN_AVAILABLE_BYTES, availableBytes)
            .add(Root.COLUMN_ICON, R.mipmap.ic_launcher)
    }
}
