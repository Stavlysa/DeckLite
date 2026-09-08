// LauncherShortcutDialogFragment.kt -- This file is part of tiny_container.
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

import android.app.Dialog
import android.content.DialogInterface
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.drawable.Icon
import android.os.Bundle
import android.view.WindowManager
import androidx.fragment.app.DialogFragment
import coil.imageLoader
import coil.request.ImageRequest
import coil.request.SuccessResult
import androidx.lifecycle.lifecycleScope
import coil.decode.SvgDecoder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.fct.tc4.R
import com.fct.tc4.databinding.Tc4DialogLauncherShortcutBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.snackbar.Snackbar
import java.io.File

/**
 * 启动器捷径生成器对话框。
 *
 * 用户输入名称和命令，点击"生成"创建桌面捷径。
 * 点击"快速填充"弹出 [DesktopFilePickerDialogFragment] 选择 .desktop 文件，
 * 选择结果通过 Fragment Result API 回填到输入框。
 *
 * 旋转保持：onSaveInstanceState 保存输入框内容；Fragment Result 由 FragmentManager 在重建后重新投递。
 */
class LauncherShortcutDialogFragment : DialogFragment() {

    private var _binding: Tc4DialogLauncherShortcutBinding? = null
    private val binding get() = _binding!!

    /** 用户从选择器选取的 desktop 文件对应的图标路径（可能为 null） */
    private var pendingIconPath: String? = null

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        _binding = Tc4DialogLauncherShortcutBinding.inflate(requireActivity().layoutInflater)

        binding.nameInput.setText(
            savedInstanceState?.getString(SAVED_NAME) ?: ""
        )
        binding.cmdInput.setText(
            savedInstanceState?.getString(SAVED_CMD) ?: ""
        )
        pendingIconPath = savedInstanceState?.getString(SAVED_ICON)

        // 监听 DesktopFilePickerDialogFragment 的选择结果
        childFragmentManager.setFragmentResultListener(
            DesktopFilePickerDialogFragment.REQUEST_DESKTOP_PICK,
            this,
        ) { _, bundle ->
            val name = bundle.getString(DesktopFilePickerDialogFragment.KEY_NAME) ?: return@setFragmentResultListener
            val command = bundle.getString(DesktopFilePickerDialogFragment.KEY_CMD) ?: return@setFragmentResultListener
            binding.nameInput.setText(name)
            binding.cmdInput.setText(command)
            binding.nameLayout.error = null
            binding.commandLayout.error = null
            pendingIconPath = bundle.getString(DesktopFilePickerDialogFragment.KEY_ICON)
        }

        return MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.tc4_shortcut_dialog_title)
            .setView(binding.root)
            .setNeutralButton(R.string.tc4_btn_quick_fill, null)
            .setNegativeButton(R.string.tc4_btn_cancel, null)
            .setPositiveButton(R.string.tc4_btn_generate, null)
            .create()
            .also { dialog ->
                dialog.window?.setSoftInputMode(
                    WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
                            or WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN
                )
            }
    }

    override fun onStart() {
        super.onStart()
        val alertDialog = dialog as? androidx.appcompat.app.AlertDialog ?: return
        val code = requireArguments().getString(ARG_CODE) ?: ""

        // Neutral: 快速填充
        alertDialog.getButton(DialogInterface.BUTTON_NEUTRAL).setOnClickListener {
            DesktopFilePickerDialogFragment.newInstance(code)
                .show(childFragmentManager, DesktopFilePickerDialogFragment.REQUEST_DESKTOP_PICK)
        }

        // Positive: 生成
        alertDialog.getButton(DialogInterface.BUTTON_POSITIVE).setOnClickListener {
            val name = binding.nameInput.text?.toString()?.trim() ?: ""
            val command = binding.cmdInput.text?.toString()?.trim() ?: ""

            if (name.isEmpty()) {
                binding.nameLayout.error = getString(R.string.tc4_validate_name_empty)
                return@setOnClickListener
            }
            if (command.isEmpty()) {
                binding.commandLayout.error = getString(R.string.tc4_validate_command_empty)
                return@setOnClickListener
            }
            binding.nameLayout.error = null
            binding.commandLayout.error = null

            lifecycleScope.launch {
                createDesktopShortcut(name, code, command, pendingIconPath)
                dismiss()
            }
        }

        // Negative: 取消
        alertDialog.getButton(DialogInterface.BUTTON_NEGATIVE).setOnClickListener {
            dismiss()
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(SAVED_NAME, binding.nameInput.text?.toString() ?: "")
        outState.putString(SAVED_CMD, binding.cmdInput.text?.toString() ?: "")
        outState.putString(SAVED_ICON, pendingIconPath)
    }

    override fun onCancel(dialog: DialogInterface) {
        super.onCancel(dialog)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    // ===================== 桌面捷径创建 =====================

    private suspend fun createDesktopShortcut(name: String, code: String, command: String, iconPath: String?) {
        val context = requireContext()
        val vault = LauncherCommandVault(File(context.noBackupFilesDir, "launcher-commands"))
        val token = try {
            vault.create(code, command)
        } catch (_: Exception) {
            Snackbar.make(binding.root, R.string.tc4_shortcut_secure_create_failed, Snackbar.LENGTH_LONG).show()
            return
        }
        val intent = android.content.Intent(context, com.fct.tc4.ui.main.MainActivity::class.java).apply {
            action = "com.fct.tc4.action.SHORTCUT"
            putExtra(LauncherCommandVault.EXTRA_TOKEN, token)
            addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val icon = iconPath?.takeIf { File(it).isFile }?.let { path ->
                val bitmap = if (path.lowercase().endsWith(".svg")) {
                    withContext(Dispatchers.IO) {
                        try {
                            val request = ImageRequest.Builder(context)
                                .decoderFactory(SvgDecoder.Factory())
                                .data(File(path))
                                .size(96)
                                .build()
                            val result = context.imageLoader.execute(request)
                            if (result is SuccessResult) {
                                val drawable = result.drawable
                                Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888).also { bmp ->
                                    drawable.setBounds(0, 0, bmp.width, bmp.height)
                                    drawable.draw(Canvas(bmp))
                                }
                            } else null
                        } catch (_: Exception) { null }
                    }
                } else {
                    withContext(Dispatchers.IO) {
                        BitmapFactory.decodeFile(path)
                    }
                }
                bitmap?.let { Icon.createWithBitmap(it) }
            } ?: Icon.createWithResource(context, R.drawable.icon_placeholder)

            @Suppress("DEPRECATION")
            val info = android.content.pm.ShortcutInfo.Builder(context, "tc4_sc_${code}_${System.currentTimeMillis()}")
                .setShortLabel(name)
                .setLongLabel(name)
                .setIcon(icon)
                .setIntent(intent)
                .build()

            val manager = context.getSystemService(android.content.pm.ShortcutManager::class.java)
            if (manager.isRequestPinShortcutSupported) {
                @Suppress("DEPRECATION")
                if (!manager.requestPinShortcut(info, null)) vault.revoke(token)
            } else {
                vault.revoke(token)
                binding.root?.let {
                    Snackbar.make(it, R.string.tc4_shortcut_pin_unsupported, Snackbar.LENGTH_SHORT).show()
                }
            }
        }
    }

    companion object {
        private const val SAVED_NAME = "saved_name"
        private const val SAVED_CMD = "saved_cmd"
        private const val SAVED_ICON = "saved_icon"

        private const val ARG_CODE = "arg_code"

        fun newInstance(code: String) = LauncherShortcutDialogFragment().apply {
            arguments = Bundle().apply { putString(ARG_CODE, code) }
        }
    }
}
