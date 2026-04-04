package com.example.myapplication.data.repository

import com.example.myapplication.data.api.SupabaseManager
import io.github.jan.supabase.gotrue.SessionStatus
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

class AuthRepository {

    val auth = SupabaseManager.auth

    // Expose the session status so UI can react (Splash -> Home or Splash -> Login)
    val sessionStatus: Flow<Boolean> = auth.sessionStatus.map { status ->
        status is SessionStatus.Authenticated
    }

    fun getUserId(): String? {
        return auth.currentUserOrNull()?.id
    }

    fun getUserEmail(): String? {
        return auth.currentUserOrNull()?.email
    }

    fun getUserDisplayName(): String? {
        val user = auth.currentUserOrNull() ?: return null

        val metadataName = user.userMetadata.firstString("full_name", "name", "given_name", "preferred_username")
        if (!metadataName.isNullOrBlank()) return metadataName

        val identityName = user.identities
            ?.firstOrNull { it.provider.equals("google", ignoreCase = true) }
            ?.identityData
            .firstString("full_name", "name", "given_name", "preferred_username")
        if (!identityName.isNullOrBlank()) return identityName

        return user.email?.substringBefore("@")?.takeIf { it.isNotBlank() }
    }

    suspend fun logout() {
        try {
            auth.signOut()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun JsonObject?.firstString(vararg keys: String): String? {
        if (this == null) return null
        return keys.firstNotNullOfOrNull { key ->
            this[key]?.jsonPrimitive?.contentOrNull?.takeIf { it.isNotBlank() }
        }
    }
}
