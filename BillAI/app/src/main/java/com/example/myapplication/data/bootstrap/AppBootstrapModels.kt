package com.example.myapplication.data.bootstrap

import com.example.myapplication.data.model.BillSummary

data class AppBootstrapConfig(
    val preloadBillsLimit: Int = 100,
    val cacheTtlMs: Long = 60_000L
)

data class AppSessionUser(
    val id: String,
    val email: String,
    val displayName: String,
    val avatarUrl: String?
)

data class AppSessionSnapshot(
    val user: AppSessionUser,
    val bills: List<BillSummary>,
    val config: AppBootstrapConfig,
    val loadedAtMillis: Long = System.currentTimeMillis(),
    val syncSucceeded: Boolean = true,
    val syncErrorMessage: String? = null
) {
    val recentBills: List<BillSummary>
        get() = bills.take(5)
}

enum class AppLaunchDestination {
    ONBOARDING,
    LOGIN,
    MAIN
}

enum class AppBootstrapStep {
    PREPARING,
    CHECKING_AUTH,
    LOADING_PROFILE,
    LOADING_HOME,
    FINALIZING
}
