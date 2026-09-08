package com.fct.tc4.ui.misc

import android.app.Dialog
import android.os.Bundle
import android.widget.Toast
import androidx.fragment.app.DialogFragment
import com.fct.tc4.R
import com.google.android.material.dialog.MaterialAlertDialogBuilder

class AppLanguageDialogFragment : DialogFragment() {
    private var selectedTag = "en"

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        selectedTag = savedInstanceState?.getString("selected_tag")
            ?.takeIf(AppLanguageOptions::isSupported) ?: AppLanguage.currentTag(requireContext())
        val choices = AppLanguageOptions.choices
        return MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.tc4_language_title)
            .setSingleChoiceItems(choices.map { it.nativeName }.toTypedArray(),
                choices.indexOfFirst { it.tag == selectedTag }) { _, index ->
                selectedTag = choices[index].tag
            }
            .setPositiveButton(android.R.string.ok) { _, _ ->
                if (AppLanguage.markChosen(requireContext(), selectedTag)) {
                    AppLanguage.apply(selectedTag)
                } else Toast.makeText(requireContext(), R.string.tc4_language_save_failed,
                    Toast.LENGTH_LONG).show()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .create()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("selected_tag", selectedTag)
        super.onSaveInstanceState(outState)
    }
}
