package com.example.myapplication.data.repository

import com.example.myapplication.data.api.SupabaseManager
import io.github.jan.supabase.gotrue.SessionStatus
import io.github.jan.supabase.gotrue.providers.Google
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

class AuthRepository {

    val auth = SupabaseManager.auth

    // Expose the session status so UI can react (Splash -> Home or Splash -> Login)
    val sessionStatus: Flow<Boolean> = auth.sessionStatus.map {
        it is SessionStatus.Authenticated
    }

    suspend fun getUserId(): String? {
        return auth.currentUserOrNull()?.id
    }

    suspend fun getUserEmail(): String? {
        return auth.currentUserOrNull()?.email
    }

    suspend fun logout() {
        try {
            auth.signOut()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    // Google OAuth is typically initiated via deep link intent on Android using the GoTrue SDK.
    // The activity will handle the explicit callback.
}
