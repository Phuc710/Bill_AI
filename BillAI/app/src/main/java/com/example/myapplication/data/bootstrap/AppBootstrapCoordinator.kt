package com.example.myapplication.data.bootstrap

import android.content.Context
import com.example.myapplication.R
import com.example.myapplication.data.preferences.AppPreferences
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.data.repository.BillRepository

class AppBootstrapCoordinator(
    context: Context,
    private val authRepository: AuthRepository = AuthRepository(),
    private val billRepository: BillRepository = BillRepository(),
    private val appPreferences: AppPreferences = AppPreferences(context.applicationContext)
) {

    suspend fun bootstrap(
        onStep: (AppBootstrapStep) -> Unit = {}
    ): AppLaunchDestination {
        onStep(AppBootstrapStep.PREPARING)
        if (!appPreferences.hasCompletedOnboarding) {
            AppSessionStore.clear()
            return AppLaunchDestination.ONBOARDING
        }

        onStep(AppBootstrapStep.CHECKING_AUTH)
        val userId = authRepository.getUserId()
        if (userId.isNullOrBlank()) {
            AppSessionStore.clear()
            return AppLaunchDestination.LOGIN
        }

        ensureSession(forceRefresh = false, onStep = onStep)
        onStep(AppBootstrapStep.FINALIZING)
        return AppLaunchDestination.MAIN
    }

    suspend fun ensureSession(
        forceRefresh: Boolean = false,
        onStep: (AppBootstrapStep) -> Unit = {}
    ): Result<AppSessionSnapshot> {
        onStep(AppBootstrapStep.CHECKING_AUTH)
        val userId = authRepository.getUserId()
            ?: return Result.failure(IllegalStateException("Missing authenticated user"))

        val config = AppBootstrapConfig()
        val cachedSnapshot = AppSessionStore.currentSnapshot(userId)
        if (!forceRefresh && cachedSnapshot != null && !isExpired(cachedSnapshot, config)) {
            return Result.success(cachedSnapshot)
        }

        onStep(AppBootstrapStep.LOADING_PROFILE)
        val fallbackDisplayName = authRepository.getUserEmail()
            .orEmpty()
            .substringBefore("@")
            .ifBlank { "Bill AI" }
        val user = AppSessionUser(
            id = userId,
            email = authRepository.getUserEmail().orEmpty(),
            displayName = authRepository.getUserDisplayName().orEmpty().ifBlank { fallbackDisplayName },
            avatarUrl = authRepository.getUserAvatarUrl()
        )

        onStep(AppBootstrapStep.LOADING_HOME)
        val snapshot = billRepository.listBills(
            userId = userId,
            page = 1,
            limit = config.preloadBillsLimit
        ).fold(
            onSuccess = { response ->
                AppSessionSnapshot(
                    user = user,
                    bills = response.data,
                    config = config,
                    syncSucceeded = true
                )
            },
            onFailure = { error ->
                AppSessionSnapshot(
                    user = user,
                    bills = cachedSnapshot?.bills.orEmpty(),
                    config = config,
                    syncSucceeded = false,
                    syncErrorMessage = error.message
                )
            }
        )

        AppSessionStore.update(snapshot)
        onStep(AppBootstrapStep.FINALIZING)
        return Result.success(snapshot)
    }

    fun stepLabelRes(step: AppBootstrapStep): Int {
        return when (step) {
            AppBootstrapStep.PREPARING -> R.string.splash_status_preparing
            AppBootstrapStep.CHECKING_AUTH -> R.string.splash_status_auth
            AppBootstrapStep.LOADING_PROFILE -> R.string.splash_status_profile
            AppBootstrapStep.LOADING_HOME -> R.string.splash_status_home
            AppBootstrapStep.FINALIZING -> R.string.splash_status_finalizing
        }
    }

    private fun isExpired(
        snapshot: AppSessionSnapshot,
        config: AppBootstrapConfig
    ): Boolean {
        return snapshot.loadedAtMillis <= 0L ||
            (System.currentTimeMillis() - snapshot.loadedAtMillis) > config.cacheTtlMs
    }
}
