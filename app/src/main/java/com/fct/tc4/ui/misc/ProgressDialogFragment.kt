// ProgressDialogFragment.kt -- This file is part of tiny_container.
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
import android.os.Bundle
import android.view.View
import androidx.fragment.app.DialogFragment
import androidx.fragment.app.FragmentManager
import com.fct.tc4.databinding.Tc4DialogProgressBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/**
 * 通用不可取消的加载中对话框 DialogFragment。
 *
 * 用法：
 *   val dialog = ProgressDialogFragment
 *       .newBuilder(childFragmentManager)
 *       .title("正在删除...")
 *       .show("delete_progress")
 *   // 更新：
 *   dialog?.updateTitle("正在删除容器文件...")
 *   // 完成后：
 *   dialog?.dismiss()
 */
class ProgressDialogFragment : DialogFragment() {

    private var _binding: Tc4DialogProgressBinding? = null
    private val binding get() = _binding!!
    private var pendingTitle: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setCancelable(false)
    }

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        _binding = Tc4DialogProgressBinding.inflate(requireActivity().layoutInflater)

        val title = pendingTitle ?: arguments?.getString(ARG_TITLE)
        pendingTitle = null
        binding.title.text = title
        binding.title.visibility = if (title != null) View.VISIBLE else View.GONE

        return MaterialAlertDialogBuilder(requireContext())
            .setView(binding.root)
            .create()
    }

    fun updateTitle(title: String?) {
        if (_binding == null) {
            pendingTitle = title
            return
        }
        if (title != null) {
            binding.title.text = title
            binding.title.visibility = View.VISIBLE
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        private const val ARG_TITLE = "title"

        fun newBuilder(fragmentManager: FragmentManager): Builder = Builder(fragmentManager)
    }

    class Builder(private val fragmentManager: FragmentManager) {
        private var title: String? = null

        fun title(value: String?) = apply { title = value }

        fun show(tag: String = "progress_${hashCode()}"): ProgressDialogFragment? {
            if (fragmentManager.findFragmentByTag(tag) != null) return null
            val fragment = ProgressDialogFragment().apply {
                arguments = Bundle().apply {
                    putString(ARG_TITLE, title)
                }
            }
            fragment.show(fragmentManager, tag)
            return fragment
        }
    }
}
