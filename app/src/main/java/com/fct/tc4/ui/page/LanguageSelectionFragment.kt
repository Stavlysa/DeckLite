package com.fct.tc4.ui.page

import android.os.Bundle
import android.view.View
import android.widget.RadioButton
import android.widget.RadioGroup
import androidx.fragment.app.Fragment
import com.fct.tc4.R
import com.fct.tc4.ui.main.MainActivity
import com.fct.tc4.ui.misc.AppLanguage
import com.fct.tc4.ui.misc.AppLanguageOptions
import com.google.android.material.button.MaterialButton
import com.google.android.material.radiobutton.MaterialRadioButton

class LanguageSelectionFragment : Fragment(R.layout.tc4_fragment_language_selection) {
    private var selectedTag = "en"

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        requireActivity().setTitle(R.string.tc4_language_welcome)
        selectedTag = savedInstanceState?.getString("selected_tag")
            ?.takeIf(AppLanguageOptions::isSupported) ?: AppLanguage.currentTag(requireContext())
        val group = view.findViewById<RadioGroup>(R.id.language_choices)
        AppLanguageOptions.choices.forEach { choice ->
            group.addView(MaterialRadioButton(requireContext()).apply {
                id = View.generateViewId()
                tag = choice.tag
                text = choice.nativeName
                textSize = 18f
                minHeight = (56 * resources.displayMetrics.density).toInt()
                layoutParams = RadioGroup.LayoutParams(
                    RadioGroup.LayoutParams.MATCH_PARENT, RadioGroup.LayoutParams.WRAP_CONTENT)
                isChecked = choice.tag == selectedTag
            })
        }
        group.setOnCheckedChangeListener { radioGroup, checkedId ->
            selectedTag = radioGroup.findViewById<RadioButton>(checkedId).tag as String
        }
        view.findViewById<MaterialButton>(R.id.language_continue).setOnClickListener {
            (requireActivity() as MainActivity).completeLanguageSelection(selectedTag)
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("selected_tag", selectedTag)
        super.onSaveInstanceState(outState)
    }
}
