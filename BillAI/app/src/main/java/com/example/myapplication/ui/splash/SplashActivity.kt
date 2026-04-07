package com.example.myapplication.ui.splash

import android.content.Intent
import android.os.Bundle
import android.os.SystemClock
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.data.bootstrap.AppBootstrapCoordinator
import com.example.myapplication.data.bootstrap.AppBootstrapStep
import com.example.myapplication.data.bootstrap.AppLaunchDestination
import com.example.myapplication.databinding.ActivitySplashBinding
import com.example.myapplication.ui.auth.LoginActivity
import com.example.myapplication.ui.main.MainActivity
import com.example.myapplication.ui.onboarding.OnboardingActivity
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class SplashActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySplashBinding
    private lateinit var bootstrapCoordinator: AppBootstrapCoordinator

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivitySplashBinding.inflate(layoutInflater)
        setContentView(binding.root)
        bootstrapCoordinator = AppBootstrapCoordinator(applicationContext)

        lifecycleScope.launch {
            val startedAt = SystemClock.elapsedRealtime()
            renderStep(AppBootstrapStep.PREPARING)

            val destination = bootstrapCoordinator.bootstrap(::renderStep)
            val elapsed = SystemClock.elapsedRealtime() - startedAt
            if (elapsed < MIN_SPLASH_DURATION_MS) {
                delay(MIN_SPLASH_DURATION_MS - elapsed)
            }

            startActivity(
                when (destination) {
                    AppLaunchDestination.ONBOARDING ->
                        Intent(this@SplashActivity, OnboardingActivity::class.java)
                    AppLaunchDestination.LOGIN ->
                        Intent(this@SplashActivity, LoginActivity::class.java)
                    AppLaunchDestination.MAIN ->
                        Intent(this@SplashActivity, MainActivity::class.java)
                }.apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                }
            )
            finish()
        }
    }

    private fun renderStep(step: AppBootstrapStep) {
        binding.tvSplashStatus.setText(bootstrapCoordinator.stepLabelRes(step))
    }

    companion object {
        private const val MIN_SPLASH_DURATION_MS = 350L
    }
}
