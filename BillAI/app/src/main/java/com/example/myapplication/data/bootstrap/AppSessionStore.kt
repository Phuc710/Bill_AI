package com.example.myapplication.data.bootstrap

object AppSessionStore {

    private var snapshot: AppSessionSnapshot? = null

    fun currentSnapshot(): AppSessionSnapshot? = snapshot

    fun currentSnapshot(userId: String): AppSessionSnapshot? {
        return snapshot?.takeIf { it.user.id == userId }
    }

    fun update(snapshot: AppSessionSnapshot) {
        this.snapshot = snapshot
    }

    fun invalidate() {
        snapshot = snapshot?.copy(loadedAtMillis = 0L)
    }

    fun clear() {
        snapshot = null
    }
}
