package com.example.myapplication.ui.auth

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.databinding.ActivitySplashBinding
import com.example.myapplication.ui.main.MainActivity
import io.github.jan.supabase.gotrue.SessionStatus
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import com.example.myapplication.data.api.SupabaseManager

/**
 * SplashActivity — màn hình loading khi khởi động.
 * Hiển thị logo + spinner, kiểm tra session Supabase,
 * sau đó redirect sang LoginActivity hoặc MainActivity.
 */
class SplashActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySplashBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivitySplashBinding.inflate(layoutInflater)
        setContentView(binding.root)

        checkAuthAndNavigate()
    }

    private fun checkAuthAndNavigate() {
        // Always show splash at least 1.5 seconds for polish
        val minimumSplashMs = 1500L
        val startTime = System.currentTimeMillis()

        lifecycleScope.launch {
            // Wait for Supabase to restore session from local storage
            val status = SupabaseManager.auth.sessionStatus.first { 
                it !is SessionStatus.LoadingFromStorage 
            }

            val elapsed = System.currentTimeMillis() - startTime
            val remaining = (minimumSplashMs - elapsed).coerceAtLeast(0)

            // Delay only remaining time to complete minimum splash duration
            Handler(Looper.getMainLooper()).postDelayed({
                when (status) {
                    is SessionStatus.Authenticated -> goToMain()
                    else -> goToLogin()
                }
            }, remaining)
        }
    }

    private fun goToMain() {
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }

    private fun goToLogin() {
        startActivity(Intent(this, LoginActivity::class.java))
        finish()
    }
}
