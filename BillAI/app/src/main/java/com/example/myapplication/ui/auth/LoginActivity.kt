package com.example.myapplication.ui.auth

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.example.myapplication.R
import com.example.myapplication.data.api.SupabaseManager
import com.example.myapplication.databinding.ActivityLoginBinding
import com.example.myapplication.ui.splash.SplashActivity
import io.github.jan.supabase.gotrue.SessionStatus
import io.github.jan.supabase.gotrue.handleDeeplinks
import io.github.jan.supabase.gotrue.providers.Google
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    private var hasNavigated = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        processDeepLink(intent)
        observeSessionStatus()

        binding.btnGoogleLogin.setOnClickListener {
            startGoogleLogin()
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        processDeepLink(intent)
    }

    private fun processDeepLink(intent: Intent?) {
        val uri = intent?.data ?: return
        runCatching {
            Log.d(TAG, "Processing deeplink: $uri")
            SupabaseManager.client.handleDeeplinks(intent)
        }.onFailure {
            Log.e(TAG, "Unable to parse deeplink", it)
        }
    }

    private fun observeSessionStatus() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                SupabaseManager.auth.sessionStatus.collect(::handleSessionStatus)
            }
        }
    }

    private fun handleSessionStatus(status: SessionStatus) {
        when (status) {
            is SessionStatus.Authenticated -> navigateToBootstrap()
            is SessionStatus.LoadingFromStorage -> setLoginState(isLoading = true)
            is SessionStatus.NotAuthenticated -> setLoginState(isLoading = false)
            is SessionStatus.NetworkError -> {
                setLoginState(isLoading = false)
                Toast.makeText(this, getString(R.string.login_error_network), Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun startGoogleLogin() {
        setLoginState(isLoading = true)
        lifecycleScope.launch {
            runCatching {
                SupabaseManager.auth.signInWith(
                    provider = Google,
                    redirectUrl = REDIRECT_URL
                )
            }.onFailure { error ->
                setLoginState(isLoading = false)
                Toast.makeText(
                    this@LoginActivity,
                    getString(R.string.login_error_failed, error.message ?: ""),
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun navigateToBootstrap() {
        if (hasNavigated || isFinishing || isDestroyed) return
        hasNavigated = true
        startActivity(
            Intent(this, SplashActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            }
        )
        finish()
    }

    private fun setLoginState(isLoading: Boolean) {
        binding.progressLogin.isVisible = isLoading
        binding.btnGoogleLogin.isEnabled = !isLoading
        binding.tvLoginFootnote.isVisible = !isLoading
    }

    companion object {
        private const val TAG = "LoginActivity"
        const val REDIRECT_URL = "billai://auth/callback"
    }
}
