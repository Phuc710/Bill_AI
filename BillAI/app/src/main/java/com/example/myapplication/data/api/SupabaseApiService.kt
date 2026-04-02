package com.example.myapplication.data.api

import com.example.myapplication.data.model.BillItem
import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.data.model.BillSummary
import retrofit2.Response
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Query
import retrofit2.http.Url

interface SupabaseApiService {

    // Fetch from v_bills_summary view
    @GET
    suspend fun listBills(
        @Url url: String,
        @Header("apikey") apiKey: String,
        @Header("Authorization") auth: String,
        @Query("user_id") userIdCondition: String, // format: eq.XYZ
        @Query("order") order: String = "created_at.desc"
    ): Response<List<BillSummary>>

    // Fetch from bills table
    @GET
    suspend fun getBillDetails(
        @Url url: String,
        @Header("apikey") apiKey: String,
        @Header("Authorization") auth: String,
        @Query("id") idCondition: String,
        @Query("select") select: String = "*,items:bill_items(*)"
    ): Response<List<Map<String, Any>>>

    // Delete from bills table
    @DELETE
    suspend fun deleteBill(
        @Url url: String,
        @Header("apikey") apiKey: String,
        @Header("Authorization") auth: String,
        @Query("id") idCondition: String
    ): Response<Unit>
}
