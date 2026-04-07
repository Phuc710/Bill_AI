package com.example.myapplication.data.preferences

import android.content.Context

class AppPreferences(context: Context) {

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var hasCompletedOnboarding: Boolean
        get() = prefs.getBoolean(KEY_ONBOARDING_DONE, false)
        set(value) = prefs.edit().putBoolean(KEY_ONBOARDING_DONE, value).apply()

    companion object {
        private const val PREFS_NAME = "bill_ai_prefs"
        private const val KEY_ONBOARDING_DONE = "key_onboarding_done"
    }
}
