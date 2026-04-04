package com.example.myapplication.ui.main

import android.content.Intent
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.animation.AccelerateDecelerateInterpolator
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.core.view.ViewCompat
import androidx.core.view.updateLayoutParams
import androidx.core.view.updatePadding
import androidx.core.view.WindowInsetsCompat
import androidx.fragment.app.Fragment
import com.example.myapplication.R
import com.example.myapplication.data.preferences.AppPreferences
import com.example.myapplication.data.repository.AuthRepository
import com.example.myapplication.databinding.ActivityMainBinding
import com.example.myapplication.ui.auth.LoginActivity
import com.example.myapplication.ui.analytics.AnalyticsFragment
import com.example.myapplication.ui.bills.BillsFragment
import com.example.myapplication.ui.home.HomeFragment
import com.example.myapplication.ui.onboarding.OnboardingActivity
import com.example.myapplication.ui.profile.ProfileFragment
import com.example.myapplication.ui.scan.ScanFragment

class MainActivity : AppCompatActivity(), MainTabController {

    private lateinit var binding: ActivityMainBinding
    private val authRepository = AuthRepository()
    private var currentTabId: Int = ViewId.NONE
    private var systemBottomInset: Int = 0

    private val bottomBarBaseMargin by lazy {
        resources.getDimensionPixelSize(R.dimen.main_bottom_bar_margin_bottom)
    }
    private val bottomBarHeight by lazy {
        resources.getDimensionPixelSize(R.dimen.main_bottom_bar_height)
    }
    private val bottomBarDockOffset by lazy {
        resources.getDimensionPixelSize(R.dimen.main_bottom_bar_dock_offset)
    }
    private val scanFabSize by lazy {
        resources.getDimensionPixelSize(R.dimen.main_scan_fab_size)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        if (redirectIfNeeded()) return

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        currentTabId = savedInstanceState?.getInt(STATE_CURRENT_TAB, ViewId.NONE) ?: ViewId.NONE
        bindWindowInsets()
        bindNavigation()

        if (savedInstanceState == null) {
            openTab(R.id.navHome)
        } else {
            updateNavigationChrome(currentTabId)
        }
    }

    override fun openTab(itemId: Int) {
        if (currentTabId == itemId) return

        val fragment: Fragment = when (itemId) {
            R.id.navHome -> HomeFragment()
            R.id.navScan -> ScanFragment()
            R.id.navBills -> BillsFragment()
            R.id.navAnalytics -> AnalyticsFragment()
            R.id.navProfile -> ProfileFragment()
            else -> return
        }

        currentTabId = itemId
        updateNavigationChrome(itemId)

        supportFragmentManager.beginTransaction()
            .setReorderingAllowed(true)
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragmentContainer, fragment)
            .commit()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putInt(STATE_CURRENT_TAB, currentTabId)
    }

    private fun bindNavigation() {
        navigationButtons.forEach { item ->
            item.view.setOnClickListener { openTab(item.itemId) }
            item.view.setOnTouchListener(ScaleOnPressTouchListener())
        }

        binding.btnScanFab.setOnClickListener { openTab(R.id.navScan) }
        binding.btnScanFab.setOnTouchListener(ScaleOnPressTouchListener(pressedScale = 0.92f))
    }

    private fun updateNavigationChrome(itemId: Int) {
        val isScanTab = itemId == R.id.navScan
        binding.bottomDockContainer.isVisible = !isScanTab
        binding.btnScanFab.isVisible = !isScanTab
        updateFragmentBottomPadding(isScanTab)

        navigationButtons.forEach { item ->
            item.view.isSelected = item.itemId == itemId
        }
    }

    private fun bindWindowInsets() {
        ViewCompat.setOnApplyWindowInsetsListener(binding.mainRoot) { _, insets ->
            val navigationInset = insets.getInsets(WindowInsetsCompat.Type.navigationBars()).bottom
            val gestureInset = insets.getInsets(WindowInsetsCompat.Type.systemGestures()).bottom
            systemBottomInset = maxOf(navigationInset, gestureInset)

            binding.bottomDockContainer.updateLayoutParams<ViewGroup.MarginLayoutParams> {
                bottomMargin = bottomBarBaseMargin + systemBottomInset
            }
            updateFragmentBottomPadding(currentTabId == R.id.navScan)

            insets
        }
        ViewCompat.requestApplyInsets(binding.mainRoot)
    }

    private fun updateFragmentBottomPadding(isScanTab: Boolean) {
        val bottomPadding = if (isScanTab) {
            0
        } else {
            bottomBarHeight + bottomBarDockOffset + bottomBarBaseMargin + systemBottomInset
        }
        binding.fragmentContainer.updatePadding(bottom = bottomPadding)
    }

    private fun redirectIfNeeded(): Boolean {
        val appPreferences = AppPreferences(this)
        val destination = when {
            !appPreferences.hasCompletedOnboarding -> Intent(this, OnboardingActivity::class.java)
            authRepository.getUserId() == null -> Intent(this, LoginActivity::class.java)
            else -> null
        } ?: return false

        destination.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        startActivity(destination)
        finish()
        return true
    }

    private val navigationButtons by lazy {
        listOf(
            NavigationItem(R.id.navHome, binding.navHomeButton),
            NavigationItem(R.id.navBills, binding.navBillsButton),
            NavigationItem(R.id.navAnalytics, binding.navAnalyticsButton),
            NavigationItem(R.id.navProfile, binding.navProfileButton)
        )
    }

    private object ViewId {
        const val NONE = -1
    }

    private data class NavigationItem(
        val itemId: Int,
        val view: View
    )

    private class ScaleOnPressTouchListener(
        private val pressedScale: Float = 0.95f
    ) : View.OnTouchListener {

        private val interpolator = AccelerateDecelerateInterpolator()

        override fun onTouch(view: View, event: MotionEvent): Boolean {
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> animate(view, pressedScale)
                MotionEvent.ACTION_UP,
                MotionEvent.ACTION_CANCEL -> animate(view, 1f)
            }
            return false
        }

        private fun animate(view: View, scale: Float) {
            view.animate()
                .scaleX(scale)
                .scaleY(scale)
                .setDuration(if (scale < 1f) 110L else 150L)
                .setInterpolator(interpolator)
                .start()
        }
    }

    companion object {
        private const val STATE_CURRENT_TAB = "state_current_tab"
    }
}
