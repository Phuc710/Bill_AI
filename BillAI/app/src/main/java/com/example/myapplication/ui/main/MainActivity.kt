package com.example.myapplication.ui.main

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.fragment.app.Fragment
import com.example.myapplication.R
import com.example.myapplication.databinding.ActivityMainBinding
import com.example.myapplication.ui.history.HistoryFragment
import com.example.myapplication.ui.profile.ProfileFragment
import com.example.myapplication.ui.scan.ScanFragment

/**
 * MainActivity — Khung chứa Bottom Navigation.
 * Quản lý 3 tabs chính: Lịch sử, Quét, và Cá nhân.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var currentTabId: Int = -1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        // Thiết lập tab mặc định là Quét bill
        if (savedInstanceState == null) {
            binding.bottomNav.selectedItemId = R.id.navScan
            navigateToTab(R.id.navScan)
        }

        binding.bottomNav.setOnItemSelectedListener { item ->
            navigateToTab(item.itemId)
            true
        }
    }

    /**
     * Chuyển tab thông minh: 
     * Chỉ thay thế Fragment nếu tab được chọn khác với tab hiện tại.
     */
    private fun navigateToTab(itemId: Int) {
        if (currentTabId == itemId) return // Đang ở tab này rồi, không làm gì cả
        
        val fragment: Fragment = when (itemId) {
            R.id.navHistory -> HistoryFragment()
            R.id.navScan    -> ScanFragment()
            R.id.navProfile -> ProfileFragment()
            else -> return
        }

        currentTabId = itemId
        supportFragmentManager.beginTransaction()
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragmentContainer, fragment)
            .commit()
    }
}
