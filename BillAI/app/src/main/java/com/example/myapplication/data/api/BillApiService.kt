package com.example.myapplication.data.api

import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.data.model.ListBillsResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface BillApiService {

    @Multipart
    @POST("bills/extract")
    suspend fun extractBill(
        @Part image: MultipartBody.Part,
        @Part("user_id") userId: RequestBody
    ): Response<BillResponse>

    @GET("bills")
    suspend fun listBills(
        @Query("user_id") userId: String,
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
        @Query("status") status: String? = null
    ): Response<ListBillsResponse>

    @GET("bills/{id}")
    suspend fun getBill(
        @Path("id") billId: String
    ): Response<BillResponse>

    @DELETE("bills/{id}")
    suspend fun deleteBill(
        @Path("id") billId: String
    ): Response<Unit>
}
