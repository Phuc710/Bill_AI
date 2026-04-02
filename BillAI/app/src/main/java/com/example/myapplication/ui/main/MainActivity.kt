package com.example.myapplication.ui.main

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import com.example.myapplication.R
import com.example.myapplication.databinding.ActivityMainBinding
import com.example.myapplication.ui.history.HistoryFragment
import com.example.myapplication.ui.profile.ProfileFragment
import com.example.myapplication.ui.scan.ScanFragment

/**
 * MainActivity — Khung chứa Bottom Navigation.
 * 3 tabs: Lịch sử | Quét bill | Tài khoản
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Show History tab by default
        if (savedInstanceState == null) {
            showFragment(HistoryFragment())
        }

        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.navHistory -> showFragment(HistoryFragment())
                R.id.navScan    -> showFragment(ScanFragment())
                R.id.navProfile -> showFragment(ProfileFragment())
            }
            true
        }
    }

    private fun showFragment(fragment: Fragment) {
        supportFragmentManager.beginTransaction()
            .replace(R.id.fragmentContainer, fragment)
            .commit()
    }
}
