package com.example.myapplication.data.api

import com.example.myapplication.data.model.BillResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part

interface BillApiService {

    @Multipart
    @POST("bills/extract")
    suspend fun extractBill(
        @Part image: MultipartBody.Part,
        @Part("user_id") userId: RequestBody
    ): Response<BillResponse>
}
