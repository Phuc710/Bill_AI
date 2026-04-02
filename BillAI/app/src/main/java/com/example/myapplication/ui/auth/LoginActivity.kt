package com.example.myapplication.ui.auth

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.myapplication.data.api.SupabaseManager
import com.example.myapplication.databinding.ActivityLoginBinding
import com.example.myapplication.ui.main.MainActivity
import io.github.jan.supabase.gotrue.SessionStatus
import io.github.jan.supabase.gotrue.providers.Google
import kotlinx.coroutines.launch

/**
 * LoginActivity — Đăng nhập bằng Google qua Supabase OAuth.
 * Lần đầu mở app: hiển thị màn login.
 * Nếu đã có session hợp lệ → SplashActivity sẽ redirect thẳng vào Main.
 */
class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Handle OAuth callback from browser deep link (billai://callback)
        handleAuthCallback()

        binding.btnGoogleLogin.setOnClickListener {
            startGoogleLogin()
        }
    }

    /**
     * Supabase GoTrue Android SDK xử lý deep link tự động khi Intent có data.
     * Đây là nơi chúng ta lắng nghe kết quả sau khi callback về.
     */
    private fun handleAuthCallback() {
        lifecycleScope.launch {
            SupabaseManager.auth.sessionStatus.collect { status ->
                when (status) {
                    is SessionStatus.Authenticated -> navigateToMain()
                    is SessionStatus.NotAuthenticated -> { /* User chưa login, ở lại màn hình này */ }
                    else -> { /* LoadingFromStorage — chờ */ }
                }
            }
        }
    }

    private fun startGoogleLogin() {
        lifecycleScope.launch {
            try {
                SupabaseManager.auth.loginWith(Google) {
                    // Redirect URI must match what's registered in Supabase Dashboard:
                    // Authentication > URL Configuration > Redirect URLs: billai://callback
                    redirectUrl = "billai://callback"
                }
            } catch (e: Exception) {
                Toast.makeText(this@LoginActivity, "Login thất bại: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun navigateToMain() {
        val intent = Intent(this, MainActivity::class.java)
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        startActivity(intent)
        finish()
    }
}
