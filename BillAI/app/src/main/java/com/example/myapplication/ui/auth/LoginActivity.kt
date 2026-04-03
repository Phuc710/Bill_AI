package com.example.myapplication.ui.auth

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.example.myapplication.data.api.SupabaseManager
import com.example.myapplication.databinding.ActivityLoginBinding
import com.example.myapplication.ui.main.MainActivity
import io.github.jan.supabase.gotrue.SessionStatus
import io.github.jan.supabase.gotrue.handleDeeplinks
import io.github.jan.supabase.gotrue.providers.Google
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding

    // Guard: chỉ navigate một lần duy nhất tránh double-navigate
    private var hasNavigated = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)
        
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        // Bước 1: Nếu app được mở từ OAuth callback deeplink → báo cho SDK parse token
        processDeepLink(intent)

        // Bước 2: Lắng nghe session status thay đổi
        observeSessionStatus()

        // Bước 3: Xử lý nút đăng nhập
        binding.btnGoogleLogin.setOnClickListener {
            startGoogleLogin()
        }
    }

    /**
     * Gọi khi Activity đang chạy và nhận deeplink mới (launchMode = singleTask).
     * Trường hợp này xảy ra khi Google OAuth callback trả về mà app vẫn còn sống.
     */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        Log.d(TAG, "onNewIntent: data=${intent.data}")
        processDeepLink(intent)
    }

    /**
     * Gọi handleDeeplinks() để SDK parse access_token / refresh_token
     * từ URL fragment của callback deeplink (billai://auth/callback#access_token=...).
     *
     * PHẢI gọi hàm này TRƯỚC khi observe sessionStatus, để SDK kịp import session.
     */
    private fun processDeepLink(intent: Intent?) {
        val uri = intent?.data
        Log.d(TAG, "processDeepLink: uri=$uri")

        if (uri != null) {
            try {
                // SDK sẽ tự parse token từ URI và cập nhật sessionStatus
                SupabaseManager.client.handleDeeplinks(intent)
                Log.d(TAG, "handleDeeplinks called successfully")
            } catch (e: Exception) {
                Log.e(TAG, "handleDeeplinks error", e)
            }
        }
    }

    /**
     * Quan sát sessionStatus từ Supabase Auth.
     * Dùng repeatOnLifecycle(STARTED) để tự động cancel khi app vào background
     * và resume khi app trở lại foreground — an toàn về memory leak.
     */
    private fun observeSessionStatus() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                SupabaseManager.auth.sessionStatus.collect { status ->
                    Log.d(TAG, "SessionStatus changed: $status")
                    handleSessionStatus(status)
                }
            }
        }
    }

    private fun handleSessionStatus(status: SessionStatus) {
        when (status) {
            is SessionStatus.Authenticated -> {
                Log.d(TAG, "✅ Authenticated! Navigating to MainActivity...")
                navigateToMain()
            }

            is SessionStatus.NotAuthenticated -> {
                // Chưa đăng nhập, hiển thị màn login bình thường
                Log.d(TAG, "Not authenticated — showing login screen")
                setLoginUiEnabled(true)
            }

            is SessionStatus.LoadingFromStorage -> {
                // Đang load session từ bộ nhớ (SharedPreferences) khi khởi động app
                Log.d(TAG, "Loading session from storage...")
                setLoginUiEnabled(false)
            }

            is SessionStatus.NetworkError -> {
                Log.e(TAG, "Network error while loading session")
                setLoginUiEnabled(true)
                Toast.makeText(this, "Lỗi kết nối mạng", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun startGoogleLogin() {
        setLoginUiEnabled(false)

        lifecycleScope.launch {
            try {
                Log.d(TAG, "Starting Google OAuth flow...")
                // SDK sẽ mở Chrome Custom Tab để user đăng nhập Google
                // Sau khi xong, Google redirect về Supabase, rồi về billai://auth/callback
                SupabaseManager.auth.signInWith(
                    provider = Google,
                    redirectUrl = REDIRECT_URL
                )
            } catch (e: Exception) {
                Log.e(TAG, "Google login error", e)
                setLoginUiEnabled(true)
                Toast.makeText(
                    this@LoginActivity,
                    "Đăng nhập thất bại: ${e.message}",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun navigateToMain() {
        // Guard: tránh navigate nhiều lần nếu sessionStatus emit nhiều lần
        if (hasNavigated || isFinishing || isDestroyed) return
        hasNavigated = true

        Log.d(TAG, "Navigating to MainActivity")
        startActivity(
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            }
        )
        finish()
    }

    private fun setLoginUiEnabled(enabled: Boolean) {
        binding.btnGoogleLogin.isEnabled = enabled
        // Nếu có progress bar thì bật/tắt ở đây
        // binding.progressBar.visibility = if (enabled) View.GONE else View.VISIBLE
    }

    companion object {
        private const val TAG = "AUTH"
        // Phải khớp với: AndroidManifest scheme="billai" host="auth" path="/callback"
        // Và khớp với redirectUrl được đăng ký trong Supabase Dashboard
        const val REDIRECT_URL = "billai://auth/callback"
    }
}
