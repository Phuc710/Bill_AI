package com.example.myapplication.data.api

import com.example.myapplication.BuildConfig
import io.github.jan.supabase.SupabaseClient
import io.github.jan.supabase.createSupabaseClient
import io.github.jan.supabase.gotrue.Auth

object SupabaseManager {
    val client: SupabaseClient by lazy {
        createSupabaseClient(
            supabaseUrl = BuildConfig.SUPABASE_URL,
            supabaseKey = BuildConfig.SUPABASE_ANON_KEY
        ) {
            install(Auth) {
                // Configures how session should be saved. E.g., encrypting shared preferences on Android.
                // Depending on the exact gotrue-kt version, session saving is handled here.
            }
        }
    }

    val auth get() = client.auth
}
