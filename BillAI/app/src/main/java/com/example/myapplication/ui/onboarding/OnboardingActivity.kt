package com.example.myapplication.ui.onboarding

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.example.myapplication.data.preferences.AppPreferences
import com.example.myapplication.databinding.ActivityOnboardingBinding
import com.example.myapplication.ui.splash.SplashActivity

class OnboardingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityOnboardingBinding
    private lateinit var appPreferences: AppPreferences

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityOnboardingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        appPreferences = AppPreferences(this)

        binding.btnStart.setOnClickListener { completeOnboarding() }
        binding.btnSkip.setOnClickListener { completeOnboarding() }
    }

    private fun completeOnboarding() {
        appPreferences.hasCompletedOnboarding = true
        startActivity(
            Intent(this, SplashActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            }
        )
        finish()
    }
}
